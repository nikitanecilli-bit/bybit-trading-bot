#!/usr/bin/env python3
"""Conservative H1 long-only limit-fill stress test.

Uses Binance OHLCV proxy and the existing strategy engine. A limit order is
considered filled only when the candle low penetrates the limit by an additional
0/5/10 bps, not merely touches it. This is a conservative fill proxy, not a
true queue model. Independent $10k per symbol; aggregate PnL is not portfolio PnL.
"""
from __future__ import annotations
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Bybit_Trading_Engine_v14_research as em
from run_uploaded_dataset_backtests import read_zip_datasets
from multibar_limit_wait import evaluate_limit_wait, prepare_signal_for_next_bar_fill

FOLDS=[(1,0.50,0.65),(2,0.65,0.80),(3,0.80,1.00)]
# name, mode, limit offset bps, required extra penetration bps, wait bars
VARIANTS=[
    ("market","market",0.0,0.0,0),
    ("limit10_pen0","limit",10.0,0.0,3),
    ("limit10_pen5","limit",10.0,5.0,3),
    ("limit10_pen10","limit",10.0,10.0,3),
    ("limit20_pen0","limit",20.0,0.0,3),
    ("limit20_pen5","limit",20.0,5.0,3),
    ("limit20_pen10","limit",20.0,10.0,3),
    ("limit30_pen0","limit",30.0,0.0,3),
    ("limit30_pen5","limit",30.0,5.0,3),
    ("limit30_pen10","limit",30.0,10.0,3),
]

def run_segment(symbol, tf, candles, start_idx, end_idx, mode, offset_bps, penetration_bps, wait_bars):
    if end_idx < 250 or start_idx >= end_idx: return None
    start_ts,end_ts=candles[start_idx].ts,candles[end_idx-1].ts
    history=candles[:end_idx]
    engine=em.UnifiedQuantEngine(journal_output_path="/tmp/ignored_h1_limit_fill_stress.json")
    cfg=engine.cfg
    cfg.bot_version=f"h1-long-fillstress-{mode}-{offset_bps:g}-{penetration_bps:g}"
    cfg.timeframe=tf; cfg.active_trading_pool=[symbol]; cfg.capital_usdt=10000.0
    cfg.max_risk_trade_pct=1.0; cfg.max_portfolio_risk_pct=2.0; cfg.max_concurrent_positions=1
    cfg.daily_stop_loss_pct=5.0; cfg.emergency_kill_switch_pct=30.0
    cfg.donchian_period=20; cfg.atr_period=14; cfg.min_volume_ratio=1.6
    cfg.stop_atr_mult=2.5; cfg.tp1_r_multiple=2.0; cfg.tp2_r_multiple=5.0
    cfg.atr_trail_mult=3.0; cfg.max_hold_bars=32
    cfg.maker_entry_and_tp1=(mode=="limit"); cfg.maker_tp1_and_target=False
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
        if sym not in engine.pending or mode=="market": return original_fill(sym,candle)
        sig=engine.pending[sym]
        meta=ages.get(sym)
        if meta is None:
            sig["entry_price"]=float(sig["entry_price"])*(1.0-offset_bps/10000.0)
            sig["order_type"]="limit"
            meta={"age":0}; ages[sym]=meta
        decision, meta["age"] = evaluate_limit_wait(
            direction="long",
            low=float(candle.low),
            high=float(candle.high),
            limit_price=float(sig["entry_price"]),
            penetration_bps=penetration_bps,
            age=meta["age"],
            max_wait_bars=wait_bars,
            open_price=float(candle.open),
        )
        timeframe_ms = {
            "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
            "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
            "4h": 14_400_000, "6h": 21_600_000, "12h": 43_200_000,
            "1d": 86_400_000,
        }.get(str(cfg.timeframe).strip().lower())
        if timeframe_ms is None:
            raise ValueError(f"unsupported delayed-limit timeframe: {cfg.timeframe!r}")
        prepare_signal_for_next_bar_fill(sig, int(candle.ts), timeframe_ms)
        if decision == "fill":
            filled=original_fill(sym,candle)
            ages.pop(sym,None)
            return filled
        # Run the engine's ordinary no-touch path so it consumes this bar's
        # pending signal, then restore the intended quote before the next wait.
        ref=float(sig["entry_price"])
        sig["entry_price"]=min(ref, float(candle.low)) * (1.0-1e-10)
        original_fill(sym,candle)
        sig["entry_price"]=ref
        if decision == "wait":
            engine.pending[sym]=sig
            return False
        ages.pop(sym,None)
        return False
    engine._try_fill_pending=wrapped_fill
    try:
        em.check_alignment({symbol:history})
        audit=em.run_simulation_pass(engine,{symbol:history},[symbol],
            data_label=f"WF {tf} {symbol} long {mode} offset{offset_bps} penetration{penetration_bps}")
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
    allowed={s.strip().upper() for s in os.getenv("H1_SYMBOL_ALLOWLIST", "").split(",") if s.strip()}
    if allowed: print("Selected-universe filter: " + ", ".join(sorted(allowed)))
    for (symbol,tf),(_,archive,candles) in sorted(datasets.items()):
        if tf!="1h" or len(candles)<500 or (allowed and symbol.upper() not in allowed): continue
        n=len(candles)
        for fold,start_frac,end_frac in FOLDS:
            start,end=int(n*start_frac),int(n*end_frac)
            for name,mode,offset,penetration,wait in VARIANTS:
                r=run_segment(symbol,tf,candles,start,end,mode,offset,penetration,wait)
                if r is None: continue
                out.append({"timeframe":tf,"symbol":symbol,"fold":fold,"variant":name,
                    "offset_bps":offset,"penetration_bps":penetration,"wait_bars":wait,
                    "test_start_ts":candles[start].ts,"test_end_ts":candles[end-1].ts,
                    "trades":r["trades"],"net_pnl":r["net"],"profit_factor":r["pf"],
                    "expectancy_r":r["exp_r"],"max_drawdown_pct":r["dd"],"costs":r["costs"],
                    "source_archive":archive})
                print(f"1h {symbol} fold={fold} {name} net={r['net']:+.2f} trades={r['trades']}")
    if not out: raise SystemExit("No results")
    with open("h1_limit_fill_stress.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
    print("\nSUMMARY (independent symbol runs; not portfolio PnL)")
    for fold,_,_ in FOLDS:
        for name,_,_,_,_ in VARIANTS:
            report(f"fold={fold} {name}",[r for r in out if r["fold"]==fold and r["variant"]==name])
    for name,_,_,_,_ in VARIANTS:
        report(f"TOTAL {name}",[r for r in out if r["variant"]==name])
    print("CAVEAT: Binance OHLCV proxy; limit fill requires 0/5/10 bps penetration; no queue, spread, partial fills or actual Bybit execution.")
if __name__=="__main__": main()
