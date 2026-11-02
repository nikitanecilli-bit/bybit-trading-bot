import sys
import time
import unittest
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.bybit_reconciliation_snapshot import (
    CollectorError,
    MAX_EXECUTION_WINDOW_MS,
    _execution_intervals,
    _signature,
    _validate_base_url,
    _NoRedirectHandler,
    collect_snapshot,
)

SAVED = "2026-10-01T00:00:00Z"


def response(rows=None, cursor=""):
    return {"retCode": 0, "result": {"list": rows or [], "nextPageCursor": cursor}}


class FakeTransport:
    def __init__(self, readonly=1, fail_endpoint=None, cursor_loop=False):
        self.readonly = readonly
        self.fail_endpoint = fail_endpoint
        self.cursor_loop = cursor_loop
        self.calls = []

    def __call__(self, url, headers=None, timeout=20):
        endpoint = urlparse(url).path
        self.calls.append((endpoint, url, headers or {}))
        if endpoint == "/v5/user/query-api":
            return {"retCode": 0, "result": {"apiKey": "key", "readOnly": self.readonly}}
        if endpoint == "/v5/market/time":
            return {"retCode": 0, "result": {}, "time": int(time.time() * 1000)}
        if endpoint == self.fail_endpoint:
            return {"retCode": 10004, "retMsg": "hidden"}
        if endpoint == "/v5/position/list" and self.cursor_loop:
            return response(cursor="loop")
        if endpoint in ("/v5/position/list", "/v5/order/realtime",
                        "/v5/execution/list"):
            return response()
        raise AssertionError(f"unexpected endpoint: {endpoint}")


class ReconciliationCollectorTests(unittest.TestCase):
    def test_signature_includes_query_string(self):
        a = _signature("1", "key", "secret", "a=1&b=2")
        b = _signature("1", "key", "secret", "b=2&a=1")
        self.assertNotEqual(a, b)

    def test_execution_intervals_never_exceed_seven_days(self):
        intervals = _execution_intervals(100, 100 + 2 * MAX_EXECUTION_WINDOW_MS + 1)
        self.assertEqual([end - start for start, end in intervals],
                         [MAX_EXECUTION_WINDOW_MS, MAX_EXECUTION_WINDOW_MS, 1])

    def test_read_only_check_precedes_all_account_snapshot_calls(self):
        fake = FakeTransport()
        snapshot = collect_snapshot("key", "secret", SAVED,
                                    base_url="https://api.bybit.kz",
                                    request_json=fake)
        endpoints = [call[0] for call in fake.calls]
        self.assertEqual(endpoints[0], "/v5/user/query-api")
        self.assertEqual(endpoints[1], "/v5/market/time")
        self.assertEqual(endpoints[2:5], [
            "/v5/position/list", "/v5/order/realtime", "/v5/execution/list"
        ])
        self.assertEqual(endpoints[-1], "/v5/market/time")
        self.assertEqual(snapshot["status"], "CAPTURED_READ_ONLY_NOT_RECONCILED")
        self.assertEqual(snapshot["counts"]["positions"], 0)
        self.assertLessEqual(
            snapshot["bybit_server_time_after_ms"] -
            snapshot["bybit_server_time_before_ms"], 120_000
        )
        self.assertEqual(len(snapshot["raw_sha256"]), 64)

    def test_non_read_only_key_stops_before_account_calls(self):
        fake = FakeTransport(readonly=0)
        with self.assertRaisesRegex(CollectorError, "not explicitly read-only"):
            collect_snapshot("key", "secret", SAVED, request_json=fake)
        self.assertEqual([call[0] for call in fake.calls], ["/v5/user/query-api"])

    def test_boolean_retcode_is_rejected(self):
        def transport(url, headers=None, timeout=20):
            if urlparse(url).path == "/v5/user/query-api":
                return {"retCode": False, "result": {"apiKey": "key", "readOnly": 1}}
            raise AssertionError("account endpoint must not be called")
        with self.assertRaisesRegex(CollectorError, "integer zero"):
            collect_snapshot("key", "secret", SAVED, request_json=transport)

    def test_repeated_pagination_cursor_fails_closed(self):
        fake = FakeTransport(cursor_loop=True)
        with self.assertRaisesRegex(CollectorError, "pagination cursor repeated"):
            collect_snapshot("key", "secret", SAVED, request_json=fake)

    def test_api_error_is_not_treated_as_empty_account(self):
        fake = FakeTransport(fail_endpoint="/v5/position/list")
        with self.assertRaisesRegex(CollectorError, "retCode must be integer zero"):
            collect_snapshot("key", "secret", SAVED, request_json=fake)

    def test_official_regional_hosts_are_allowed(self):
        for host in (
            "api.bybit.com", "api.bytick.com", "api.bybit.kz",
            "api.bybit.tr", "api.bybitgeorgia.ge", "api.bybit.ae",
            "api.bybit.eu", "api.bybit.id",
        ):
            with self.subTest(host=host):
                _validate_base_url(f"https://{host}")

    def test_redirect_handler_refuses_redirects(self):
        handler = _NoRedirectHandler()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {},
                                                   "https://attacker.example/"))

    def test_rejects_non_bybit_https_host_before_credentials_are_sent(self):
        fake = FakeTransport()
        with self.assertRaisesRegex(ValueError, "official HTTPS Bybit API host"):
            collect_snapshot("key", "secret", SAVED,
                             base_url="https://attacker.example", request_json=fake)
        self.assertEqual(fake.calls, [])

    def test_rejects_http_non_tls_base_url(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            collect_snapshot("key", "secret", SAVED, base_url="http://example.test",
                             request_json=FakeTransport())

    def test_rejects_non_utc_offset_even_when_timezone_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "expressed in UTC"):
            collect_snapshot("key", "secret", "2026-10-01T03:00:00+03:00",
                             request_json=FakeTransport())

    def test_rejects_backup_timestamp_in_future_of_exchange(self):
        with self.assertRaisesRegex(CollectorError, "not earlier than Bybit server time"):
            collect_snapshot("key", "secret", "2099-01-01T00:00:00Z",
                             request_json=FakeTransport())


if __name__ == "__main__":
    unittest.main()
