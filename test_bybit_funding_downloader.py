import json
import unittest
from unittest.mock import patch

import bybit_funding_downloader as funding


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FundingDownloaderTests(unittest.TestCase):
    def test_paginates_sorts_and_deduplicates(self):
        pages = [
            [
                {"symbol": "BTCUSDT", "fundingRateTimestamp": "3000", "fundingRate": "0.001"},
                {"symbol": "BTCUSDT", "fundingRateTimestamp": "2000", "fundingRate": "-0.001"},
            ],
            [
                {"symbol": "BTCUSDT", "fundingRateTimestamp": "2000", "fundingRate": "-0.001"},
                {"symbol": "BTCUSDT", "fundingRateTimestamp": "1000", "fundingRate": "0.0001"},
            ],
            [],
        ]
        def fake_urlopen(_req, timeout=20):
            payload = pages.pop(0)
            return _Response({"retCode": 0, "result": {"list": payload}})

        with patch.object(funding.urllib.request, "urlopen", side_effect=fake_urlopen):
            rows = funding.fetch_funding_history("BTCUSDT", 1000, 3000, pause_seconds=0)
        self.assertEqual([r["funding_timestamp_ms"] for r in rows], [1000, 2000, 3000])
        self.assertEqual(rows[1]["funding_rate"], -0.001)

    def test_rejects_wrong_symbol(self):
        with patch.object(funding, "_request_page", return_value=[
            {"symbol": "ETHUSDT", "fundingRateTimestamp": "1000", "fundingRate": "0.001"}
        ]):
            with self.assertRaisesRegex(ValueError, "unexpected symbol"):
                funding.fetch_funding_history("BTCUSDT", 1000, 2000, pause_seconds=0)

    def test_rejects_invalid_rate(self):
        with patch.object(funding, "_request_page", return_value=[
            {"symbol": "BTCUSDT", "fundingRateTimestamp": "1000", "fundingRate": "nan"}
        ]):
            with self.assertRaisesRegex(ValueError, "Invalid funding"):
                funding.fetch_funding_history("BTCUSDT", 1000, 2000, pause_seconds=0)

    def test_rejects_bad_range(self):
        with self.assertRaises(ValueError):
            funding.fetch_funding_history("BTCUSDT", 2000, 1000, pause_seconds=0)


if __name__ == "__main__":
    unittest.main()
