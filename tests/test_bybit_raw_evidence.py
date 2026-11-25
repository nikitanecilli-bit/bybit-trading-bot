"""Offline tests for content-addressed Bybit response evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.bybit_raw_evidence import (
    assert_snapshot_paths_available, capture_response, finalize_snapshot_evidence,
    validate_evidence_manifest, write_evidence_manifest,
)
from scripts.snapshot_bybit_instruments import _request_page as instrument_request
from scripts.snapshot_bybit_risk_limits import _request_page as risk_request


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body
        self.status = 200
        self.headers = {
            "Date": "Wed, 25 Nov 2026 00:00:00 GMT",
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class FakeOpener:
    def __init__(self, body: bytes):
        self.body = body
        self.request = None

    def open(self, request, timeout):
        self.request = request
        return FakeResponse(self.body)


class RawEvidenceTests(unittest.TestCase):
    def test_capture_manifest_and_tamper_detection(self):
        body = b'{"retCode":0,"result":{"list":[]}}'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "snapshot.json"
            output.write_text('{"instruments":[]}', encoding="utf-8")
            records = []
            record = capture_response(
                body, base_url="https://api.bybit.com",
                endpoint="/v5/market/instruments-info",
                params={"category": "linear", "limit": 1000},
                http_status=200, response_headers={"Content-Type": "application/json"},
                evidence_dir=root, records=records,
            )
            manifest = root / "evidence.json"
            write_evidence_manifest(
                manifest, source="fixture", category="linear",
                normalized_output=output, records=records,
                collection_pages=[{
                    "page_index": 1,
                    "raw_response_request_id": record["request_id"],
                    "raw_response_body_sha256": record["body_sha256"],
                }], capture_dir=root / "raw_evidence" / "capture-test",
            )
            self.assertTrue(validate_evidence_manifest(manifest)["ok"])
            (root / record["body_file"]).write_bytes(body + b" ")
            report = validate_evidence_manifest(manifest)
            self.assertFalse(report["ok"])
            self.assertIn("raw_body_hash_mismatch", report["errors"])

    def test_finalize_snapshot_rebases_paths_and_refuses_overwrite(self):
        body = b'{"retCode":0,"result":{"list":[]}}'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = []
            record = capture_response(
                body, base_url="https://api.bybit.com",
                endpoint="/v5/market/risk-limit", params={"category": "linear"},
                http_status=200, response_headers={},
                evidence_dir=root / "raw_evidence" / "capture-test", records=records,
            )
            output = root / "2026-11-25T08-00-00Z.json"
            assert_snapshot_paths_available(root, "2026-11-25T08-00-00Z")
            output.write_text('{"tiers":[]}', encoding="utf-8")
            manifest = finalize_snapshot_evidence(
                root, "2026-11-25T08-00-00Z", source="fixture",
                category="linear", normalized_output=output, records=records,
                collection_pages=[{
                    "page_index": 1,
                    "raw_response_request_id": record["request_id"],
                    "raw_response_body_sha256": record["body_sha256"],
                }],
            )
            report = validate_evidence_manifest(manifest)
            self.assertTrue(report["ok"], report["errors"])
            self.assertTrue((root / records[0]["body_file"]).is_file())
            self.assertTrue((root / records[0]["audit_file"]).is_file())
            with self.assertRaises(FileExistsError):
                assert_snapshot_paths_available(root, "2026-11-25T08-00-00Z")

    def test_normalized_output_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "snapshot.json"
            output.write_text('{"version":1}', encoding="utf-8")
            manifest = root / "evidence.json"
            write_evidence_manifest(
                manifest, source="fixture", category="linear",
                normalized_output=output, records=[], collection_pages=[],
            )
            output.write_text('{"version":2}', encoding="utf-8")
            report = validate_evidence_manifest(manifest)
            self.assertFalse(report["ok"])
            self.assertIn("normalized_output_hash_mismatch", report["errors"])

    def test_instrument_endpoint_captures_exact_response_and_params(self):
        body = json.dumps({
            "retCode": 0, "result": {
                "list": [{"symbol": "BTCUSDT", "status": "Trading"}],
                "nextPageCursor": "",
            },
        }).encode()
        opener = FakeOpener(body)
        with tempfile.TemporaryDirectory() as tmp:
            records = []
            with patch("scripts.snapshot_bybit_instruments.urllib.request.build_opener", return_value=opener):
                rows, cursor = instrument_request(
                    "https://api.bybit.com", "linear", None, status="Trading",
                    raw_evidence_dir=tmp, raw_records=records,
                )
            self.assertEqual(rows[0]["symbol"], "BTCUSDT")
            self.assertIsNone(cursor)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["body_sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(records[0]["request"]["params"]["status"], "Trading")
            self.assertEqual((Path(tmp) / records[0]["body_file"]).read_bytes(), body)

    def test_risk_limit_endpoint_captures_exact_response_and_params(self):
        body = json.dumps({"retCode": 0, "result": {"list": [], "nextPageCursor": ""}}).encode()
        opener = FakeOpener(body)
        with tempfile.TemporaryDirectory() as tmp:
            records = []
            with patch("scripts.snapshot_bybit_risk_limits.urllib.request.build_opener", return_value=opener):
                rows, cursor = risk_request(
                    "https://api.bybit.com", "linear", None,
                    raw_evidence_dir=tmp, raw_records=records,
                )
            self.assertEqual(rows, [])
            self.assertIsNone(cursor)
            self.assertEqual(records[0]["request"]["endpoint"], "/v5/market/risk-limit")
            self.assertEqual((Path(tmp) / records[0]["body_file"]).read_bytes(), body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
