import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.validate_bybit_raw_semantics import validate_semantics


class BybitRawSemanticsTests(unittest.TestCase):
    def test_valid_pages_and_detects_false_page_row_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records, streams = [], {}
            fixtures = {
                "funding": ("/v5/market/funding/history",
                            {"symbol": "BTCUSDT", "fundingRateTimestamp": "3600000"}),
                "trade_kline": ("/v5/market/kline",
                               ["3600000", "1", "2", "1", "2", "3", "6"]),
                "mark_price": ("/v5/market/mark-price-kline",
                               ["3600000", "1", "2", "1", "2"]),
            }
            for stream, (endpoint, row) in fixtures.items():
                body = {"retCode": 0, "result": {"list": [row]}}
                body_bytes = json.dumps(body).encode()
                digest = hashlib.sha256(body_bytes).hexdigest()
                body_file = f"{stream}.json"
                (root / body_file).write_bytes(body_bytes)
                request_id = f"id-{stream}"
                records.append({
                    "request_id": request_id, "body_file": body_file,
                    "body_sha256": digest,
                    "request": {"method": "GET", "endpoint": endpoint,
                                "params": {"category": "linear", "symbol": "BTCUSDT"}},
                })
                streams[stream] = [{
                    "raw_response_request_id": request_id,
                    "raw_response_body_sha256": digest,
                    "response_rows": 1, "first_ts": 3600000, "last_ts": 3600000,
                    "request_start_ms": 3600000, "request_end_ms": 3600000,
                }]
            manifest = {"schema_version": 1, "symbol": "BTCUSDT", "category": "linear",
                        "records": records, "collection_pages": streams}
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            result = validate_semantics(manifest_path)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["pages_checked"], 3)

            manifest["collection_pages"]["funding"][0]["response_rows"] = 2
            manifest_path.write_text(json.dumps(manifest))
            result = validate_semantics(manifest_path)
            self.assertFalse(result["ok"])
            self.assertIn("funding_row_count_mismatch", result["errors"])

    def test_detects_wrong_endpoint_and_timestamp_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records, streams = [], {}
            for stream, endpoint, row in (
                ("funding", "/v5/market/funding/history",
                 {"symbol": "BTCUSDT", "fundingRateTimestamp": "3600000"}),
                ("trade_kline", "/v5/market/kline",
                 ["3600000", "1", "2", "1", "2", "3", "6"]),
                ("mark_price", "/v5/market/mark-price-kline",
                 ["3600000", "1", "2", "1", "2"]),
            ):
                raw = json.dumps({"retCode": 0, "result": {"list": [row]}}).encode()
                digest = hashlib.sha256(raw).hexdigest()
                body_file = stream + ".json"
                (root / body_file).write_bytes(raw)
                rid = "id-" + stream
                records.append({"request_id": rid, "body_file": body_file,
                                "body_sha256": digest,
                                "request": {"method": "GET", "endpoint": endpoint,
                                            "params": {"category": "linear", "symbol": "BTCUSDT"}}})
                streams[stream] = [{"raw_response_request_id": rid,
                                    "raw_response_body_sha256": digest, "response_rows": 1,
                                    "first_ts": 3600000, "last_ts": 3600000,
                                    "request_start_ms": 3600001, "request_end_ms": 3600002}]
            streams["mark_price"][0]["raw_response_request_id"] = "wrong"
            path = root / "manifest.json"
            path.write_text(json.dumps({"schema_version": 1, "symbol": "BTCUSDT",
                                        "category": "linear", "records": records,
                                        "collection_pages": streams}))
            result = validate_semantics(path)
            self.assertFalse(result["ok"])
            self.assertIn("trade_kline_timestamp_outside_request", result["errors"])
            self.assertIn("mark_price_record_missing", result["errors"])


if __name__ == "__main__":
    unittest.main()
