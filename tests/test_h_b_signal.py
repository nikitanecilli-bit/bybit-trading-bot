"""Deterministic, standard-library tests for the isolated H-B signal predicate."""
from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from h_b_signal import H1_INTERVAL_MS, evaluate_h_b_signal, evaluate_h_b_signal_with_classifier, prepare_h_b_entry
from market_regime import RegimeConfig


def make_fixture():
    ts0 = 1_800_000_000_000
    closes = [110.0] + [100.0] * 23
    candles = [
        {
            "ts": ts0 + i * H1_INTERVAL_MS,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
        }
        for i, close in enumerate(closes)
    ]
    # t = index 24; stabilization = index 25.
    candles.append({
        "ts": ts0 + 24 * H1_INTERVAL_MS,
        "open": 99.0,
        "high": 102.0,
        "low": 88.0,
        "close": 100.0,  # exactly at the 2 * ATR threshold
    })
    candles.append({
        "ts": ts0 + 25 * H1_INTERVAL_MS,
        "open": 100.0,
        "high": 104.0,
        "low": 99.0,
        "close": 103.0,  # strictly above shock high
    })
    regimes = ["unknown"] * len(candles)
    regimes[23] = "range"  # regime is read before the shock candle
    atr = [5.0] * len(candles)
    atr[24] = 9999.0  # must not alter its own shock threshold
    return candles, regimes, atr


class TestHBSignal(unittest.TestCase):
    def test_happy_path_uses_causal_timing_and_frozen_levels(self):
        candles, regimes, atr = make_fixture()
        signal = evaluate_h_b_signal(candles, regimes, atr, 24)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["strategy"], "H-B-mean-reversion")
        self.assertEqual(signal["direction"], "long")
        self.assertEqual(signal["shock_ts_ms"], candles[24]["ts"])
        self.assertEqual(signal["signal_ts_ms"], candles[25]["ts"])
        self.assertEqual(signal["entry_ts_ms"], candles[25]["ts"] + H1_INTERVAL_MS)
        self.assertEqual(signal["stop_price"], 88.0)
        self.assertAlmostEqual(signal["target_price"], (110.0 + 23 * 100.0) / 24.0)

    def test_range_gate_is_read_from_t_minus_one_not_shock_or_confirmation(self):
        candles, regimes, atr = make_fixture()
        regimes[23] = "transition"
        regimes[24] = "range"
        regimes[25] = "range"
        self.assertIsNone(evaluate_h_b_signal(candles, regimes, atr, 24))

    def test_shock_threshold_is_inclusive_and_uses_atr_t_minus_one(self):
        candles, regimes, atr = make_fixture()
        self.assertIsNotNone(evaluate_h_b_signal(candles, regimes, atr, 24))
        candles[24]["close"] = 100.000001
        candles[24]["high"] = 101.0
        self.assertIsNone(evaluate_h_b_signal(candles, regimes, atr, 24))

    def test_stabilization_must_close_strictly_above_shock_high(self):
        candles, regimes, atr = make_fixture()
        candles[25]["close"] = candles[24]["high"]
        self.assertIsNone(evaluate_h_b_signal(candles, regimes, atr, 24))

    def test_future_mutation_after_confirmation_cannot_change_signal(self):
        candles, regimes, atr = make_fixture()
        first = evaluate_h_b_signal(candles, regimes, atr, 24)
        extended_candles = copy.deepcopy(candles)
        extended_candles.extend([
            {"ts": candles[-1]["ts"] + H1_INTERVAL_MS, "open": 1.0, "high": 1.0,
             "low": 1.0, "close": 1.0},
            {"ts": candles[-1]["ts"] + 2 * H1_INTERVAL_MS, "open": 5000.0, "high": 9000.0,
             "low": 100.0, "close": 8000.0},
        ])
        extended_regimes = regimes + ["trend_down", "high_vol_chop"]
        extended_atr = atr + [1e9, 1e-9]
        self.assertEqual(
            evaluate_h_b_signal(extended_candles, extended_regimes, extended_atr, 24),
            first,
        )

    def test_missing_h1_bar_fails_closed(self):
        candles, regimes, atr = make_fixture()
        candles[25]["ts"] += 1
        with self.assertRaisesRegex(ValueError, "H1 timestamp grid"):
            evaluate_h_b_signal(candles, regimes, atr, 24)

    def test_duplicate_timestamp_fails_closed(self):
        candles, regimes, atr = make_fixture()
        candles[25]["ts"] = candles[24]["ts"]
        with self.assertRaisesRegex(ValueError, "H1 timestamp grid"):
            evaluate_h_b_signal(candles, regimes, atr, 24)

    def test_invalid_atr_fails_closed(self):
        candles, regimes, atr = make_fixture()
        atr[23] = float("nan")
        with self.assertRaisesRegex(ValueError, r"ATR\[t-1\]"):
            evaluate_h_b_signal(candles, regimes, atr, 24)

    def test_invalid_ohlc_fails_closed(self):
        candles, regimes, atr = make_fixture()
        candles[24]["high"] = 80.0
        with self.assertRaisesRegex(ValueError, "invalid OHLC"):
            evaluate_h_b_signal(candles, regimes, atr, 24)

    def test_insufficient_history_returns_no_signal(self):
        candles, regimes, atr = make_fixture()
        self.assertIsNone(evaluate_h_b_signal(candles, regimes, atr, 23))




