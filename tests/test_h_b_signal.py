"""Deterministic tests for the isolated H-B signal predicate."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import copy
import pytest

from h_b_signal import H1_INTERVAL_MS, evaluate_h_b_signal


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


def test_happy_path_uses_causal_timing_and_frozen_levels():
    candles, regimes, atr = make_fixture()
    signal = evaluate_h_b_signal(candles, regimes, atr, 24)
    assert signal is not None
    assert signal["strategy"] == "H-B-mean-reversion"
    assert signal["direction"] == "long"
    assert signal["shock_ts_ms"] == candles[24]["ts"]
    assert signal["signal_ts_ms"] == candles[25]["ts"]
    assert signal["entry_ts_ms"] == candles[25]["ts"] + H1_INTERVAL_MS
    assert signal["stop_price"] == 88.0
    assert signal["target_price"] == pytest.approx((110.0 + 23 * 100.0) / 24.0)


def test_range_gate_is_read_from_t_minus_one_not_shock_or_confirmation():
    candles, regimes, atr = make_fixture()
    regimes[23] = "transition"
    regimes[24] = "range"
    regimes[25] = "range"
    assert evaluate_h_b_signal(candles, regimes, atr, 24) is None


def test_shock_threshold_is_inclusive_and_uses_atr_t_minus_one():
    candles, regimes, atr = make_fixture()
    assert evaluate_h_b_signal(candles, regimes, atr, 24) is not None
    candles[24]["close"] = 100.000001
    candles[24]["high"] = 101.0
    assert evaluate_h_b_signal(candles, regimes, atr, 24) is None


def test_stabilization_must_close_strictly_above_shock_high():
    candles, regimes, atr = make_fixture()
    candles[25]["close"] = candles[24]["high"]
    assert evaluate_h_b_signal(candles, regimes, atr, 24) is None


def test_future_mutation_after_confirmation_cannot_change_signal():
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
    assert evaluate_h_b_signal(extended_candles, extended_regimes, extended_atr, 24) == first


def test_missing_h1_bar_fails_closed():
    candles, regimes, atr = make_fixture()
    candles[25]["ts"] += 1
    with pytest.raises(ValueError, match="H1 timestamp grid"):
        evaluate_h_b_signal(candles, regimes, atr, 24)


def test_duplicate_timestamp_fails_closed():
    candles, regimes, atr = make_fixture()
    candles[25]["ts"] = candles[24]["ts"]
    with pytest.raises(ValueError, match="H1 timestamp grid"):
        evaluate_h_b_signal(candles, regimes, atr, 24)


def test_invalid_atr_fails_closed():
    candles, regimes, atr = make_fixture()
    atr[23] = float("nan")
    with pytest.raises(ValueError, match=r"ATR\[t-1\]"):
        evaluate_h_b_signal(candles, regimes, atr, 24)


def test_invalid_ohlc_fails_closed():
    candles, regimes, atr = make_fixture()
    candles[24]["high"] = 80.0
    with pytest.raises(ValueError, match="invalid OHLC"):
        evaluate_h_b_signal(candles, regimes, atr, 24)


def test_insufficient_history_returns_no_signal():
    candles, regimes, atr = make_fixture()
    assert evaluate_h_b_signal(candles, regimes, atr, 23) is None
