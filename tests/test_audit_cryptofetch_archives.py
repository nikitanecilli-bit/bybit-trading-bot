"""Tests for CryptoFetch archive overlap/provenance auditing."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import csv
import tempfile
import unittest
import zipfile

from scripts.audit_cryptofetch_archives import inspect_archives, compare_groups, write_outputs


def csv_bytes(rows):
    import io
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=[
        "open_time_ms", "open", "high", "low", "close", "volume"
    ])
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def candle(ts, close="10"):
    return {"open_time_ms": ts, "open": "9", "high": "11", "low": "8",
            "close": close, "volume": "100"}


class CryptoFetchArchiveAuditTests(unittest.TestCase):
    def test_identical_overlap_and_longest_superset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / "a.zip", "w") as z:
                z.writestr("BTCUSDT_1h_a.csv", csv_bytes([candle(3600000), candle(7200000)]))
            with zipfile.ZipFile(root / "b.zip", "w") as z:
                z.writestr("BTCUSDT_1h_b.csv", csv_bytes([
                    candle(3600000), candle(7200000), candle(10800000)
                ]))
            inventory, groups = inspect_archives(root)
            pairs, summary = compare_groups(groups)
            self.assertEqual(summary["conflicting_overlap_bars"], 0)
            self.assertEqual(pairs[0]["overlap_bars"], 2)
            self.assertEqual(pairs[0]["exact_overlap_bars"], 2)
            self.assertTrue(pairs[0]["legacy_longest_is_superset_of_pair"])
            self.assertEqual(len(inventory), 2)

    def test_longest_file_can_fail_to_cover_other_archive_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / "a.zip", "w") as z:
                z.writestr("ETHUSDT_1h_a.csv", csv_bytes([
                    candle(3600000), candle(7200000), candle(10800000), candle(14400000)
                ]))
            with zipfile.ZipFile(root / "b.zip", "w") as z:
                z.writestr("ETHUSDT_1h_b.csv", csv_bytes([
                    candle(3600000), candle(7200000), candle(18000000)
                ]))
            _, groups = inspect_archives(root)
            pairs, summary = compare_groups(groups)
            self.assertEqual(summary["longest_archive_not_superset_pair_count"], 1)
            self.assertFalse(pairs[0]["legacy_longest_is_superset_of_pair"])
            self.assertEqual(pairs[0]["right_only_bars"], 1)

    def test_conflicting_overlapping_candle_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / "a.zip", "w") as z:
                z.writestr("SOLUSDT_1h_a.csv", csv_bytes([candle(3600000), candle(7200000)]))
            with zipfile.ZipFile(root / "b.zip", "w") as z:
                z.writestr("SOLUSDT_1h_b.csv", csv_bytes([
                    candle(3600000), candle(7200000, close="10.5")
                ]))
            _, groups = inspect_archives(root)
            pairs, summary = compare_groups(groups)
            self.assertEqual(summary["conflicting_overlap_bars"], 1)
            self.assertEqual(pairs[0]["first_conflict_ts"], 7200000)

    def test_single_candle_member_is_valid_but_not_backtest_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / "one.zip", "w") as z:
                z.writestr("ADAUSDT_1h_one.csv", csv_bytes([candle(3600000)]))
            inventory, groups = inspect_archives(root)
            self.assertEqual(len(inventory), 1)
            self.assertTrue(inventory[0]["valid"])
            self.assertEqual(inventory[0]["bars"], 1)
            self.assertFalse(inventory[0]["backtest_eligible"])
            self.assertEqual(len(groups[("ADAUSDT", "1h")]), 1)

    def test_empty_member_is_recorded_without_being_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / "empty.zip", "w") as z:
                z.writestr("XMRUSDT_1h_empty.csv", csv_bytes([]))
            inventory, groups = inspect_archives(root)
            self.assertTrue(inventory[0]["valid"])
            self.assertEqual(inventory[0]["bars"], 0)
            self.assertFalse(inventory[0]["has_data"])
            self.assertEqual(len(groups[("XMRUSDT", "1h")]), 1)

    def test_output_files_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            write_outputs(out, [], [], {
                "candidate_files": 0, "valid_files": 0, "backtest_eligible_files": 0,
                "too_short_for_backtest_files": 0, "empty_files": 0, "rejected_files": 0,
                "duplicate_symbol_timeframe_groups": 0, "pairwise_comparisons": 0,
                "conflicting_overlap_bars": 0,
                "longest_archive_not_superset_pair_count": 0,
            })
            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "README.md").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
