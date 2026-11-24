"""Offline tests for the bounded OKX public market-data archive loader."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.okx_public_data_archive import (
    HOUR_MS, fetch_paged, hourly_grid_report, parse_candle, parse_funding,
    parse_time, _save_raw,
)


def candle(ts, confirm="1"):
    return [str(ts), "100", "102", "99", "101", "1", "1", "101", confirm]


class OkxArchiveTests(unittest.TestCase):
    def test_parse_time_requires_timezone_and_hour_alignment(self):
        self.assertEqual(parse_time("2026-01-01T00:00:00Z"), 1767225600000)
        with self.assertRaisesRegex(ValueError, "timezone"):
            parse_time("2026-01-01T00:00:00")
        with self.assertRaisesRegex(ValueError, "exact UTC hour"):
            parse_time("2026-01-01T00:01:00Z")

    def test_parse_candle_preserves_decimal_strings_and_confirm(self):
        row = parse_candle(candle(HOUR_MS), "candles")
        self.assertEqual(row["open"], "100")
        self.assertEqual(row["timestamp_ms"], HOUR_MS)
        self.assertEqual(row["confirm"], "1")

    def test_parse_candle_rejects_bad_ohlc(self):
        with self.assertRaisesRegex(ValueError, "OHLC ordering"):
            parse_candle([str(HOUR_MS), "100", "98", "99", "101"], "mark_price")

    def test_parse_funding_keeps_formula_metadata(self):
        row = parse_funding({
            "fundingTime": str(HOUR_MS), "fundingRate": "0.0001",
            "realizedRate": "0.0001", "formulaType": "withRate", "method": "current_period",
        })
        self.assertEqual(row["funding_rate"], "0.0001")
        self.assertEqual(row["formula_type"], "withRate")
        self.assertEqual(row["method"], "current_period")

    def test_backward_pagination_saves_exact_pages_and_returns_sorted_rows(self):
        start, end = HOUR_MS, 102 * HOUR_MS
        all_rows = [candle(ts * HOUR_MS) for ts in range(101, 0, -1)]
        calls = []

        def fake_fetch(url):
            query = parse_qs(urlparse(url).query)
            after = int(query["after"][0]) if "after" in query else None
            calls.append(after)
            page = [row for row in all_rows if after is None or int(row[0]) < after][:100]
            body = json.dumps({"code": "0", "msg": "", "data": page}).encode()
            return body, json.loads(body)

        with tempfile.TemporaryDirectory() as tmp:
            rows, pages = fetch_paged(
                "candles", "/api/v5/market/history-candles",
                {"instId": "BTC-USDT-SWAP", "bar": "1H", "limit": 100},
                start, end, Path(tmp), fake_fetch, 0, 10,
            )
            self.assertEqual(len(rows), 101)
            self.assertEqual(len(pages), 2)
            self.assertEqual(calls, [None, HOUR_MS * 2])
            self.assertEqual(rows[0]["timestamp_ms"], start)
            self.assertEqual(rows[-1]["timestamp_ms"], 101 * HOUR_MS)
            raw1 = Path(tmp) / pages[0]["raw_file"]
            self.assertEqual(hashlib.sha256(raw1.read_bytes()).hexdigest(), pages[0]["raw_sha256"])

    def test_pagination_rejects_duplicate_or_non_decreasing_page(self):
        ts = 5 * HOUR_MS
        body = json.dumps({"code": "0", "data": [candle(ts), candle(ts)]}).encode()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "strictly newest-first"):
                fetch_paged(
                    "candles", "/history", {"limit": 100}, HOUR_MS, 6 * HOUR_MS,
                    Path(tmp), lambda _: (body, json.loads(body)), 0, 2,
                )

    def test_hourly_report_detects_missing_and_unconfirmed_candles(self):
        rows = [
            {"timestamp_ms": HOUR_MS, "confirm": "1"},
            {"timestamp_ms": 3 * HOUR_MS, "confirm": "0"},
        ]
        report = hourly_grid_report(rows, HOUR_MS, 4 * HOUR_MS)
        self.assertFalse(report["complete"])
        self.assertEqual(report["missing_count"], 1)
        self.assertEqual(report["unconfirmed_count"], 1)


if __name__ == "__main__":
    unittest.main()
