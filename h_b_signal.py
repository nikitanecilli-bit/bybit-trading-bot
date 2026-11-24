"""Pure, synthetic-testable H-B v0.1 signal predicate.

This module intentionally does not integrate with the trading engine. It validates
only the causal H1 signal contract; execution, sizing, persistence, exits, PnL and
exchange behavior remain out of scope.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

H1_INTERVAL_MS = 3_600_000
H_B_POLICY_VERSION = "v0.1"
H_B_STRATEGY = "H-B-mean-reversion"


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


def evaluate_h_b_signal(
    candles: Sequence[Mapping[str, object]],
    regimes: Sequence[str],
    atr_values: Sequence[object],
    shock_index: int,
) -> dict[str, Any] | None:
    """Evaluate one proposed shock index using data available through t+1 only.

    Contract:
      * regime[t-1] must already be "range";
      * close[t] <= close[t-24] - 2 * ATR[t-1];
      * close[t+1] > high[t];
      * entry is scheduled for the next H1 open (t+2), never at close[t+1].

    Returns None when a validly shaped input does not satisfy the signal. Invalid
    data raises ValueError (fail closed). The function does not inspect candles
    after t+1, does not choose RegimeConfig thresholds, and does not simulate a
    fill or position lifecycle.
    """
    if isinstance(shock_index, bool) or not isinstance(shock_index, int):
        raise ValueError("shock_index must be an integer")
    if len(candles) != len(regimes) or len(candles) != len(atr_values):
        raise ValueError("candles, regimes and atr_values must have equal lengths")
    if shock_index < 24 or shock_index + 1 >= len(candles):
        return None

    start = shock_index - 24
    end = shock_index + 1
    used_rows = candles[start : end + 1]
    parsed: list[dict[str, float | int]] = []
    previous_ts: int | None = None

    for offset, row in enumerate(used_rows):
        absolute_index = start + offset
        raw_ts = row.get("ts")
        if isinstance(raw_ts, bool) or not isinstance(raw_ts, int) or raw_ts <= 0:
            raise ValueError(f"candle[{absolute_index}].ts must be a positive integer")
        ts = raw_ts
        if previous_ts is not None and ts - previous_ts != H1_INTERVAL_MS:
            raise ValueError("H-B requires an uninterrupted exact H1 timestamp grid")
        op = _positive_finite(row.get("open"), f"candle[{absolute_index}].open")
        high = _positive_finite(row.get("high"), f"candle[{absolute_index}].high")
        low = _positive_finite(row.get("low"), f"candle[{absolute_index}].low")
        close = _positive_finite(row.get("close"), f"candle[{absolute_index}].close")
        if high < max(op, low, close) or low > min(op, high, close):
            raise ValueError(f"candle[{absolute_index}] has invalid OHLC boundaries")
        parsed.append({"ts": ts, "open": op, "high": high, "low": low, "close": close})
        previous_ts = ts

    atr_previous = _positive_finite(atr_values[shock_index - 1], "ATR[t-1]")
    if regimes[shock_index - 1] != "range":
        return None

    pre_shock_closes = [
        float(candles[index]["close"])
        for index in range(shock_index - 24, shock_index)
    ]
    shock = parsed[24]
    stabilization = parsed[25]
    shock_threshold = pre_shock_closes[0] - 2.0 * atr_previous
    if float(shock["close"]) > shock_threshold:
        return None
    if float(stabilization["close"]) <= float(shock["high"]):
        return None

    stop_price = float(shock["low"])
    target_price = sum(pre_shock_closes) / 24.0
    if stop_price >= target_price:
        return None

    signal_ts_ms = int(stabilization["ts"])
    return {
        "strategy": H_B_STRATEGY,
        "direction": "long",
        "policy_version": H_B_POLICY_VERSION,
        "shock_index": shock_index,
        "shock_ts_ms": int(shock["ts"]),
        "signal_ts_ms": signal_ts_ms,
        "entry_ts_ms": signal_ts_ms + H1_INTERVAL_MS,
        "stop_price": stop_price,
        "target_price": target_price,
    }
