from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.audit_instrument_snapshot_coverage import audit_directory, build_report, main


def write_snapshot(root: Path, name: str, fetched_at: str, instruments: list[dict],
                   started_at: str | None = None) -> None:
    payload = {
        "schema_version": 1,
        "source": "Bybit V5 GET /v5/market/instruments-info",
        "category": "linear",
        "fetched_at": fetched_at,
        "count": len(instruments),
        "instruments": instruments,
    }
    if started_at is not None:
        payload["collection_started_at"] = started_at
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(payload), encoding="utf-8")


def instrument(symbol: str, status: str = "Trading") -> dict:
    return {"symbol": symbol, "status": status}


class InstrumentSnapshotCoverageAuditTests(unittest.TestCase):
    def test_empty_repository_reports_no_data_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_report(Path(tmp))
        self.assertEqual(report["status"], "NO_DATA")
        self.assertEqual(report["sections"]["linear_universe"]["snapshot_count"], 0)

    def test_reports_collection_duration_cadence_and_symbol_status_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root, "a.json", "2026-11-01T00:00:02.000Z",
                           [instrument("BTCUSDT"), instrument("ETHUSDT")],
                           "2026-11-01T00:00:00.000Z")
            write_snapshot(root, "b.json", "2026-11-01T01:00:04.000Z",
                           [instrument("BTCUSDT", "Closed"), instrument("SOLUSDT")],
                           "2026-11-01T01:00:00.000Z")
            report = audit_directory(root)
        self.assertEqual(report["snapshot_count"], 2)
        self.assertEqual(report["collection_duration_ms"]["max"], 2000)
        self.assertEqual(report["inter_snapshot_gap_ms"]["max"], 3_598_000)
        self.assertEqual(report["intervals"][0]["symbols_added"], 1)
        self.assertEqual(report["intervals"][0]["symbols_removed"], 1)
        self.assertEqual(report["intervals"][0]["status_changes"], 1)
        self.assertEqual(report["intervals"][0]["gap_basis"], "completion_to_start")

    def test_legacy_snapshot_without_start_time_uses_completion_to_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root, "a.json", "2026-11-01T00:00:00.000Z",
                           [instrument("BTCUSDT")])
            write_snapshot(root, "b.json", "2026-11-01T00:10:00.000Z",
                           [instrument("BTCUSDT")])
            report = audit_directory(root)
        self.assertEqual(report["snapshots_missing_collection_started_at"], 2)
        self.assertEqual(report["intervals"][0]["gap_basis"], "completion_to_completion")
        self.assertEqual(report["intervals"][0]["gap_from_previous_completion_ms"], 600_000)

    def test_overlapping_collection_windows_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root, "a.json", "2026-11-01T00:00:02.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:00.000Z")
            write_snapshot(root, "b.json", "2026-11-01T00:00:03.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:01.000Z")
            report = audit_directory(root)
        self.assertEqual(report["overlapping_collection_windows"], 1)
        self.assertEqual(report["intervals"][0]["gap_from_previous_completion_ms"], -1000)

    def test_overlapping_collection_windows_fail_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "data" / "universe_history" / "linear"
            write_snapshot(target, "a.json", "2026-11-01T00:00:02.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:00.000Z")
            write_snapshot(target, "b.json", "2026-11-01T00:00:03.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:01.000Z")
            with patch("sys.argv", ["audit", "--root", str(root)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = main()
        self.assertEqual(result, 1)

    def test_duplicate_snapshot_timestamps_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root, "a.json", "2026-11-01T00:00:00.000Z", [instrument("BTCUSDT")])
            write_snapshot(root, "b.json", "2026-11-01T00:00:00.000Z", [instrument("ETHUSDT")])
            with self.assertRaisesRegex(ValueError, "duplicate fetched_at"):
                audit_directory(root)

    def test_optional_gap_threshold_is_user_supplied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root / "data" / "universe_history" / "linear", "a.json",
                           "2026-11-01T00:00:00.000Z", [instrument("BTCUSDT")])
            write_snapshot(root / "data" / "universe_history" / "linear", "b.json",
                           "2026-11-01T01:00:00.000Z", [instrument("BTCUSDT")])
            output = io.StringIO()
            with patch("sys.argv", ["audit", "--root", str(root), "--max-gap-hours", "0.5"]):
                with contextlib.redirect_stdout(output):
                    result = main()
        self.assertEqual(result, 1)
        self.assertIn('"status": "DATA_FOUND"', output.getvalue())


    def test_optional_collection_duration_threshold_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "data" / "instrument_specs" / "linear"
            write_snapshot(target, "a.json", "2026-11-01T00:00:10.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:00.000Z")
            output = io.StringIO()
            with patch("sys.argv", ["audit", "--root", str(root),
                                    "--max-collection-minutes", "0.1"]):
                with contextlib.redirect_stdout(output):
                    result = main()
        self.assertEqual(result, 1)

    def test_require_data_is_explicit_and_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch("sys.argv", ["audit", "--root", tmp, "--require-data"]):
                with contextlib.redirect_stdout(output):
                    result = main()
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
