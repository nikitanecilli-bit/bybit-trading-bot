"""Unit tests for per-regime baseline report helpers."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from types import SimpleNamespace

from scripts.run_regime_analysis import summarize_trades, trade_signal_regime


def trade(entry_date, pnl, r=0.0, fees=1.0, slip=0.5, signal_ts_ms=None):
    return SimpleNamespace(
        entry_date=entry_date, pnl_usdt=pnl, r_multiple=r,
        exchange_fees_usdt=fees, slippage_cost_usdt=slip,
        signal_ts_ms=signal_ts_ms,
    )


def test_signal_regime_uses_previous_completed_candle():
    # Entry at 01:00 on an hourly chart belongs to the signal candle opened at 00:00.
    t = trade("2026-01-01T01:00:00Z", 10)
    labels = {1_767_225_600_000: "trend_up"}  # 2026-01-01T00:00:00Z
    assert trade_signal_regime(t, labels, 3_600_000) == "trend_up"


def test_exact_original_signal_timestamp_overrides_entry_time_fallback():
    # The fill is delayed: the original signal candle is at 00:00, not 03:00.
    t = trade("2026-01-01T04:00:00Z", 10, signal_ts_ms=1_767_225_600_000)
    labels = {
        1_767_225_600_000: "trend_up",  # 2026-01-01T00:00:00Z
        1_767_236_400_000: "range",     # 2026-01-01T03:00:00Z
    }
    assert trade_signal_regime(t, labels, 3_600_000) == "trend_up"


def test_invalid_exact_signal_timestamp_fails_closed():
    t = trade("2026-01-01T04:00:00Z", 10, signal_ts_ms="not-a-timestamp")
    labels = {1_767_236_400_000: "range"}
    assert trade_signal_regime(t, labels, 3_600_000) == "unknown"


def test_missing_signal_candle_is_unknown():
    t = trade("2026-01-01T01:00:00Z", 10)
    assert trade_signal_regime(t, {}, 3_600_000) == "unknown"


def test_summary_reports_net_metrics_and_costs():
    trades = [trade("2026-01-01T01:00:00Z", 10, 0.5), trade("2026-01-01T02:00:00Z", -5, -0.2)]
    summary = summarize_trades(trades)
    assert summary["trades"] == 2
    assert summary["wins"] == 1
    assert summary["win_rate_pct"] == 50.0
    assert summary["net_pnl_usdt"] == 5.0
    assert summary["profit_factor"] == 2.0
    assert summary["expectancy_r"] == 0.15
    assert summary["fees_usdt"] == 2.0
    assert summary["slippage_usdt"] == 1.0


def test_empty_summary_is_explicit():
    summary = summarize_trades([])
    assert summary["trades"] == 0
    assert summary["net_pnl_usdt"] == 0.0
    assert summary["expectancy_r"] == ""


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("All regime-analysis report tests passed.")
