"""Offline tests for funding/mark-price coverage preflight."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import tempfile
import unittest
from pathlib import Path

from scripts.validate_funding_coverage import validate_coverage


class FundingCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.funding = self.root / "funding"
        self.marks = self.root / "marks"
        self.trades = self.root / "trades"
        self.funding.mkdir()
        self.marks.mkdir()
        self.trades.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write_funding(self, rows):
        (self.funding / "BTCUSDT.csv").write_text(
            "symbol,funding_timestamp_ms,funding_rate\n" +
            "".join(f"BTCUSDT,{ts},{rate}\n" for ts, rate in rows),
            encoding="utf-8",
        )

    def write_marks(self, rows):
        (self.marks / "BTCUSDT.csv").write_text(
            "symbol,timestamp_ms,open\n" +
            "".join(f"BTCUSDT,{ts},{price}\n" for ts, price in rows),
            encoding="utf-8",
        )

    def write_trades(self, rows):
        (self.trades / "BTCUSDT.csv").write_text(
            "symbol,timestamp_ms,open,high,low,close,volume,turnover\n" +
            "".join(f"BTCUSDT,{ts},100,102,99,101,10,1010\n" for ts in rows),
            encoding="utf-8",
        )

    def test_trade_ohlcv_and_mark_timestamp_grids_must_match(self):
        self.write_funding([(1000, "0.001")])
        self.write_marks([(1000, 100), (2000, 101)])
        self.write_trades([1000, 2000])
        report = validate_coverage(self.funding, self.marks, trade_kline_dir=self.trades)
        self.assertTrue(report["ok"])
        self.assertEqual(report["results"][0]["trade_candles"], 2)

    def test_trade_ohlcv_allows_one_exact_terminal_mark_boundary(self):
        self.write_funding([(3000, "0.001")])
        self.write_marks([(1000, 100), (2000, 101), (3000, 102)])
        self.write_trades([1000, 2000])
        report = validate_coverage(self.funding, self.marks, trade_kline_dir=self.trades)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["results"][0]["terminal_boundary_mark_candles"], 1)
        self.assertEqual(report["results"][0]["trade_mark_timestamp_mismatch"], 0)

    def test_trade_ohlcv_rejects_nonterminal_extra_mark_timestamp(self):
        self.write_funding([(1000, "0.001")])
        self.write_marks([(1000, 100), (2000, 101), (4000, 102)])
        self.write_trades([1000, 2000])
        report = validate_coverage(self.funding, self.marks, trade_kline_dir=self.trades)
        self.assertFalse(report["ok"])
        self.assertEqual(report["results"][0]["trade_mark_timestamp_mismatch"], 1)

    def test_trade_ohlcv_missing_timestamp_fails_preflight(self):
        self.write_funding([(1000, "0.001")])
        self.write_marks([(1000, 100), (2000, 101)])
        self.write_trades([1000])
        report = validate_coverage(self.funding, self.marks, trade_kline_dir=self.trades)
        self.assertFalse(report["ok"])
        self.assertEqual(report["results"][0]["trade_mark_timestamp_mismatch"], 1)

    def test_full_timestamp_coverage_passes(self):
        self.write_funding([(1000, "0.001"), (2000, "-0.002")])
        self.write_marks([(1000, 100), (2000, 101), (3000, 102)])
        report = validate_coverage(self.funding, self.marks)
        self.assertTrue(report["ok"])
        self.assertEqual(report["results"][0]["matched_events"], 2)

    def test_missing_settlement_mark_fails_with_sample(self):
        self.write_funding([(1000, "0.001"), (2000, "0.002")])
        self.write_marks([(1000, 100)])
        report = validate_coverage(self.funding, self.marks)
        self.assertFalse(report["ok"])
        self.assertEqual(report["results"][0]["missing_timestamps_sample"], [2000])

    def test_missing_mark_file_and_missing_funding_file_fail(self):
        self.write_funding([(1000, "0.001")])
        report = validate_coverage(self.funding, self.marks, ["BTCUSDT", "ETHUSDT"])
        self.assertFalse(report["ok"])
        self.assertEqual(report["results"][0]["status"], "missing_mark_file")
        self.assertEqual(report["results"][1]["status"], "missing_funding_file")

    def test_duplicate_funding_timestamp_rejected(self):
        self.write_funding([(1000, "0.001"), (1000, "0.002")])
        self.write_marks([(1000, 100)])
        with self.assertRaisesRegex(ValueError, "duplicate funding timestamp"):
            validate_coverage(self.funding, self.marks)

    def test_duplicate_mark_timestamp_rejected(self):
        self.write_funding([(1000, "0.001")])
        self.write_marks([(1000, 100), (1000, 101)])
        with self.assertRaisesRegex(ValueError, "duplicate mark timestamp"):
            validate_coverage(self.funding, self.marks)

    def test_row_symbol_must_match_filename(self):
        (self.funding / "BTCUSDT.csv").write_text(
            "symbol,funding_timestamp_ms,funding_rate\nETHUSDT,1000,0.001\n",
            encoding="utf-8",
        )
        self.write_marks([(1000, 100)])
        with self.assertRaisesRegex(ValueError, "symbol does not match filename"):
            validate_coverage(self.funding, self.marks)

    def test_empty_funding_events_fail(self):
        self.write_funding([])
        self.write_marks([(1000, 100)])
        report = validate_coverage(self.funding, self.marks)
        self.assertFalse(report["ok"])
        self.assertEqual(report["results"][0]["status"], "incomplete")


if __name__ == "__main__":
    unittest.main(verbosity=2)
