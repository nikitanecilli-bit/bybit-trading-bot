"""Deterministic unittest coverage for Bybit isolated USDT-linear liquidation."""
import unittest
from decimal import Decimal

from bybit_risk_tiers import RiskTier
from mark_price_liquidation import calculate_isolated_usdt_liquidation_price


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
    def test_bybit_published_isolated_long_example(self):
        result = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="long", entry_price="40000",
            quantity="1", leverage="50",
            tiers=[tier(1, "1000000", "0.005", "100")],
            taker_fee_rate="0.00055", extra_margin="3000",
        )
        self.assertEqual(result.liquidation_price.quantize(Decimal("0.01")), Decimal("36380.25"))

    def test_long_and_short_prices_are_on_adverse_sides_of_entry(self):
        tiers = [tier(1, "1000000", "0.005", "100")]
        long = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="long", entry_price="40000",
            quantity="1", leverage="10", tiers=tiers,
        )
        short = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="short", entry_price="40000",
            quantity="1", leverage="10", tiers=tiers,
        )
        self.assertLess(long.liquidation_price, Decimal("40000"))
        self.assertGreater(short.liquidation_price, Decimal("40000"))

    def test_long_liquidation_can_fall_into_a_lower_risk_tier(self):
        tiers = [
            tier(1, "100000", "0.005", "100"),
            tier(2, "500000", "0.01", "50", "500"),
        ]
        result = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="long", entry_price="120000",
            quantity="1", leverage="5", tiers=tiers,
        )
        self.assertEqual(result.tier_id, 1)
        self.assertLessEqual(result.liquidation_position_value, Decimal("100000"))

    def test_short_liquidation_can_enter_a_higher_risk_tier(self):
        tiers = [
            tier(1, "100000", "0.005", "100"),
            tier(2, "500000", "0.01", "50", "500"),
        ]
        result = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="short", entry_price="95000",
            quantity="1", leverage="10", tiers=tiers,
        )
        self.assertEqual(result.tier_id, 2)
        self.assertGreater(result.liquidation_position_value, Decimal("100000"))
        self.assertLessEqual(result.liquidation_position_value, Decimal("500000"))

    def test_rejects_entry_over_highest_risk_limit(self):
        with self.assertRaisesRegex(ValueError, "entry notional exceeds"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="long", entry_price="600000",
                quantity="1", leverage="10",
                tiers=[tier(1, "500000", "0.005", "100")],
            )

    def test_rejects_leverage_above_entry_tier_limit(self):
        with self.assertRaisesRegex(ValueError, "entry tier maxLeverage"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="long", entry_price="120000",
                quantity="1", leverage="60",
                tiers=[
                    tier(1, "100000", "0.005", "100"),
                    tier(2, "500000", "0.01", "50", "500"),
                ],
            )

    def test_rejects_tier_for_different_symbol(self):
        with self.assertRaisesRegex(ValueError, "belong to the requested symbol"):
            calculate_isolated_usdt_liquidation_price(
                symbol="ETHUSDT", direction="long", entry_price="100",
                quantity="1", leverage="10",
                tiers=[tier(1, "1000000", "0.005", "100")],
            )

    def test_rejects_invalid_inputs_and_duplicate_tier_limits(self):
        tiers = [tier(1, "1000000", "0.005", "100")]
        with self.assertRaisesRegex(ValueError, "direction"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="flat", entry_price="100",
                quantity="1", leverage="10", tiers=tiers,
            )
        with self.assertRaisesRegex(ValueError, "fee"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="long", entry_price="100",
                quantity="1", leverage="10", tiers=tiers, taker_fee_rate="1",
            )
        with self.assertRaisesRegex(ValueError, "unique"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="long", entry_price="100",
                quantity="1", leverage="10",
                tiers=[tier(1, "1000", "0.005", "100"), tier(2, "1000", "0.01", "50")],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
