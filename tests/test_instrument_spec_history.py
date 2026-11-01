"""Tests for historical as-of selection of Bybit instrument specs."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import json
import tempfile
import unittest
from pathlib import Path

from instrument_spec_history import InstrumentSpecHistory


def row(symbol="BTCUSDT", tick="0.1", status="Trading"):
    return {
        "symbol": symbol, "status": status, "category": "linear",
        "priceFilter": {"tickSize": tick},
        "lotSizeFilter": {
            "qtyStep": "0.001", "minOrderQty": "0.001",
            "maxOrderQty": "100", "maxMktOrderQty": "50",
            "minNotionalValue": "5",
        },
        "leverageFilter": {
            "minLeverage": "1", "maxLeverage": "50", "leverageStep": "0.01",
        },
    }


def write_snapshot(root, filename, fetched_at, instruments):
    payload = {
        "schema_version": 1, "category": "linear", "fetched_at": fetched_at,
        "count": len(instruments), "instruments": instruments,
    }
    (root / filename).write_text(json.dumps(payload), encoding="utf-8")


class InstrumentSpecHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_snapshot(self.root, "a.json", "2026-11-01T00:00:00Z", [row(tick="0.1")])
        write_snapshot(self.root, "b.json", "2026-11-02T00:00:00Z", [row(tick="0.01")])

    def tearDown(self):
        self.tmp.cleanup()

    def test_uses_latest_snapshot_not_later_than_as_of(self):
        history = InstrumentSpecHistory.from_directory(self.root)
        before = history.get_spec("BTCUSDT", 1_793_577_599_999)
        after = history.get_spec("BTCUSDT", 1_793_577_600_000)
        self.assertEqual(str(before.tick_size), "0.1")
        self.assertEqual(str(after.tick_size), "0.01")

    def test_never_uses_future_snapshot(self):
        history = InstrumentSpecHistory.from_directory(self.root)
        with self.assertRaisesRegex(ValueError, "no linear instrument snapshot"):
            history.get_spec("BTCUSDT", 1_793_491_199_999)

    def test_staleness_limit_is_enforced(self):
        history = InstrumentSpecHistory.from_directory(self.root)
        with self.assertRaisesRegex(ValueError, "stale"):
            history.get_spec("BTCUSDT", 1_793_577_600_000 + 10_000,
                             max_age_ms=1_000)

    def test_missing_symbol_in_latest_full_snapshot_fails_closed(self):
        write_snapshot(self.root, "c.json", "2026-11-03T00:00:00Z", [row("ETHUSDT")])
        history = InstrumentSpecHistory.from_directory(self.root)
        with self.assertRaisesRegex(ValueError, "absent from latest"):
            history.get_spec("BTCUSDT", 1_793_664_000_000)

    def test_non_trading_status_fails_closed(self):
        write_snapshot(self.root, "c.json", "2026-11-03T00:00:00Z",
                       [row(status="PreLaunch")])
        history = InstrumentSpecHistory.from_directory(self.root)
        with self.assertRaisesRegex(ValueError, "not Trading"):
            history.get_spec("BTCUSDT", 1_793_664_000_000)

    def test_duplicate_timestamp_and_wrong_category_rejected(self):
        write_snapshot(self.root, "duplicate.json", "2026-11-02T00:00:00Z", [row()])
        with self.assertRaisesRegex(ValueError, "duplicate instrument snapshot timestamps"):
            InstrumentSpecHistory.from_directory(self.root)
        (self.root / "duplicate.json").unlink()
        payload = json.loads((self.root / "a.json").read_text())
        payload["category"] = "spot"
        (self.root / "a.json").write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, "expected category"):
            InstrumentSpecHistory.from_directory(self.root)

    def test_snapshot_count_must_match_rows(self):
        payload = json.loads((self.root / "a.json").read_text())
        payload["count"] = 999
        (self.root / "a.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            InstrumentSpecHistory.from_directory(self.root)

    def test_missing_or_malformed_required_snapshot_fields_rejected(self):
        (self.root / "b.json").write_text("not-json", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "cannot read"):
            InstrumentSpecHistory.from_directory(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
