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
        "contractType": "LinearPerpetual",
        "baseCoin": symbol.removesuffix("USDT"), "quoteCoin": "USDT", "settleCoin": "USDT",
        "priceFilter": {"minPrice": "0.01", "maxPrice": "1000000", "tickSize": tick},
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
        "schema_version": 1, "source": "Bybit V5 GET /v5/market/instruments-info",
        "category": "linear", "fetched_at": fetched_at,
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

    def test_as_of_inside_collection_window_uses_previous_completed_snapshot(self):
        payload = json.loads((self.root / "b.json").read_text())
        payload["collection_started_at"] = "2026-11-01T23:59:59.000Z"
        (self.root / "b.json").write_text(json.dumps(payload), encoding="utf-8")
        history = InstrumentSpecHistory.from_directory(self.root)
        # The newer snapshot was not complete at this as-of instant.
        spec = history.get_spec("BTCUSDT", 1_793_577_599_500)
        self.assertEqual(str(spec.tick_size), "0.1")

    def test_all_exchange_constraints_are_selected_from_the_as_of_snapshot(self):
        changed = row(tick="0.01")
        changed["priceFilter"]["minPrice"] = "0.02"
        changed["lotSizeFilter"]["qtyStep"] = "0.01"
        changed["lotSizeFilter"]["minOrderQty"] = "0.02"
        changed["lotSizeFilter"]["minNotionalValue"] = "10"
        changed["leverageFilter"]["maxLeverage"] = "25"
        changed["leverageFilter"]["leverageStep"] = "0.1"
        write_snapshot(self.root, "b.json", "2026-11-02T00:00:00Z", [changed])

        history = InstrumentSpecHistory.from_directory(self.root)
        before = history.get_spec("BTCUSDT", 1_793_577_599_999)
        after = history.get_spec("BTCUSDT", 1_793_577_600_000)

        self.assertEqual(str(before.tick_size), "0.1")
        self.assertEqual(str(before.qty_step), "0.001")
        self.assertEqual(str(before.min_order_qty), "0.001")
        self.assertEqual(str(before.min_notional_value), "5")
        self.assertEqual(str(before.max_leverage), "50")
        self.assertEqual(str(before.leverage_step), "0.01")

        self.assertEqual(str(after.tick_size), "0.01")
        self.assertEqual(str(after.min_price), "0.02")
        self.assertEqual(str(after.qty_step), "0.01")
        self.assertEqual(str(after.min_order_qty), "0.02")
        self.assertEqual(str(after.min_notional_value), "10")
        self.assertEqual(str(after.max_leverage), "25")
        self.assertEqual(str(after.leverage_step), "0.1")

    def test_uses_envelope_category_when_bybit_rows_omit_category(self):
        for filename in ("a.json", "b.json"):
            payload = json.loads((self.root / filename).read_text())
            for instrument in payload["instruments"]:
                instrument.pop("category")
            (self.root / filename).write_text(json.dumps(payload), encoding="utf-8")
        history = InstrumentSpecHistory.from_directory(self.root)
        spec = history.get_spec("BTCUSDT", 1_793_577_600_000)
        self.assertEqual(spec.category, "linear")
        self.assertEqual(str(spec.tick_size), "0.01")

    def test_row_category_mismatch_is_not_overridden_by_envelope(self):
        payload = json.loads((self.root / "a.json").read_text())
        payload["instruments"][0]["category"] = "spot"
        (self.root / "a.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "only supports linear"):
            InstrumentSpecHistory.from_directory(self.root)

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

    def test_later_status_is_not_applied_retroactively_to_earlier_as_of(self):
        write_snapshot(self.root, "c.json", "2026-11-03T00:00:00Z",
                       [row(status="Closed")])
        history = InstrumentSpecHistory.from_directory(self.root)

        # Immediately before the Closed snapshot, the latest observed status
        # is still Trading; at the snapshot timestamp, Closed must fail closed.
        earlier = history.get_spec("BTCUSDT", 1_793_663_999_999)
        self.assertEqual(earlier.status, "Trading")
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

    def test_as_of_timestamp_must_be_strict_integer_milliseconds(self):
        history = InstrumentSpecHistory.from_directory(self.root)
        for value in (1_793_577_600_000.5, True, "1793577600000"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "as_of_ts must be an integer"):
                    history.get_spec("BTCUSDT", value)

    def test_collection_interval_must_be_valid_and_not_after_completion(self):
        payload = json.loads((self.root / "a.json").read_text())
        payload["collection_started_at"] = "2026-11-01T00:00:00Z"
        (self.root / "a.json").write_text(json.dumps(payload), encoding="utf-8")
        history = InstrumentSpecHistory.from_directory(self.root)
        self.assertIsNotNone(history.snapshots[0].collection_started_at_ms)

        payload["collection_started_at"] = "2026-11-02T00:00:00Z"
        (self.root / "a.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "cannot be after"):
            InstrumentSpecHistory.from_directory(self.root)

        payload["collection_started_at"] = 123
        (self.root / "a.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must be an ISO-8601 string"):
            InstrumentSpecHistory.from_directory(self.root)

    def test_snapshot_timestamp_rejects_submillisecond_precision(self):
        payload = json.loads((self.root / "a.json").read_text())
        payload["fetched_at"] = "2026-11-01T00:00:00.000500Z"
        (self.root / "a.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "millisecond precision"):
            InstrumentSpecHistory.from_directory(self.root)

    def test_snapshot_count_must_match_rows(self):
        payload = json.loads((self.root / "a.json").read_text())
        payload["count"] = 999
        (self.root / "a.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            InstrumentSpecHistory.from_directory(self.root)

    def test_snapshot_schema_version_and_count_require_integer_types(self):
        payload = json.loads((self.root / "a.json").read_text())
        payload["schema_version"] = True
        (self.root / "a.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported instrument snapshot schema"):
            InstrumentSpecHistory.from_directory(self.root)

        payload["schema_version"] = 1
        payload["count"] = True
        (self.root / "a.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            InstrumentSpecHistory.from_directory(self.root)


    def test_symbol_reuse_with_different_contract_identity_fails_closed(self):
        changed = row()
        changed["contractType"] = "LinearFutures"
        write_snapshot(self.root, "c.json", "2026-11-03T00:00:00Z", [changed])
        with self.assertRaisesRegex(ValueError, "identity changed while symbol was reused"):
            InstrumentSpecHistory.from_directory(self.root)


    def test_symbol_reuse_after_absence_from_intermediate_snapshot_fails(self):
        write_snapshot(self.root, "a.json", "2026-11-01T00:00:00Z", [row("BTCUSDT")])
        write_snapshot(self.root, "b.json", "2026-11-02T00:00:00Z", [row("ETHUSDT")])
        reused = row("BTCUSDT")
        reused["contractType"] = "LinearFutures"
        write_snapshot(self.root, "c.json", "2026-11-03T00:00:00Z", [reused])
        with self.assertRaisesRegex(ValueError, "identity changed while symbol was reused"):
            InstrumentSpecHistory.from_directory(self.root)

    def test_possible_symbol_rename_is_reported_but_never_merged(self):
        previous = row("BTCUSDT")
        renamed = row("XBTUSDT")
        renamed["baseCoin"] = "BTC"
        write_snapshot(self.root, "a.json", "2026-11-01T00:00:00Z", [previous])
        write_snapshot(self.root, "b.json", "2026-11-02T00:00:00Z", [renamed])
        history = InstrumentSpecHistory.from_directory(self.root)
        self.assertEqual(len(history.possible_renames), 1)
        self.assertEqual(history.possible_renames[0]["previous_symbol"], "BTCUSDT")
        self.assertEqual(history.possible_renames[0]["current_symbol"], "XBTUSDT")
        self.assertEqual(
            history.possible_renames[0]["classification"],
            "possible_rename_not_proven",
        )
        with self.assertRaisesRegex(ValueError, "absent from latest"):
            history.get_spec("BTCUSDT", 1_793_577_600_000)


    def test_possible_symbol_rename_is_reported_across_absent_snapshot(self):
        previous = row("BTCUSDT")
        renamed = row("XBTUSDT")
        renamed["baseCoin"] = "BTC"
        write_snapshot(self.root, "a.json", "2026-11-01T00:00:00Z", [previous])
        write_snapshot(self.root, "b.json", "2026-11-02T00:00:00Z", [row("ETHUSDT")])
        write_snapshot(self.root, "c.json", "2026-11-03T00:00:00Z", [renamed])
        history = InstrumentSpecHistory.from_directory(self.root)
        self.assertEqual(len(history.possible_renames), 1)
        self.assertEqual(history.possible_renames[0]["previous_symbol"], "BTCUSDT")
        self.assertEqual(history.possible_renames[0]["current_symbol"], "XBTUSDT")
        self.assertEqual(history.possible_renames[0]["previous_fetched_at"],
                         "2026-11-01T00:00:00Z")

    def test_missing_contract_identity_fields_are_rejected(self):
        malformed = row()
        malformed.pop("baseCoin")
        write_snapshot(self.root, "c.json", "2026-11-03T00:00:00Z", [malformed])
        with self.assertRaisesRegex(ValueError, "missing or invalid identity field baseCoin"):
            InstrumentSpecHistory.from_directory(self.root)

    def test_duplicate_contract_identity_with_two_symbols_is_ambiguous(self):
        first = row("BTCUSDT")
        second = row("XBTUSDT")
        second["baseCoin"] = "BTC"
        write_snapshot(self.root, "c.json", "2026-11-03T00:00:00Z", [first, second])
        with self.assertRaisesRegex(ValueError, "ambiguous duplicate contract identity"):
            InstrumentSpecHistory.from_directory(self.root)

    def test_identity_is_stable_when_only_trading_constraints_change(self):
        history = InstrumentSpecHistory.from_directory(self.root)
        self.assertEqual(history.snapshots[0].identities["BTCUSDT"],
                         history.snapshots[1].identities["BTCUSDT"])
        self.assertEqual(str(history.get_spec("BTCUSDT", 1_793_577_600_000).tick_size), "0.01")

    def test_missing_or_malformed_required_snapshot_fields_rejected(self):
        (self.root / "b.json").write_text("not-json", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "cannot read"):
            InstrumentSpecHistory.from_directory(self.root)


    def test_missing_or_mismatched_source_is_rejected(self):
        payload = json.loads((self.root / "a.json").read_text())
        payload.pop("source")
        (self.root / "a.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid or missing Bybit instruments-info source"):
            InstrumentSpecHistory.from_directory(self.root)

if __name__ == "__main__":
    unittest.main(verbosity=2)
