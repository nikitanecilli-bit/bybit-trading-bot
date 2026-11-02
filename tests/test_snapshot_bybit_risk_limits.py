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
            None: ([row("BTCUSDT"), row("BTCUSDT", 2, "500000")], "next"),
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
            return [row()], "same"
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

    def test_snapshot_is_timestamped_and_counts_symbols_and_tiers(self):
        snapshot = build_snapshot(
            [row("BTCUSDT"), row("BTCUSDT", 2, "500000"), row("ETHUSDT")],
            "linear", "2026-11-02T00:00:00Z",
        )
        self.assertEqual(snapshot["symbol_count"], 2)
        self.assertEqual(snapshot["tier_count"], 3)
        self.assertEqual(snapshot["fetched_at"], "2026-11-02T00:00:00Z")

    def test_snapshot_rejects_duplicate_tier_keys(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            build_snapshot([row(), row()], "linear")

    def test_output_is_atomically_written(self):
        snapshot = build_snapshot([row()], "linear", "2026-11-02T00:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            path = write_snapshot(snapshot, Path(tmp) / "nested" / "snapshot.json")
            self.assertTrue(path.exists())
            self.assertIn('"tier_count": 1', path.read_text(encoding="utf-8"))

    def test_only_official_https_hosts_are_allowed(self):
        _validate_base_url("https://api.bybit.com")
        for url in ("http://api.bybit.com", "https://example.com",
                    "https://" + "user" + ":" + "pass" + "@api.bybit.com", "https://api.bybit.com:444"):
            with self.assertRaises(ValueError):
                _validate_base_url(url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
