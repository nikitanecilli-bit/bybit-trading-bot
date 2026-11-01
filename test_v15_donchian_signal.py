"""Regression tests for the isolated v15 signal module (stdlib unittest only)."""
import unittest

from research_v15.donchian_signal import donchian_breakout, ema, v15_signal


def candle(open_, high, low, close):
    return {"open": float(open_), "high": float(high), "low": float(low), "close": float(close)}


class DonchianSignalTests(unittest.TestCase):
    def setUp(self):
        self.flat = [candle(100, 101, 99, 100) for _ in range(5)]

    def test_long_breakout_uses_prior_candles_only(self):
        candles = self.flat + [candle(100, 103, 99, 102)]
        self.assertEqual(donchian_breakout(candles, 5, period=5), "long")

    def test_short_breakout_uses_prior_candles_only(self):
        candles = self.flat + [candle(100, 100, 97, 98)]
        self.assertEqual(donchian_breakout(candles, 5, period=5), "short")

    def test_no_signal_when_close_stays_inside_prior_range(self):
        candles = self.flat + [candle(100, 102, 99, 100.5)]
        self.assertIsNone(donchian_breakout(candles, 5, period=5))

    def test_insufficient_history_returns_no_signal(self):
        self.assertIsNone(donchian_breakout(self.flat, 3, period=5))

    def test_invalid_period_rejected(self):
        with self.assertRaises(ValueError):
            donchian_breakout(self.flat, 4, period=0)

    def test_ema_matches_simple_recursive_calculation(self):
        self.assertEqual(ema([10, 10, 20], period=3), [10.0, 10.0, 15.0])

    def test_v15_long_signal_passes_uptrend_filter(self):
        candles = []
        for i in range(30):
            close = 100 + i
            candles.append(candle(close - 0.2, close + 0.5, close - 0.5, close))
        previous_close = candles[-1]["close"]
        candles.append(candle(previous_close, previous_close + 2, previous_close - 0.5, previous_close + 1.5))
        self.assertEqual(v15_signal(candles, len(candles) - 1, 5, 3, 8), "long")

    def test_v15_rejects_invalid_ohlc(self):
        candles = self.flat + [candle(100, 99, 101, 100)]
        with self.assertRaises(ValueError):
            v15_signal(candles, len(candles) - 1, 5, 3, 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
