"""Deterministic unittest coverage for Bybit isolated USDT-linear risk formulas."""
import unittest
from decimal import Decimal

from bybit_risk_tiers import RiskTier
from mark_price_liquidation import (
    calculate_isolated_usdt_liquidation_price,
    calculate_mark_price_maintenance_margin,
)


def tier(tier_id, limit, mmr, max_lev, deduction="0"):
    return RiskTier(
        symbol="BTCUSDT", tier_id=tier_id,
        risk_limit_value=Decimal(limit),
        maintenance_margin_rate=Decimal(mmr),
        initial_margin_rate=Decimal("0.01"),
        max_leverage=Decimal(max_lev),
        mm_deduction=Decimal(deduction),
        is_lowest_risk=(tier_id == 1),
    )


class IsolatedLiquidationTests(unittest.TestCase):
    def setUp(self):
        self.tiers = [
            tier(1, "100000", "0.005", "100"),
            tier(2, "500000", "0.01", "50", "500"),
        ]

    def test_bybit_published_isolated_long_example(self):
        result = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="long", entry_price="40000",
            quantity="1", leverage="50",
            tiers=[tier(1, "1000000", "0.005", "100")],
            taker_fee_rate="0.00055", extra_margin="3000",
        )
        self.assertEqual(result.liquidation_price.quantize(Decimal("0.01")), Decimal("36380.25"))

    def test_long_and_short_prices_are_on_adverse_sides_of_entry(self):
        one_tier = [tier(1, "1000000", "0.005", "100")]
        long = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="long", entry_price="40000",
            quantity="1", leverage="10", tiers=one_tier,
        )
        short = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="short", entry_price="40000",
            quantity="1", leverage="10", tiers=one_tier,
        )
        self.assertLess(long.liquidation_price, Decimal("40000"))
        self.assertGreater(short.liquidation_price, Decimal("40000"))

    def test_liquidation_price_uses_entry_tier_even_when_lp_notional_crosses_tier(self):
        long = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="long", entry_price="120000",
            quantity="1", leverage="5", tiers=self.tiers,
        )
        short = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="short", entry_price="95000",
            quantity="1", leverage="10", tiers=self.tiers,
        )
        self.assertEqual(long.tier_id, 2)
        self.assertLess(long.liquidation_position_value, Decimal("100000"))
        self.assertEqual(short.tier_id, 1)
        self.assertGreater(short.liquidation_position_value, Decimal("100000"))

    def test_mark_price_mm_uses_dynamic_tier_for_long_and_short(self):
        long = calculate_mark_price_maintenance_margin(
            symbol="BTCUSDT", direction="long", entry_price="120000",
            mark_price="95000", quantity="1", leverage="5", tiers=self.tiers,
        )
        short = calculate_mark_price_maintenance_margin(
            symbol="BTCUSDT", direction="short", entry_price="95000",
            mark_price="105000", quantity="1", leverage="10", tiers=self.tiers,
        )
        self.assertEqual(long.tier_id, 1)
        self.assertEqual(short.tier_id, 2)
        self.assertEqual(long.maintenance_margin_rate, Decimal("0.005"))
        self.assertEqual(short.maintenance_margin_rate, Decimal("0.01"))

    def test_mark_price_mm_includes_directional_estimated_close_fee(self):
        long = calculate_mark_price_maintenance_margin(
            symbol="BTCUSDT", direction="long", entry_price="40000",
            mark_price="39000", quantity="1", leverage="10",
            tiers=[tier(1, "1000000", "0.005", "100")],
            taker_fee_rate="0.00055",
        )
        short = calculate_mark_price_maintenance_margin(
            symbol="BTCUSDT", direction="short", entry_price="40000",
            mark_price="41000", quantity="1", leverage="10",
            tiers=[tier(1, "1000000", "0.005", "100")],
            taker_fee_rate="0.00055",
        )
        self.assertEqual(long.estimated_close_fee, Decimal("1.98"))
        self.assertEqual(short.estimated_close_fee, Decimal("2.42"))
        self.assertEqual(long.maintenance_margin, Decimal("196.98"))
        self.assertEqual(short.maintenance_margin, Decimal("207.42"))

    def test_rejects_entry_over_highest_risk_limit(self):
        with self.assertRaisesRegex(ValueError, "exceeds highest"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="long", entry_price="600000",
                quantity="1", leverage="10",
                tiers=[tier(1, "500000", "0.005", "100")],
            )

    def test_rejects_leverage_above_entry_or_dynamic_mark_tier_limit(self):
        with self.assertRaisesRegex(ValueError, "entry tier maxLeverage"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="long", entry_price="120000",
                quantity="1", leverage="60", tiers=self.tiers,
            )
        with self.assertRaisesRegex(ValueError, "Mark-Price tier maxLeverage"):
            calculate_mark_price_maintenance_margin(
                symbol="BTCUSDT", direction="short", entry_price="95000",
                mark_price="105000", quantity="1", leverage="60", tiers=self.tiers,
            )

    def test_rejects_invalid_inputs_duplicate_tiers_and_wrong_symbol(self):
        one_tier = [tier(1, "1000000", "0.005", "100")]
        with self.assertRaisesRegex(ValueError, "direction"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="flat", entry_price="100",
                quantity="1", leverage="10", tiers=one_tier,
            )
        with self.assertRaisesRegex(ValueError, "fee"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="long", entry_price="100",
                quantity="1", leverage="10", tiers=one_tier, taker_fee_rate="1",
            )
        with self.assertRaisesRegex(ValueError, "unique"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="long", entry_price="100",
                quantity="1", leverage="10",
                tiers=[tier(1, "1000", "0.005", "100"), tier(2, "1000", "0.01", "50")],
            )
        with self.assertRaisesRegex(ValueError, "requested symbol"):
            calculate_isolated_usdt_liquidation_price(
                symbol="ETHUSDT", direction="long", entry_price="100",
                quantity="1", leverage="10", tiers=one_tier,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
