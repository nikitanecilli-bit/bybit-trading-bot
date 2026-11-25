import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.validate_bybit_raw_semantics import validate_semantics


class BybitRawSemanticsTests(unittest.TestCase):
    def build_fixture(self, root):
        records, streams, outputs = [], {}, {}
        fixtures = {
            "funding": ("/v5/market/funding/history",
                        {"symbol": "BTCUSDT", "fundingRateTimestamp": "3600000",
                         "fundingRate": "0.0001"},
                        ["symbol", "funding_timestamp_ms", "funding_rate"],
                        {"symbol": "BTCUSDT", "funding_timestamp_ms": "3600000",
                         "funding_rate": "0.0001"}),
            "trade_kline": ("/v5/market/kline",
                            ["3600000", "1", "2", "1", "2", "3", "6"],
                            ["symbol", "timestamp_ms", "open", "high", "low",
                             "close", "volume", "turnover"],
                            {"symbol": "BTCUSDT", "timestamp_ms": "3600000",
                             "open": "1", "high": "2", "low": "1", "close": "2",
                             "volume": "3", "turnover": "6"}),
            "mark_price": ("/v5/market/mark-price-kline",
                           ["3600000", "1", "2", "1", "2"],
                           ["symbol", "timestamp_ms", "open", "high", "low", "close"],
                           {"symbol": "BTCUSDT", "timestamp_ms": "3600000",
                            "open": "1", "high": "2", "low": "1", "close": "2"}),
        }
        output_map = {"funding": "funding_csv", "trade_kline": "trade_kline_csv",
                      "mark_price": "mark_price_csv"}
        for stream, (endpoint, raw_row, headers, csv_row) in fixtures.items():
            raw = json.dumps({"retCode": 0, "result": {"list": [raw_row]}}).encode()
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
                                "request_start_ms": 3600000, "request_end_ms": 3600000}]
            csv_name = stream + ".csv"
            with (root / csv_name).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers)
                writer.writeheader()
                writer.writerow(csv_row)
            outputs[output_map[stream]] = {"path": csv_name}
        return {"schema_version": 1, "symbol": "BTCUSDT", "category": "linear",
                "records": records, "collection_pages": streams, "normalized_outputs": outputs}

    def test_validates_raw_pages_and_reconstructs_normalized_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.build_fixture(root)
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest))
            result = validate_semantics(path)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["pages_checked"], 3)

            # Keep hashes and page inventory valid, but alter a normalized value.
            csv_path = root / "trade_kline.csv"
            text = csv_path.read_text().replace(",1,2,1,2,3,6", ",1,2,1,2,30,6")
            csv_path.write_text(text)
            result = validate_semantics(path)
            self.assertFalse(result["ok"])
            self.assertIn("trade_kline_normalized_csv_content_mismatch", result["errors"])

    def test_detects_page_inventory_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.build_fixture(root)
            path = root / "manifest.json"
            manifest["collection_pages"]["funding"][0]["response_rows"] = 2
            manifest["collection_pages"]["trade_kline"][0]["request_start_ms"] = 3600001
            manifest["collection_pages"]["mark_price"][0]["raw_response_request_id"] = "missing"
            path.write_text(json.dumps(manifest))
            result = validate_semantics(path)
            self.assertFalse(result["ok"])
            self.assertIn("funding_row_count_mismatch", result["errors"])
            self.assertIn("trade_kline_timestamp_outside_request", result["errors"])
            self.assertIn("mark_price_record_missing", result["errors"])


if __name__ == "__main__":
    unittest.main()
