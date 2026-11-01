#!/usr/bin/env python3
"""Rolling walk-forward selection of entry execution policy.

Each fold selects one policy using only the training prefix, then evaluates that
frozen policy on the next non-overlapping chronological segment. Binance OHLCV
is a proxy; OHLC touches are optimistic limit-fill assumptions.
"""
from __future__ import annotations
import csv, os, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Bybit_Trading_Engine_v14_research as em
from run_uploaded_dataset_backtests import read_zip_datasets

# Fixed candidate set; selection is train-only.
CANDIDATES = [("market", 0.0, 0), ("limit_5bps_wait3", 5.0, 3),
              ("limit_10bps_wait3", 10.0, 3), ("limit_20bps_wait3", 20.0, 3)]
FOLDS = [(0.50, 0.65), (0.65, 0.80), (0.80, 1.00)]

def run_segment(symbol, timeframe, all_candles, end_idx, start_idx, mode, offset, wait):
    candles = all_candles[:end_idx]
    if end_idx < 250 or start_idx >= end_idx:
        return None
    start_ts, end_ts = all_candles[start_idx].ts, all_candles[end_idx-1].ts
    engine = em.UnifiedQuantEngine(journal_output_path="/tmp/ignored_walk_forward_journal.json")
    cfg = engine.cfg
    cfg.bot_version = "wf-" + mode
    cfg.timeframe = timeframe
    cfg.active_trading_pool = [symbol]
    cfg.capital_usdt = 10000.0
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
    cfg.maker_entry_and_tp1 = mode != "market"
    cfg.maker_tp1_and_target = False
    cfg.enable_h2_range_fade = False
    cfg.validate()
    engine.risk_mgr.cfg = cfg
    engine.tg.send_message = lambda *_a, **_k: None
    original_eval = em.QuantStrategyCore.evaluate_signal
    def gated_eval(symbol_arg, history, cfg_arg):
        if not history or not (start_ts <= history[-1].ts <= end_ts):
            return None
        return original_eval(symbol_arg, history, cfg_arg)
    em.QuantStrategyCore.evaluate_signal = staticmethod(gated_eval)
    original_fill = engine._try_fill_pending
    pending_age = {}
    def try_fill(symbol_arg, candle):
        if symbol_arg not in engine.pending or mode == "market":
            return original_fill(symbol_arg, candle)
        sig = engine.pending[symbol_arg]
        meta = pending_age.get(symbol_arg)
        if meta is None:
            signed = -offset if sig["direction"] == "long" else offset
            sig["entry_price"] = float(sig["entry_price"]) * (1.0 + signed / 10000.0)
            sig["order_type"] = "limit"
            meta = {"age": 0}
            pending_age[symbol_arg] = meta
        meta["age"] += 1
        ref = float(sig["entry_price"])
        touched = candle.low <= ref if sig["direction"] == "long" else candle.high >= ref
        filled = original_fill(symbol_arg, candle)
        if filled:
            pending_age.pop(symbol_arg, None)
            return True
        if not touched and meta["age"] < wait:
            engine.pending[symbol_arg] = sig
            return False
        pending_age.pop(symbol_arg, None)
        return False
    engine._try_fill_pending = try_fill
    try:
        em.check_alignment({symbol: candles})
        audit = em.run_simulation_pass(engine, {symbol: candles}, [symbol],
            data_label=f"WF_BINANCE_PROXY {timeframe} {symbol} {mode}")
    finally:
        em.QuantStrategyCore.evaluate_signal = staticmethod(original_eval)
    trades = engine.closed_trades
    return {"net": round(audit["net_pnl"], 2), "trades": audit["total_trades"],
            "pf": round(audit["pf"], 4), "exp_r": round(audit["expectancy_r"], 4),
            "dd": round(audit["max_dd_pct"], 2),
            "costs": round(sum(t.exchange_fees_usdt+t.slippage_cost_usdt for t in trades), 2)}

def main():
    datasets = read_zip_datasets()
    if not datasets: raise SystemExit("No valid OHLCV datasets in ZIP archives.")
    results, selected_counts = [], Counter()
    for (symbol, tf), (_, archive, candles) in sorted(datasets.items()):
        n = len(candles)
        # Each fold's test window is disjoint; the policy is re-selected on its
        # expanding historical prefix only. No symbol-specific selection uses test PnL.
        for fold_no, (train_end_frac, test_end_frac) in enumerate(FOLDS, 1):
            train_end = int(n*train_end_frac)
            test_end = int(n*test_end_frac)
            if train_end < 250 or test_end <= train_end: continue
            train_scores = []
            for mode, offset, wait in CANDIDATES:
                r = run_segment(symbol, tf, candles, train_end, 25, mode, offset, wait)
                if r is not None: train_scores.append((r["net"], mode, offset, wait, r))
            if not train_scores: continue
            # Train-only selection; tie-break toward simpler market execution.
            train_scores.sort(key=lambda x: (x[0], x[1] == "market"), reverse=True)
            _, chosen, offset, wait, train_result = train_scores[0]
            test_start = train_end
            # Ensure signal warm-up/history is retained while entries are gated to test window.
            selected_counts[(tf, fold_no, chosen)] += 1
            chosen_test = run_segment(symbol, tf, candles, test_end, test_start, chosen, offset, wait)
            market_test = run_segment(symbol, tf, candles, test_end, test_start, "market", 0.0, 0)
            if chosen_test is None or market_test is None: continue
            results.append({"timeframe":tf,"symbol":symbol,"fold":fold_no,
                "train_end_fraction":train_end_frac,"test_end_fraction":test_end_frac,
                "selected_policy":chosen,"selected_offset_bps":offset,"selected_wait_bars":wait,
                "train_net_pnl":train_result["net"],"test_trades":chosen_test["trades"],
                "selected_test_net_pnl":chosen_test["net"],"market_test_net_pnl":market_test["net"],
                "delta_vs_market":round(chosen_test["net"]-market_test["net"],2),
                "selected_test_pf":chosen_test["pf"],"selected_test_expectancy_r":chosen_test["exp_r"],
                "selected_test_max_dd_pct":chosen_test["dd"],"selected_test_costs":chosen_test["costs"],
                "source_archive":archive})
            print(f"WF {tf} {symbol} fold={fold_no} selected={chosen} test={chosen_test['net']:+.2f} market={market_test['net']:+.2f}")
    if not results: raise SystemExit("No walk-forward results produced.")
    with open("execution_walk_forward.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(results[0].keys())); w.writeheader(); w.writerows(results)
    print("\nWALK-FORWARD SUMMARY (independent per-symbol runs, not portfolio PnL)")
    for tf in ("15m","1h"):
        group=[r for r in results if r["timeframe"]==tf]
        if not group: continue
        print(f"SUMMARY {tf}: symbol-folds={len(group)} selected_net={sum(r['selected_test_net_pnl'] for r in group):+.2f} "
              f"market_net={sum(r['market_test_net_pnl'] for r in group):+.2f} "
              f"delta={sum(r['delta_vs_market'] for r in group):+.2f} "
              f"profitable_selected={sum(r['selected_test_net_pnl']>0 for r in group)} "
              f"median_pf={sorted(r['selected_test_pf'] for r in group)[len(group)//2]:.3f}")
    print("\nPOLICY SELECTION COUNTS")
    for (tf,fold,policy),count in sorted(selected_counts.items()):
        print(f"SELECTED {tf} fold={fold} {policy}: {count}")
    print("CAVEAT: Binance OHLCV proxy; modelled costs; optimistic candle-touch limit fills; no queue, spread, partial fills or live Bybit execution.")

if __name__=="__main__": main()
