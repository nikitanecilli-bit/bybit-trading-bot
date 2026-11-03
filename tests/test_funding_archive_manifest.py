"""Tests for funding archive query-provenance manifests."""
import json
import tempfile
import unittest
from pathlib import Path

from funding_archive_manifest import record_funding_collection, validate_funding_manifest


class FundingArchiveManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.csv = self.root / "BTCUSDT_funding.csv"
        self.manifest = self.root / "BTCUSDT_funding.audit.json"
        self.csv.write_text("timestamp,datetime,funding_rate\n1000,1970-01-01,0.001\n2000,1970-01-01,0.002\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def record(self):
        return record_funding_collection(
            self.csv, self.manifest, symbol="BTCUSDT", category="linear",
            api_base="https://api.bybit.com", requested_start_ms=1000,
            requested_end_ms=2000,
            pages=[
                {"request_start_ms": 1000, "request_end_ms": 2000, "response_rows": 1, "first_ts": 2000, "last_ts": 2000},
                {"request_start_ms": 1000, "request_end_ms": 1999, "response_rows": 1, "first_ts": 1000, "last_ts": 1000},
            ],
            collected_at_ms=3000,
        )

    def test_manifest_records_hash_rows_and_query_pages(self):
        payload = self.record()
        self.assertEqual(payload["csv_data_rows"], 2)
        self.assertEqual(len(payload["runs"][0]["pages"]), 2)
        self.assertFalse(payload["settlement_schedule_verified"])

    def test_validator_rejects_missing_dated_schedule_even_with_full_query_coverage(self):
        self.record()
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=1000, required_end_ms=2000,
        )
        self.assertTrue(report["query_coverage_ok"])
        self.assertFalse(report["ok"])
        self.assertIn("dated_settlement_schedule_not_verified", report["errors"])

    def test_validator_detects_csv_mutation_after_collection(self):
        self.record()
        self.csv.write_text("timestamp,datetime,funding_rate\n1000,1970-01-01,0.001\n", encoding="utf-8")
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=1000, required_end_ms=2000,
        )
        self.assertIn("csv_hash_mismatch", report["errors"])

    def test_validator_detects_query_window_gap(self):
        payload = self.record()
        payload["runs"][0]["pages"] = [
            {"request_start_ms": 1000, "request_end_ms": 1499, "response_rows": 1}
        ]
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")
        report = validate_funding_manifest(
            self.csv, self.manifest, symbol="BTCUSDT",
            required_start_ms=1000, required_end_ms=2000,
        )
        self.assertIn("query_window_not_fully_covered", report["errors"])


if __name__ == "__main__":
    unittest.main()
