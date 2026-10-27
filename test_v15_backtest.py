"""Regression tests for the v15 simulator."""
import unittest

from research_v15.backtest import Bar, backtest_symbol, limit_order_expired, limit_order_fill, rolling_atr


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
