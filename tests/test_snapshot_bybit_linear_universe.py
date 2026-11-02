"""Offline tests for the Bybit point-in-time linear universe collector."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import json
import tempfile
import unittest
from pathlib import Path

from scripts.snapshot_bybit_linear_universe import (
    CAPTURED_STATUSES, STATUSES, build_universe_snapshot, fetch_linear_universe,
    fetch_status, is_linear_usdt_perpetual_available_at, validate_instrument_row,
)
from scripts.snapshot_bybit_instruments import write_snapshot


def row(symbol, status, launch="1000", delivery="0", contract="LinearPerpetual",
        quote="USDT", settle="USDT"):
    return {"symbol": symbol, "status": status, "launchTime": launch,
            "deliveryTime": delivery, "contractType": contract,
            "quoteCoin": quote, "settleCoin": settle}


class PointInTimeUniverseTests(unittest.TestCase):
    def test_queries_default_and_all_statuses_and_keeps_closed_rows(self):
        seen = []
        fixtures = {
            None: [row("BTCUSDT", "Trading"), row("PENDUSDT", "PendingOpen", launch="5000")],
            "PreLaunch": [row("NEWUSDT", "PreLaunch", launch="5000")],
            "Settling": [row("OLDUSDT", "Settling", delivery="9000")],
            "Delivering": [row("DELIVUSDT", "Delivering", delivery="8000")],
            "Closed": [row("DELISTEDUSDT", "Closed", delivery="7000")],
        }
        def fetch(status, cursor):
            seen.append((status, cursor))
            return fixtures[status], None
        rows, counts = fetch_linear_universe(fetch)
        self.assertEqual([status for status, cursor in seen], [None, *STATUSES])
        self.assertEqual(counts["Closed"], 1)
        self.assertEqual(counts["Trading"], 1)
        self.assertEqual(counts["PendingOpen"], 1)
        self.assertEqual({item["symbol"] for item in rows},
                         {"BTCUSDT", "PENDUSDT", "NEWUSDT", "OLDUSDT", "DELIVUSDT", "DELISTEDUSDT"})

    def test_empty_status_pages_are_valid_but_empty_total_universe_fails(self):
        with self.assertRaisesRegex(RuntimeError, "empty linear instrument universe"):
            fetch_linear_universe(lambda status, cursor: ([], None))

    def test_status_pagination_sorts_and_rejects_repeated_cursor(self):
        pages = {
            None: ([row("ETHUSDT", "Trading")], "next"),
            "next": ([row("BTCUSDT", "Trading")], None),
        }
        rows = fetch_status(None, lambda cursor: pages[cursor])
        self.assertEqual([item["symbol"] for item in rows], ["BTCUSDT", "ETHUSDT"])
        with self.assertRaisesRegex(RuntimeError, "cursor repeated"):
            fetch_status(None, lambda cursor: ([row("BTCUSDT", "Trading")], "loop"))

    def test_status_mismatch_and_invalid_timestamps_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "status mismatch"):
            validate_instrument_row(row("BTCUSDT", "Closed"), "Settling")
        with self.assertRaisesRegex(ValueError, "invalid launchTime"):
            validate_instrument_row(row("BTCUSDT", "Trading", launch="0"), None)
        with self.assertRaisesRegex(ValueError, "precedes launchTime"):
            validate_instrument_row(row("BTCUSDT", "Closed", launch="2000", delivery="1000"), "Closed")

    def test_point_in_time_availability_respects_launch_and_delivery_boundaries(self):
        closed = row("BTCUSDT", "Closed", launch="1000", delivery="3000")
        self.assertFalse(is_linear_usdt_perpetual_available_at(closed, 999))
        self.assertTrue(is_linear_usdt_perpetual_available_at(closed, 1000))
        self.assertTrue(is_linear_usdt_perpetual_available_at(closed, 2999))
        self.assertFalse(is_linear_usdt_perpetual_available_at(closed, 3000))
        self.assertFalse(is_linear_usdt_perpetual_available_at(row("NEWUSDT", "PreLaunch"), 2000))
        self.assertFalse(is_linear_usdt_perpetual_available_at(row("PENDUSDT", "PendingOpen"), 2000))
        self.assertFalse(is_linear_usdt_perpetual_available_at(
            row("BTCUSDC", "Trading", quote="USDC", settle="USDC"), 2000))
        self.assertFalse(is_linear_usdt_perpetual_available_at(
            row("BTCUSDT-30DEC", "Trading", contract="LinearFutures", delivery="3000"), 2000))

    def test_snapshot_requires_complete_status_counts(self):
        rows = [row("BTCUSDT", "Trading")]
        counts = {status: int(status == "Trading") for status in CAPTURED_STATUSES}
        snapshot = build_universe_snapshot(rows, counts, "2026-11-03T00:00:00Z")
        self.assertEqual(snapshot["count"], 1)
        self.assertEqual(snapshot["status_counts"]["Closed"], 0)
        with self.assertRaisesRegex(ValueError, "status counts"):
            build_universe_snapshot(rows, {status: 0 for status in CAPTURED_STATUSES})

    def test_snapshot_writer_round_trips(self):
        rows = [row("BTCUSDT", "Trading")]
        counts = {status: int(status == "Trading") for status in CAPTURED_STATUSES}
        snapshot = build_universe_snapshot(rows, counts, "2026-11-03T00:00:00Z")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "linear" / "snapshot.json"
            write_snapshot(snapshot, path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), snapshot)


if __name__ == "__main__":
    unittest.main(verbosity=2)
