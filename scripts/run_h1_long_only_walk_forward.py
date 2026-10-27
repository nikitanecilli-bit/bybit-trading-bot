#!/usr/bin/env python3
"""Train-selected H1 long-only candidates evaluated on the chronological holdout.

Selection uses only the first 70% of each Binance OHLCV series. The final 30%
is replayed with the same frozen engine parameters and a long-only signal filter.
For the holdout, prior candles remain available for indicators, but no entries are
allowed before the cutoff. This is a diagnostic walk-forward, not live validation.
"""
from __future__ import annotations

import csv
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import Bybit_Trading_Engine_v14_research as engine_mod
from run_uploaded_dataset_backtests import read_zip_datasets

TRAIN_FRACTION = 0.70
MIN_TRAIN_TRADES = 30


def run_segment(symbol, candles, timeframe, label, cutoff_ts=None):
    engine = engine_mod.UnifiedQuantEngine(
        journal_output_path="/tmp/ignored_h1_long_only_walk_forward.json"
    )
    cfg = engine.cfg
    cfg.bot_version = "h1-long-only-walk-forward"
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

    core = engine_mod.QuantStrategyCore
    original = core.evaluate_signal

    def long_only(symbol_arg, history, cfg_arg):
        if not history:
            return None
        # On holdout, keep earlier candles for causal indicators but suppress
        # all entries until the chronological cutoff.
        if cutoff_ts is not None and history[-1].ts < cutoff_ts:
            return None
        signal = original(symbol_arg, history, cfg_arg)
        if signal is None:
            return None
        return signal if str(signal.get("direction", "")).lower() == "long" else None

    core.evaluate_signal = staticmethod(long_only)
    try:
        data = {symbol: candles}
        engine_mod.check_alignment(data)
        audit = engine_mod.run_simulation_pass(
            engine, data, [symbol], data_label=label
        )
        trades = engine.closed_trades
        return {
            "trades": int(audit["total_trades"]),
            "gross_pnl_usdt": round(sum(float(t.gross_pnl) for t in trades), 2),
            "costs_usdt": round(sum(float(t.exchange_fees_usdt) + float(t.slippage_cost_usdt) for t in trades), 2),
            "net_pnl_usdt": round(float(audit["net_pnl"]), 2),
            "profit_factor": round(float(audit["pf"]), 4),
            "expectancy_r": round(float(audit["expectancy_r"]), 4),
            "max_dd_pct": round(float(audit["max_dd_pct"]), 2),
        }
    finally:
        core.evaluate_signal = staticmethod(original)


def run(output_path="h1_long_only_walk_forward.csv"):
    datasets = read_zip_datasets()
    datasets = {key: value for key, value in datasets.items() if key[1] == "1h"}
    if not datasets:
        raise SystemExit("No valid H1 datasets found in uploaded ZIP archives.")

    rows = []
    for (symbol, timeframe), (_count, archive, candles) in sorted(datasets.items()):
        split = int(len(candles) * TRAIN_FRACTION)
        train = candles[:split]
        if len(train) < 500 or len(candles) - split < 400:
            print(f"SKIP {symbol}: insufficient bars for train/holdout")
            continue
        cutoff_ts = candles[split].ts

        train_result = run_segment(symbol, train, timeframe, f"TRAIN LONG-ONLY {symbol}")
        selected = (
            train_result["trades"] >= MIN_TRAIN_TRADES
            and train_result["net_pnl_usdt"] > 0
            and train_result["profit_factor"] > 1.0
            and train_result["expectancy_r"] > 0
        )
        holdout_result = run_segment(
            symbol, candles, timeframe, f"HOLDOUT LONG-ONLY {symbol}",
            cutoff_ts=cutoff_ts,
        )
        holdout_pass = (
            selected and holdout_result["trades"] >= 10
            and holdout_result["net_pnl_usdt"] > 0
            and holdout_result["profit_factor"] > 1.0
            and holdout_result["expectancy_r"] > 0
        )
        rows.append({
            "symbol": symbol,
            "timeframe": timeframe,
            "source_archive": archive,
            "bars_total": len(candles),
            "train_bars": len(train),
            "holdout_bars": len(candles) - split,
            "holdout_start_utc": datetime.fromtimestamp(
                cutoff_ts / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "selected_on_train_only": selected,
            **{f"train_{k}": v for k, v in train_result.items()},
            **{f"holdout_{k}": v for k, v in holdout_result.items()},
            "holdout_passes_frozen_criteria": holdout_pass,
        })

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    selected_rows = [row for row in rows if row["selected_on_train_only"]]
    passed_rows = [row for row in rows if row["holdout_passes_frozen_criteria"]]
    print("H1 LONG-ONLY WALK-FORWARD — per-symbol runs, 10,000 USDT each")
    print("Train = first 70%; holdout = final 30%. Candidate selection uses train metrics only.")
    print("The holdout uses prior candles for indicators but suppresses entries before cutoff.")
    print("symbol,train_trades,train_net,train_pf,train_expR,selected,holdout_trades,holdout_net,holdout_pf,holdout_expR,holdout_dd_pct,holdout_pass")
    for row in rows:
        print(",".join(str(row[k]) for k in (
            "symbol", "train_trades", "train_net_pnl_usdt", "train_profit_factor",
            "train_expectancy_r", "selected_on_train_only", "holdout_trades",
            "holdout_net_pnl_usdt", "holdout_profit_factor", "holdout_expectancy_r",
            "holdout_max_dd_pct", "holdout_passes_frozen_criteria"
        )))
    print(
        f"SUMMARY: H1 symbols={len(rows)}, train_candidates={len(selected_rows)}, "
        f"candidates_passing_holdout={len(passed_rows)}, "
        f"all_symbols_holdout_net_sum={sum(row['holdout_net_pnl_usdt'] for row in rows):.2f} USDT, "
        f"train_selected_holdout_net_sum={sum(row['holdout_net_pnl_usdt'] for row in selected_rows):.2f} USDT"
    )
    if not passed_rows:
        print("NO LONG-ONLY CANDIDATE CONFIRMED by frozen holdout criteria.")
    else:
        print("HOLDOUT PASS: " + ";".join(row["symbol"] for row in passed_rows))
    print("CAVEAT: the overall final-30% long-only result has already been inspected in earlier research; this is a train-selected robustness check, not a pristine untouched test.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="h1_long_only_walk_forward.csv")
    run(parser.parse_args().output)
