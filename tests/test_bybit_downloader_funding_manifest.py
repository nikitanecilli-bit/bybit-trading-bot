"""Offline tests for Bybit funding collector query provenance."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import bybit_downloader as downloader


def test_funding_download_writes_page_provenance_and_hash_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        calls = []

        def fake_api_get(session, base_url, endpoint, params):
            calls.append(dict(params))
            if len(calls) == 1:
                return {"list": [
                    {"fundingRateTimestamp": "2000", "fundingRate": "0.002"}
                ]}
            return {"list": [
                {"fundingRateTimestamp": "1000", "fundingRate": "0.001"}
            ]}

        with patch.object(downloader, "api_get", side_effect=fake_api_get), \
             patch.object(downloader, "now_ms", return_value=3000):
            csv_path = downloader.download_dataset(
                object(), "https://api.bybit.com", "funding", "linear",
                "BTCUSDT", None, "1h", 1000, 2000, root, delay=0,
            )

        manifest_path = csv_path.with_suffix(csv_path.suffix + ".audit.json")
        assert csv_path.is_file()
        assert manifest_path.is_file()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        run = manifest["runs"][0]
        assert run["requested_start_ms"] == 1000
        assert run["requested_end_ms"] == 2000
        assert len(run["pages"]) == 2
        assert run["pages"][0]["request_start_ms"] == 1000
        assert run["pages"][0]["request_end_ms"] == 2000
        assert run["pages"][1]["request_start_ms"] == 1000
        assert run["pages"][1]["request_end_ms"] == 1999
        assert manifest["csv_data_rows"] == 2
        assert len(manifest["csv_sha256"]) == 64
        assert manifest["settlement_schedule_evidence"] is None


def test_funding_download_preserves_prior_collection_runs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        calls = []

        def fake_api_get(session, base_url, endpoint, params):
            calls.append(dict(params))
            ts = int(params["endTime"])
            return {"list": [
                {"fundingRateTimestamp": str(ts), "fundingRate": "0.001"}
            ]}

        with patch.object(downloader, "api_get", side_effect=fake_api_get), \
             patch.object(downloader, "now_ms", return_value=5000):
            first = downloader.download_dataset(
                object(), "https://api.bybit.com", "funding", "linear",
                "BTCUSDT", None, "1h", 1000, 1000, root, delay=0,
            )
            second = downloader.download_dataset(
                object(), "https://api.bybit.com", "funding", "linear",
                "BTCUSDT", None, "1h", 2000, 2000, root, delay=0,
            )
        assert first == second
        manifest = json.loads(
            first.with_suffix(first.suffix + ".audit.json").read_text(encoding="utf-8")
        )
        assert len(manifest["runs"]) == 2
        assert manifest["csv_data_rows"] == 2


def test_incremental_download_refuses_to_rebless_modified_existing_csv():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        def first_page(session, base_url, endpoint, params):
            return {"list": [
                {"fundingRateTimestamp": "1000", "fundingRate": "0.001"}
            ]}

        with patch.object(downloader, "api_get", side_effect=first_page), \\
             patch.object(downloader, "now_ms", return_value=3000):
            csv_path = downloader.download_dataset(
                object(), "https://api.bybit.com", "funding", "linear",
                "BTCUSDT", None, "1h", 1000, 1000, root, delay=0,
            )
        csv_path.write_text(
            "timestamp,datetime,funding_rate\\n999,1970-01-01,0.001\\n",
            encoding="utf-8",
        )
        try:
            with patch.object(downloader, "api_get", side_effect=AssertionError("API must not be called")):
                downloader.download_dataset(
                    object(), "https://api.bybit.com", "funding", "linear",
                    "BTCUSDT", None, "1h", 2000, 2000, root, delay=0,
                )
        except ValueError as exc:
            assert "hash differs from its manifest" in str(exc)
        else:
            raise AssertionError("modified CSV must not be re-attested by incremental download")


if __name__ == "__main__":
    test_funding_download_writes_page_provenance_and_hash_manifest()
    test_funding_download_preserves_prior_collection_runs()
