"""Offline next-H1-open geometry check for H-B synthetic/replay research.

This is not an execution simulator. It checks only whether the observed t+2 open
lies strictly between the frozen stop and target. Spread, slippage, fees, queue,
partial fills, sizing and portfolio effects are intentionally excluded.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from h_b_signal import H1_INTERVAL_MS, H_B_POLICY_VERSION, H_B_STRATEGY


def _positive_finite(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite positive number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a finite positive number") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    return result


def validate_h_b_replay_fill(
    candles: Sequence[Mapping[str, object]],
    signal: Mapping[str, object],
) -> dict[str, Any] | None:
    """Validate a historical t+2 open against the H-B frozen stop/target.

    The signal is formed after close t+1 and schedules the next H1 open t+2.
    Missing t+2 data or a valid open outside the strict stop/target interval
    returns None. Malformed candles or inconsistent timestamps raise ValueError.
    """
    if signal.get("strategy") != H_B_STRATEGY:
        raise ValueError("signal strategy must be H-B-mean-reversion")
    if signal.get("direction") != "long":
        raise ValueError("H-B replay fill supports long direction only")
    if signal.get("policy_version") != H_B_POLICY_VERSION:
        raise ValueError("unsupported H-B policy version")

    shock_index = signal.get("shock_index")
    if isinstance(shock_index, bool) or not isinstance(shock_index, int) or shock_index < 0:
        raise ValueError("signal shock_index must be a non-negative integer")

    shock_ts = signal.get("shock_ts_ms")
    signal_ts = signal.get("signal_ts_ms")
    entry_ts = signal.get("entry_ts_ms")
    for name, value in (("shock_ts_ms", shock_ts), ("signal_ts_ms", signal_ts), ("entry_ts_ms", entry_ts)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"signal {name} must be a positive integer")

    stop = _positive_finite(signal.get("stop_price"), "signal stop_price")
    target = _positive_finite(signal.get("target_price"), "signal target_price")
    if not stop < target:
        raise ValueError("H-B stop must be strictly below target")
    if entry_ts != signal_ts + H1_INTERVAL_MS:
        raise ValueError("H-B entry timestamp must be the H1 open after signal candle")

    fill_index = shock_index + 2
    if fill_index >= len(candles):
        return None

    parsed: list[dict[str, float | int]] = []
    previous_ts: int | None = None
    for index in range(shock_index, fill_index + 1):
        row = candles[index]
        if not isinstance(row, Mapping):
            raise ValueError(f"candle[{index}] must be a mapping")
        raw_ts = row.get("ts")
        if isinstance(raw_ts, bool) or not isinstance(raw_ts, int) or raw_ts <= 0:
            raise ValueError(f"candle[{index}].ts must be a positive integer")
        ts = raw_ts
        if previous_ts is not None and ts - previous_ts != H1_INTERVAL_MS:
            raise ValueError("H-B replay fill requires exact next-H1 candle timestamps")
        op = _positive_finite(row.get("open"), f"candle[{index}].open")
        high = _positive_finite(row.get("high"), f"candle[{index}].high")
        low = _positive_finite(row.get("low"), f"candle[{index}].low")
        close = _positive_finite(row.get("close"), f"candle[{index}].close")
        if high < max(op, low, close) or low > min(op, high, close):
            raise ValueError(f"candle[{index}] has invalid OHLC boundaries")
        parsed.append({"ts": ts, "open": op, "high": high, "low": low, "close": close})
        previous_ts = ts

    if parsed[0]["ts"] != shock_ts:
        raise ValueError("signal shock timestamp does not match shock candle")
    if parsed[1]["ts"] != signal_ts:
        raise ValueError("signal timestamp does not match stabilization candle")
    if parsed[2]["ts"] != entry_ts:
        raise ValueError("entry timestamp does not match actual next-H1 candle")

    fill_price = float(parsed[2]["open"])
    if not stop < fill_price < target:
        return None

    risk_per_unit = fill_price - stop
    gross_reward_per_unit = target - fill_price
    return {
        "strategy": H_B_STRATEGY,
        "direction": "long",
        "policy_version": H_B_POLICY_VERSION,
        "fill_model": "next_h1_open_reference_only",
        "entry_ts_ms": int(parsed[2]["ts"]),
        "entry_price": fill_price,
        "fill_ts_ms": int(parsed[2]["ts"]),
        "fill_price": fill_price,
        "stop_price": stop,
        "target_price": target,
        "risk_per_unit": risk_per_unit,
        "gross_reward_per_unit": gross_reward_per_unit,
        "gross_reward_to_risk": gross_reward_per_unit / risk_per_unit,
    }
