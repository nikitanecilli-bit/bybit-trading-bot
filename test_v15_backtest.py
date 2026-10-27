"""Regression tests for the v15 simulator."""
import unittest

from research_v15.backtest import Bar, backtest_symbol, breakeven_action, limit_order_expired, limit_order_fill, resolve_stop_target, rolling_atr, stop_order_fill, trade_economics, position_size, mark_to_market_equity


class V15BacktestTests(unittest.TestCase):
    def test_rolling_atr_is_positive_and_matches_simple_range(self):
        bars = [Bar(i * 3_600_000 + 1, 10, 12, 9, 11) for i in range(3)]
        self.assertEqual(rolling_atr(bars, 2), [3.0, 3.0, 3.0])

    def test_short_history_returns_zero_trade_result(self):
        bars = [Bar(i * 3_600_000 + 1, 100, 101, 99, 100) for i in range(20)]
        result = backtest_symbol(bars, symbol="TEST", donchian_period=5, ema_fast_period=3, ema_slow_period=8)
        self.assertEqual(result["trades_count"], 0)
        self.assertEqual(result["net_pnl"], 0.0)

    def test_duplicate_or_unsorted_timestamps_rejected(self):
        bars = [Bar(1000, 100, 101, 99, 100), Bar(1000, 100, 101, 99, 100)]
        with self.assertRaises(ValueError):
            backtest_symbol(bars, donchian_period=1, ema_fast_period=1, ema_slow_period=1, atr_period=1)

    def test_invalid_risk_rejected(self):
        bars = [Bar(i * 3_600_000 + 1, 100, 101, 99, 100) for i in range(10)]
        with self.assertRaises(ValueError):
            backtest_symbol(bars, risk_pct=0, donchian_period=2, ema_fast_period=2, ema_slow_period=3)


    def test_long_limit_not_filled_when_low_stays_above_limit(self):
        bar = Bar(1, 102, 104, 101, 103)
        self.assertIsNone(limit_order_fill(bar, "long", 100))

    def test_long_limit_fills_at_limit_when_touched_intrabar(self):
        bar = Bar(1, 102, 104, 100, 103)
        self.assertEqual(limit_order_fill(bar, "long", 100), 100)

    def test_long_limit_gets_better_open_price_on_gap_down(self):
        bar = Bar(1, 98, 100, 97, 99)
        self.assertEqual(limit_order_fill(bar, "long", 100), 98)

    def test_short_limit_not_filled_when_high_stays_below_limit(self):
        bar = Bar(1, 98, 99, 96, 97)
        self.assertIsNone(limit_order_fill(bar, "short", 100))

    def test_short_limit_fills_at_limit_when_touched_intrabar(self):
        bar = Bar(1, 98, 100, 96, 97)
        self.assertEqual(limit_order_fill(bar, "short", 100), 100)

    def test_short_limit_gets_better_open_price_on_gap_up(self):
        bar = Bar(1, 102, 103, 100, 101)
        self.assertEqual(limit_order_fill(bar, "short", 100), 102)

    def test_limit_fill_rejects_invalid_side_or_price(self):
        bar = Bar(1, 100, 101, 99, 100)
        with self.assertRaises(ValueError):
            limit_order_fill(bar, "buy", 100)
        with self.assertRaises(ValueError):
            limit_order_fill(bar, "long", 0)

    def test_limit_order_expiry_includes_last_valid_bar(self):
        self.assertFalse(limit_order_expired(1, 3))
        self.assertFalse(limit_order_expired(3, 3))
        self.assertTrue(limit_order_expired(4, 3))

    def test_limit_order_expiry_rejects_invalid_age_or_lifetime(self):
        with self.assertRaises(ValueError):
            limit_order_expired(-1, 3)
        with self.assertRaises(ValueError):
            limit_order_expired(1, 0)

    def test_long_limit_intrabar_touch_fills_at_limit(self):
        bar = Bar(1, 101, 103, 99, 102)
        self.assertEqual(limit_order_fill(bar, "long", 100), 100)

    def test_short_limit_intrabar_touch_fills_at_limit(self):
        bar = Bar(1, 99, 101, 97, 98)
        self.assertEqual(limit_order_fill(bar, "short", 100), 100)

    def test_long_limit_gap_gets_better_open_price(self):
        bar = Bar(1, 95, 99, 94, 97)
        self.assertEqual(limit_order_fill(bar, "long", 100), 95)

    def test_short_limit_gap_gets_better_open_price(self):
        bar = Bar(1, 105, 107, 101, 103)
        self.assertEqual(limit_order_fill(bar, "short", 100), 105)

    def test_limit_not_touched_does_not_fill(self):
        bar = Bar(1, 102, 104, 101, 103)
        self.assertIsNone(limit_order_fill(bar, "long", 100))
        self.assertIsNone(limit_order_fill(bar, "short", 105))

    def test_limit_order_lifetime_counts_only_post_signal_bars(self):
        self.assertFalse(limit_order_expired(1, 3))
        self.assertFalse(limit_order_expired(3, 3))
        self.assertTrue(limit_order_expired(4, 3))

    def test_invalid_limit_order_inputs_rejected(self):
        bar = Bar(1, 100, 101, 99, 100)
        with self.assertRaises(ValueError):
            limit_order_fill(bar, "buy", 100)
        with self.assertRaises(ValueError):
            limit_order_fill(bar, "long", 0)
        with self.assertRaises(ValueError):
            limit_order_expired(-1, 3)


    def test_long_stop_hit_fills_at_stop(self):
        bar = Bar(1, 102, 104, 98, 101)
        self.assertEqual(stop_order_fill(bar, "long", 99), 99)

    def test_long_stop_gap_fills_at_worse_open(self):
        bar = Bar(1, 95, 98, 94, 97)
        self.assertEqual(stop_order_fill(bar, "long", 99), 95)

    def test_short_stop_gap_fills_at_worse_open(self):
        bar = Bar(1, 105, 107, 102, 103)
        self.assertEqual(stop_order_fill(bar, "short", 101), 105)

    def test_stop_not_touched_returns_none(self):
        bar = Bar(1, 102, 104, 100, 103)
        self.assertIsNone(stop_order_fill(bar, "long", 99))
        self.assertIsNone(stop_order_fill(bar, "short", 105))

    def test_stop_wins_when_stop_and_target_both_touched(self):
        long_bar = Bar(1, 100, 112, 88, 101)
        short_bar = Bar(2, 100, 112, 88, 99)
        self.assertEqual(resolve_stop_target(long_bar, "long", 90, 110), (90, "stop_or_gap", False))
        self.assertEqual(resolve_stop_target(short_bar, "short", 110, 90), (110, "stop_or_gap", False))

    def test_target_fill_is_limit_style_when_stop_not_touched(self):
        long_bar = Bar(1, 100, 112, 95, 108)
        short_bar = Bar(2, 100, 105, 88, 92)
        self.assertEqual(resolve_stop_target(long_bar, "long", 90, 110), (110, "target", True))
        self.assertEqual(resolve_stop_target(short_bar, "short", 110, 90), (90, "target", True))

    def test_target_can_be_disabled(self):
        bar = Bar(1, 100, 112, 95, 108)
        self.assertIsNone(resolve_stop_target(bar, "long", 90, 110, target_allowed=False))

    def test_stop_helpers_reject_invalid_inputs(self):
        bar = Bar(1, 100, 101, 99, 100)
        with self.assertRaises(ValueError):
            stop_order_fill(bar, "buy", 99)
        with self.assertRaises(ValueError):
            stop_order_fill(bar, "long", 0)
        with self.assertRaises(ValueError):
            resolve_stop_target(bar, "buy", 99, 101)


    def test_breakeven_does_not_trigger_before_threshold(self):
        bar = Bar(1, 100, 108, 99, 107)
        self.assertIsNone(breakeven_action(bar, "long", 100, 10, 0.95, False))
        self.assertIsNone(breakeven_action(bar, "short", 100, 10, 0.95, False))

    def test_breakeven_moves_stop_when_threshold_reached_without_return(self):
        long_bar = Bar(1, 102, 110, 101, 109)
        short_bar = Bar(2, 98, 99, 90, 91)
        self.assertEqual(breakeven_action(long_bar, "long", 100, 10, 0.95, False), "move")
        self.assertEqual(breakeven_action(short_bar, "short", 100, 10, 0.95, False), "move")

    def test_breakeven_same_bar_return_exits_conservatively(self):
        long_bar = Bar(1, 100, 110, 99, 101)
        short_bar = Bar(2, 100, 101, 90, 99)
        self.assertEqual(breakeven_action(long_bar, "long", 100, 10, 0.95, False), "exit")
        self.assertEqual(breakeven_action(short_bar, "short", 100, 10, 0.95, False), "exit")

    def test_breakeven_does_not_retrigger_after_moved_or_on_entry_bar(self):
        bar = Bar(1, 100, 115, 99, 110)
        self.assertIsNone(breakeven_action(bar, "long", 100, 10, 0.95, True))
        self.assertIsNone(breakeven_action(bar, "long", 100, 10, 0.95, False, entry_bar=True))

    def test_breakeven_rejects_invalid_inputs(self):
        bar = Bar(1, 100, 101, 99, 100)
        with self.assertRaises(ValueError):
            breakeven_action(bar, "buy", 100, 10, 0.95, False)
        with self.assertRaises(ValueError):
            breakeven_action(bar, "long", 100, 0, 0.95, False)


    def test_breakeven_exit_still_loses_to_fees_and_slippage(self):
        for side in ("long", "short"):
            with self.subTest(side=side):
                result = trade_economics(side, 100, 100, 2, maker_entry=True, maker_exit=False)
                self.assertEqual(result["gross_pnl"], 0)
                self.assertGreater(result["fees"], 0)
                self.assertGreater(result["slippage"], 0)
                self.assertLess(result["net_pnl"], 0)
                self.assertAlmostEqual(
                    result["net_pnl"],
                    result["gross_pnl"] - result["fees"] - result["slippage"],
                )

    def test_target_maker_exit_has_no_taker_slippage(self):
        result = trade_economics("long", 100, 110, 2, maker_entry=True, maker_exit=True)
        self.assertEqual(result["exit_price"], 110)
        self.assertEqual(result["slippage"], 0)
        self.assertAlmostEqual(
            result["net_pnl"],
            result["gross_pnl"] - result["fees"] - result["slippage"],
        )

    def test_trade_economics_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError):
            trade_economics("buy", 100, 101, 1)
        with self.assertRaises(ValueError):
            trade_economics("long", 100, 101, 0)


    def test_mark_to_market_equity_includes_entry_and_estimated_exit_costs(self):
        equity = mark_to_market_equity(10_000, "long", 100, 101, 2)
        gross_marked_equity = 10_000 + (101 - 100) * 2
        self.assertLess(equity, gross_marked_equity)
        self.assertAlmostEqual(
            equity,
            10_000 + trade_economics("long", 100, 101, 2, maker_entry=True, maker_exit=False)["net_pnl"],
        )

    def test_mark_to_market_equity_handles_short_position(self):
        equity = mark_to_market_equity(10_000, "short", 100, 99, 2)
        gross_marked_equity = 10_000 + (100 - 99) * 2
        self.assertLess(equity, gross_marked_equity)
        self.assertGreater(equity, 10_000)

    def test_position_size_respects_risk_budget_and_notional_cap(self):
        sized = position_size(10_000, 0.01, 100, 5)
        self.assertAlmostEqual(sized["risk_budget"], 100)
        self.assertLess(sized["qty"], sized["qty_by_price_risk"])
        self.assertAlmostEqual(sized["notional"], sized["qty"] * 100)
        self.assertLessEqual(sized["total_estimated_stop_loss"], sized["risk_budget"] + 1e-9)
        self.assertLessEqual(sized["total_estimated_stop_loss_pct_equity"], 0.01)
        self.assertGreater(sized["estimated_stop_cost"], 0)

    def test_position_size_notional_cap_limits_high_risk_quantity(self):
        sized = position_size(10_000, 0.05, 100, 0.1)
        self.assertAlmostEqual(sized["qty"], 100)
        self.assertAlmostEqual(sized["notional"], 10_000)
        self.assertAlmostEqual(sized["planned_stop_loss"], 10)
        self.assertLessEqual(sized["notional"], 10_000)

    def test_gap_stop_can_exceed_planned_risk_and_costs_are_separate(self):
        sized = position_size(10_000, 0.01, 100, 5)
        # Long stop is 95, but market gaps down to 90 before execution.
        economics = trade_economics("long", 100, 90, sized["qty"], maker_entry=True, maker_exit=False)
        self.assertGreater(abs(economics["gross_pnl"]), sized["planned_stop_loss"])
        self.assertLess(economics["net_pnl"], economics["gross_pnl"])
        self.assertGreater(economics["fees"], 0)
        self.assertGreater(economics["slippage"], 0)

    def test_short_position_size_uses_short_stop_above_entry(self):
        sized = position_size(10_000, 0.01, 100, 5, "short")
        self.assertAlmostEqual(sized["qty"], sized["qty_by_total_risk"])
        self.assertLessEqual(sized["total_estimated_stop_loss"], sized["risk_budget"] + 1e-9)
        self.assertGreater(sized["estimated_stop_cost"], 0)

    def test_position_size_rejects_invalid_inputs(self):
        for args in ((0, 0.01, 100, 5), (1000, 0, 100, 5), (1000, 0.01, 0, 5), (1000, 0.01, 100, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                position_size(*args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
