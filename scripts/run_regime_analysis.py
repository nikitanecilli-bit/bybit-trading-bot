#!/usr/bin/env python3
"""Report baseline backtest outcomes grouped by the regime at signal-candle close.

Input datasets are the uploaded Binance OHLCV ZIPs used by the existing research
runner. This is diagnostic analysis only: no regime filter is applied, and this
report does not include Bybit funding unless the underlying engine/data setup does.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import Bybit_Trading_Engine_v14_research as engine_mod
from market_regime import classify_candles
from scripts.run_uploaded_dataset_backtests import read_zip_datasets


TIMEFRAME_MS = {"15m": 900_000, "1h": 3_600_000}


def trade_signal_regime(trade, labels_by_candle_ts, timeframe_ms):
    """Use the last completed signal candle, never the entry candle's future OHLC."""
    entry_dt = datetime.strptime(trade.entry_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    entry_ts = int(entry_dt.timestamp() * 1000)
    signal_candle_ts = entry_ts - timeframe_ms
    return labels_by_candle_ts.get(signal_candle_ts, "unknown")


def summarize_trades(trades):
    count = len(trades)
    if not count:
        return {
            "trades": 0, "wins": 0, "win_rate_pct": "", "net_pnl_usdt": 0.0,
            "avg_net_pnl_usdt": "", "profit_factor": "", "expectancy_r": "",
            "fees_usdt": 0.0, "slippage_usdt": 0.0,
        }
    pnls = [float(t.pnl_usdt) for t in trades]
    rs = [float(t.r_multiple) for t in trades]
    gross_wins = sum(p for p in pnls if p > 0)
    gross_losses = -sum(p for p in pnls if p < 0)
    return {
        "trades": count,
        "wins": sum(p > 0 for p in pnls),
        "win_rate_pct": round(100.0 * sum(p > 0 for p in pnls) / count, 2),
        "net_pnl_usdt": round(sum(pnls), 2),
        "avg_net_pnl_usdt": round(sum(pnls) / count, 4),
        "profit_factor": round(gross_wins / gross_losses, 4) if gross_losses else ("inf" if gross_wins else 0.0),
        "expectancy_r": round(sum(rs) / count, 5),
        "fees_usdt": round(sum(float(t.exchange_fees_usdt) for t in trades), 2),
        "slippage_usdt": round(sum(float(t.slippage_cost_usdt) for t in trades), 2),
    }


def run(output_path):
    datasets = read_zip_datasets()
    if not datasets:
        raise SystemExit("No valid OHLCV datasets found in uploaded ZIP archives.")

    report = []
    for (symbol, timeframe), (bar_count, archive, candles) in sorted(datasets.items()):
        timeframe_ms = TIMEFRAME_MS[timeframe]
        rows = [
            {"ts": c.ts, "open": c.open, "high": c.high, "low": c.low,
             "close": c.close, "volume": c.volume}
            for c in candles
        ]
        labelled = classify_candles(rows)
        labels_by_ts = {int(row["ts"]): str(row["regime"]) for row in labelled}

        engine = engine_mod.UnifiedQuantEngine(
            journal_output_path="/tmp/ignored_regime_analysis_journal.json"
        )
        cfg = engine.cfg
        cfg.bot_version = "regime-analysis-baseline"
        cfg.timeframe = timeframe
        cfg.active_trading_pool = [symbol]
        cfg.capital_usdt = 10_000.0
        cfg.max_risk_trade_pct = 1.0
        cfg.max_portfolio_risk_pct = 2.0
        cfg.max_concurrent_positions = 1
        cfg.daily_stop_loss_pct = 5.0
        cfg.emergency_kill_switch_pct = 30.0
        cfg.donchian_period = 20
        cfg.atr_period = 14
        cfg.min_volume_ratio = 1.6
        cfg.stop_atr_mult = 2.5
        cfg.tp1_r_multiple = 2.0
        cfg.tp2_r_multiple = 5.0
        cfg.atr_trail_mult = 3.0
        cfg.max_hold_bars = 32
        cfg.maker_entry_and_tp1 = False
        cfg.enable_h2_range_fade = False
        cfg.validate()
        engine.risk_mgr.cfg = cfg
        engine.tg.send_message = lambda *_args, **_kwargs: None
        engine_mod.check_alignment({symbol: candles})
        engine_mod.run_simulation_pass(
            engine, {symbol: candles}, [symbol],
            data_label=f"BINANCE_PROXY {timeframe} {symbol}",
        )

        # Preserve both aggregate rows and the direction split. Direction is
        # the executed trade direction, while regime belongs to the completed
        # signal candle immediately before the entry candle.
        groups = defaultdict(list)
        for trade in engine.closed_trades:
            regime = trade_signal_regime(trade, labels_by_ts, timeframe_ms)
            groups[(regime, trade.direction.lower())].append(trade)
            groups[(regime, "both")].append(trade)
            groups[("__all__", trade.direction.lower())].append(trade)
            groups[("__all__", "both")].append(trade)

        for (regime, direction), trades in sorted(groups.items()):
            stats = summarize_trades(trades)
            report.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "archive": archive,
                "bars": bar_count,
                "regime": "all_baseline" if regime == "__all__" else regime,
                "direction": direction,
                **stats,
            })

    if not report:
        raise SystemExit("No regime-analysis rows were produced.")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fields = list(report[0].keys())
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report)
    print(f"Wrote {len(report)} symbol/timeframe/regime/direction rows to {output_path}")
    print("Reminder: regime grouping is descriptive, not evidence that a gate improves out-of-sample performance.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="regime_analysis.csv", help="Output summary CSV")
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
