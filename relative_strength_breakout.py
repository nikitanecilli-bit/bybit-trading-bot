"""Causal H1 cross-sectional relative-strength breakout hypothesis (H-A).

This module contains pure feature/signal functions. It does not fetch data,
run a backtest, or place orders.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

H1_MS = 3_600_000
FAST_LOOKBACK = 24
SLOW_LOOKBACK = 72
ATR_PERIOD = 14
DONCHIAN_PERIOD = 20
MIN_CROSS_SECTION = 5
LONG_RANK_THRESHOLD = 0.80
SHORT_RANK_THRESHOLD = 0.20


def _atr_from_completed_bars(rows: List[Any], period: int = ATR_PERIOD) -> float:
    if len(rows) < period + 1:
        return 0.0
    tail = rows[-(period + 1):]
    true_ranges = []
    for index in range(1, len(tail)):
        current, previous = tail[index], tail[index - 1]
        true_ranges.append(max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        ))
    return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0


def _midranks(scores: Dict[str, float]) -> Dict[str, float]:
    if not scores:
        return {}
    count = len(scores)
    if count == 1:
        return {next(iter(scores)): 0.5}
    result = {}
    for symbol, score in scores.items():
        lower = sum(value < score for value in scores.values())
        equal = sum(value == score for value in scores.values())
        result[symbol] = (lower + (equal - 1) / 2.0) / (count - 1)
    return result


def build_strength_context(
    as_of_ts: int,
    histories: Dict[str, List[Any]],
    _cfg: Any = None,
    *,
    min_cross_section: int = MIN_CROSS_SECTION,
) -> Dict[str, Any]:
    """Build timestamp-causal normalized 24h/72h strength and cross-section ranks.

    histories must contain only actual bars available at as_of_ts. A history is
    eligible after 72 completed hourly lookback bars plus the current bar.
    """
    if isinstance(as_of_ts, bool) or not isinstance(as_of_ts, int) or as_of_ts <= 0:
        raise ValueError("as_of_ts must be a positive integer")
    if min_cross_section < 1:
        raise ValueError("min_cross_section must be positive")

    scores: Dict[str, float] = {}
    for symbol, rows in histories.items():
        if not rows:
            continue
        if rows[-1].ts + H1_MS != as_of_ts:
            raise ValueError(
                f"{symbol}: history is not aligned to requested H1 close boundary"
            )
        if len(rows) < SLOW_LOOKBACK + 1:
            continue
        close = float(rows[-1].close)
        close_24 = float(rows[-1 - FAST_LOOKBACK].close)
        close_72 = float(rows[-1 - SLOW_LOOKBACK].close)
        if min(close, close_24, close_72) <= 0:
            continue
        atr = _atr_from_completed_bars(rows[:-1], ATR_PERIOD)
        atr_pct = atr / close if close > 0 else 0.0
        if not math.isfinite(atr_pct) or atr_pct <= 0:
            continue
        ret_24 = close / close_24 - 1.0
        ret_72 = close / close_72 - 1.0
        score = (0.5 * ret_24 + 0.5 * ret_72) / atr_pct
        if math.isfinite(score):
            scores[symbol] = score

    ranks = _midranks(scores) if len(scores) >= min_cross_section else {}
    return {
        "as_of_ts": as_of_ts,
        "scores": scores,
        "ranks": ranks,
        "eligible_symbols": tuple(sorted(scores)),
        "cross_section_size": len(scores),
        "min_cross_section": min_cross_section,
    }


def evaluate_relative_strength_breakout(
    symbol: str,
    candles: List[Any],
    cfg: Any,
    context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Frozen H-A signal: Donchian(20) breakout gated by cross-sectional RS rank."""
    if str(getattr(cfg, "timeframe", "")).strip().lower() != "1h":
        return None
    if len(candles) < SLOW_LOOKBACK + 1:
        return None
    if symbol in getattr(cfg, "disabled_instruments", set()):
        return None
    if symbol not in getattr(cfg, "active_trading_pool", []):
        return None
    if symbol not in context.get("ranks", {}):
        return None

    current = candles[-1]
    if context.get("as_of_ts") != current.ts + H1_MS:
        raise ValueError("H-A context timestamp does not match signal candle close")
    session_hour = datetime.fromtimestamp(
        current.ts / 1000.0, tz=timezone.utc,
    ).hour
    session = "asia" if session_hour < 8 else ("eu" if session_hour < 16 else "us")
    signal_dt = datetime.fromtimestamp(current.ts / 1000.0, tz=timezone.utc)
    if session in getattr(cfg, "blocked_sessions_utc", set()):
        return None
    if signal_dt.weekday() in getattr(cfg, "blocked_weekdays_utc", set()):
        return None
    if signal_dt.hour in getattr(cfg, "blocked_signal_hours_utc", set()):
        return None
    max_chase = float(getattr(cfg, "max_chase_limit_pct", 100.0))
    if current.open > 0 and abs(current.close - current.open) / current.open * 100.0 > max_chase:
        return None

    previous = candles[:-1]
    donchian = previous[-DONCHIAN_PERIOD:]
    if len(donchian) < DONCHIAN_PERIOD:
        return None
    upper = max(float(row.high) for row in donchian)
    lower = min(float(row.low) for row in donchian)
    atr = _atr_from_completed_bars(previous, ATR_PERIOD)
    if atr <= 0:
        return None

    rank = float(context["ranks"][symbol])
    direction = None
    if current.close > upper and rank >= LONG_RANK_THRESHOLD:
        direction = "long"
    elif current.close < lower and rank <= SHORT_RANK_THRESHOLD:
        direction = "short"
    if direction is None or direction in getattr(cfg, "blocked_directions", set()):
        return None

    stop_dist = atr * float(cfg.stop_atr_mult)
    if stop_dist <= 0:
        return None
    if direction == "long":
        stop_price = current.close - stop_dist
        tp1 = current.close + stop_dist * float(cfg.tp1_r_multiple)
        tp2 = current.close + stop_dist * float(cfg.tp2_r_multiple)
    else:
        stop_price = current.close + stop_dist
        tp1 = current.close - stop_dist * float(cfg.tp1_r_multiple)
        tp2 = current.close - stop_dist * float(cfg.tp2_r_multiple)

    score = float(context["scores"][symbol])
    return {
        "symbol": symbol,
        "direction": direction,
        "strategy": "H-A-relative-strength-breakout",
        "signal_ts": current.ts,
        "entry_price": float(current.close),
        "stop_price": stop_price,
        "tp1_price": tp1,
        "tp2_price": tp2,
        "stop_dist": stop_dist,
        "atr": atr,
        "breakout_level": upper if direction == "long" else lower,
        "vol_ratio": 1.0,
        "priority_score": abs(score),
        "relative_strength_score": score,
        "relative_strength_rank": rank,
        "cross_section_size": int(context["cross_section_size"]),
        "session": session,
        "order_type": "market",
    }
