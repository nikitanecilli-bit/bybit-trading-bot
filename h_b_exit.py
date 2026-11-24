"""Synthetic-only H-B exit contract; no engine or market-PnL integration."""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from h_b_signal import H1_INTERVAL_MS, H_B_POLICY_VERSION, H_B_STRATEGY

H_B_TIME_STOP_BARS = 24


def _finite_positive(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be finite and positive")
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be finite and positive") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return parsed


def evaluate_h_b_exit(
    position: Mapping[str, object],
    candle: Mapping[str, object],
    bars_held: int,
) -> dict[str, Any] | None:
    """Evaluate one completed H1 bar under the frozen synthetic exit candidate.

    Ordering: protective stop (including stop gap) -> mean target -> 24-bar
    close-based time stop. The fill bar (bars_held=1) has protective stop active,
    but discretionary target is disabled because its high may predate the fill.
    Stop wins when stop and target are both touched. Target gaps receive no
    price improvement. Fees, slippage, funding and executable fills are out of
    scope.
    """
    if not isinstance(position, Mapping) or not isinstance(candle, Mapping):
        raise ValueError("position and candle must be mappings")
    if position.get("strategy") != H_B_STRATEGY or position.get("direction") != "long":
        raise ValueError("position must be an H-B long position")
    if position.get("policy_version") != H_B_POLICY_VERSION:
        raise ValueError("unsupported H-B exit policy version")
    if isinstance(bars_held, bool) or not isinstance(bars_held, int):
        raise ValueError("bars_held must be an integer")
    if bars_held < 1 or bars_held > H_B_TIME_STOP_BARS:
        raise ValueError("bars_held must be within the H-B holding window")

    entry_ts = position.get("entry_ts_ms")
    candle_ts = candle.get("ts")
    if isinstance(entry_ts, bool) or not isinstance(entry_ts, int) or entry_ts <= 0:
        raise ValueError("position entry_ts_ms must be a positive integer")
    if isinstance(candle_ts, bool) or not isinstance(candle_ts, int) or candle_ts <= 0:
        raise ValueError("candle ts must be a positive integer")
    expected_ts = entry_ts + (bars_held - 1) * H1_INTERVAL_MS
    if candle_ts != expected_ts:
        raise ValueError("H-B exit candle timestamp does not match bars_held")

    entry = _finite_positive(position.get("entry_price"), "entry_price")
    stop = _finite_positive(position.get("stop_price"), "stop_price")
    target = _finite_positive(position.get("target_price"), "target_price")
    if not stop < entry < target:
        raise ValueError("H-B long position requires stop < entry < target")

    op = _finite_positive(candle.get("open"), "candle open")
    high = _finite_positive(candle.get("high"), "candle high")
    low = _finite_positive(candle.get("low"), "candle low")
    close = _finite_positive(candle.get("close"), "candle close")
    if high < max(op, low, close) or low > min(op, high, close):
        raise ValueError("candle has invalid OHLC boundaries")

    reason: str | None = None
    exit_price: float | None = None
    if low <= stop:
        reason = "h_b_stop"
        exit_price = min(stop, op)
    elif bars_held > 1 and high >= target:
        reason = "h_b_mean_target"
        exit_price = target
    elif bars_held == H_B_TIME_STOP_BARS:
        reason = "h_b_time_stop"
        exit_price = close

    if reason is None or exit_price is None:
        return None
    return {
        "strategy": H_B_STRATEGY,
        "policy_version": H_B_POLICY_VERSION,
        "exit_reason": reason,
        "exit_ts_ms": candle_ts,
        "exit_price": exit_price,
        "bars_held": bars_held,
    }
