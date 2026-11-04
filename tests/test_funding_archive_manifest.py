"""Tests for funding archive query-provenance manifests."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from funding_archive_manifest import (
    attach_funding_settlement_schedule, record_funding_collection,
    validate_funding_manifest, validate_archive_funding_manifests, sha256_file,
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

    def attach_schedule(
        self, payload, expected_events, *,
        coverage_start_ms=3_600_000, coverage_end_ms=7_200_000,
        interval_minutes=60,
    ):
        source_snapshots = []
        for ts in sorted(set((coverage_start_ms, coverage_end_ms))):
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
                "instruments": [{
                    "symbol": "BTCUSDT",
                    "fundingInterval": str(interval_minutes),
                }],
            }), encoding="utf-8")
            source_snapshots.append({
                "path": snapshot_path.name,
                "sha256": sha256_file(snapshot_path),
                "fetched_at_ms": ts,
                "funding_interval_minutes": interval_minutes,
            })
        schedule_path = self.root / "BTCUSDT.schedule.json"
        schedule = {
            "schema_version": 1,
            "source": "bybit_dated_instrument_snapshots",
            "symbol": "BTCUSDT",
            "category": "linear",
            "coverage_start_ms": coverage_start_ms,
            "coverage_end_ms": coverage_end_ms,
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

    def _write_interval_snapshot(self, timestamp_ms, interval_minutes=60, include_symbol=True):
        path = self.root / f"interval_{timestamp_ms}.json"
        fetched_at = datetime.fromtimestamp(
            timestamp_ms / 1000, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")
        path.write_text(json.dumps({
            "schema_version": 1,
            "source": "Bybit V5 GET /v5/market/instruments-info",
            "category": "linear",
            "fetched_at": fetched_at,
            "count": 1 if include_symbol else 0,
            "instruments": ([{
                "symbol": "BTCUSDT",
                "fundingInterval": str(interval_minutes),
            }] if include_symbol else []),
        }), encoding="utf-8")
        return path

    def test_collector_attaches_hash_pinned_schedule_from_bracketing_snapshots(self):
        self.record()
        snapshots = [
            self._write_interval_snapshot(3_599_999),
            self._write_interval_snapshot(7_200_001),
        ]
        schedule = attach_funding_settlement_schedule(
            self.csv, self.manifest, symbol="BTCUSDT", category="linear",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
            snapshot_paths=snapshots, snapshot_copy_dir=self.root / "copied_snapshots",
        )
        self.assertEqual(
            schedule["expected_settlement_timestamps_ms"],
            [3_600_000, 7_200_000],
        )
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue(report["settlement_schedule_verified"])


    def test_collector_allows_symbol_absence_outside_its_lifecycle_window(self):
        self.record()
        snapshots = [
            self._write_interval_snapshot(1_000_000, include_symbol=False),
            self._write_interval_snapshot(3_599_999, include_symbol=True),
            self._write_interval_snapshot(7_200_001, include_symbol=True),
            self._write_interval_snapshot(8_000_000, include_symbol=False),
        ]
        schedule = attach_funding_settlement_schedule(
            self.csv, self.manifest, symbol="BTCUSDT", category="linear",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
            snapshot_paths=snapshots, snapshot_copy_dir=self.root / "copied_snapshots",
        )
        self.assertEqual(
            schedule["expected_settlement_timestamps_ms"],
            [3_600_000, 7_200_000],
        )

    def test_collector_rejects_symbol_absence_inside_its_lifecycle_window(self):
        self.record()
        snapshots = [
            self._write_interval_snapshot(3_599_999, include_symbol=True),
            self._write_interval_snapshot(5_000_000, include_symbol=False),
            self._write_interval_snapshot(7_200_001, include_symbol=True),
        ]
        with self.assertRaisesRegex(ValueError, "absent from a dated instrument snapshot"):
            attach_funding_settlement_schedule(
                self.csv, self.manifest, symbol="BTCUSDT", category="linear",
                required_start_ms=3_600_000, required_end_ms=7_200_000,
                snapshot_paths=snapshots, snapshot_copy_dir=self.root / "copied_snapshots",
            )


    def test_collector_refuses_unresolved_interval_change(self):
        self.record()
        snapshots = [
            self._write_interval_snapshot(3_599_999, 60),
            self._write_interval_snapshot(7_200_001, 120),
        ]
        with self.assertRaisesRegex(ValueError, "effective boundary is unknown"):
            attach_funding_settlement_schedule(
                self.csv, self.manifest, symbol="BTCUSDT", category="linear",
                required_start_ms=3_600_000, required_end_ms=7_200_000,
                snapshot_paths=snapshots, snapshot_copy_dir=self.root / "copied_snapshots",
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

    def test_validator_rejects_duplicate_funding_timestamp_even_when_manifest_is_rehashed(self):
        payload = self.record()
        with self.csv.open("a", encoding="utf-8") as handle:
            handle.write("3600000,1970-01-01,0.001\\n")
        payload["csv_sha256"] = sha256_file(self.csv)
        payload["csv_data_rows"] = 3
        self.attach_schedule(payload, [3_600_000, 7_200_000])
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertFalse(report["ok"])
        self.assertIn("duplicate_funding_timestamp_in_csv", report["errors"])


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
            "first_ts": 5_400_000,
            "last_ts": 7_200_000,
            "response_order_descending": True,
            "response_timestamps_unique": True,
            "complete": False,
            "saturated": True,
        }]
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=3_600_000, required_end_ms=7_200_000,
        )
        self.assertIn("query_window_not_fully_covered", report["errors"])


    def test_archive_level_validator_uses_each_symbols_lifecycle_clipped_range(self):
        archive_root = self.root / "archive"
        funding_dir = archive_root / "funding"
        snapshot_dir = archive_root / "instrument_snapshots"
        funding_dir.mkdir(parents=True)
        snapshot_dir.mkdir(parents=True)

        csv_path = funding_dir / "BTCUSDT.csv"
        csv_path.write_text(
            "symbol,funding_timestamp_ms,funding_rate\\n"
            "BTCUSDT,3600000,0.001\\n",
            encoding="utf-8",
        )
        manifest_path = csv_path.with_suffix(csv_path.suffix + ".audit.json")
        record_funding_collection(
            csv_path, manifest_path, symbol="BTCUSDT", category="linear",
            api_base="https://api.bybit.com",
            requested_start_ms=3_600_000, requested_end_ms=7_199_999,
            pages=[{
                "request_start_ms": 3_600_000,
                "request_end_ms": 7_199_999,
                "response_rows": 1,
                "first_ts": 3_600_000,
                "last_ts": 3_600_000,
                "complete": True,
                "saturated": False,
                "out_of_window_rows": 0,
            }],
            collected_at_ms=7_200_001,
        )
        snapshots = []
        for timestamp in (3_600_000, 7_200_000):
            path = snapshot_dir / f"{timestamp}.json"
            fetched_at = datetime.fromtimestamp(
                timestamp / 1000, tz=timezone.utc
            ).isoformat().replace("+00:00", "Z")
            path.write_text(json.dumps({
                "schema_version": 1,
                "source": "Bybit V5 GET /v5/market/instruments-info",
                "category": "linear",
                "fetched_at": fetched_at,
                "count": 1,
                "instruments": [{
                    "symbol": "BTCUSDT",
                    "fundingInterval": "60",
                }],
            }), encoding="utf-8")
            snapshots.append(path)
        attach_funding_settlement_schedule(
            csv_path, manifest_path, symbol="BTCUSDT", category="linear",
            required_start_ms=3_600_000, required_end_ms=7_199_999,
            snapshot_paths=snapshots, snapshot_copy_dir=snapshot_dir,
        )
        (archive_root / "archive_manifest.json").write_text(json.dumps({
            "category": "linear",
            "interval": "60",
            "results": [{
                "symbol": "BTCUSDT",
                "requested_start_ms": 3_600_000,
                "requested_end_exclusive_ms": 10_800_000,
                "start_ms": 3_600_000,
                "end_exclusive_ms": 7_200_000,
                "lifecycle_clipped": True,
            }],
        }), encoding="utf-8")

        report = validate_archive_funding_manifests(
            archive_root, ["BTCUSDT"],
            requested_start_ms=3_600_000,
            requested_end_exclusive_ms=10_800_000,
        )
        self.assertTrue(report["ok"], report)
        self.assertTrue(report["results"][0]["settlement_schedule_verified"])

    def test_archive_level_validator_rejects_mismatched_requested_range(self):
        archive_root = self.root / "archive"
        archive_root.mkdir()
        (archive_root / "archive_manifest.json").write_text(json.dumps({
            "category": "linear",
            "interval": "60",
            "results": [{
                "symbol": "BTCUSDT",
                "requested_start_ms": 3_600_000,
                "requested_end_exclusive_ms": 7_200_000,
                "start_ms": 3_600_000,
                "end_exclusive_ms": 7_200_000,
                "lifecycle_clipped": False,
            }],
        }), encoding="utf-8")
        report = validate_archive_funding_manifests(
            archive_root, ["BTCUSDT"],
            requested_start_ms=3_600_000,
            requested_end_exclusive_ms=10_800_000,
        )
        self.assertFalse(report["ok"])
        self.assertEqual(report["results"][0]["status"], "invalid_symbol_archive_range")

    def test_validator_accepts_complete_descending_saturated_page_chain(self):
        start_ms = 0
        end_ms = 200 * 3_600_000
        timestamps = list(range(start_ms, end_ms + 1, 3_600_000))
        self.csv.write_text(
            "timestamp,datetime,funding_rate\n"
            + "".join(f"{ts},1970-01-01,0.001\n" for ts in timestamps),
            encoding="utf-8",
        )
        payload = record_funding_collection(
            self.csv, self.manifest, symbol="BTCUSDT", category="linear",
            api_base="https://api.bybit.com",
            requested_start_ms=start_ms, requested_end_ms=end_ms,
            pages=[
                {
                    "request_start_ms": start_ms,
                    "request_end_ms": end_ms,
                    "response_rows": 200,
                    "first_ts": 3_600_000,
                    "last_ts": end_ms,
                    "response_order_descending": True,
                    "response_timestamps_unique": True,
                    "complete": False,
                    "saturated": True,
                    "out_of_window_rows": 0,
                },
                {
                    "request_start_ms": start_ms,
                    "request_end_ms": 3_599_999,
                    "response_rows": 1,
                    "first_ts": 0,
                    "last_ts": 0,
                    "complete": True,
                    "saturated": False,
                    "out_of_window_rows": 0,
                },
            ],
            collected_at_ms=end_ms + 1,
        )
        self.attach_schedule(
            payload, timestamps, coverage_start_ms=start_ms,
            coverage_end_ms=end_ms, interval_minutes=60,
        )
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=start_ms, required_end_ms=end_ms,
        )
        self.assertTrue(report["ok"], report["errors"])

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
        self.assertIn(
            "expected_settlement_schedule_not_reconstructed_from_interval",
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
