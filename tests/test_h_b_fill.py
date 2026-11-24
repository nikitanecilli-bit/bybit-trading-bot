"""Synthetic tests for H-B next-open fill geometry; no PnL or execution claims."""
from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from h_b_fill import validate_h_b_replay_fill
from h_b_regime import evaluate_h_b_candidate
from h_b_signal import H1_INTERVAL_MS


def make_candidate(fill_price=98.0, include_fill=True):
    ts0 = 1_800_000_000_000
    candles = []
    for i in range(128):
        close = 99.0 if i % 2 == 0 else 101.0
        candles.append({
            "ts": ts0 + i * H1_INTERVAL_MS,
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
        })
    candles.append({
        "ts": ts0 + 128 * H1_INTERVAL_MS,
        "open": 94.0, "high": 95.0, "low": 93.0, "close": 94.0,
    })
    candles.append({
        "ts": ts0 + 129 * H1_INTERVAL_MS,
        "open": 94.5, "high": 96.0, "low": 94.0, "close": 95.5,
    })
    signal = evaluate_h_b_candidate(candles, 128)
    if include_fill:
        candles.append({
            "ts": ts0 + 130 * H1_INTERVAL_MS,
            "open": fill_price,
            "high": fill_price + 0.5,
            "low": fill_price - 0.5,
            "close": fill_price + 0.1,
        })
    return candles, signal


class TestHBNexOpenFillGeometry(unittest.TestCase):
    def test_valid_next_open_inside_frozen_stop_target(self):
        candles, signal = make_candidate(98.0)
        fill = validate_h_b_replay_fill(candles, signal)
        self.assertIsNotNone(fill)
        self.assertEqual(fill["fill_ts_ms"], candles[130]["ts"])
        self.assertEqual(fill["fill_price"], 98.0)
        self.assertEqual(fill["risk_per_unit"], 5.0)
        self.assertEqual(fill["gross_reward_per_unit"], 2.0)
        self.assertAlmostEqual(fill["gross_reward_to_risk"], 0.4)
        self.assertEqual(fill["fill_model"], "next_h1_open_reference_only")

    def test_missing_next_open_bar_returns_no_fill(self):
        candles, signal = make_candidate(include_fill=False)
        self.assertIsNone(validate_h_b_replay_fill(candles, signal))

    def test_gap_at_or_below_stop_is_rejected(self):
        for price in (93.0, 92.0):
            candles, signal = make_candidate(price)
            self.assertIsNone(validate_h_b_replay_fill(candles, signal))

    def test_gap_at_or_above_target_is_rejected(self):
        _, signal = make_candidate()
        target = signal["target_price"]
        for price in (target, target + 1.0):
            candles, candidate = make_candidate(price)
            self.assertIsNone(validate_h_b_replay_fill(candles, candidate))

    def test_wrong_next_bar_timestamp_fails_closed(self):
        candles, signal = make_candidate()
        candles[130]["ts"] += 1
        with self.assertRaisesRegex(ValueError, "exact next-H1"):
            validate_h_b_replay_fill(candles, signal)

    def test_signal_timestamp_must_match_stabilization_bar(self):
        candles, signal = make_candidate()
        signal["signal_ts_ms"] += H1_INTERVAL_MS
        with self.assertRaisesRegex(ValueError, "stabilization candle"):
            validate_h_b_replay_fill(candles, signal)

    def test_invalid_fill_ohlc_fails_closed(self):
        candles, signal = make_candidate()
        candles[130]["high"] = 1.0
        with self.assertRaisesRegex(ValueError, "invalid OHLC"):
            validate_h_b_replay_fill(candles, signal)

    def test_future_bars_after_fill_do_not_change_fill_geometry(self):
        candles, signal = make_candidate()
        first = validate_h_b_replay_fill(candles, signal)
        extended = copy.deepcopy(candles)
        extended.append({
            "ts": candles[-1]["ts"] + 1,
            "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
        })
        self.assertEqual(validate_h_b_replay_fill(extended, signal), first)


if __name__ == "__main__":
    unittest.main()
