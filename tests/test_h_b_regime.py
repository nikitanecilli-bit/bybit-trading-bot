"""Synthetic tests for the frozen H-B regime-to-signal adapter."""
from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from h_b_regime import (
    H_B_REGIME_CONFIG,
    H_B_REGIME_POLICY_VERSION,
    H_B_REGIME_WARMUP_BARS,
    evaluate_h_b_candidate,
)
from h_b_signal import H1_INTERVAL_MS


def make_range_fixture():
    # Alternating, low-drift prices produce a synthetic range under the
    # pre-existing classifier defaults; this is a mechanics fixture, not market data.
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
    # t = 128; t-24 close is 99 and the prior ATR is 2.5.
    candles.append({
        "ts": ts0 + 128 * H1_INTERVAL_MS,
        "open": 94.0,
        "high": 95.0,
        "low": 93.0,
        "close": 94.0,
    })
    candles.append({
        "ts": ts0 + 129 * H1_INTERVAL_MS,
        "open": 94.5,
        "high": 96.0,
        "low": 94.0,
        "close": 95.5,
    })
    return candles


class TestHBRegimeAdapter(unittest.TestCase):
    def test_frozen_default_config_produces_causal_range_signal(self):
        candles = make_range_fixture()
        signal = evaluate_h_b_candidate(candles, 128)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["regime_label"], "range")
        self.assertEqual(signal["regime_ts_ms"], candles[127]["ts"])
        self.assertEqual(signal["regime_policy_version"], H_B_REGIME_POLICY_VERSION)
        self.assertEqual(signal["regime_config"]["volatility_lookback"], 100)
        self.assertEqual(signal["entry_ts_ms"], candles[129]["ts"] + H1_INTERVAL_MS)

    def test_classifier_history_gap_fails_closed(self):
        candles = make_range_fixture()
        candles[50]["ts"] += 1
        with self.assertRaisesRegex(ValueError, "uninterrupted exact H1 grid"):
            evaluate_h_b_candidate(candles, 128)

    def test_future_rows_after_confirmation_do_not_change_candidate(self):
        candles = make_range_fixture()
        first = evaluate_h_b_candidate(candles, 128)
        extended = copy.deepcopy(candles)
        # These future rows are deliberately malformed for H1 cadence. They
        # must not be read because the signal is decided through t+1 only.
        extended.extend([
            {"ts": candles[-1]["ts"] + 1, "open": 1, "high": 1, "low": 1, "close": 1},
            {"ts": candles[-1]["ts"] + 2, "open": 2, "high": 2, "low": 2, "close": 2},
        ])
        self.assertEqual(evaluate_h_b_candidate(extended, 128), first)

    def test_warmup_is_required_before_regime_label_can_be_used(self):
        candles = make_range_fixture()
        self.assertEqual(H_B_REGIME_WARMUP_BARS, 100)
        self.assertIsNone(evaluate_h_b_candidate(candles[:101], 99))

    def test_missing_confirmation_bar_returns_no_signal(self):
        candles = make_range_fixture()[:129]
        self.assertIsNone(evaluate_h_b_candidate(candles, 128))

    def test_regime_config_is_immutable(self):
        with self.assertRaises((AttributeError, TypeError)):
            H_B_REGIME_CONFIG.range_er_max = 0.99


if __name__ == "__main__":
    unittest.main()
