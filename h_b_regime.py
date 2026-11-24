"""Frozen, H1-specific regime adapter for the synthetic H-B candidate.

The thresholds intentionally inherit the pre-existing RegimeConfig defaults.
They are frozen as a research candidate, not calibrated or validated for market PnL.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Mapping, Sequence

from h_b_signal import H1_INTERVAL_MS, evaluate_h_b_signal
from market_regime import RegimeConfig, classify_candles

H_B_REGIME_POLICY_VERSION = "H-B-RANGE-DEFAULTS-v1"
H_B_REGIME_CONFIG = RegimeConfig(
    efficiency_period=20,
    atr_period=14,
    ema_fast_period=10,
    ema_slow_period=30,
    slope_lookback=5,
    volatility_lookback=100,
    trend_er_min=0.35,
    range_er_max=0.25,
    trend_slope_atr_min=0.25,
    range_slope_atr_max=0.15,
    high_vol_ratio=1.5,
    high_vol_er_max=0.30,
)
H_B_REGIME_CONFIG.validate()

H_B_REGIME_WARMUP_BARS = max(
    H_B_REGIME_CONFIG.efficiency_period + 1,
    H_B_REGIME_CONFIG.atr_period,
    H_B_REGIME_CONFIG.ema_slow_period + H_B_REGIME_CONFIG.slope_lookback,
    H_B_REGIME_CONFIG.volatility_lookback,
)


def evaluate_h_b_candidate(
    candles: Sequence[Mapping[str, object]],
    shock_index: int,
) -> dict[str, object] | None:
    """Apply the frozen causal regime classifier and H-B signal predicate.

    Only the prefix through the stabilization candle (t+1) is read. The entire
    prefix must be an uninterrupted H1 grid because the regime classifier uses
    rolling windows and recursive EMA state. The regime label and ATR at t-1 are
    therefore derived from a contiguous, completed history.

    The function schedules a possible entry at open t+2; it does not require or
    inspect that future candle, simulate a fill, validate fill geometry, or manage
    a position. Those belong to a later isolated execution-adapter decision.
    """
    if isinstance(shock_index, bool) or not isinstance(shock_index, int):
        raise ValueError("shock_index must be an integer")
    if shock_index < 0:
        raise ValueError("shock_index must be non-negative")
    if shock_index < H_B_REGIME_WARMUP_BARS or shock_index + 1 >= len(candles):
        return None

    prefix: list[dict[str, object]] = []
    previous_ts: int | None = None
    for index, source_row in enumerate(candles[: shock_index + 2]):
        if not isinstance(source_row, Mapping):
            raise ValueError(f"candle[{index}] must be a mapping")
        row = dict(source_row)
        raw_ts = row.get("ts")
        if isinstance(raw_ts, bool) or not isinstance(raw_ts, int) or raw_ts <= 0:
            raise ValueError(f"candle[{index}].ts must be a positive integer")
        ts = raw_ts
        if previous_ts is not None and ts - previous_ts != H1_INTERVAL_MS:
            raise ValueError("H-B regime history requires an uninterrupted exact H1 grid")
        previous_ts = ts
        prefix.append(row)

    labelled = classify_candles(prefix, H_B_REGIME_CONFIG)
    regimes = [str(row["regime"]) for row in labelled]
    atr_values = [
        None if row["atr"] == "" else row["atr"]
        for row in labelled
    ]
    signal = evaluate_h_b_signal(prefix, regimes, atr_values, shock_index)
    if signal is None:
        return None

    signal["regime_policy_version"] = H_B_REGIME_POLICY_VERSION
    signal["regime_config"] = asdict(H_B_REGIME_CONFIG)
    signal["regime_label"] = regimes[shock_index - 1]
    signal["regime_ts_ms"] = prefix[shock_index - 1]["ts"]
    return signal
