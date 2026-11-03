from __future__ import annotations

"""Research-only causal market-structure filters. No production signal changes."""


def ema_series(values, period):
    """Full-history recursive EMA values; input must be chronological and closed."""
    if isinstance(period, bool) or not isinstance(period, int) or period < 1:
        raise ValueError("EMA period must be a positive integer")
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    current = float(values[0])
    output = [current]
    for item in values[1:]:
        current += alpha * (float(item) - current)
        output.append(current)
    return output


def ema(values, period):
    """Return the final value of the full-history recursive EMA."""
    values = list(values)
    if not values:
        return 0.0
    return ema_series(values, period)[-1]


def trend_direction(candles, fast=10, slow=30, slope=5):
    """Classify up/down/neutral using full-history EMAs of closed candles only.

    Unlike a rolling-window EMA approximation, the EMA state is carried from the
    beginning of the supplied chronological history. Trend direction requires
    fast/slow alignment, slow-EMA slope, and close relative to the slow EMA.
    """
    if (
        isinstance(fast, bool) or not isinstance(fast, int) or fast < 1
        or isinstance(slow, bool) or not isinstance(slow, int) or slow < 2
        or isinstance(slope, bool) or not isinstance(slope, int) or slope < 1
        or fast >= slow
    ):
        raise ValueError("require 1 <= fast < slow and slope >= 1")
    closes = [float(c.close) for c in candles]
    if len(closes) < slow + slope + 1:
        return "neutral"
    fast_values = ema_series(closes, fast)
    slow_values = ema_series(closes, slow)
    fast_ema = fast_values[-1]
    slow_ema = slow_values[-1]
    prior_slow = slow_values[-slope - 1]
    if fast_ema > slow_ema and slow_ema > prior_slow and closes[-1] > slow_ema:
        return "up"
    if fast_ema < slow_ema and slow_ema < prior_slow and closes[-1] < slow_ema:
        return "down"
    return "neutral"


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