def make_classifier_fixture():
    ts0 = 1_800_000_000_000
    candles = []
    for i in range(30):
        close = 100.0 + (0.05 if i % 2 else -0.05)
        candles.append({
            "ts": ts0 + i * H1_INTERVAL_MS,
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
        })
    candles.append({
        "ts": ts0 + 30 * H1_INTERVAL_MS,
        "open": 99.0,
        "high": 99.2,
        "low": 98.0,
        "close": 98.5,
    })
    candles.append({
        "ts": ts0 + 31 * H1_INTERVAL_MS,
        "open": 98.6,
        "high": 99.5,
        "low": 98.4,
        "close": 99.3,
    })
    return candles, 30


class TestHBClassifierBinding(unittest.TestCase):
    def setUp(self):
        self.config = RegimeConfig(
            efficiency_period=5,
            atr_period=3,
            ema_fast_period=3,
            ema_slow_period=6,
            slope_lookback=2,
            volatility_lookback=8,
            trend_er_min=0.35,
            range_er_max=0.25,
            trend_slope_atr_min=1.0,
            range_slope_atr_max=1.0,
            high_vol_ratio=10.0,
            high_vol_er_max=0.3,
        )

    def test_explicit_config_is_required(self):
        candles, index = make_classifier_fixture()
        with self.assertRaisesRegex(ValueError, "explicit RegimeConfig"):
            evaluate_h_b_signal_with_classifier(candles, None, index)

    def test_classifier_binding_emits_config_provenance(self):
        candles, index = make_classifier_fixture()
        signal = evaluate_h_b_signal_with_classifier(candles, self.config, index)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["regime_config"], {
            "efficiency_period": 5,
            "atr_period": 3,
            "ema_fast_period": 3,
            "ema_slow_period": 6,
            "slope_lookback": 2,
            "volatility_lookback": 8,
            "trend_er_min": 0.35,
            "range_er_max": 0.25,
            "trend_slope_atr_min": 1.0,
            "range_slope_atr_max": 1.0,
            "high_vol_ratio": 10.0,
            "high_vol_er_max": 0.3,
        })

    def test_future_rows_after_confirmation_do_not_enter_classifier_prefix(self):
        candles, index = make_classifier_fixture()
        baseline = evaluate_h_b_signal_with_classifier(candles, self.config, index)
        extended = copy.deepcopy(candles)
        extended.extend([
            {"ts": candles[-1]["ts"] + H1_INTERVAL_MS, "open": 1.0, "high": 1.0,
             "low": 1.0, "close": 1.0},
            {"ts": candles[-1]["ts"] + 2 * H1_INTERVAL_MS, "open": 5000.0, "high": 9000.0,
             "low": 100.0, "close": 8000.0},
        ])
        self.assertEqual(
            evaluate_h_b_signal_with_classifier(extended, self.config, index),
            baseline,
        )


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()



class TestHBEntryPreparation(unittest.TestCase):
    def setUp(self):
        self.signal = {
            "strategy": "H-B-mean-reversion",
            "direction": "long",
            "policy_version": "v0.1",
            "signal_ts_ms": 1_800_000_000_000,
            "entry_ts_ms": 1_800_000_000_000 + H1_INTERVAL_MS,
            "stop_price": 98.0,
            "target_price": 101.0,
            "regime_config": {"efficiency_period": 5},
        }
        self.entry_candle = {
            "ts": self.signal["entry_ts_ms"],
            "open": 99.0,
            "high": 100.0,
            "low": 98.5,
            "close": 99.5,
        }

    def test_accepts_exact_next_h1_open_and_preserves_signal_provenance(self):
        prepared = prepare_h_b_entry(self.signal, self.entry_candle)
        self.assertIsNotNone(prepared)
        self.assertEqual(prepared["entry_price"], 99.0)
        self.assertEqual(prepared["stop_price"], 98.0)
        self.assertEqual(prepared["target_price"], 101.0)
        self.assertEqual(prepared["regime_config"], {"efficiency_period": 5})

    def test_missing_or_gapped_next_bar_fails_closed(self):
        self.assertIsNone(prepare_h_b_entry(self.signal, None))
        wrong_bar = dict(self.entry_candle, ts=self.entry_candle["ts"] + 1)
        self.assertIsNone(prepare_h_b_entry(self.signal, wrong_bar))

    def test_open_position_blocks_new_h_b_entry(self):
        self.assertIsNone(prepare_h_b_entry(self.signal, self.entry_candle, True))

    def test_entry_at_or_below_stop_is_rejected(self):
        candle = dict(self.entry_candle, open=98.0)
        self.assertIsNone(prepare_h_b_entry(self.signal, candle))

    def test_entry_at_or_above_target_is_rejected(self):
        candle = dict(self.entry_candle, open=101.0)
        self.assertIsNone(prepare_h_b_entry(self.signal, candle))

    def test_invalid_entry_open_fails_closed(self):
        candle = dict(self.entry_candle, open=float("nan"))
        with self.assertRaisesRegex(ValueError, "entry open"):
            prepare_h_b_entry(self.signal, candle)


if __name__ == "__main__":
    unittest.main()
