"""Offline tests for official Bybit funding and mark-price history collection."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.archive_bybit_market_history import (
    FUNDING_WINDOW_MS, fetch_funding_history, fetch_mark_klines, fetch_trade_klines,
    normalize_symbol, parse_funding_rows, parse_mark_rows, parse_trade_rows, validate_base_url,
)


class BybitMarketHistoryTests(unittest.TestCase):
    def test_funding_fetches_bounded_windows_and_sorts_events(self):
        start, end = 10_000, 10_000 + FUNDING_WINDOW_MS + 10_000
        calls = []
        def fetch(a, b):
            calls.append((a, b))
            ts = a + 1
            return [{"symbol": "BTCUSDT", "fundingRateTimestamp": str(ts),
                     "fundingRate": "0.0001"}]
        rows = fetch_funding_history("btcusdt", start, end, fetch)
        self.assertEqual(len(calls), 2)
        self.assertEqual(rows[0]["funding_timestamp_ms"], start + 1)
        self.assertEqual(rows[1]["funding_timestamp_ms"], start + FUNDING_WINDOW_MS + 1)
        self.assertEqual(calls[-1][1], end - 1)

    def test_funding_rejects_saturated_page(self):
        def fetch(a, b):
            return [{"symbol": "BTCUSDT", "fundingRateTimestamp": str(a+i+1),
                     "fundingRate": "0.001"} for i in range(200)]
        with self.assertRaisesRegex(RuntimeError, "page limit"):
            fetch_funding_history("BTCUSDT", 10_000, 20_000, fetch)

    def test_funding_rejects_empty_history_and_symbol_mismatch(self):
        with self.assertRaisesRegex(RuntimeError, "no funding events"):
            fetch_funding_history("BTCUSDT", 10_000, 20_000, lambda a, b: [])
        with self.assertRaisesRegex(ValueError, "symbol mismatch"):
            parse_funding_rows([{"symbol":"ETHUSDT","fundingRateTimestamp":"1000",
                                 "fundingRate":"0.001"}], "BTCUSDT")

    def test_funding_rejects_non_finite_rate(self):
        with self.assertRaisesRegex(ValueError, "invalid funding rate"):
            parse_funding_rows([{"symbol":"BTCUSDT","fundingRateTimestamp":"1000",
                                 "fundingRate":"NaN"}], "BTCUSDT")

    def test_trade_kline_fetch_sorts_and_requires_complete_hour_grid(self):
        hour = 3_600_000
        start, end = hour, hour * 4
        source = [
            [str(hour*3), "103", "105", "102", "104", "12", "1248"],
            [str(hour*2), "102", "104", "101", "103", "11", "1133"],
            [str(hour), "101", "103", "100", "102", "10", "1020"],
        ]
        rows = fetch_trade_klines("BTCUSDT", start, end, "60",
                                  lambda a, b, limit: source)
        self.assertEqual([x["timestamp_ms"] for x in rows], [hour, hour*2, hour*3])
        self.assertEqual(rows[0]["volume"], "10")
        self.assertEqual(rows[0]["turnover"], "1020")

    def test_trade_kline_gap_and_invalid_ohlcv_fail_closed(self):
        hour = 3_600_000
        with self.assertRaisesRegex(RuntimeError, "incomplete trade kline coverage"):
            fetch_trade_klines("BTCUSDT", hour, hour*4, "60",
                               lambda a,b,l: [[str(hour), "100","101","99","100","1","100"]])
        with self.assertRaisesRegex(ValueError, "volume and turnover"):
            parse_trade_rows([[str(hour),"100","101","99","100","-1","100"]], "BTCUSDT", hour)

    def test_mark_fetch_sorts_and_requires_complete_hour_grid(self):
        hour = 3_600_000
        start, end = hour, hour * 4
        source = [
            [str(hour*3), "103", "105", "102", "104"],
            [str(hour*2), "102", "104", "101", "103"],
            [str(hour), "101", "103", "100", "102"],
        ]
        rows = fetch_mark_klines("BTCUSDT", start, end, "60",
                                 lambda a, b, limit: source)
        self.assertEqual([x["timestamp_ms"] for x in rows], [hour, hour*2, hour*3])
        self.assertEqual(rows[0]["open"], "101")

    def test_mark_gap_fails_closed(self):
        hour = 3_600_000
        with self.assertRaisesRegex(RuntimeError, "incomplete mark kline coverage"):
            fetch_mark_klines("BTCUSDT", hour, hour*4, "60",
                              lambda a, b, limit: [[str(hour), "100", "101", "99", "100"],
                                                   [str(hour*3), "100", "101", "99", "100"]])

    def test_mark_range_rejects_current_or_future_unclosed_candle(self):
        hour = 3_600_000
        now_ms = int(__import__("time").time() * 1000)
        next_boundary = (now_ms // hour + 1) * hour
        with self.assertRaisesRegex(ValueError, "unclosed candle"):
            fetch_mark_klines("BTCUSDT", next_boundary-hour, next_boundary, "60",
                              lambda a,b,l: [])

    def test_mark_range_must_be_interval_aligned(self):
        hour = 3_600_000
        with self.assertRaisesRegex(ValueError, "align"):
            fetch_mark_klines("BTCUSDT", hour+1, hour*2, "60", lambda a,b,l: [])

    def test_mark_rejects_bad_ohlc(self):
        with self.assertRaisesRegex(ValueError, "OHLC ordering"):
            parse_mark_rows([["3600000","100","99","98","100"]], "BTCUSDT", 3_600_000)

    def test_mark_chunks_avoid_full_page_truncation(self):
        hour = 3_600_000
        start, end = hour, hour * 901
        calls = []
        def fetch(a, b, limit):
            calls.append((a, b, limit))
            return [[str(ts), "100", "101", "99", "100"]
                    for ts in range(a, b+1, hour)]
        rows = fetch_mark_klines("BTCUSDT", start, end, "60", fetch)
        self.assertEqual(len(rows), 900)
        self.assertEqual(len(calls), 2)
        self.assertLess(calls[0][2], 1000)

    def test_symbol_path_traversal_and_invalid_characters_rejected(self):
        self.assertEqual(normalize_symbol("btcusdt"), "BTCUSDT")
        for symbol in ("../BTCUSDT", "BTC/USDT", "A", "BTC USDT"):
            with self.assertRaises(ValueError):
                normalize_symbol(symbol)

    def test_only_official_https_hosts_are_allowed(self):
        validate_base_url("https://api.bybit.com")
        for url in ("http://api.bybit.com", "https://example.com",
                    "https://api.bybit.com:444", "https://" + "user" + ":" + "pass" + "@api.bybit.com"):
            with self.assertRaises(ValueError):
                validate_base_url(url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
