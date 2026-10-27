from __future__ import annotations

"""Research-only causal market-structure filters. No production signal changes."""


def ema(values, period):
    if not values or period < 1:
        return 0.0
    alpha = 2.0 / (period + 1.0)
    value = float(values[0])
    for item in values[1:]:
        value += alpha * (float(item) - value)
    return value


def trend_direction(candles, fast=10, slow=30, slope=5):
    """Classify up/down/neutral using closed candles only."""
    closes = [float(c.close) for c in candles]
    if len(closes) < slow + slope + 1:
        return "neutral"
    fast_ema = ema(closes[-fast:], fast)
    slow_ema = ema(closes[-slow:], slow)
    prior_slow = ema(closes[-(slow + slope):-slope], slow)
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
