"""Deterministic tests for Bybit instrument specification parsing and rounding."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import unittest
from decimal import Decimal

from bybit_instrument_specs import InstrumentSpec


SNAPSHOT = {
    "fetched_at": "2026-11-02T00:00:00Z",
    "instrument": {
        "symbol": "TESTUSDT",
        "category": "linear",
        "status": "Trading",
        "priceFilter": {"minPrice": "0.05", "maxPrice": "1000000", "tickSize": "0.05"},
        "lotSizeFilter": {
            "qtyStep": "0.001",
            "minOrderQty": "0.01",
            "maxOrderQty": "1000",
            "maxMktOrderQty": "800",
            "minNotionalValue": "5",
        },
        "leverageFilter": {
            "minLeverage": "1",
            "maxLeverage": "50",
            "leverageStep": "0.01",
        },
    },
}


class InstrumentSpecTests(unittest.TestCase):
    def setUp(self):
        self.spec = InstrumentSpec.from_snapshot(SNAPSHOT)

    def test_snapshot_fields_are_decimal_and_versioned(self):
        self.assertEqual(self.spec.schema_version, 1)
        self.assertEqual(self.spec.symbol, "TESTUSDT")
        self.assertEqual(self.spec.tick_size, Decimal("0.05"))
        self.assertEqual(self.spec.min_price, Decimal("0.05"))
        self.assertEqual(self.spec.max_price, Decimal("1000000"))
        self.assertEqual(self.spec.qty_step, Decimal("0.001"))
        self.assertEqual(self.spec.min_notional_value, Decimal("5"))
        self.assertEqual(self.spec.fetched_at, "2026-11-02T00:00:00Z")

    def test_buy_price_rounds_down_and_sell_price_rounds_up(self):
        self.assertEqual(self.spec.round_price("100.079", side="buy"), Decimal("100.05"))
        self.assertEqual(self.spec.round_price("100.051", side="sell"), Decimal("100.10"))
        with self.assertRaisesRegex(ValueError, "rounds to zero"):
            self.spec.round_price("0.01", side="buy")

    def test_quantity_rounds_down_not_up(self):
        self.assertEqual(self.spec.round_qty("1.2349"), Decimal("1.234"))

    def test_order_validates_min_qty_and_notional(self):
        self.assertEqual(self.spec.validate_order("0.0519", "100"), Decimal("0.051"))
        with self.assertRaisesRegex(ValueError, "minOrderQty"):
            self.spec.validate_order("0.0099", "100")
        with self.assertRaisesRegex(ValueError, "minNotionalValue"):
            self.spec.validate_order("0.01", "100")
        with self.assertRaisesRegex(ValueError, "tickSize"):
            self.spec.validate_order("0.051", "100.01")

    def test_order_validates_max_qty(self):
        with self.assertRaisesRegex(ValueError, "maxOrderQty"):
            self.spec.validate_order("1000.001", "100")

    def test_market_order_uses_its_own_maximum_quantity(self):
        with self.assertRaisesRegex(ValueError, "maxMktOrderQty"):
            self.spec.validate_order("800.001", "100", order_type="market")
        self.assertEqual(self.spec.validate_order("800", "100.03", order_type="market"),
                         Decimal("800"))
        with self.assertRaisesRegex(ValueError, "order_type"):
            self.spec.validate_order("1", "100", order_type="stop")

    def test_missing_required_exchange_fields_fail_closed(self):
        broken = {"instrument": dict(SNAPSHOT["instrument"])}
        broken["instrument"]["priceFilter"] = {}
        with self.assertRaisesRegex(ValueError, "tickSize"):
            InstrumentSpec.from_snapshot(broken)

    def test_invalid_side_and_nonpositive_values_rejected(self):
        with self.assertRaisesRegex(ValueError, "side"):
            self.spec.round_price("100", side="long")
        with self.assertRaisesRegex(ValueError, r"> 0"):
            self.spec.round_qty("0")

    def test_limit_price_respects_exchange_price_bounds(self):
        low_price_snapshot = {"instrument": dict(SNAPSHOT["instrument"])}
        low_price_snapshot["instrument"]["priceFilter"] = {
            "minPrice": "0.10", "maxPrice": "1000000", "tickSize": "0.05"
        }
        low_price_spec = InstrumentSpec.from_snapshot(low_price_snapshot)
        with self.assertRaisesRegex(ValueError, "minPrice/maxPrice"):
            low_price_spec.round_price("0.05", side="buy")
        with self.assertRaisesRegex(ValueError, "minPrice/maxPrice"):
            self.spec.validate_order("1", "1000000.05")
        with self.assertRaisesRegex(ValueError, "minPrice/maxPrice"):
            self.spec.round_price("1000000.01", side="sell")

    def test_non_linear_category_is_rejected(self):
        broken = {"instrument": dict(SNAPSHOT["instrument"])}
        broken["instrument"]["category"] = "spot"
        with self.assertRaisesRegex(ValueError, "only supports linear"):
            InstrumentSpec.from_snapshot(broken)

    def test_non_trading_instrument_cannot_be_sized(self):
        broken = {"instrument": dict(SNAPSHOT["instrument"])}
        broken["instrument"]["status"] = "PendingOpen"
        spec = InstrumentSpec.from_snapshot(broken)
        with self.assertRaisesRegex(ValueError, "not tradable"):
            spec.validate_order("1", "100")

    def test_invalid_min_max_relationship_rejected(self):
        broken = {"instrument": dict(SNAPSHOT["instrument"])}
        broken["instrument"]["lotSizeFilter"] = dict(SNAPSHOT["instrument"]["lotSizeFilter"])
        broken["instrument"]["lotSizeFilter"]["maxOrderQty"] = "0.001"
        with self.assertRaisesRegex(ValueError, "maxOrderQty"):
            InstrumentSpec.from_snapshot(broken)


if __name__ == "__main__":
    unittest.main(verbosity=2)
