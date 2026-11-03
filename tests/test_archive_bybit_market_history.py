"""Offline tests for official Bybit funding and mark-price history collection."""
from pathlib import Path
import hashlib
import json
import os
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.archive_bybit_market_history import (
    FUNDING_WINDOW_MS, fetch_funding_history, fetch_mark_klines, fetch_trade_klines,
    normalize_symbol, parse_funding_rows, parse_mark_rows, parse_trade_rows, validate_base_url,
    clip_range_to_lifecycle, load_universe_lifecycle, validate_archive_range,
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

    def test_funding_saturated_page_is_split_until_complete(self):
        calls = []
        def fetch(a, b):
            calls.append((a, b))
            timestamps = [10_001 + i for i in range(200) if a <= 10_001+i <= b]
            if b-a+1 > 5_000:
                timestamps = list(range(a+1, a+201))
            return [{"symbol": "BTCUSDT", "fundingRateTimestamp": str(ts),
                     "fundingRate": "0.001"} for ts in timestamps[:200]]
        rows = fetch_funding_history("BTCUSDT", 10_000, 20_000, fetch, pause=0)
        self.assertEqual(len(rows), 200)
        self.assertGreater(len(calls), 1)
        self.assertEqual([x["funding_timestamp_ms"] for x in rows],
                         sorted(x["funding_timestamp_ms"] for x in rows))

    def test_funding_still_fails_if_minimum_window_is_saturated(self):
        def fetch(a, b):
            return [{"symbol": "BTCUSDT", "fundingRateTimestamp": str(a),
                     "fundingRate": "0.001"} for _ in range(200)]
        with self.assertRaisesRegex(RuntimeError, "minimum window"):
            fetch_funding_history("BTCUSDT", 10_000, 10_001, fetch, pause=0)

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


    def test_requested_archive_range_is_validated_before_network(self):
        hour = 3_600_000
        validate_archive_range(hour, hour * 3, hour)
        with self.assertRaisesRegex(ValueError, "boundaries must align"):
            validate_archive_range(hour + 1, hour * 3, hour)
        with self.assertRaisesRegex(ValueError, "boundaries must align"):
            validate_archive_range(hour, hour * 3 + 1, hour)
        with self.assertRaisesRegex(ValueError, "valid archive range"):
            validate_archive_range(hour * 3, hour, hour)

    def test_lifecycle_clips_to_complete_candle_boundaries(self):
        hour = 3_600_000
        lifecycle = {"NEWUSDT": {"launch_ms": hour + 1_000, "delivery_ms": hour * 5 + 2_000}}
        self.assertEqual(
            clip_range_to_lifecycle("NEWUSDT", hour, hour * 8, hour, lifecycle),
            (hour * 2, hour * 5),
        )

    def test_lifecycle_preserves_requested_bounds_when_inside_lifecycle(self):
        hour = 3_600_000
        lifecycle = {"BTCUSDT": {"launch_ms": hour, "delivery_ms": 0}}
        self.assertEqual(
            clip_range_to_lifecycle("BTCUSDT", hour * 3, hour * 8, hour, lifecycle),
            (hour * 3, hour * 8),
        )

    def test_lifecycle_rejects_missing_symbol_and_empty_overlap(self):
        hour = 3_600_000
        lifecycle = {"OLDUSDT": {"launch_ms": hour, "delivery_ms": hour * 4}}
        with self.assertRaisesRegex(ValueError, "absent"):
            clip_range_to_lifecycle("NEWUSDT", hour, hour * 8, hour, lifecycle)
        with self.assertRaisesRegex(ValueError, "no complete"):
            clip_range_to_lifecycle("OLDUSDT", hour * 5, hour * 8, hour, lifecycle)

    def test_universe_snapshot_loader_hashes_and_validates_lifecycle(self):
        snapshot = {
            "category": "linear",
            "fetched_at": "2026-11-03T00:00:00Z",
            "instruments": [{
                "symbol": "BTCUSDT", "contractType": "LinearPerpetual",
                "quoteCoin": "USDT", "settleCoin": "USDT",
                "launchTime": "3600000", "deliveryTime": "0", "status": "Trading",
            }],
        }
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                path = Path("universe.json")
                path.write_text(json.dumps(snapshot), encoding="utf-8")
                lifecycle, digest, fetched_at = load_universe_lifecycle(path)
                self.assertEqual(lifecycle["BTCUSDT"]["launch_ms"], 3_600_000)
                self.assertEqual(lifecycle["BTCUSDT"]["delivery_ms"], 0)
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(fetched_at, snapshot["fetched_at"])
            finally:
                os.chdir(original_cwd)

    def test_universe_snapshot_rejects_closed_contract_without_delivery_time(self):
        snapshot = {
            "category": "linear",
            "fetched_at": "2026-11-03T00:00:00Z",
            "instruments": [{
                "symbol": "OLDUSDT", "contractType": "LinearPerpetual",
                "quoteCoin": "USDT", "settleCoin": "USDT",
                "launchTime": "3600000", "deliveryTime": "0", "status": "Closed",
            }],
        }
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                Path("universe.json").write_text(json.dumps(snapshot), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "lifecycle end is unknown"):
                    load_universe_lifecycle("universe.json")
            finally:
                os.chdir(original_cwd)

    def test_universe_snapshot_excludes_prelaunch_and_pending_open(self):
        snapshot = {
            "category": "linear",
            "fetched_at": "2026-11-03T00:00:00Z",
            "instruments": [
                {
                    "symbol": "BTCUSDT", "contractType": "LinearPerpetual",
                    "quoteCoin": "USDT", "settleCoin": "USDT",
                    "launchTime": "3600000", "deliveryTime": "0", "status": "Trading",
                },
                {
                    "symbol": "FUTUREUSDT", "contractType": "LinearPerpetual",
                    "quoteCoin": "USDT", "settleCoin": "USDT",
                    "launchTime": "9999999999999", "deliveryTime": "0", "status": "PendingOpen",
                },
            ],
        }
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                Path("universe.json").write_text(json.dumps(snapshot), encoding="utf-8")
                lifecycle, _, _ = load_universe_lifecycle("universe.json")
                self.assertIn("BTCUSDT", lifecycle)
                self.assertNotIn("FUTUREUSDT", lifecycle)
            finally:
                os.chdir(original_cwd)

    def test_symbol_path_traversal_and_invalid_characters_rejected(self):
        self.assertEqual(normalize_symbol("btcusdt"), "BTCUSDT")
        for symbol in ("../BTCUSDT", "BTC/USDT", "A", "BTC USDT"):
            with self.assertRaises(ValueError):
                normalize_symbol(symbol)

    def test_only_official_https_hosts_are_allowed(self):
        for host in ("api.bybit.com", "api.bytick.com", "api.bybit.kz",
                     "api.bybit.tr", "api.bybitgeorgia.ge", "api.bybit.ae",
                     "api.bybit.eu", "api.bybit.id"):
            validate_base_url(f"https://{host}")
        for url in ("http://api.bybit.com", "https://example.com",
                    "https://api.bybit.com:444", "https://" + "user" + ":" + "pass" + "@api.bybit.com",
                    "https://api.bybit.nl", "https://api.bybit-tr.com"):
            with self.assertRaises(ValueError):
                validate_base_url(url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
