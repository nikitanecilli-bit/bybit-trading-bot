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
    fetch_status, is_linear_usdt_perpetual_within_lifecycle_at, validate_instrument_row,
    _timestamp_ms,
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

    def test_symbol_must_be_a_non_empty_string(self):
        for symbol in (None, 123, True, "", "   "):
            with self.subTest(symbol=symbol):
                malformed = row("BTCUSDT", "Trading")
                malformed["symbol"] = symbol
                with self.assertRaisesRegex(ValueError, "invalid symbol"):
                    validate_instrument_row(malformed, None)

    def test_status_mismatch_and_invalid_timestamps_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "status mismatch"):
            validate_instrument_row(row("BTCUSDT", "Closed"), "Settling")
        with self.assertRaisesRegex(ValueError, "invalid launchTime"):
            validate_instrument_row(row("BTCUSDT", "Trading", launch="0"), None)
        with self.assertRaisesRegex(ValueError, "precedes launchTime"):
            validate_instrument_row(row("BTCUSDT", "Closed", launch="2000", delivery="1000"), "Closed")
        missing_delivery = row("BTCUSDT", "Trading")
        missing_delivery.pop("deliveryTime")
        with self.assertRaisesRegex(ValueError, "invalid deliveryTime"):
            validate_instrument_row(missing_delivery, None)

    def test_lifecycle_zero_delivery_is_open_ended_only_for_trading_perpetual(self):
        perpetual = row("BTCUSDT", "Trading", delivery="0")
        self.assertTrue(is_linear_usdt_perpetual_within_lifecycle_at(perpetual, 10_000))
        self.assertFalse(is_linear_usdt_perpetual_within_lifecycle_at(
            row("OLDUSDT", "Closed", delivery="0"), 10_000
        ))
        self.assertFalse(is_linear_usdt_perpetual_within_lifecycle_at(
            row("OLDUSDT", "Settling", delivery="0"), 10_000
        ))
        self.assertFalse(is_linear_usdt_perpetual_within_lifecycle_at(
            row("OLDUSDT", "Delivering", delivery="0"), 10_000
        ))

    def test_lifecycle_timestamp_parser_rejects_implicit_coercions(self):
        for value in (True, False, 1000.0, " 1000", "1000 ", "+1000", "-1", "1.5"):
            with self.subTest(value=value):
                malformed = row("BTCUSDT", "Trading")
                malformed["launchTime"] = value
                with self.assertRaisesRegex(ValueError, "invalid launchTime"):
                    validate_instrument_row(malformed, None)
        for value in (True, 1000.0, " 0", "+0", "-0", "0.0"):
            with self.subTest(delivery=value):
                malformed = row("BTCUSDT", "Trading")
                malformed["deliveryTime"] = value
                with self.assertRaisesRegex(ValueError, "invalid deliveryTime"):
                    validate_instrument_row(malformed, None)

    def test_timestamp_parser_zero_policy_and_integer_types(self):
        self.assertEqual(_timestamp_ms("0", "deliveryTime", allow_zero=True), 0)
        self.assertEqual(_timestamp_ms(1234, "launchTime", allow_zero=False), 1234)
        for value in (0, True, 1234.0, "001  ", "+1234", "-1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "invalid timestamp"):
                    _timestamp_ms(value, "timestamp", allow_zero=False)

    def test_lifecycle_timestamp_integer_values_are_accepted(self):
        instrument = row("BTCUSDT", "Trading")
        instrument["launchTime"] = 1000
        instrument["deliveryTime"] = 0
        validated = validate_instrument_row(instrument, None)
        self.assertEqual(validated["launchTime"], 1000)
        self.assertTrue(is_linear_usdt_perpetual_within_lifecycle_at(validated, 1000))

    def test_point_in_time_lifecycle_respects_launch_and_delivery_boundaries(self):
        closed = row("BTCUSDT", "Closed", launch="1000", delivery="3000")
        self.assertFalse(is_linear_usdt_perpetual_within_lifecycle_at(closed, 999))
        self.assertTrue(is_linear_usdt_perpetual_within_lifecycle_at(closed, 1000))
        self.assertTrue(is_linear_usdt_perpetual_within_lifecycle_at(closed, 2999))
        self.assertFalse(is_linear_usdt_perpetual_within_lifecycle_at(closed, 3000))
        self.assertFalse(is_linear_usdt_perpetual_within_lifecycle_at(row("NEWUSDT", "PreLaunch"), 2000))
        self.assertFalse(is_linear_usdt_perpetual_within_lifecycle_at(row("PENDUSDT", "PendingOpen"), 2000))
        self.assertFalse(is_linear_usdt_perpetual_within_lifecycle_at(row("DELISTEDUSDT", "Closed", delivery="0"), 2000))
        self.assertFalse(is_linear_usdt_perpetual_within_lifecycle_at(
            row("BTCUSDC", "Trading", quote="USDC", settle="USDC"), 2000))
        self.assertFalse(is_linear_usdt_perpetual_within_lifecycle_at(
            row("BTCUSDT-30DEC", "Trading", contract="LinearFutures", delivery="3000"), 2000))

    def test_snapshot_requires_complete_status_counts(self):
        rows = [row("BTCUSDT", "Trading")]
        counts = {status: int(status == "Trading") for status in CAPTURED_STATUSES}
        snapshot = build_universe_snapshot(rows, counts, "2026-11-03T00:00:00Z")
        self.assertEqual(snapshot["count"], 1)
        self.assertEqual(snapshot["status_counts"]["Closed"], 0)
        with self.assertRaisesRegex(ValueError, "status counts"):
            build_universe_snapshot(rows, {status: 0 for status in CAPTURED_STATUSES})

    def test_snapshot_rejects_negative_or_boolean_status_counts(self):
        rows = [row("BTCUSDT", "Trading")]
        counts = {status: int(status == "Trading") for status in CAPTURED_STATUSES}
        counts["Trading"] = True
        with self.assertRaisesRegex(ValueError, "status counts"):
            build_universe_snapshot(rows, counts)
        counts["Trading"] = -1
        counts["PendingOpen"] = 2
        with self.assertRaisesRegex(ValueError, "status counts"):
            build_universe_snapshot(rows, counts)

    def test_snapshot_rejects_counts_that_do_not_match_statuses(self):
        rows = [row("BTCUSDT", "Trading")]
        counts = {status: 0 for status in CAPTURED_STATUSES}
        counts["PendingOpen"] = 1
        with self.assertRaisesRegex(ValueError, "status counts"):
            build_universe_snapshot(rows, counts)

    def test_snapshot_rejects_invalid_timestamps(self):
        rows = [row("BTCUSDT", "Trading")]
        counts = {status: int(status == "Trading") for status in CAPTURED_STATUSES}
        for timestamp in ("not-a-time", "2026-11-03T00:00:00", "2026-11-03T00:00:00.000500Z"):
            with self.subTest(timestamp=timestamp):
                with self.assertRaisesRegex(ValueError, "fetched_at"):
                    build_universe_snapshot(rows, counts, timestamp)

    def test_collection_interval_is_recorded_and_ordered(self):
        rows = [row("BTCUSDT", "Trading")]
        counts = {status: int(status == "Trading") for status in CAPTURED_STATUSES}
        snapshot = build_universe_snapshot(
            rows, counts, "2026-11-03T00:00:02Z", "2026-11-03T00:00:01Z"
        )
        self.assertEqual(snapshot["collection_started_at"], "2026-11-03T00:00:01.000Z")
        with self.assertRaisesRegex(ValueError, "cannot be after"):
            build_universe_snapshot(
                rows, counts, "2026-11-03T00:00:01Z", "2026-11-03T00:00:02Z"
            )


    def test_universe_snapshot_records_page_observations(self):
        from scripts.snapshot_bybit_instruments import build_page_observation
        rows = [row("BTCUSDT", "Trading")]
        counts = {status: int(status == "Trading") for status in CAPTURED_STATUSES}
        observations = [build_page_observation(
            "default", 1, "2026-11-03T00:00:00.000Z",
            "2026-11-03T00:00:00.250Z", rows, None,
        )]
        snapshot = build_universe_snapshot(
            rows, counts, "2026-11-03T00:00:01.000Z",
            "2026-11-03T00:00:00.000Z", observations,
        )
        self.assertEqual(snapshot["page_observations"], observations)

    def test_universe_snapshot_rejects_page_observation_after_fetched_at(self):
        from scripts.snapshot_bybit_instruments import build_page_observation
        rows = [row("BTCUSDT", "Trading")]
        counts = {status: int(status == "Trading") for status in CAPTURED_STATUSES}
        observations = [build_page_observation(
            "default", 1, "2026-11-03T00:00:02.000Z",
            "2026-11-03T00:00:03.000Z", rows, None,
        )]
        with self.assertRaisesRegex(ValueError, "after fetched_at"):
            build_universe_snapshot(
                rows, counts, "2026-11-03T00:00:02.500Z",
                "2026-11-03T00:00:00.000Z", observations,
            )

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
