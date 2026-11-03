
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
import unittest
from types import SimpleNamespace

from market_structure import (breakout_quality, ema_series, trend_direction,\n                              trend_direction_series, trend_label_index,\n                              lookup_trend_label)


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


    def test_trend_labels_reject_duplicate_or_out_of_order_timestamps(self):
        for timestamps in ([1, 2, 2, 4], [1, 3, 2, 4]):
            candles = make_candles([100.0, 101.0, 102.0, 103.0])
            for candle, timestamp in zip(candles, timestamps):
                candle.ts = timestamp
            with self.assertRaises(ValueError):
                trend_direction_series(candles, fast=2, slow=3, slope=1)


    def test_ema_trend_label_index_uses_exact_timestamp_and_1000_bar_burnin(self):
        h1_ms = 3_600_000
        candles = make_candles([100.0 + i * 0.5 for i in range(1001)])
        for i, candle in enumerate(candles):
            candle.ts = (i + 1) * h1_ms
        labels = trend_label_index(
            candles, fast=50, slow=200, slope=5,
            expected_interval_ms=h1_ms,
        )
        self.assertEqual(len(labels), len(candles))
        self.assertEqual(lookup_trend_label(labels, candles[999].ts), "neutral")
        self.assertEqual(lookup_trend_label(labels, candles[1000].ts), "up")
        with self.assertRaises(KeyError):
            lookup_trend_label(labels, candles[1000].ts + h1_ms)

    def test_ema_trend_label_index_is_prefix_invariant_after_burnin(self):
        h1_ms = 3_600_000
        closes = [100.0 + i * 0.2 for i in range(1100)]
        full = make_candles(closes)
        prefix = make_candles(closes[:1050])
        for rows in (full, prefix):
            for i, candle in enumerate(rows):
                candle.ts = (i + 1) * h1_ms
        full_labels = trend_label_index(full, expected_interval_ms=h1_ms)
        prefix_labels = trend_label_index(prefix, expected_interval_ms=h1_ms)
        for candle in prefix[1000:]:
            self.assertEqual(
                lookup_trend_label(prefix_labels, candle.ts),
                lookup_trend_label(full_labels, candle.ts),
            )

    def test_ema_trend_label_index_fails_closed_on_short_or_gapped_history(self):
        h1_ms = 3_600_000
        short = make_candles([100.0 + i for i in range(1000)])
        for i, candle in enumerate(short):
            candle.ts = (i + 1) * h1_ms
        with self.assertRaises(ValueError):
            trend_label_index(short)
        with self.assertRaises(ValueError):
            trend_label_index(
                make_candles([100.0 + i for i in range(1001)]),
                burn_in_bars=999,
            )

        gapped = make_candles([100.0 + i for i in range(1002)])
        for i, candle in enumerate(gapped):
            candle.ts = (i + 1) * h1_ms + (h1_ms if i >= 1001 else 0)
        with self.assertRaises(ValueError):
            trend_label_index(gapped, expected_interval_ms=h1_ms)


    def test_non_finite_ema_and_trend_inputs_are_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError):
                ema_series([100.0, bad, 101.0], 3)
            candles = make_candles([100.0 + i for i in range(210)])
            candles[-1].close = bad
            with self.assertRaises(ValueError):
                trend_direction(candles, fast=50, slow=200, slope=5)
        candles = make_candles([100.0 + i for i in range(210)])
        candles[-1].close = 0.0
        with self.assertRaises(ValueError):
            trend_direction(candles, fast=50, slow=200, slope=5)

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
