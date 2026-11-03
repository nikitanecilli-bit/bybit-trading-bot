from __future__ import annotations

import math

"""Research-only causal market-structure filters. No production signal changes."""


def ema_series(values, period):
    """Full-history recursive EMA values; input must be chronological and closed."""
    if isinstance(period, bool) or not isinstance(period, int) or period < 1:
        raise ValueError("EMA period must be a positive integer")
    if not values:
        return []
    try:
        numeric_values = [float(item) for item in values]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("EMA values must be numeric") from exc
    if any(not math.isfinite(item) for item in numeric_values):
        raise ValueError("EMA values must be finite")
    alpha = 2.0 / (period + 1.0)
    current = numeric_values[0]
    output = [current]
    for item in numeric_values[1:]:
        current += alpha * (item - current)
        output.append(current)
    return output


def ema(values, period):
    """Return the final value of the full-history recursive EMA."""
    values = list(values)
    if not values:
        return 0.0
    return ema_series(values, period)[-1]


def _validate_trend_periods(fast, slow, slope):
    if (
        isinstance(fast, bool) or not isinstance(fast, int) or fast < 1
        or isinstance(slow, bool) or not isinstance(slow, int) or slow < 2
        or isinstance(slope, bool) or not isinstance(slope, int) or slope < 1
        or fast >= slow
    ):
        raise ValueError("require 1 <= fast < slow and slope >= 1")


def trend_direction_series(candles, fast=10, slow=30, slope=5):
    """Return causal up/down/neutral labels for every completed candle.

    Full-history EMA states are computed once in O(N); use this function rather
    than calling trend_direction repeatedly inside a per-bar replay.
    """
    _validate_trend_periods(fast, slow, slope)
    try:
        timestamps = [int(c.ts) for c in candles]
        closes = [float(c.close) for c in candles]
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("trend candles must expose timestamp and numeric close values") from exc
    if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
        raise ValueError("trend candle timestamps must be strictly increasing")
    if any(not math.isfinite(close) or close <= 0 for close in closes):
        raise ValueError("trend candle closes must be finite and > 0")
    if not closes:
        return []
    fast_values = ema_series(closes, fast)
    slow_values = ema_series(closes, slow)
    output = ["neutral"] * len(closes)
    for i in range(slow + slope, len(closes)):
        fast_ema = fast_values[i]
        slow_ema = slow_values[i]
        prior_slow = slow_values[i - slope]
        if fast_ema > slow_ema and slow_ema > prior_slow and closes[i] > slow_ema:
            output[i] = "up"
        elif fast_ema < slow_ema and slow_ema < prior_slow and closes[i] < slow_ema:
            output[i] = "down"
    return output



def trend_label_index(candles, fast=50, slow=200, slope=5,
                      burn_in_bars=None, expected_interval_ms=None):
    """Build an exact timestamp->trend map with conservative EMA seed burn-in.

    The default burn-in is five slow-EMA periods (1,000 H1 bars for EMA200).
    Labels are causal at each candle close. Timestamps are exact bar-open keys;
    callers must not substitute nearest/stale labels.
    """
    _validate_trend_periods(fast, slow, slope)
    if burn_in_bars is None:
        burn_in_bars = 5 * slow
    if (isinstance(burn_in_bars, bool) or not isinstance(burn_in_bars, int)
            or burn_in_bars < 5 * slow):
        raise ValueError("EMA trend burn-in must be an integer >= 5 * slow period")
    if expected_interval_ms is not None:
        if (isinstance(expected_interval_ms, bool)
                or not isinstance(expected_interval_ms, int)
                or expected_interval_ms <= 0):
            raise ValueError("expected_interval_ms must be a positive integer")
    timestamps = []
    for candle in candles:
        ts = getattr(candle, "ts", None)
        if isinstance(ts, bool) or not isinstance(ts, int) or ts <= 0:
            raise ValueError("trend label timestamps must be positive integer milliseconds")
        timestamps.append(ts)
    if len(candles) <= burn_in_bars:
        raise ValueError(
            f"EMA trend context requires at least {burn_in_bars + 1} candles "
            "to complete the configured seed burn-in"
        )
    labels = trend_direction_series(candles, fast=fast, slow=slow, slope=slope)
    output = {}
    for i, ts in enumerate(timestamps):
        if i and ts <= timestamps[i - 1]:
            raise ValueError("trend label timestamps must be strictly increasing and unique")
        if expected_interval_ms is not None and i and ts - timestamps[i - 1] != expected_interval_ms:
            raise ValueError("trend label candles must be contiguous at expected_interval_ms")
        output[ts] = labels[i] if i >= burn_in_bars else "neutral"
    return output


