"""Offline tests for funding/mark-price coverage preflight."""
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
        self.funding.mkdir()
        self.marks.mkdir()

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
