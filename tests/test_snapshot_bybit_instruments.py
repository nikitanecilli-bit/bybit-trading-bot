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
    build_page_observation, build_snapshot, fetch_all_instruments, write_snapshot,
)


class SnapshotCollectorTests(unittest.TestCase):
    def test_collects_all_pages_and_sorts_symbols(self):
        pages = {
            ("PreLaunch", None): ([{"symbol": "BIOUSDT", "status": "PreLaunch"}], None),
            ("Trading", None): ([{"symbol": "ETHUSDT", "status": "Trading"},
                                 {"symbol": "BTCUSDT", "status": "Trading"}], "cursor-2"),
            ("Trading", "cursor-2"): ([{"symbol": "SOLUSDT", "status": "Trading"}], None),
        }
        seen = []
        def fetch(cursor, status):
            seen.append((status, cursor))
            return pages.get((status, cursor), ([], None))
        rows = fetch_all_instruments("linear", fetch)
        self.assertEqual(seen, [
            ("PreLaunch", None), ("Trading", None), ("Trading", "cursor-2"),
            ("Settling", None), ("Delivering", None), ("Closed", None),
        ])
        self.assertEqual([row["symbol"] for row in rows],
                         ["BIOUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"])

    def test_identical_duplicate_from_overlapping_pages_is_deduplicated(self):
        row = {"symbol": "BTCUSDT", "status": "Trading"}
        pages = {
            None: ([row], "next"),
            "next": ([dict(row)], None),
        }
        rows = fetch_all_instruments(
            "linear", lambda cursor, status: pages[cursor] if status == "Trading" else ([], None)
        )
        self.assertEqual(rows, [row])

    def test_conflicting_duplicate_is_rejected(self):
        pages = {
            ("PreLaunch", None): ([{"symbol": "BTCUSDT", "status": "PreLaunch"}], None),
            ("Trading", None): ([{"symbol": "BTCUSDT", "status": "Trading"}], None),
        }
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            fetch_all_instruments("linear", lambda cursor, status: pages.get((status, cursor), ([], None)))

    def test_repeated_cursor_is_rejected(self):
        def fetch(cursor, status):
            return ([{"symbol": "BTCUSDT", "status": status}], "loop")
        with self.assertRaisesRegex(RuntimeError, "cursor repeated"):
            fetch_all_instruments("linear", fetch)

    def test_empty_universe_and_missing_or_malformed_symbol_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "empty instrument"):
            fetch_all_instruments("linear", lambda cursor, status: ([], None))
        for symbol in (None, 123, True, "", "   "):
            with self.subTest(symbol=symbol):
                row = {} if symbol is None else {"symbol": symbol}
                with self.assertRaisesRegex(ValueError, "missing or has invalid symbol"):
                    fetch_all_instruments("linear", lambda cursor, status: ([row], None))

    def test_snapshot_builder_rejects_non_string_symbols(self):
        for symbol in (123, True, "", "   "):
            with self.subTest(symbol=symbol):
                with self.assertRaisesRegex(ValueError, "string symbols"):
                    build_snapshot([{"symbol": symbol}], "linear")

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
                    "linear", lambda cursor, status: ([{"symbol": "BTCUSDT", "status": status}], "next")
                )
        finally:
            collector.MAX_PAGES = previous

    def test_pagination_cursor_must_be_string(self):
        with self.assertRaisesRegex(ValueError, "nextPageCursor must be a string"):
            collector._validate_next_cursor(123)
        self.assertIsNone(collector._validate_next_cursor(""))

    def test_page_observation_records_request_window_and_symbols(self):
        observation = build_page_observation(
            "Trading", 1, "2026-11-02T00:00:00.000Z",
            "2026-11-02T00:00:00.250Z",
            [{"symbol": "ethusdt"}, {"symbol": "BTCUSDT"}], "cursor",
        )
        self.assertEqual(observation["status_filter"], "Trading")
        self.assertEqual(observation["page_index"], 1)
        self.assertEqual(observation["row_count"], 2)
        self.assertEqual(observation["symbols"], ["BTCUSDT", "ETHUSDT"])
        self.assertTrue(observation["has_next_page"])

    def test_page_observation_rejects_bad_window_and_duplicate_symbols(self):
        with self.assertRaisesRegex(ValueError, "cannot be after"):
            build_page_observation(
                "Trading", 1, "2026-11-02T00:00:01.000Z",
                "2026-11-02T00:00:00.000Z", [{"symbol": "BTCUSDT"}], None,
            )
        with self.assertRaisesRegex(ValueError, "duplicate symbols"):
            build_page_observation(
                "Trading", 1, "2026-11-02T00:00:00.000Z",
                "2026-11-02T00:00:00.000Z",
                [{"symbol": "BTCUSDT"}, {"symbol": "BTCUSDT"}], None,
            )

    def test_snapshot_round_trips_validated_page_observations(self):
        observations = []
        for index, status in enumerate(collector.INSTRUMENT_STATUS_FILTERS["linear"]):
            rows = [{"symbol": "BTCUSDT"}] if status == "Trading" else []
            start_ms = index * 10
            started = f"2026-11-02T00:00:00.{start_ms:03d}Z"
            completed = f"2026-11-02T00:00:00.{start_ms + 1:03d}Z"
            observations.append(build_page_observation(
                status, 1, started, completed, rows, None,
            ))
        snapshot = build_snapshot(
            [{"symbol": "BTCUSDT"}], "linear",
            "2026-11-02T00:00:01.000Z", "2026-11-02T00:00:00.000Z",
            observations,
        )
        self.assertEqual(snapshot["page_observations"], observations)

    def test_snapshot_rejects_non_chronological_page_observations(self):
        observations = [
            build_page_observation("Trading", 1, "2026-11-02T00:00:01.000Z",
                                   "2026-11-02T00:00:02.000Z",
                                   [{"symbol": "BTCUSDT"}], None),
            build_page_observation("Closed", 1, "2026-11-02T00:00:00.000Z",
                                   "2026-11-02T00:00:00.500Z",
                                   [{"symbol": "OLDUSDT"}], None),
        ]
        with self.assertRaisesRegex(ValueError, "not chronological"):
            build_snapshot(
                [{"symbol": "BTCUSDT"}, {"symbol": "OLDUSDT"}], "linear",
                "2026-11-02T00:00:03.000Z", page_observations=observations,
            )


    def test_page_continuation_flags_must_match_page_sequence(self):
        observations = [
            build_page_observation("Trading", 1, "2026-11-02T00:00:00.000Z",
                                   "2026-11-02T00:00:00.100Z",
                                   [{"symbol": "BTCUSDT"}], None),
            build_page_observation("Trading", 2, "2026-11-02T00:00:00.200Z",
                                   "2026-11-02T00:00:00.300Z",
                                   [{"symbol": "ETHUSDT"}], None),
        ]
        with self.assertRaisesRegex(ValueError, "continuation flags"):
            collector.validate_page_observations(observations)

    def test_snapshot_requires_all_expected_status_filters(self):
        observation = build_page_observation(
            "Trading", 1, "2026-11-02T00:00:00.000Z",
            "2026-11-02T00:00:00.100Z", [{"symbol": "BTCUSDT"}], None,
        )
        with self.assertRaisesRegex(ValueError, "expected status filters"):
            build_snapshot(
                [{"symbol": "BTCUSDT"}], "linear",
                "2026-11-02T00:00:01.000Z", page_observations=[observation],
            )

    def test_snapshot_has_provenance_and_exact_timestamp(self):
        snapshot = build_snapshot(
            [{"symbol": "BTCUSDT"}], "linear", "2026-11-02T00:00:00.000Z"
        )
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["count"], 1)
        self.assertEqual(snapshot["fetched_at"], "2026-11-02T00:00:00.000Z")
        self.assertIn("instruments-info", snapshot["source"])

    def test_default_snapshot_timestamp_has_millisecond_precision(self):
        snapshot = build_snapshot([{"symbol": "BTCUSDT"}], "linear")
        self.assertRegex(snapshot["fetched_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

    def test_snapshot_timestamp_requires_timezone_and_millisecond_precision(self):
        for value in ("2026-11-02T00:00:00", "2026-11-02T00:00:00.000500Z"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "timezone|millisecond precision"):
                    build_snapshot([{"symbol": "BTCUSDT"}], "linear", value)

    def test_default_snapshot_round_trips_through_as_of_history_loader(self):
        from instrument_spec_history import InstrumentSpecHistory
        instrument = {
            "symbol": "BTCUSDT", "status": "Trading", "category": "linear",
            "priceFilter": {"minPrice": "0.01", "maxPrice": "1000000", "tickSize": "0.1"},
            "lotSizeFilter": {
                "qtyStep": "0.001", "minOrderQty": "0.001", "maxOrderQty": "100",
                "maxMktOrderQty": "50", "minNotionalValue": "5",
            },
            "leverageFilter": {
                "minLeverage": "1", "maxLeverage": "50", "leverageStep": "0.01",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            snapshot = build_snapshot([instrument], "linear")
            write_snapshot(snapshot, Path(directory) / "snapshot.json")
            history = InstrumentSpecHistory.from_directory(directory)
            spec = history.get_spec("BTCUSDT", history.snapshots[0].fetched_at_ms)
            self.assertEqual(spec.symbol, "BTCUSDT")

    def test_collection_interval_is_recorded_and_ordered(self):
        snapshot = build_snapshot(
            [{"symbol": "BTCUSDT"}], "linear",
            "2026-11-02T00:00:02.000Z", "2026-11-02T00:00:01.000Z",
        )
        self.assertEqual(snapshot["collection_started_at"], "2026-11-02T00:00:01.000Z")
        with self.assertRaisesRegex(ValueError, "cannot be after"):
            build_snapshot(
                [{"symbol": "BTCUSDT"}], "linear",
                "2026-11-02T00:00:01.000Z", "2026-11-02T00:00:02.000Z",
            )

    def test_snapshot_timestamp_normalizes_offset_to_utc(self):
        snapshot = build_snapshot(
            [{"symbol": "BTCUSDT"}], "linear", "2026-11-02T03:00:00.123+03:00"
        )
        self.assertEqual(snapshot["fetched_at"], "2026-11-02T00:00:00.123Z")

    def test_snapshot_rejects_duplicate_symbols(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_snapshot([{"symbol": "BTCUSDT"}, {"symbol": "BTCUSDT"}], "linear")

    def test_atomic_writer_round_trips_json(self):
        snapshot = build_snapshot([{"symbol": "BTCUSDT"}], "linear",
                                  "2026-11-02T00:00:00.000Z")
        with tempfile.TemporaryDirectory() as directory:
            path = write_snapshot(snapshot, Path(directory) / "linear" / "test.json")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), snapshot)


if __name__ == "__main__":
    unittest.main(verbosity=2)
