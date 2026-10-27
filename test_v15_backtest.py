"""Regression tests for the v15 simulator."""
import unittest

from research_v15.backtest import Bar, backtest_symbol, limit_order_expired, limit_order_fill, resolve_stop_target, rolling_atr, stop_order_fill


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
