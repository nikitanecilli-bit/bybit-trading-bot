import unittest
from types import SimpleNamespace

from market_structure import breakout_quality, trend_direction


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

    def test_invalid_breakout_direction_rejected(self):
        self.assertFalse(breakout_quality(make_candles([100+i for i in range(60)]), "neutral"))


if __name__ == "__main__":
    unittest.main()
