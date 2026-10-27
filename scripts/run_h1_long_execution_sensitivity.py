#!/usr/bin/env python3
"""Frozen H1 long-only execution sensitivity across chronological test folds.

All variants are fixed in advance. Binance OHLCV proxy, modeled costs, optimistic
OHLC-touch limit fills. Each symbol starts with independent 10k capital; sums
are diagnostic aggregates, not a shared-capital portfolio backtest.
"""
from __future__ import annotations
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Bybit_Trading_Engine_v14_research as em
from run_uploaded_dataset_backtests import read_zip_datasets

FOLDS=[(1,0.50,0.65),(2,0.65,0.80),(3,0.80,1.00)]
# name, entry mode, offset bps, max wait bars
VARIANTS=[
    ("market","market",0.0,0),
    ("limit_5bps_wait3","limit",5.0,3),
    ("limit_10bps_wait3","limit",10.0,3),
    ("limit_20bps_wait1","limit",20.0,1),
    ("limit_20bps_wait3","limit",20.0,3),
    ("limit_20bps_wait5","limit",20.0,5),
    ("limit_30bps_wait3","limit",30.0,3),
]

def run_segment(symbol, tf, candles, start_idx, end_idx, entry_mode, offset_bps, wait_bars):
    if end_idx < 250 or start_idx >= end_idx: return None
    start_ts,end_ts=candles[start_idx].ts,candles[end_idx-1].ts
    history=candles[:end_idx]
    engine=em.UnifiedQuantEngine(journal_output_path="/tmp/ignored_h1_exec_sensitivity.json")
    cfg=engine.cfg
    cfg.bot_version=f"h1-long-{entry_mode}-{offset_bps:g}-{wait_bars}"
    cfg.timeframe=tf; cfg.active_trading_pool=[symbol]; cfg.capital_usdt=10000.0
    cfg.max_risk_trade_pct=1.0; cfg.max_portfolio_risk_pct=2.0; cfg.max_concurrent_positions=1
    cfg.daily_stop_loss_pct=5.0; cfg.emergency_kill_switch_pct=30.0
    cfg.donchian_period=20; cfg.atr_period=14; cfg.min_volume_ratio=1.6
    cfg.stop_atr_mult=2.5; cfg.tp1_r_multiple=2.0; cfg.tp2_r_multiple=5.0
    cfg.atr_trail_mult=3.0; cfg.max_hold_bars=32
    cfg.maker_entry_and_tp1=(entry_mode=="limit"); cfg.maker_tp1_and_target=False
    cfg.enable_h2_range_fade=False; cfg.validate(); engine.risk_mgr.cfg=cfg
    engine.tg.send_message=lambda *_a,**_k:None
    core=em.QuantStrategyCore; original_eval=core.evaluate_signal
    def wrapped_eval(sym,bars,conf):
        if not bars or not (start_ts <= bars[-1].ts <= end_ts): return None
        sig=original_eval(sym,bars,conf)
        if sig is not None and str(sig.get("direction","")).lower()!="long": return None
        return sig
    core.evaluate_signal=staticmethod(wrapped_eval)
    original_fill=engine._try_fill_pending
    ages={}
    def wrapped_fill(sym,candle):
        if sym not in engine.pending or entry_mode=="market": return original_fill(sym,candle)
        sig=engine.pending[sym]
        meta=ages.get(sym)
        if meta is None:
            sig["entry_price"]=float(sig["entry_price"])*(1.0-offset_bps/10000.0)
            sig["order_type"]="limit"
            meta={"age":0}; ages[sym]=meta
        meta["age"]+=1
        ref=float(sig["entry_price"])
        touched=candle.low<=ref
        filled=original_fill(sym,candle)
        if filled:
            ages.pop(sym,None); return True
        if not touched and meta["age"]<wait_bars:
            engine.pending[sym]=sig
            return False
        ages.pop(sym,None); return False
    engine._try_fill_pending=wrapped_fill
    try:
        em.check_alignment({symbol:history})
        audit=em.run_simulation_pass(engine,{symbol:history},[symbol],
            data_label=f"WF {tf} {symbol} long {entry_mode} {offset_bps}bps wait{wait_bars}")
    finally:
        core.evaluate_signal=staticmethod(original_eval)
    trades=engine.closed_trades
    costs=sum(t.exchange_fees_usdt+t.slippage_cost_usdt for t in trades)
    return {"trades":int(audit["total_trades"]),"net":round(float(audit["net_pnl"]),2),
        "pf":round(float(audit["pf"]),4),"exp_r":round(float(audit["expectancy_r"]),4),
        "dd":round(float(audit["max_dd_pct"]),2),"costs":round(float(costs),2)}

def report(label,rows):
    if not rows:return
    pfs=sorted(float(r["profit_factor"]) for r in rows)
    mid=len(pfs)//2
    median=pfs[mid] if len(pfs)%2 else (pfs[mid-1]+pfs[mid])/2
    print(f"{label}: runs={len(rows)} trades={sum(int(r['trades']) for r in rows)} "
          f"net={sum(float(r['net_pnl']) for r in rows):+.2f} "
          f"positive_runs={sum(float(r['net_pnl'])>0 for r in rows)} "
          f"median_pf={median:.3f} costs={sum(float(r['costs']) for r in rows):.2f}")

def main():
    datasets=read_zip_datasets(); out=[]
    for (symbol,tf),(_,archive,candles) in sorted(datasets.items()):
        if tf!="1h" or len(candles)<500: continue
        n=len(candles)
        for fold,start_frac,end_frac in FOLDS:
            start,end=int(n*start_frac),int(n*end_frac)
            for name,mode,offset,wait in VARIANTS:
                r=run_segment(symbol,tf,candles,start,end,mode,offset,wait)
                if r is None: continue
                out.append({"timeframe":tf,"symbol":symbol,"fold":fold,"variant":name,
                    "test_start_ts":candles[start].ts,"test_end_ts":candles[end-1].ts,
                    "trades":r["trades"],"net_pnl":r["net"],"profit_factor":r["pf"],
                    "expectancy_r":r["exp_r"],"max_drawdown_pct":r["dd"],"costs":r["costs"],
                    "source_archive":archive})
                print(f"1h {symbol} fold={fold} {name} net={r['net']:+.2f} trades={r['trades']}")
    if not out: raise SystemExit("No results")
    with open("h1_long_execution_sensitivity.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
    print("\nSUMMARY (independent symbol runs; not portfolio PnL)")
    for fold,_,_ in FOLDS:
        for name,_,_,_ in VARIANTS:
            report(f"fold={fold} {name}",[r for r in out if r["fold"]==fold and r["variant"]==name])
    for name,_,_,_ in VARIANTS:
        report(f"TOTAL {name}",[r for r in out if r["variant"]==name])
    print("CAVEAT: Binance OHLCV proxy; optimistic OHLC-touch fills; no queue, spread or partial-fill model; not Bybit execution.")

if __name__=="__main__": main()
