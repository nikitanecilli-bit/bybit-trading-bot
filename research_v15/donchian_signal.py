"""Isolated v15 swing-signal prototype.

This module intentionally contains signal generation only. It does not place orders,
simulate fills, or claim profitability. Signals use completed OHLC candles and never
include the breakout candle in its own Donchian range.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

Candle = Mapping[str, float]
Signal = Literal["long", "short"] | None


def _validate_candles(candles: Sequence[Candle]) -> None:
    for i, candle in enumerate(candles):
        missing = {"open", "high", "low", "close"} - candle.keys()
        if missing:
            raise ValueError(f"Candle {i} missing fields: {sorted(missing)}")
        high = float(candle["high"])
        low = float(candle["low"])
        open_ = float(candle["open"])
        close = float(candle["close"])
        if low > high or not (low <= open_ <= high) or not (low <= close <= high):
            raise ValueError(f"Invalid OHLC values at candle {i}")


def ema(values: Sequence[float], period: int) -> list[float]:
    """Return an EMA seeded with the first value; no future values are used."""
    if period < 1:
        raise ValueError("period must be >= 1")
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(alpha * float(value) + (1.0 - alpha) * result[-1])
    return result


def donchian_breakout(
    candles: Sequence[Candle], index: int, period: int = 48
) -> Signal:
    """Signal on candle index close versus the previous period candles.

    Long: current close is strictly above prior highs maximum.
    Short: current close is strictly below prior lows minimum.
    The current candle is deliberately excluded from the range.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    if index < period or index >= len(candles):
        return None

    window = candles[index - period:index]
    prior_high = max(float(c["high"]) for c in window)
    prior_low = min(float(c["low"]) for c in window)
    close = float(candles[index]["close"])

    if close > prior_high:
        return "long"
    if close < prior_low:
        return "short"
    return None


def v15_signal(
    candles: Sequence[Candle],
    index: int,
    donchian_period: int = 48,
    ema_fast_period: int = 50,
    ema_slow_period: int = 200,
) -> Signal:
    """Combine Donchian close breakout with EMA trend filter.

    EMAs use only candles up to and including index. For a usable 50/200
    trend comparison, callers should supply at least 200 prior candles.
    """
    _validate_candles(candles)
    if index < 0 or index >= len(candles):
        raise IndexError("index is outside candle sequence")
    if ema_fast_period < 1 or ema_slow_period < 1:
        raise ValueError("EMA periods must be >= 1")

    breakout = donchian_breakout(candles, index, donchian_period)
    if breakout is None:
        return None

    closes = [float(c["close"]) for c in candles[:index + 1]]
    fast = ema(closes, ema_fast_period)[-1]
    slow = ema(closes, ema_slow_period)[-1]

    if breakout == "long" and fast > slow:
        return "long"
    if breakout == "short" and fast < slow:
        return "short"
    return None
