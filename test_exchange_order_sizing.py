"""Tests for conversion from notional sizing to Bybit-valid quantity."""
import unittest
from decimal import Decimal

from bybit_instrument_specs import InstrumentSpec
from exchange_order_sizing import size_to_exchange_constraints


SNAPSHOT = {
    "instrument": {
        "symbol": "TESTUSDT", "category": "linear", "status": "Trading",
        "priceFilter": {"tickSize": "0.05"},
        "lotSizeFilter": {
            "qtyStep": "0.001", "minOrderQty": "0.01",
            "maxOrderQty": "1000", "maxMktOrderQty": "800",
            "minNotionalValue": "5",
        },
    }
}


class ExchangeSizingTests(unittest.TestCase):
    def setUp(self):
        self.spec = InstrumentSpec.from_snapshot(SNAPSHOT)

    def test_market_quantity_is_floored_and_risk_never_increases(self):
        order = size_to_exchange_constraints(
            self.spec, "1000", "100.03", "10",
            order_type="market", side="buy",
        )
        self.assertEqual(order.qty, Decimal("9.997"))
        self.assertEqual(order.price, Decimal("100.03"))
        self.assertLessEqual(order.notional_usdt, Decimal("1000"))
        self.assertLessEqual(order.risk_usdt, Decimal("10"))

    def test_limit_price_is_tick_rounded_then_quantity_recalculated(self):
        order = size_to_exchange_constraints(
            self.spec, "1000", "100.079", "10",
            order_type="limit", side="buy",
        )
        self.assertEqual(order.price, Decimal("100.05"))
        self.assertEqual(order.qty, Decimal("9.995"))
        self.assertLessEqual(order.notional_usdt, Decimal("1000"))
        self.assertLessEqual(order.risk_usdt, Decimal("10"))

    def test_sell_limit_rounds_up_without_exceeding_notional_budget(self):
        order = size_to_exchange_constraints(
            self.spec, "1000", "100.051", "10",
            order_type="limit", side="sell",
        )
        self.assertEqual(order.price, Decimal("100.10"))
        self.assertLessEqual(order.notional_usdt, Decimal("1000"))

    def test_minimum_notional_rejection(self):
        with self.assertRaisesRegex(ValueError, "minNotionalValue"):
            size_to_exchange_constraints(
                self.spec, "4.99", "100", "1",
                order_type="market", side="buy",
            )

    def test_market_and_limit_quantity_caps_are_distinct(self):
        with self.assertRaisesRegex(ValueError, "maxMktOrderQty"):
            size_to_exchange_constraints(
                self.spec, "90_000", "100", "100",
                order_type="market", side="buy",
            )
        with self.assertRaisesRegex(ValueError, "maxOrderQty"):
            size_to_exchange_constraints(
                self.spec, "110_000", "100", "100",
                order_type="limit", side="buy",
            )

    def test_invalid_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError, "side"):
            size_to_exchange_constraints(
                self.spec, 100, 100, 1, order_type="market", side="short"
            )
        with self.assertRaisesRegex(ValueError, "risk_budget"):
            size_to_exchange_constraints(
                self.spec, 100, 100, 0, order_type="market", side="buy"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
