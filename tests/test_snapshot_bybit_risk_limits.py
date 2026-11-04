"""Offline tests for dated Bybit risk-limit tier snapshots."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.snapshot_bybit_risk_limits import (
    build_snapshot, fetch_all_tiers, validate_tier, write_snapshot, _validate_base_url,
)

def row(symbol="BTCUSDT", tier_id=1, risk="200000", mm="0.005", im="0.01",
        lowest=1, leverage="100", deduction="0"):
    return {
        "id": tier_id, "symbol": symbol, "riskLimitValue": risk,
        "maintenanceMargin": mm, "initialMargin": im,
        "isLowestRisk": lowest, "maxLeverage": leverage, "mmDeduction": deduction,
    }


class RiskLimitSnapshotTests(unittest.TestCase):
    def test_paginates_all_symbols_and_tiers(self):
        pages = {
            None: ([row("BTCUSDT"), row("BTCUSDT", 2, "500000", mm="0.01", im="0.02", lowest=0, leverage="50", deduction="1000")], "next"),
            "next": ([row("ETHUSDT"), row("SOLUSDT")], None),
        }
        seen = []
        def fetch(cursor):
            seen.append(cursor)
            return pages[cursor]
        rows = fetch_all_tiers("linear", fetch)
        self.assertEqual(seen, [None, "next"])
        self.assertEqual(len(rows), 4)
        self.assertEqual({x["symbol"] for x in rows}, {"BTCUSDT", "ETHUSDT", "SOLUSDT"})

    def test_repeated_cursor_fails_closed(self):
        def fetch(cursor):
            return ([row()], "same") if cursor is None else ([], "same")
        with self.assertRaisesRegex(RuntimeError, "cursor repeated"):
            fetch_all_tiers("linear", fetch)

    def test_duplicate_tier_fails_closed(self):
        def fetch(cursor):
            return [row(), row()], None
        with self.assertRaisesRegex(ValueError, "duplicate risk tier"):
            fetch_all_tiers("linear", fetch)

    def test_empty_universe_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "empty"):
            fetch_all_tiers("linear", lambda cursor: ([], None))

    def test_invalid_numeric_and_boolean_fields_are_rejected(self):
        bad = row()
        bad["maintenanceMargin"] = "NaN"
        with self.assertRaisesRegex(ValueError, "non-finite"):
            validate_tier(bad)
        bad = row()
        bad["isLowestRisk"] = True
        with self.assertRaisesRegex(ValueError, "integer 0 or 1"):
            validate_tier(bad)

    def test_rejects_float_is_lowest_risk(self):
        bad = row()
        bad["isLowestRisk"] = 1.0
        with self.assertRaisesRegex(ValueError, "isLowestRisk must be integer 0 or 1"):
            validate_tier(bad)

    def test_snapshot_is_timestamped_and_counts_symbols_and_tiers(self):
        snapshot = build_snapshot(
            [row("BTCUSDT"), row("BTCUSDT", 2, "500000", mm="0.01", im="0.02", lowest=0, leverage="50", deduction="1000"), row("ETHUSDT")],
            "linear", "2026-11-02T00:00:00.000Z",
        )
        self.assertEqual(snapshot["symbol_count"], 2)
        self.assertEqual(snapshot["tier_count"], 3)
        self.assertEqual(snapshot["fetched_at"], "2026-11-02T00:00:00.000Z")


    def test_snapshot_records_validated_page_timing_and_collection_bounds(self):
        observations = [
            {
                "page_index": 1,
                "request_started_at": "2026-11-02T00:00:00.000Z",
                "request_completed_at": "2026-11-02T00:00:00.120Z",
                "tier_count": 2, "symbol_count": 1,
                "symbols": ["BTCUSDT"], "has_next_page": True,
            },
            {
                "page_index": 2,
                "request_started_at": "2026-11-02T00:00:00.220Z",
                "request_completed_at": "2026-11-02T00:00:00.350Z",
                "tier_count": 1, "symbol_count": 1,
                "symbols": ["ETHUSDT"], "has_next_page": False,
            },
        ]
        snapshot = build_snapshot(
            [row("BTCUSDT"), row("BTCUSDT", 2, "500000", mm="0.01",
             im="0.02", lowest=0, leverage="50", deduction="1000"),
             row("ETHUSDT")],
            "linear", "2026-11-02T00:00:01.000Z",
            collection_started_at="2026-11-02T00:00:00.000Z",
            page_observations=observations,
        )
        self.assertEqual(snapshot["page_observations"], observations)
        self.assertEqual(snapshot["collection_started_at"], "2026-11-02T00:00:00.000Z")

    def test_page_observations_reject_missing_continuation_and_symbol_mismatch(self):
        observation = {
            "page_index": 1,
            "request_started_at": "2026-11-02T00:00:00.000Z",
            "request_completed_at": "2026-11-02T00:00:00.100Z",
            "tier_count": 1, "symbol_count": 1,
            "symbols": ["BTCUSDT"], "has_next_page": True,
        }
        with self.assertRaisesRegex(ValueError, "last risk page"):
            build_snapshot(
                [row()], "linear", "2026-11-02T00:00:01.000Z",
                collection_started_at="2026-11-02T00:00:00.000Z",
                page_observations=[observation],
            )
        observation["has_next_page"] = False
        observation["symbols"] = ["ETHUSDT"]
        with self.assertRaisesRegex(ValueError, "do not match snapshot"):
            build_snapshot(
                [row()], "linear", "2026-11-02T00:00:01.000Z",
                collection_started_at="2026-11-02T00:00:00.000Z",
                page_observations=[observation],
            )


    def test_page_tier_counts_must_match_snapshot_rows(self):
        observation = {
            "page_index": 1,
            "request_started_at": "2026-11-02T00:00:00.000Z",
            "request_completed_at": "2026-11-02T00:00:00.100Z",
            "tier_count": 2, "symbol_count": 1,
            "symbols": ["BTCUSDT"], "has_next_page": False,
        }
        with self.assertRaisesRegex(ValueError, "tier counts do not match"):
            build_snapshot(
                [row()], "linear", "2026-11-02T00:00:01.000Z",
                collection_started_at="2026-11-02T00:00:00.000Z",
                page_observations=[observation],
            )

    def test_default_snapshot_timestamp_has_millisecond_precision(self):
        snapshot = build_snapshot([row()], "linear")
        self.assertRegex(snapshot["fetched_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

    def test_snapshot_timestamp_requires_timezone_and_millisecond_precision(self):
        for value in ("2026-11-02T00:00:00", "2026-11-02T00:00:00.000500Z"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "timezone|millisecond precision"):
                    build_snapshot([row()], "linear", value)

    def test_default_snapshot_round_trips_through_as_of_history_loader(self):
        from bybit_risk_tiers import RiskTierHistory
        with tempfile.TemporaryDirectory() as directory:
            snapshot = build_snapshot([row()], "linear")
            write_snapshot(snapshot, Path(directory) / "snapshot.json")
            history = RiskTierHistory.from_directory(directory)
            tiers = history.get_tiers("BTCUSDT", history.snapshots[0].fetched_at_ms)
            self.assertEqual([tier.tier_id for tier in tiers], [1])

    def test_snapshot_timestamp_normalizes_offset_to_utc(self):
        snapshot = build_snapshot(
            [row()], "linear", "2026-11-02T03:00:00.123+03:00"
        )
        self.assertEqual(snapshot["fetched_at"], "2026-11-02T00:00:00.123Z")

    def test_tier_group_checks_monotonic_rates_and_mm_deduction_recurrence(self):
        valid = [
            row("BTCUSDT", 1, "100000", mm="0.005", im="0.01", lowest=1, leverage="100", deduction="0"),
            row("BTCUSDT", 2, "200000", mm="0.01", im="0.02", lowest=0, leverage="50", deduction="500"),
        ]
        snapshot = build_snapshot(valid, "linear", "2026-11-02T00:00:00.000Z")
        self.assertEqual(snapshot["tier_count"], 2)

        broken = [dict(item) for item in valid]
        broken[1]["mmDeduction"] = "499"
        with self.assertRaisesRegex(ValueError, "mmDeduction"):
            build_snapshot(broken, "linear", "2026-11-02T00:00:00.000Z")

    def test_tier_group_rejects_increasing_max_leverage(self):
        invalid = [
            row("BTCUSDT", 1, "100000", lowest=1, leverage="50"),
            row("BTCUSDT", 2, "200000", mm="0.01", im="0.02", lowest=0, leverage="60", deduction="500"),
        ]
        with self.assertRaisesRegex(ValueError, "maxLeverage"):
            build_snapshot(invalid, "linear", "2026-11-02T00:00:00.000Z")

    def test_tier_group_requires_exactly_one_lowest_tier(self):
        invalid = [
            row("BTCUSDT", 1, "100000", lowest=1),
            row("BTCUSDT", 2, "200000", mm="0.01", im="0.02", lowest=1, deduction="500"),
        ]
        with self.assertRaisesRegex(ValueError, "isLowestRisk"):
            build_snapshot(invalid, "linear", "2026-11-02T00:00:00.000Z")

    def test_snapshot_rejects_duplicate_tier_keys(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            build_snapshot([row(), row()], "linear")

    def test_output_is_atomically_written(self):
        snapshot = build_snapshot([row()], "linear", "2026-11-02T00:00:00.000Z")
        with tempfile.TemporaryDirectory() as tmp:
            path = write_snapshot(snapshot, Path(tmp) / "nested" / "snapshot.json")
            self.assertTrue(path.exists())
            self.assertIn('"tier_count": 1', path.read_text(encoding="utf-8"))

    def test_only_official_https_hosts_are_allowed(self):
        _validate_base_url("https://api.bybit.com")
        _validate_base_url("https://api.bybit.tr")
        _validate_base_url("https://api.bybit.kz")
        for url in ("http://api.bybit.com", "https://example.com",
                    "https://" + "user" + ":" + "pass" + "@api.bybit.com",
                    "https://api.bybit.com:444", "https://api.bybit.nl",
                    "https://api.bybit-tr.com"):
            with self.assertRaises(ValueError):
                _validate_base_url(url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
