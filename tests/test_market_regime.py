"""Regression tests for causal market-regime classification."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from market_regime import RegimeConfig, classify_candles


def make_candles(closes, width=0.4):
    rows = []
    ts0 = 1_800_000_000_000
    for i, close in enumerate(closes):
        rows.append({
            "ts": ts0 + i * 900_000,
            "open": close,
            "high": close + width,
            "low": max(0.01, close - width),
            "close": close,
            "volume": 100 + i,
        })
    return rows


def test_empty_input():
    assert classify_candles([]) == []


def test_warmup_is_unknown():
    cfg = RegimeConfig(
        efficiency_period=5, atr_period=3, ema_fast_period=3,
        ema_slow_period=6, slope_lookback=2, volatility_lookback=8,
    )
    out = classify_candles(make_candles([100 + i for i in range(7)]), cfg)
    assert all(row["regime"] == "unknown" for row in out)


def test_persistent_rise_is_uptrend():
    cfg = RegimeConfig(
        efficiency_period=8, atr_period=5, ema_fast_period=3,
        ema_slow_period=8, slope_lookback=3, volatility_lookback=10,
        trend_er_min=0.3, trend_slope_atr_min=0.1,
    )
    closes = [100 + i * 2 for i in range(80)]
    out = classify_candles(make_candles(closes, width=0.2), cfg)
    assert out[-1]["regime"] == "trend_up", out[-1]



def test_rising_fast_ema_below_slow_ema_is_not_trend_up():
    cfg = RegimeConfig(
        efficiency_period=8, atr_period=5, ema_fast_period=3,
        ema_slow_period=8, slope_lookback=3, volatility_lookback=10,
        trend_er_min=0.3, trend_slope_atr_min=0.1,
    )
    closes = [300.0] * 50 + [100.0 + i * 0.5 for i in range(30)]
    row = classify_candles(make_candles(closes, width=0.2), cfg)[-1]
    assert row["ema_alignment"] == "down"
    assert row["regime"] != "trend_up"
    assert row["regime"] == "transition"



def test_persistent_fall_is_downtrend():
    cfg = RegimeConfig(
        efficiency_period=8, atr_period=5, ema_fast_period=3,
        ema_slow_period=8, slope_lookback=3, volatility_lookback=10,
        trend_er_min=0.3, trend_slope_atr_min=0.1,
    )
    closes = [300 - i * 2 for i in range(80)]
    out = classify_candles(make_candles(closes, width=0.2), cfg)
    assert out[-1]["regime"] == "trend_down", out[-1]


def test_oscillating_series_is_not_trend():
    cfg = RegimeConfig(
        efficiency_period=10, atr_period=5, ema_fast_period=3,
        ema_slow_period=8, slope_lookback=3, volatility_lookback=10,
        trend_er_min=0.4, trend_slope_atr_min=0.3,
    )
    closes = [100 + (3 if i % 2 else -3) for i in range(80)]
    out = classify_candles(make_candles(closes, width=0.3), cfg)
    assert out[-1]["regime"] in {"range", "transition", "high_vol_chop"}, out[-1]
    assert out[-1]["regime"] not in {"trend_up", "trend_down"}


def test_no_lookahead_future_change_does_not_rewrite_past_labels():
    cfg = RegimeConfig(
        efficiency_period=5, atr_period=3, ema_fast_period=3,
        ema_slow_period=6, slope_lookback=2, volatility_lookback=8,
    )
    base = [100 + i * 0.8 for i in range(40)]
    first = classify_candles(make_candles(base), cfg)
    extended = classify_candles(make_candles(base + [1000, 10, 1500, 5]), cfg)
    assert [r["regime"] for r in first] == [r["regime"] for r in extended[:len(first)]]


def test_bad_ohlc_rejected():
    rows = make_candles([100, 101, 102])
    rows[1]["high"] = 1
    try:
        classify_candles(rows)
    except ValueError as exc:
        assert "OHLC" in str(exc)
    else:
        raise AssertionError("invalid OHLC must be rejected")


def test_duplicate_timestamp_rejected():
    rows = make_candles([100, 101, 102])
    rows[2]["ts"] = rows[1]["ts"]
    try:
        classify_candles(rows)
    except ValueError as exc:
        assert "strictly increasing" in str(exc)
    else:
        raise AssertionError("duplicate timestamps must be rejected")


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("All market-regime tests passed.")
