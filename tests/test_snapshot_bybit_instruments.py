"""Offline tests for the dated Bybit instrument snapshot collector."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import json
import tempfile
import unittest
from pathlib import Path

import scripts.snapshot_bybit_instruments as collector
from scripts.snapshot_bybit_instruments import (
    build_snapshot, fetch_all_instruments, write_snapshot,
)


class SnapshotCollectorTests(unittest.TestCase):
    def test_collects_all_pages_and_sorts_symbols(self):
        pages = {
            None: ([{"symbol": "ETHUSDT"}, {"symbol": "BTCUSDT"}], "cursor-2"),
            "cursor-2": ([{"symbol": "SOLUSDT"}], None),
        }
        seen = []
        def fetch(cursor):
            seen.append(cursor)
            return pages[cursor]
        rows = fetch_all_instruments("linear", fetch)
        self.assertEqual(seen, [None, "cursor-2"])
        self.assertEqual([row["symbol"] for row in rows],
                         ["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    def test_identical_duplicate_from_overlapping_pages_is_deduplicated(self):
        row = {"symbol": "BTCUSDT", "status": "Trading"}
        pages = {
            None: ([row], "next"),
            "next": ([dict(row)], None),
        }
        rows = fetch_all_instruments("linear", lambda cursor: pages[cursor])
        self.assertEqual(rows, [row])

    def test_conflicting_duplicate_is_rejected(self):
        pages = {
            None: ([{"symbol": "BTCUSDT", "status": "Trading"}], "next"),
            "next": ([{"symbol": "BTCUSDT", "status": "PreLaunch"}], None),
        }
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            fetch_all_instruments("linear", lambda cursor: pages[cursor])

    def test_repeated_cursor_is_rejected(self):
        def fetch(cursor):
            return ([{"symbol": "BTCUSDT"}], "loop")
        with self.assertRaisesRegex(RuntimeError, "cursor repeated"):
            fetch_all_instruments("linear", fetch)

    def test_empty_universe_and_missing_symbol_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "empty instrument"):
            fetch_all_instruments("linear", lambda cursor: ([], None))
        with self.assertRaisesRegex(ValueError, "missing symbol"):
            fetch_all_instruments("linear", lambda cursor: ([{}], None))

    def test_strict_retcode_rejects_boolean_false(self):
        with self.assertRaisesRegex(RuntimeError, "non-zero or invalid retCode"):
            collector._check_ret_code({"retCode": False, "result": {"list": []}})

    def test_workflow_regional_hosts_are_in_allowlist(self):
        for host in ("api.bybit.com", "api.bytick.com", "api.bybit.kz",
                     "api.bybit.tr", "api.bybitgeorgia.ge", "api.bybit.ae", "api.bybit.id"):
            collector._validate_base_url("https://" + host)
        for host in ("api.bybit.nl", "api.bybit-tr.com"):
            with self.assertRaises(ValueError):
                collector._validate_base_url("https://" + host)

    def test_public_collector_rejects_non_bybit_host_before_request(self):
        with self.assertRaisesRegex(ValueError, "official HTTPS Bybit API host"):
            collector._request_page("https://attacker.example", "linear", None)

    def test_pagination_page_limit_fails_closed(self):
        previous = collector.MAX_PAGES
        collector.MAX_PAGES = 1
        try:
            with self.assertRaisesRegex(RuntimeError, "exceeded safety limit"):
                fetch_all_instruments(
                    "linear", lambda cursor: ([{"symbol": "BTCUSDT"}], "next")
                )
        finally:
            collector.MAX_PAGES = previous

    def test_pagination_cursor_must_be_string(self):
        with self.assertRaisesRegex(ValueError, "nextPageCursor must be a string"):
            collector._validate_next_cursor(123)
        self.assertIsNone(collector._validate_next_cursor(""))
    def test_snapshot_has_provenance_and_exact_timestamp(self):
        snapshot = build_snapshot(
            [{"symbol": "BTCUSDT"}], "linear", "2026-11-02T00:00:00Z"
        )
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["count"], 1)
        self.assertEqual(snapshot["fetched_at"], "2026-11-02T00:00:00Z")
        self.assertIn("instruments-info", snapshot["source"])

    def test_snapshot_rejects_duplicate_symbols(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_snapshot([{"symbol": "BTCUSDT"}, {"symbol": "BTCUSDT"}], "linear")

    def test_atomic_writer_round_trips_json(self):
        snapshot = build_snapshot([{"symbol": "BTCUSDT"}], "linear",
                                  "2026-11-02T00:00:00Z")
        with tempfile.TemporaryDirectory() as directory:
            path = write_snapshot(snapshot, Path(directory) / "linear" / "test.json")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), snapshot)


if __name__ == "__main__":
    unittest.main(verbosity=2)
