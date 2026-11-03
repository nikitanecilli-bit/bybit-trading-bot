"""Causal signal-candle feature reconstruction tests."""
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import Bybit_Trading_Engine_v14_research as em
from scripts.diagnose_h_a_signal_candles import H1_MS, _summarize_group, extract_signal_features


def _candle(ts, open_, high, low, close, volume=10.0):
    return em.Candle(ts, open_, high, low, close, volume)


def _fixture(direction="long"):
    start = 1_800_000_000_000
    rows = [
        _candle(start + i * H1_MS, 100.0, 101.0, 99.0, 100.0)
        for i in range(30)
    ]
    signal_ts = start + 30 * H1_MS
    if direction == "long":
        rows.append(_candle(signal_ts, 100.0, 103.0, 99.5, 102.5, 20.0))
        entry_price = 102.7
    else:
        rows.append(_candle(signal_ts, 100.0, 100.5, 97.0, 97.5, 20.0))
        entry_price = 97.3
    entry_ts = signal_ts + H1_MS
    rows.append(_candle(entry_ts, entry_price, entry_price + 0.2, entry_price - 0.2, entry_price))
    entry_date = datetime.fromtimestamp(entry_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    trade = {
        "symbol": "BTCUSDT",
        "direction": direction,
        "entry_date": entry_date,
        "exit_date": datetime.fromtimestamp((entry_ts + H1_MS) / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exit_reason": "stop_loss",
        "entry_price": entry_price,
        "size_usdt": 1_000.0,
        "risk_usdt": 50.0,
    }
    index = {row.ts: i for i, row in enumerate(rows)}
    return rows, index, trade


def test_long_signal_features_use_previous_closed_bar_and_pre_signal_history():
    rows, index, trade = _fixture("long")
    features = extract_signal_features(rows, index, trade)

    assert features["signal_ts_ms"] == rows[-2].ts
    assert abs(features["signal_range_atr"] - 1.75) < 1e-9
    assert abs(features["signal_body_atr"] - 1.25) < 1e-9
    assert abs(features["signal_directional_close_location"] - (3.0 / 3.5)) < 1e-9
    assert abs(features["signal_volume_ratio_20"] - 2.0) < 1e-9
    assert abs(features["breakout_close_clearance_atr"] - 0.75) < 1e-9
    assert abs(features["entry_adverse_gap_atr"] - 0.1) < 1e-9

    # Future bars after entry must not change features for this completed signal.
    future = _candle(rows[-1].ts + H1_MS, 102.8, 110.0, 90.0, 105.0, 1_000.0)
    extended = rows + [future]
    extended_index = {row.ts: i for i, row in enumerate(extended)}
    assert extract_signal_features(extended, extended_index, trade) == features


def test_short_signal_features_are_directionally_symmetric():
    rows, index, trade = _fixture("short")
    features = extract_signal_features(rows, index, trade)

    assert abs(features["signal_directional_body_atr"] - 1.25) < 1e-9
    assert abs(features["signal_directional_close_location"] - (3.0 / 3.5)) < 1e-9
    assert abs(features["breakout_close_clearance_atr"] - 0.75) < 1e-9
    assert abs(features["breakout_wick_overshoot_atr"] - 1.0) < 1e-9
    assert abs(features["entry_adverse_gap_atr"] - 0.1) < 1e-9


def test_signal_diagnostics_fail_closed_without_exact_entry_bar():
    rows, index, trade = _fixture("long")
    del index[rows[-1].ts]
    try:
        extract_signal_features(rows, index, trade)
    except ValueError as exc:
        assert "entry candle is absent" in str(exc)
    else:
        raise AssertionError("missing entry candle must fail closed")


def test_post_entry_followthrough_is_causal_and_exit_bar_is_excluded():
    rows, index, trade = _fixture("long")
    entry_ts = rows[-1].ts
    entry_price = float(trade["entry_price"])
    closes = [100.8, 102.0, 103.0, 104.0, 105.0]
    for offset, close in enumerate(closes, start=1):
        ts = entry_ts + offset * H1_MS
        rows.append(_candle(ts, close - 0.1, close + 0.5, close - 0.5, close, 12.0))
    index = {row.ts: i for i, row in enumerate(rows)}

    # A time-stop occurs at the sixth completed bar close, so all six bars count.
    trade["exit_date"] = datetime.fromtimestamp((entry_ts + 6 * H1_MS) / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    trade["exit_reason"] = "time_stop"
    features = extract_signal_features(rows, index, trade)
    assert features["post_entry_completed_bars"] == 6
    assert features["post_entry_retest_inside_3bars"] == 1
    assert features["post_entry_3bar_close_return_r"] < 0
    assert features["post_entry_6bar_close_return_r"] > 0
    assert features["post_entry_first3_max_adverse_r"] > 0

    # An intrabar stop on the sixth bar must not use that bar's later close.
    trade["exit_reason"] = "stop_loss"
    stopped = extract_signal_features(rows, index, trade)
    assert stopped["post_entry_completed_bars"] == 5
    assert stopped["post_entry_3bar_close_return_r"] == features["post_entry_3bar_close_return_r"]
    assert stopped["post_entry_6bar_close_return_r"] is None


def test_cohort_summary_reports_non_missing_feature_sample_counts():
    rows = [
        {"net_pnl": -10.0, "mfe_r": 0.4, "mae_r": 1.0, "post_entry_3bar_close_return_r": -0.2},
        {"net_pnl": 5.0, "mfe_r": 1.2, "mae_r": 0.3, "post_entry_3bar_close_return_r": None},
    ]
    summary = _summarize_group(rows, "1", "H-A", "stop_loss")
    assert summary["trades"] == 2
    assert summary["n_post_entry_3bar_close_return_r"] == 1
    assert summary["avg_post_entry_3bar_close_return_r"] == -0.2


def test_signal_diagnostics_reject_non_next_bar_entry():
    rows, index, trade = _fixture("long")
    rows[-1].ts += H1_MS
    index = {row.ts: i for i, row in enumerate(rows)}
    trade["entry_date"] = datetime.fromtimestamp(rows[-1].ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        extract_signal_features(rows, index, trade)
    except ValueError as exc:
        assert "strict next-H1-bar entry" in str(exc)
    else:
        raise AssertionError("non-next-bar entry must fail closed")


if __name__ == "__main__":
    tests = [
        test_long_signal_features_use_previous_closed_bar_and_pre_signal_history,
        test_short_signal_features_are_directionally_symmetric,
        test_signal_diagnostics_fail_closed_without_exact_entry_bar,
        test_signal_diagnostics_reject_non_next_bar_entry,
        test_post_entry_followthrough_is_causal_and_exit_bar_is_excluded,
        test_cohort_summary_reports_non_missing_feature_sample_counts,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} tests passed")
