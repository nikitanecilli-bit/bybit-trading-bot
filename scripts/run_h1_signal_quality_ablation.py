#!/usr/bin/env python3
"""H1 long-only signal-quality ablation with fixed conservative limit execution.

All filters are fixed before evaluating the three chronological test folds.
Execution is held constant: 20 bps limit offset, 5 bps extra penetration, 3-bar
expiry, market exits. Binance OHLCV proxy; independent $10k per symbol; summed
PnL is not portfolio PnL and OHLC penetration is not a queue/fill model.
"""
from __future__ import annotations
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Bybit_Trading_Engine_v14_research as em
from run_uploaded_dataset_backtests import read_zip_datasets
from multibar_limit_wait import prepare_signal_for_next_bar_fill

FOLDS=[(1,0.50,0.65),(2,0.65,0.80),(3,0.80,1.00)]
VOL_THRESHOLDS=[1.2,1.6,2.0,2.5]
BREAKOUT_ATR_THRESHOLDS=[0.0,0.10,0.25]
ENTRY_OFFSET_BPS=20.0
ENTRY_PENETRATION_BPS=5.0
WAIT_BARS=3

def run_segment(symbol, tf, candles, start_idx, end_idx, min_vol, min_breakout_atr):
    if end_idx < 250 or start_idx >= end_idx: return None
    start_ts,end_ts=candles[start_idx].ts,candles[end_idx-1].ts
    history=candles[:end_idx]
    engine=em.UnifiedQuantEngine(journal_output_path="/tmp/ignored_h1_signal_quality.json")
    cfg=engine.cfg
    cfg.bot_version=f"h1-long-quality-v{min_vol:g}-b{min_breakout_atr:g}"
    cfg.timeframe=tf; cfg.active_trading_pool=[symbol]; cfg.capital_usdt=10000.0
    cfg.max_risk_trade_pct=1.0; cfg.max_portfolio_risk_pct=2.0; cfg.max_concurrent_positions=1
    cfg.daily_stop_loss_pct=5.0; cfg.emergency_kill_switch_pct=30.0
    cfg.donchian_period=20; cfg.atr_period=14; cfg.min_volume_ratio=min_vol
    cfg.stop_atr_mult=2.5; cfg.tp1_r_multiple=2.0; cfg.tp2_r_multiple=5.0
    cfg.atr_trail_mult=3.0; cfg.max_hold_bars=32
    cfg.maker_entry_and_tp1=True; cfg.maker_tp1_and_target=False
    cfg.enable_h2_range_fade=False; cfg.validate(); engine.risk_mgr.cfg=cfg
    engine.tg.send_message=lambda *_a,**_k:None
    core=em.QuantStrategyCore; original_eval=core.evaluate_signal
    def wrapped_eval(sym,bars,conf):
        if not bars or not (start_ts <= bars[-1].ts <= end_ts): return None
        sig=original_eval(sym,bars,conf)
        if sig is None or str(sig.get("direction","")).lower()!="long": return None
        if float(sig.get("vol_ratio",0.0)) < min_vol: return None
        if min_breakout_atr > 0:
            prev=bars[:-1]
            hi_ch,_,_=core.compute_donchian_and_volume(prev,conf.donchian_period)
            atr=float(sig.get("atr",0.0))
            if atr <= 0 or (float(bars[-1].close)-hi_ch)/atr < min_breakout_atr: return None
        return sig
    core.evaluate_signal=staticmethod(wrapped_eval)
    original_fill=engine._try_fill_pending
    ages={}
    def wrapped_fill(sym,candle):
        if sym not in engine.pending: return original_fill(sym,candle)
        sig=engine.pending[sym]
        meta=ages.get(sym)
        if meta is None:
            sig["entry_price"]=float(sig["entry_price"])*(1.0-ENTRY_OFFSET_BPS/10000.0)
            sig["order_type"]="limit"
            meta={"age":0}; ages[sym]=meta
        meta["age"]+=1
        ref=float(sig["entry_price"])
        required_low=ref*(1.0-ENTRY_PENETRATION_BPS/10000.0)
        if float(candle.low)<=required_low:
            timeframe_ms = {"1h": 3_600_000}.get(str(tf).strip().lower())
            if timeframe_ms is None: raise ValueError(f"unsupported delayed-limit timeframe: {tf!r}")
            prepare_signal_for_next_bar_fill(sig,int(candle.ts),timeframe_ms)
            filled=original_fill(sym,candle)
            if filled:
                ages.pop(sym,None); return True
            ages.pop(sym,None)
            return False
        # Use engine's normal no-touch path while retaining the intended limit.
        sig["entry_price"]=min(ref,float(candle.low))*(1.0-1e-10)
        timeframe_ms = {"1h": 3_600_000}.get(str(tf).strip().lower())
        if timeframe_ms is None: raise ValueError(f"unsupported delayed-limit timeframe: {tf!r}")
        prepare_signal_for_next_bar_fill(sig,int(candle.ts),timeframe_ms)
        original_fill(sym,candle)
        sig["entry_price"]=ref
        if meta["age"]<WAIT_BARS:
            engine.pending[sym]=sig
            return False
        ages.pop(sym,None)
        return False
    engine._try_fill_pending=wrapped_fill
    try:
        em.check_alignment({symbol:history})
        audit=em.run_simulation_pass(engine,{symbol:history},[symbol],
            data_label=f"WF {tf} {symbol} long vol>={min_vol} breakoutATR>={min_breakout_atr}")
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
            for min_vol in VOL_THRESHOLDS:
                for min_breakout in BREAKOUT_ATR_THRESHOLDS:
                    r=run_segment(symbol,tf,candles,start,end,min_vol,min_breakout)
                    if r is None: continue
                    variant=f"vol{min_vol:g}_breakATR{min_breakout:g}"
                    out.append({"timeframe":tf,"symbol":symbol,"fold":fold,"variant":variant,
                        "min_volume_ratio":min_vol,"min_breakout_atr":min_breakout,
                        "entry_offset_bps":ENTRY_OFFSET_BPS,"entry_penetration_bps":ENTRY_PENETRATION_BPS,
                        "wait_bars":WAIT_BARS,"test_start_ts":candles[start].ts,"test_end_ts":candles[end-1].ts,
                        "trades":r["trades"],"net_pnl":r["net"],"profit_factor":r["pf"],
                        "expectancy_r":r["exp_r"],"max_drawdown_pct":r["dd"],"costs":r["costs"],
                        "source_archive":archive})
                    print(f"1h {symbol} fold={fold} {variant} net={r['net']:+.2f} trades={r['trades']}")
    if not out: raise SystemExit("No results")
    with open("h1_signal_quality_ablation.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
    print("\nSUMMARY (independent symbol runs; not portfolio PnL)")
    variants=sorted({r["variant"] for r in out})
    for fold,_,_ in FOLDS:
        for variant in variants: report(f"fold={fold} {variant}",[r for r in out if r["fold"]==fold and r["variant"]==variant])
    for variant in variants: report(f"TOTAL {variant}",[r for r in out if r["variant"]==variant])
    print("CAVEAT: Binance OHLCV proxy; fixed 20 bps limit, 5 bps penetration; no queue/spread/partial fills; not actual Bybit execution.")
if __name__=="__main__": main()
