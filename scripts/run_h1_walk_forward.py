#!/usr/bin/env python3
"""Chronological H1 train/holdout check for uploaded OHLCV datasets."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import Bybit_Trading_Engine_v14_research as engine_mod
from run_uploaded_dataset_backtests import read_zip_datasets

TRAIN_FRACTION = 0.70
MIN_TRAIN_TRADES = 30


def run_segment(symbol, candles, timeframe, label):
    engine = engine_mod.UnifiedQuantEngine(journal_output_path="/tmp/ignored_h1_walk_forward.json")
    cfg = engine.cfg
    cfg.bot_version = "h1-walk-forward-audit"
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
    data = {symbol: candles}
    engine_mod.check_alignment(data)
    audit = engine_mod.run_simulation_pass(engine, data, [symbol], data_label=label)
    trades = engine.closed_trades
    return {
        "trades": audit["total_trades"],
        "gross": round(sum(t.gross_pnl for t in trades), 2),
        "costs": round(sum(t.exchange_fees_usdt + t.slippage_cost_usdt for t in trades), 2),
        "net": round(audit["net_pnl"], 2),
        "pf": round(audit["pf"], 4),
        "expectancy_r": round(audit["expectancy_r"], 4),
        "max_dd_pct": round(audit["max_dd_pct"], 2),
        "bars": len(candles),
    }


def run():
    datasets = read_zip_datasets()
    datasets = {k: v for k, v in datasets.items() if k[1] == "1h"}
    if not datasets:
        raise SystemExit("No valid H1 datasets found in uploaded ZIP archives.")

    rows = []
    for (symbol, timeframe), (_count, archive, candles) in sorted(datasets.items()):
        split = int(len(candles) * TRAIN_FRACTION)
        train = candles[:split]
        holdout = candles[split:]
        if len(train) < 500 or len(holdout) < 400:
            print(f"SKIP {symbol}: insufficient bars for train/holdout")
            continue
        # Independent engines prevent state, open positions, equity and risk flags
        # from leaking across the chronological split. The holdout starts flat.
        train_result = run_segment(symbol, train, timeframe, f"TRAIN {symbol}")
        holdout_result = run_segment(symbol, holdout, timeframe, f"HOLDOUT {symbol}")
        selected = (
            train_result["trades"] >= MIN_TRAIN_TRADES
            and train_result["net"] > 0
            and train_result["pf"] > 1.0
            and train_result["expectancy_r"] > 0
        )
        rows.append((symbol, train_result, holdout_result, selected, archive))

    print("H1 CHRONOLOGICAL WALK-FORWARD — independent per-symbol runs, 10,000 USDT each")
    print("Train = first 70%; holdout = final 30%. Holdout engine starts flat; no parameter tuning performed.")
    print("Candidate flag is based ONLY on train metrics: >=30 trades, net>0, PF>1, expectancy R>0.")
    print("symbol,train_bars,train_trades,train_net,train_pf,train_expR,train_dd_pct,train_candidate,holdout_bars,holdout_trades,holdout_net,holdout_pf,holdout_expR,holdout_dd_pct")
    for symbol, tr, ho, selected, _archive in rows:
        print(
            f"{symbol},{tr['bars']},{tr['trades']},{tr['net']:.2f},{tr['pf']:.4f},"
            f"{tr['expectancy_r']:.4f},{tr['max_dd_pct']:.2f},{str(selected).upper()},"
            f"{ho['bars']},{ho['trades']},{ho['net']:.2f},{ho['pf']:.4f},"
            f"{ho['expectancy_r']:.4f},{ho['max_dd_pct']:.2f}"
        )
    selected_rows = [r for r in rows if r[3]]
    holdout_pass = [
        r for r in selected_rows
        if r[2]["trades"] >= 10 and r[2]["net"] > 0
        and r[2]["pf"] > 1.0 and r[2]["expectancy_r"] > 0
    ]
    print(
        f"SUMMARY: H1 symbols={len(rows)}, train_candidates={len(selected_rows)}, "
        f"candidates_profitable_in_holdout={len(holdout_pass)}"
    )
    if not selected_rows:
        print("NO TRAIN CANDIDATES: current parameter set did not qualify any H1 symbol.")
    elif not holdout_pass:
        print("NO CANDIDATE CONFIRMED: none of the train-selected symbols passed holdout criteria.")
    else:
        print("HOLDOUT CANDIDATES: " + ";".join(r[0] for r in holdout_pass))


if __name__ == "__main__":
    run()