def lookup_trend_label(label_index, timestamp_ms):
    """Return only the exact timestamp label; missing context fails closed."""
    if not isinstance(label_index, dict):
        raise ValueError("trend label index must be a timestamp mapping")
    if isinstance(timestamp_ms, bool) or not isinstance(timestamp_ms, int):
        raise ValueError("trend lookup timestamp must be an integer")
    if timestamp_ms not in label_index:
        raise KeyError(f"no exact trend label for candle timestamp {timestamp_ms}")
    label = label_index[timestamp_ms]
    if label not in {"up", "down", "neutral"}:
        raise ValueError(f"invalid trend label at timestamp {timestamp_ms}: {label!r}")
    return label


def trend_direction(candles, fast=10, slow=30, slope=5):
    """Return the latest causal trend label using full-history EMAs."""
    labels = trend_direction_series(candles, fast=fast, slow=slow, slope=slope)
    return labels[-1] if labels else "neutral"


def _atr(candles, period=14):
    if len(candles) < 2:
        return 0.0
    tail = candles[-(period + 1):]
    tr = []
    for i in range(1, len(tail)):
        cur, prev = tail[i], tail[i - 1]
        tr.append(max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close)))
    return sum(tr) / len(tr) if tr else 0.0


def breakout_quality(candles, direction, lookback=20, approach_bars=3,
                     min_volume_ratio=1.6, min_body_atr=0.6,
                     compact_range_ratio=0.85):
    """Require tight approach near a prior level, rising volume, and an impulse close.

    candles includes the completed breakout candle. Support/resistance is calculated
    before the approach window, avoiding use of the breakout candle in its own level.
    """
    if direction not in ("long", "short"):
        return False
    if len(candles) < lookback + approach_bars + 15:
        return False
    curr = candles[-1]
    prior = candles[:-1]
    level_window = prior[-(lookback + approach_bars):-approach_bars]
    approach = prior[-approach_bars:]
    if len(level_window) != lookback or len(approach) != approach_bars:
        return False
    level = max(c.high for c in level_window) if direction == "long" else min(c.low for c in level_window)
    atr = _atr(prior, 14)
    if atr <= 0:
        return False
    # Require approach candles to remain within 0.75 ATR of the level.
    if direction == "long":
        near = all(-0.15 * atr <= level - c.close <= 0.75 * atr for c in approach)
    else:
        near = all(-0.15 * atr <= c.close - level <= 0.75 * atr for c in approach)
    ref_ranges = sorted(c.high - c.low for c in level_window)
    median_range = ref_ranges[len(ref_ranges) // 2]
    avg_approach_range = sum(c.high - c.low for c in approach) / approach_bars
    compact = median_range > 0 and avg_approach_range <= median_range * compact_range_ratio
    approach_volumes = [float(c.volume) for c in approach]
    ref_avg_volume = sum(float(c.volume) for c in level_window) / lookback
    rising_volume = (approach_volumes[-1] >= approach_volumes[0]
                     and sum(approach_volumes) / approach_bars >= ref_avg_volume)
    if not (near and compact and rising_volume):
        return False
    avg_volume = sum(float(c.volume) for c in prior[-lookback:]) / lookback
    volume_ratio = float(curr.volume) / avg_volume if avg_volume > 0 else 0.0
    body_atr = abs(float(curr.close) - float(curr.open)) / atr
    candle_range = max(float(curr.high) - float(curr.low), 1e-12)
    close_pos = (float(curr.close) - float(curr.low)) / candle_range
    if direction == "long":
        impulse = curr.close > level and body_atr >= min_body_atr and close_pos >= 0.75
    else:
        impulse = curr.close < level and body_atr >= min_body_atr and close_pos <= 0.25
    return bool(impulse and volume_ratio >= min_volume_ratio)

def previous_bar_breakout_confirmed(candles, direction, lookback=20):
    """True if the candle immediately before the current signal closed beyond its
    Donchian boundary calculated strictly from candles before that confirmation bar.
    The current signal candle is present as candles[-1] and is not used.
    """
    if direction not in ("long", "short") or len(candles) < lookback + 2:
        return False
    confirmation = candles[-2]
    reference = candles[-(lookback + 2):-2]
    if len(reference) != lookback:
        return False
    level = max(c.high for c in reference) if direction == "long" else min(c.low for c in reference)
    return confirmation.close > level if direction == "long" else confirmation.close < level
