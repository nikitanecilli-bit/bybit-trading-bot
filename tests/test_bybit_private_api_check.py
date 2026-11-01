import unittest

from scripts.bybit_private_api_check import (
    build_headers,
    make_signature,
    verify_response,
)


class BybitPrivateApiCheckTests(unittest.TestCase):
    def test_signature_is_deterministic(self):
        signature = make_signature("1700000000000", "test-key", "test-secret")
        self.assertEqual(len(signature), 64)
        self.assertEqual(
            signature,
            make_signature("1700000000000", "test-key", "test-secret"),
        )

    def test_headers_include_v5_auth_fields(self):
        headers = build_headers("test-key", "test-secret", timestamp="1700000000000")
        self.assertEqual(headers["X-BAPI-API-KEY"], "test-key")
        self.assertEqual(headers["X-BAPI-TIMESTAMP"], "1700000000000")
        self.assertEqual(headers["X-BAPI-RECV-WINDOW"], "5000")
        self.assertEqual(len(headers["X-BAPI-SIGN"]), 64)

    def test_accepts_read_only_key(self):
        ok, _ = verify_response(
            {
                "retCode": 0,
                "result": {
                    "apiKey": "test-key",
                    "readOnly": 1,
                    "permissions": {"ContractTrade": ["Order", "Position"]},
                },
            },
            "test-key",
        )
        self.assertTrue(ok)

    def test_rejects_key_not_marked_read_only(self):
        ok, message = verify_response(
            {"retCode": 0, "result": {"apiKey": "test-key", "readOnly": 0}},
            "test-key",
        )
        self.assertFalse(ok)
        self.assertIn("not marked read-only", message)

    def test_rejects_trade_permissions(self):
        ok, message = verify_response(
            {
                "retCode": 0,
                "result": {
                    "apiKey": "test-key",
                    "readOnly": 1,
                    "permissions": {"ContractTrade": ["Order"]},
                },
            },
            "test-key",
        )
        self.assertFalse(ok)
        self.assertIn("trade permissions", message)

    def test_rejects_api_error(self):
        ok, message = verify_response(
            {"retCode": 10004, "retMsg": "Error sign"},
            "test-key",
        )
        self.assertFalse(ok)
        self.assertIn("retCode=10004", message)


if __name__ == "__main__":
    unittest.main()
