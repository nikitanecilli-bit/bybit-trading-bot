#!/usr/bin/env python3
"""Frozen H1 ablation: direction (both/long-only) x entry (market/limit 20bps).

Three disjoint expanding walk-forward test windows. All rules are fixed before
the test; no per-symbol policy selection. Research only, Binance OHLCV proxy.
"""
from __future__ import annotations
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Bybit_Trading_Engine_v14_research as em
from run_uploaded_dataset_backtests import read_zip_datasets

FOLDS=[(0.50,0.65),(0.65,0.80),(0.80,1.00)]
VARIANTS=[("both_market","both","market"),("long_market","long","market"),
          ("both_limit20","both","limit20"),("long_limit20","long","limit20")]

def run_segment(symbol, tf, candles, start_idx, end_idx, direction_mode, entry_mode):
    if end_idx<250 or start_idx>=end_idx: return None
    start_ts,end_ts=candles[start_idx].ts,candles[end_idx-1].ts
    history=candles[:end_idx]
    engine=em.UnifiedQuantEngine(journal_output_path="/tmp/ignored_direction_execution_journal.json")
    cfg=engine.cfg
    cfg.bot_version=f"dir-exec-{direction_mode}-{entry_mode}"
    cfg.timeframe=tf; cfg.active_trading_pool=[symbol]; cfg.capital_usdt=10000.0
    cfg.max_risk_trade_pct=1.0; cfg.max_portfolio_risk_pct=2.0; cfg.max_concurrent_positions=1
    cfg.daily_stop_loss_pct=5.0; cfg.emergency_kill_switch_pct=30.0
    cfg.donchian_period=20; cfg.atr_period=14; cfg.min_volume_ratio=1.6
    cfg.stop_atr_mult=2.5; cfg.tp1_r_multiple=2.0; cfg.tp2_r_multiple=5.0
    cfg.atr_trail_mult=3.0; cfg.max_hold_bars=32
    cfg.maker_entry_and_tp1=(entry_mode!="market"); cfg.maker_tp1_and_target=False
    cfg.enable_h2_range_fade=False; cfg.validate(); engine.risk_mgr.cfg=cfg
    engine.tg.send_message=lambda *_a,**_k:None
    core=em.QuantStrategyCore; original_eval=core.evaluate_signal
    def wrapped_eval(sym, bars, conf):
        if not bars or not (start_ts <= bars[-1].ts <= end_ts): return None
        sig=original_eval(sym,bars,conf)
        if sig is not None and direction_mode=="long" and str(sig.get("direction","")).lower()!="long": return None
        return sig
    core.evaluate_signal=staticmethod(wrapped_eval)
    original_fill=engine._try_fill_pending
    ages={}
    def wrapped_fill(sym,candle):
        if sym not in engine.pending or entry_mode=="market": return original_fill(sym,candle)
        sig=engine.pending[sym]
        meta=ages.get(sym)
        if meta is None:
            sig["entry_price"]=float(sig["entry_price"])*(1.0-0.002 if sig["direction"]=="long" else 1.0+0.002)
            sig["order_type"]="limit"; meta={"age":0}; ages[sym]=meta
        meta["age"]+=1
        ref=float(sig["entry_price"])
        touched=candle.low<=ref if sig["direction"]=="long" else candle.high>=ref
        filled=original_fill(sym,candle)
        if filled: ages.pop(sym,None); return True
        if not touched and meta["age"]<3:
            engine.pending[sym]=sig; return False
        ages.pop(sym,None); return False
    engine._try_fill_pending=wrapped_fill
    try:
        em.check_alignment({symbol:history})
        audit=em.run_simulation_pass(engine,{symbol:history},[symbol],data_label=f"WF {tf} {symbol} {direction_mode} {entry_mode}")
    finally: core.evaluate_signal=staticmethod(original_eval)
    trades=engine.closed_trades
    costs=sum(t.exchange_fees_usdt+t.slippage_cost_usdt for t in trades)
    return {"trades":audit["total_trades"],"net":round(audit["net_pnl"],2),
            "pf":round(audit["pf"],4),"exp_r":round(audit["expectancy_r"],4),
            "dd":round(audit["max_dd_pct"],2),"costs":round(costs,2)}

def main():
    datasets=read_zip_datasets()
    out=[]
    for (symbol,tf),(_,archive,candles) in sorted(datasets.items()):
        if tf!="1h" or len(candles)<500: continue
        n=len(candles)
        for fold,(train_frac,test_frac) in enumerate(FOLDS,1):
            start,end=int(n*train_frac),int(n*test_frac)
            for name,direction,entry in VARIANTS:
                r=run_segment(symbol,tf,candles,start,end,direction,entry)
                if r is None: continue
                out.append({"timeframe":tf,"symbol":symbol,"fold":fold,"variant":name,
                    "test_start_ts":candles[start].ts,"test_end_ts":candles[end-1].ts,
                    "trades":r["trades"],"net_pnl":r["net"],"profit_factor":r["pf"],
                    "expectancy_r":r["exp_r"],"max_drawdown_pct":r["dd"],"costs":r["costs"],
                    "source_archive":archive})
                print(f"{tf} {symbol} fold={fold} {name} net={r['net']:+.2f} trades={r['trades']}")
    if not out: raise SystemExit("No results")
    with open("h1_direction_execution_ablation.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
    def report(label, rows):
        pfs=sorted(row["profit_factor"] for row in rows)
        median_pf=pfs[len(pfs)//2] if len(pfs)%2 else (pfs[len(pfs)//2-1]+pfs[len(pfs)//2])/2
        print(f"{label}: runs={len(rows)} trades={sum(row['trades'] for row in rows)} "
              f"net={sum(row['net_pnl'] for row in rows):+.2f} "
              f"positive_runs={sum(row['net_pnl']>0 for row in rows)} "
              f"median_pf={median_pf:.3f} costs={sum(row['costs'] for row in rows):.2f}")
    print("\\nSUMMARY (independent symbol runs; not portfolio PnL)")
    for fold in sorted(set(row["fold"] for row in out)):
        for variant in [v[0] for v in VARIANTS]:
            group=[row for row in out if row["fold"]==fold and row["variant"]==variant]
            if group: report(f"fold={fold} {variant}",group)
    for variant in [v[0] for v in VARIANTS]:
        group=[row for row in out if row["variant"]==variant]
        if group: report(f"TOTAL {variant}",group)
    print("CAVEAT: Binance OHLCV proxy; fixed limit touched by candle assumed filled; no queue/spread/partial-fill model; not Bybit execution.")
if __name__=="__main__": main()
