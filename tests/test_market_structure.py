
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
import unittest
from types import SimpleNamespace

from market_structure import breakout_quality, ema_series, trend_direction, trend_direction_series


def make_candles(closes, volumes=None, ranges=None):
    volumes = volumes or [100.0] * len(closes)
    ranges = ranges or [1.0] * len(closes)
    out = []
    for i, close in enumerate(closes):
        r = ranges[i]
        out.append(SimpleNamespace(
            ts=i, open=close - 0.3*r, high=close + 0.7*r,
            low=close - 0.7*r, close=close, volume=volumes[i]
        ))
    return out


class MarketStructureTests(unittest.TestCase):
    def test_trend_up(self):
        self.assertEqual(trend_direction(make_candles([100+i for i in range(60)])), "up")

    def test_trend_down(self):
        self.assertEqual(trend_direction(make_candles([160-i for i in range(60)])), "down")

    def test_short_history_is_neutral(self):
        self.assertEqual(trend_direction(make_candles([100+i for i in range(10)])), "neutral")


    def test_ema50_200_first_directional_label_requires_206_candles(self):
        rising_205 = make_candles([100 + i * 0.5 for i in range(205)])
        rising_206 = make_candles([100 + i * 0.5 for i in range(206)])
        self.assertEqual(
            trend_direction(rising_205, fast=50, slow=200, slope=5),
            "neutral",
        )
        self.assertEqual(
            trend_direction(rising_206, fast=50, slow=200, slope=5),
            "up",
        )

    def test_full_history_ema50_200_trend_up_and_down(self):
        rising = make_candles([100 + i * 0.5 for i in range(320)])
        falling = make_candles([500 - i * 0.5 for i in range(320)])
        self.assertEqual(trend_direction(rising, fast=50, slow=200, slope=5), "up")
        self.assertEqual(trend_direction(falling, fast=50, slow=200, slope=5), "down")

    def test_ema50_200_stays_bearish_during_rally_below_slow_ema(self):
        closes = [1000.0] * 220 + [100.0 + i * 0.5 for i in range(220)]
        self.assertEqual(
            trend_direction(make_candles(closes), fast=50, slow=200, slope=5),
            "down",
        )

    def test_full_history_ema_retains_older_history_and_is_prefix_causal(self):
        shared_tail = [200.0 + i * 0.2 for i in range(200)]
        low_history = [100.0] * 200 + shared_tail
        high_history = [1000.0] * 200 + shared_tail
        self.assertNotEqual(
            ema_series(low_history, 200)[-1],
            ema_series(high_history, 200)[-1],
        )
        full = [100.0 + i * 0.1 for i in range(400)]
        prefix = full[:260]
        self.assertAlmostEqual(
            ema_series(prefix, 200)[-1],
            ema_series(full, 200)[len(prefix) - 1],
            places=12,
        )


    def test_trend_direction_series_is_prefix_invariant(self):
        closes = [100 + i * 0.3 for i in range(260)] + [178 - i * 0.2 for i in range(40)]
        candles = make_candles(closes)
        prefix_labels = trend_direction_series(candles[:250], fast=50, slow=200, slope=5)
        full_labels = trend_direction_series(candles, fast=50, slow=200, slope=5)
        self.assertEqual(prefix_labels, full_labels[:250])
        self.assertEqual(len(full_labels), len(candles))


    def test_invalid_ema_trend_parameters_rejected(self):
        candles = make_candles([100 + i for i in range(60)])
        with self.assertRaises(ValueError):
            trend_direction(candles, fast=200, slow=50, slope=5)
        with self.assertRaises(ValueError):
            ema_series([1.0, 2.0], 0)


    def test_invalid_breakout_direction_rejected(self):
        self.assertFalse(breakout_quality(make_candles([100+i for i in range(60)]), "neutral"))


if __name__ == "__main__":
    unittest.main()
