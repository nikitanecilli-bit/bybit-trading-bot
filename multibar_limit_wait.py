"""Deterministic multi-bar limit-wait policy for research harnesses.

This module does not model exchange queue priority or guarantee a maker fill.
It only decides whether an OHLC candle penetrated a configured limit threshold.
"""
from __future__ import annotations


def evaluate_limit_wait(
    direction: str,
    low: float,
    high: float,
    limit_price: float,
    penetration_bps: float,
    age: int,
    max_wait_bars: int,
) -> tuple[str, int]:
    """Return (fill|wait|expire, updated_age) for one eligible candle."""
    side = str(direction).strip().lower()
    if side not in {"long", "short"}:
        raise ValueError(f"unsupported direction: {direction!r}")
    values = (low, high, limit_price, penetration_bps)
    if any(not isinstance(value, (int, float)) for value in values):
        raise TypeError("OHLC and limit parameters must be numeric")
    if not all(__import__("math").isfinite(float(value)) for value in values):
        raise ValueError("OHLC and limit parameters must be finite")
    if low <= 0 or high <= 0 or limit_price <= 0 or low > high:
        raise ValueError("invalid OHLC/limit price range")
    if penetration_bps < 0 or age < 0 or max_wait_bars < 1:
        raise ValueError("penetration_bps, age, and max_wait_bars are out of range")

    next_age = age + 1
    penetration = (
        low <= limit_price * (1.0 - penetration_bps / 10_000.0)
        if side == "long"
        else high >= limit_price * (1.0 + penetration_bps / 10_000.0)
    )
    if penetration:
        return "fill", next_age
    if next_age >= max_wait_bars:
        return "expire", next_age
    return "wait", next_age


def prepare_signal_for_next_bar_fill(
    signal: dict,
    fill_bar_open_ts: int,
    timeframe_ms: int,
) -> int:
    """Adapt a delayed signal to the engine's strict next-bar fill contract.

    Preserve the actual signal timestamp separately. The engine consumes
    signal_ts only as a one-bar freshness guard; entry_ts is the fill candle.
    """
    if not isinstance(fill_bar_open_ts, int) or isinstance(fill_bar_open_ts, bool):
        raise TypeError("fill_bar_open_ts must be an integer")
    if not isinstance(timeframe_ms, int) or isinstance(timeframe_ms, bool) or timeframe_ms <= 0:
        raise ValueError("timeframe_ms must be a positive integer")
    original_ts = signal.get("signal_origin_ts", signal.get("signal_ts"))
    if not isinstance(original_ts, int) or isinstance(original_ts, bool):
        raise ValueError("signal must contain an integer signal_ts")
    signal["signal_origin_ts"] = original_ts
    signal["signal_ts"] = fill_bar_open_ts - timeframe_ms
    return original_ts
