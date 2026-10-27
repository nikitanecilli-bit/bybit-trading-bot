"""Regression tests for the v15 simulator."""
import unittest

from research_v15.backtest import Bar, backtest_symbol, rolling_atr


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
