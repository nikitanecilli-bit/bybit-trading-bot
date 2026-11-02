#!/usr/bin/env python3
"""Two-period H1 screen on symbols with continuous full-year archived coverage.

The first period is a chronological screening window; the second is a later
forward window. Every symbol uses the same dates and the baseline engine config.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import Bybit_Trading_Engine_v14_research as engine_mod
from scripts.run_uploaded_dataset_backtests import read_zip_datasets

WINDOWS = (
    ("screen_2025-10-27_to_2026-04-29", "2025-10-27T00:00:00+00:00", "2026-04-29T00:00:00+00:00"),
    ("forward_2026-04-29_to_2026-10-27", "2026-04-29T00:00:00+00:00", "2026-10-27T00:00:00+00:00"),
)


def ms(value: str) -> int:
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def run_one(symbol: str, candles: list, label: str) -> dict:
    engine = engine_mod.UnifiedQuantEngine(journal_output_path="/tmp/ignored_two_period_journal.json")
    cfg = engine.cfg
    cfg.bot_version = "h1-two-period-screen"
    cfg.timeframe = "1h"
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
    audit = engine_mod.run_simulation_pass(engine, {symbol: candles}, [symbol], data_label=label)
    trades = engine.closed_trades
    costs = sum(t.exchange_fees_usdt + t.slippage_cost_usdt for t in trades)
    return {
        "period": label, "symbol": symbol, "bars": len(candles),
        "trades": audit["total_trades"],
        "gross_pnl_usdt": round(sum(t.gross_pnl for t in trades), 2),
        "costs_usdt": round(costs, 2), "net_pnl_usdt": round(audit["net_pnl"], 2),
        "net_pf": round(audit["pf"], 4), "expectancy_r": round(audit["expectancy_r"], 4),
        "max_dd_pct": round(audit["max_dd_pct"], 2),
    }


def main() -> None:
    datasets = read_zip_datasets()
    eligible = {}
    start_all, end_all = ms(WINDOWS[0][1]), ms(WINDOWS[1][2])
    for (symbol, timeframe), (count, archive, candles) in datasets.items():
        if timeframe != "1h":
            continue
        if candles[0].ts <= start_all and candles[-1].ts >= end_all - 3_600_000:
            eligible[symbol] = candles
    print(f"ELIGIBLE_FULL_WINDOW_H1_SYMBOLS={len(eligible)}")
    if not eligible:
        raise SystemExit("No H1 symbols have continuous coverage across both windows.")
    results = []
    for symbol, full in sorted(eligible.items()):
        for label, start, end in WINDOWS:
            lo, hi = ms(start), ms(end)
            sliced = [c for c in full if lo <= c.ts < hi]
            if len(sliced) < 200:
                print(f"SKIP {symbol} {label}: only {len(sliced)} bars")
                continue
            results.append(run_one(symbol, sliced, label))
    print("period,symbol,bars,trades,gross_pnl_usdt,costs_usdt,net_pnl_usdt,net_pf,expectancy_r,max_dd_pct")
    for r in results:
        print(",".join(str(r[k]) for k in (
            "period", "symbol", "bars", "trades", "gross_pnl_usdt", "costs_usdt",
            "net_pnl_usdt", "net_pf", "expectancy_r", "max_dd_pct")))
    for label, _, _ in WINDOWS:
        group = [r for r in results if r["period"] == label]
        print(f"SUMMARY {label}: symbols={len(group)}, trades={sum(r['trades'] for r in group)}, "
              f"profitable_symbols={sum(r['net_pnl_usdt'] > 0 for r in group)}, "
              f"net_pnl_sum={sum(r['net_pnl_usdt'] for r in group):.2f} USDT, "
              f"median_pf={sorted(r['net_pf'] for r in group)[len(group)//2]:.4f}")


if __name__ == "__main__":
    main()
