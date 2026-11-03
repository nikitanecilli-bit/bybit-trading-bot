"""Tests for funding archive query-provenance manifests."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from funding_archive_manifest import (
    record_funding_collection, validate_funding_manifest, sha256_file,
)


class FundingArchiveManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.csv = self.root / "BTCUSDT_funding.csv"
        self.manifest = self.root / "BTCUSDT_funding.audit.json"
        self.csv.write_text(
            "timestamp,datetime,funding_rate\n"
            "3600000,1970-01-01,0.001\n"
            "7200000,1970-01-01,0.002\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def attach_schedule(self, payload, expected_events):
        source_snapshots = []
        for ts in (3_600_000, 7_200_000):
            snapshot_path = self.root / f"instrument_snapshot_{ts}.json"
            fetched_at = datetime.fromtimestamp(
                ts / 1000, tz=timezone.utc
            ).isoformat().replace("+00:00", "Z")
            snapshot_path.write_text(json.dumps({
                "schema_version": 1,
                "source": "Bybit V5 GET /v5/market/instruments-info",
                "category": "linear",
                "fetched_at": fetched_at,
                "count": 1,
                "instruments": [{"symbol": "BTCUSDT", "fundingInterval": "60"}],
            }), encoding="utf-8")
            source_snapshots.append({
                "path": snapshot_path.name,
                "sha256": sha256_file(snapshot_path),
                "fetched_at_ms": ts,
                "funding_interval_minutes": 60,
            })
        schedule_path = self.root / "BTCUSDT.schedule.json"
        schedule = {
            "schema_version": 1,
            "source": "bybit_dated_instrument_snapshots",
            "symbol": "BTCUSDT",
            "category": "linear",
            "coverage_start_ms": 3_600_000,
            "coverage_end_ms": 7_200_000,
            "source_snapshots": source_snapshots,
            "expected_settlement_timestamps_ms": expected_events,
        }
        schedule_path.write_text(json.dumps(schedule), encoding="utf-8")
        payload["settlement_schedule_evidence"] = {
            "path": schedule_path.name,
            "sha256": sha256_file(schedule_path),
        }
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def record(self):
        return record_funding_collection(
            self.csv, self.manifest, symbol="BTCUSDT", category="linear",
            api_base="https://api.bybit.com",
            requested_start_ms=3_600_000, requested_end_ms=7_200_000,
            pages=[
                {
                    "request_start_ms": 3_600_000,
                    "request_end_ms": 7_200_000,
                    "response_rows": 1,
                    "complete": True,
                    "saturated": False,
                    "first_ts": 7_200_000,
                    "last_ts": 7_200_000,
                },
                {
                    "request_start_ms": 3_600_000,
                    "request_end_ms": 7_199_999,
                    "response_rows": 1,
                    "complete": True,
                    "saturated": False,
                    "first_ts": 3_600_000,
                    "last_ts": 3_600_000,
                },
            ],
            collected_at_ms=7_200_001,
        )

    def test_manifest_records_hash_rows_and_query_pages(self):
        payload = self.record()
        self.assertEqual(payload["csv_data_rows"], 2)
        self.assertEqual(len(payload["runs"][0]["pages"]), 2)
        self.assertIsNone(payload["settlement_schedule_evidence"])

    def test_validator_rejects_missing_dated_schedule_even_with_full_query_coverage(self):
        self.record()
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertTrue(report["query_coverage_ok"])
        self.assertFalse(report["ok"])
        self.assertIn("dated_settlement_schedule_evidence_missing", report["errors"])

    def test_validator_accepts_matching_dated_schedule_and_funding_rows(self):
        payload = self.record()
        self.attach_schedule(payload, [3_600_000, 7_200_000])
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue(report["settlement_schedule_verified"])

    def test_validator_rejects_matching_csv_and_schedule_that_both_omit_a_settlement(self):
        payload = self.record()
        self.csv.write_text(
            "timestamp,datetime,funding_rate\\n"
            "3600000,1970-01-01,0.001\\n",
            encoding="utf-8",
        )
        payload["csv_sha256"] = sha256_file(self.csv)
        payload["csv_data_rows"] = 1
        self.attach_schedule(payload, [3_600_000])
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertFalse(report["ok"])
        self.assertIn(
            "expected_settlement_schedule_not_reconstructed_from_interval",
            report["errors"],
        )
        self.assertFalse(report["settlement_schedule_verified"])

    def test_validator_fails_closed_when_dated_interval_changes_without_effective_boundary(self):
        payload = self.record()
        self.attach_schedule(payload, [3_600_000, 7_200_000])
        schedule_path = self.root / "BTCUSDT.schedule.json"
        schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
        first_snapshot = self.root / schedule["source_snapshots"][0]["path"]
        raw_snapshot = json.loads(first_snapshot.read_text(encoding="utf-8"))
        raw_snapshot["instruments"][0]["fundingInterval"] = "120"
        first_snapshot.write_text(json.dumps(raw_snapshot), encoding="utf-8")
        schedule["source_snapshots"][0]["sha256"] = sha256_file(first_snapshot)
        schedule["source_snapshots"][0]["funding_interval_minutes"] = 120
        schedule_path.write_text(json.dumps(schedule), encoding="utf-8")
        payload["settlement_schedule_evidence"]["sha256"] = sha256_file(schedule_path)
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertIn(
            "funding_interval_changed_without_effective_boundary_evidence",
            report["errors"],
        )
        self.assertFalse(report["settlement_schedule_verified"])

    def test_validator_detects_csv_mutation_after_collection(self):
        payload = self.record()
        self.attach_schedule(payload, [3_600_000, 7_200_000])
        self.csv.write_text(
            "timestamp,datetime,funding_rate\n3600000,1970-01-01,0.001\n",
            encoding="utf-8",
        )
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertIn("csv_hash_mismatch", report["errors"])

    def test_validator_rejects_timestamp_not_aligned_to_raw_snapshot_interval(self):
        payload = self.record()
        self.attach_schedule(payload, [3_600_000, 7_200_000])
        schedule_path = self.root / "BTCUSDT.schedule.json"
        schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
        first_snapshot = self.root / schedule["source_snapshots"][0]["path"]
        raw_snapshot = json.loads(first_snapshot.read_text(encoding="utf-8"))
        raw_snapshot["instruments"][0]["fundingInterval"] = "120"
        first_snapshot.write_text(json.dumps(raw_snapshot), encoding="utf-8")
        schedule["source_snapshots"][0]["sha256"] = sha256_file(first_snapshot)
        schedule["source_snapshots"][0]["funding_interval_minutes"] = 120
        schedule_path.write_text(json.dumps(schedule), encoding="utf-8")
        payload["settlement_schedule_evidence"]["sha256"] = sha256_file(schedule_path)
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertIn(
            "funding_interval_changed_without_effective_boundary_evidence",
            report["errors"],
        )

    def test_validator_detects_query_window_gap(self):
        payload = self.record()
        self.attach_schedule(payload, [3_600_000, 7_200_000])
        payload["runs"][0]["pages"] = [{
            "request_start_ms": 3_600_000,
            "request_end_ms": 5_399_999,
            "response_rows": 1,
            "complete": True,
            "saturated": False,
            "complete": True,
            "saturated": False,
        }]
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertIn("query_window_not_fully_covered", report["errors"])

    def test_validator_does_not_count_saturated_parent_page_as_complete_coverage(self):
        payload = self.record()
        self.attach_schedule(payload, [3_600_000, 7_200_000])
        payload["runs"][0]["pages"] = [{
            "request_start_ms": 3_600_000,
            "request_end_ms": 7_200_000,
            "response_rows": 200,
            "first_ts": 3_600_000,
            "last_ts": 7_200_000,
            "complete": False,
            "saturated": True,
        }]
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertIn("query_window_not_fully_covered", report["errors"])

    def test_validator_rejects_settlement_off_dated_funding_interval_grid(self):
        payload = self.record()
        self.attach_schedule(payload, [3_600_000, 7_200_000])
        schedule_path = self.root / "BTCUSDT.schedule.json"
        schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
        schedule["expected_settlement_timestamps_ms"] = [3_600_000, 7_200_001]
        schedule_path.write_text(json.dumps(schedule), encoding="utf-8")
        payload["settlement_schedule_evidence"]["sha256"] = sha256_file(schedule_path)
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertIn("funding_events_do_not_match_dated_schedule", report["errors"])


if __name__ == "__main__":
    unittest.main()
