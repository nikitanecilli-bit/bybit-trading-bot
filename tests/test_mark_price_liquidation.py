"""Deterministic unittest coverage for Bybit isolated USDT-linear risk formulas."""
import unittest
from decimal import Decimal

from bybit_risk_tiers import RiskTier
from mark_price_liquidation import (
    calculate_isolated_usdt_liquidation_price,
    calculate_mark_price_maintenance_margin,
    evaluate_isolated_margin_health,
    calculate_isolated_usdt_bankruptcy_price,
    mark_candle_crosses_liquidation,
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
        self.assertEqual(long.estimated_close_fee, Decimal("19.80"))
        self.assertEqual(short.estimated_close_fee, Decimal("24.20"))
        self.assertEqual(long.maintenance_margin, Decimal("214.80"))
        self.assertEqual(short.maintenance_margin, Decimal("229.20"))

    def test_dynamic_mark_tier_can_trigger_shortfall_before_fixed_entry_tier_lp(self):
        tiers = [
            tier(1, "100000", "0.005", "100"),
            tier(2, "500000", "0.10", "50", "9500"),
        ]
        fixed_lp = calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="short", entry_price="99000",
            quantity="1", leverage="50", tiers=tiers,
        )
        health = evaluate_isolated_margin_health(
            symbol="BTCUSDT", direction="short", entry_price="99000",
            mark_price="100450", quantity="1", leverage="50", tiers=tiers,
        )
        self.assertEqual(health.tier_id, 2)
        self.assertLess(Decimal("100450"), fixed_lp.liquidation_price)
        self.assertLessEqual(health.position_margin_balance, health.maintenance_margin)
        self.assertTrue(health.liquidation_triggered)

    def test_isolated_margin_balance_accounts_for_extra_margin_and_funding(self):
        one_tier = [tier(1, "1000000", "0.005", "100")]
        health = evaluate_isolated_margin_health(
            symbol="BTCUSDT", direction="long", entry_price="40000",
            mark_price="39000", quantity="1", leverage="10", tiers=one_tier,
            extra_margin="200", funding_net_cost="10",
        )
        self.assertEqual(health.unrealized_pnl, Decimal("-1000"))
        self.assertEqual(health.position_margin_balance, Decimal("3209.80"))
        self.assertEqual(health.maintenance_margin, Decimal("214.80"))
        self.assertEqual(health.margin_surplus, Decimal("2995.00"))
        self.assertFalse(health.liquidation_triggered)

    def test_remaining_quantity_after_tp1_scales_position_margin(self):
        one_tier = [tier(1, "1000000", "0.005", "100")]
        full = evaluate_isolated_margin_health(
            symbol="BTCUSDT", direction="long", entry_price="40000",
            mark_price="39000", quantity="1", leverage="10", tiers=one_tier,
        )
        remaining = evaluate_isolated_margin_health(
            symbol="BTCUSDT", direction="long", entry_price="40000",
            mark_price="39000", quantity="0.5", leverage="10", tiers=one_tier,
        )
        self.assertEqual(remaining.position_margin_balance, full.position_margin_balance / 2)
        self.assertEqual(remaining.maintenance_margin, full.maintenance_margin / 2)

    def test_funding_credit_increases_isolated_margin_balance(self):
        one_tier = [tier(1, "1000000", "0.005", "100")]
        paid = evaluate_isolated_margin_health(
            symbol="BTCUSDT", direction="long", entry_price="40000",
            mark_price="39000", quantity="1", leverage="10", tiers=one_tier,
            funding_net_cost="20",
        )
        received = evaluate_isolated_margin_health(
            symbol="BTCUSDT", direction="long", entry_price="40000",
            mark_price="39000", quantity="1", leverage="10", tiers=one_tier,
            funding_net_cost="-20",
        )
        self.assertEqual(received.position_margin_balance - paid.position_margin_balance, Decimal("40"))

    def test_isolated_bankruptcy_price_and_directional_tick_rounding(self):
        self.assertEqual(
            calculate_isolated_usdt_bankruptcy_price(
                direction="long", entry_price="40000", leverage="50"
            ),
            Decimal("39200"),
        )
        self.assertEqual(
            calculate_isolated_usdt_bankruptcy_price(
                direction="short", entry_price="40000", leverage="50"
            ),
            Decimal("40800"),
        )
        self.assertEqual(
            calculate_isolated_usdt_bankruptcy_price(
                direction="long", entry_price="40000.03", leverage="50", tick_size="0.1"
            ),
            Decimal("39200.1"),
        )
        self.assertEqual(
            calculate_isolated_usdt_bankruptcy_price(
                direction="short", entry_price="40000.03", leverage="50", tick_size="0.1"
            ),
            Decimal("40800.0"),
        )

    def test_mark_candle_detects_long_and_short_liquidation_crossings(self):
        self.assertTrue(mark_candle_crosses_liquidation(
            direction="long", liquidation_price="95000",
            mark_low="94000", mark_high="98000",
        ))
        self.assertTrue(mark_candle_crosses_liquidation(
            direction="short", liquidation_price="105000",
            mark_low="102000", mark_high="106000",
        ))
        self.assertFalse(mark_candle_crosses_liquidation(
            direction="long", liquidation_price="95000",
            mark_low="96000", mark_high="98000",
        ))
        self.assertFalse(mark_candle_crosses_liquidation(
            direction="short", liquidation_price="105000",
            mark_low="102000", mark_high="104000",
        ))

    def test_rejects_entry_over_highest_risk_limit(self):
        with self.assertRaisesRegex(ValueError, "exceeds highest"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="long", entry_price="600000",
                quantity="1", leverage="10",
                tiers=[tier(1, "500000", "0.005", "100")],
            )

    def test_rejects_entry_leverage_but_still_calculates_mm_after_mark_tier_change(self):
        with self.assertRaisesRegex(ValueError, "entry tier maxLeverage"):
            calculate_isolated_usdt_liquidation_price(
                symbol="BTCUSDT", direction="long", entry_price="120000",
                quantity="1", leverage="60", tiers=self.tiers,
            )
        mark_mm = calculate_mark_price_maintenance_margin(
            symbol="BTCUSDT", direction="short", entry_price="95000",
            mark_price="105000", quantity="1", leverage="60", tiers=self.tiers,
        )
        self.assertEqual(mark_mm.tier_id, 2)

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
