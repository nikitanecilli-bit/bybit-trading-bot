#!/usr/bin/env python3
"""Predeclared causal entry-filter sensitivity; no parameter search/optimization."""
from __future__ import annotations
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import Bybit_Trading_Engine_v14_research as em
from scripts.run_uploaded_dataset_backtests import read_zip_datasets

WINDOWS=(("screen","2025-10-27T00:00:00+00:00","2026-04-29T00:00:00+00:00"),
         ("forward","2026-04-29T00:00:00+00:00","2026-10-27T00:00:00+00:00"))
HOUR=3600000
FILTERS=("baseline","no_us_session","aligned_24h","atr_ge_1p1","aligned_and_atr","aligned_no_us")

def ms(s):return int(datetime.fromisoformat(s).timestamp()*1000)
def atr_pct(cs):
    if len(cs)<16:return None
    tail=cs[-15:]; trs=[]
    for i in range(1,len(tail)):
        c,p=tail[i],tail[i-1]
        trs.append(max(c.high-c.low,abs(c.high-p.close),abs(c.low-p.close)))
    return sum(trs)/len(trs)/tail[-1].close*100 if tail[-1].close else None

def run_one(sym,part,label,filter_name):
    e=em.UnifiedQuantEngine(journal_output_path="/tmp/ignored_filter_sensitivity.json")
    c=e.cfg;c.bot_version="h1-filter-sensitivity";c.timeframe="1h"
    c.active_trading_pool=[sym];c.capital_usdt=10000.0;c.max_risk_trade_pct=1.0
    c.max_portfolio_risk_pct=2.0;c.max_concurrent_positions=1;c.daily_stop_loss_pct=5.0
    c.emergency_kill_switch_pct=30.0;c.donchian_period=20;c.atr_period=14
    c.min_volume_ratio=1.6;c.stop_atr_mult=2.5;c.tp1_r_multiple=2.0
    c.tp2_r_multiple=5.0;c.atr_trail_mult=3.0;c.max_hold_bars=32
    c.maker_entry_and_tp1=False;c.enable_h2_range_fade=False
    if filter_name in ("no_us_session","aligned_no_us"):c.blocked_sessions_utc=["us"]
    c.validate();e.risk_mgr.cfg=c;e.tg.send_message=lambda *_a,**_k:None
    original=em.QuantStrategyCore.evaluate_signal
    def filtered(symbol,candles,cfg):
        sig=original(symbol,candles,cfg)
        if sig is None or filter_name=="baseline" or filter_name=="no_us_session":return sig
        # candles[-1] is the completed signal candle. Use only bars before it
        # for trend/ATR context; no future bar or exit information is accessed.
        prior=candles[:-1]
        if len(prior)<73:return None
        ret24=(prior[-1].close/prior[-25].close-1)*100
        ap=atr_pct(prior)
        aligned=(ret24>0 if sig["direction"]=="long" else ret24<0)
        if filter_name=="aligned_24h" and not aligned:return None
        if filter_name=="atr_ge_1p1" and (ap is None or ap<1.1):return None
        if filter_name=="aligned_and_atr" and (not aligned or ap is None or ap<1.1):return None
        if filter_name=="aligned_no_us" and not aligned:return None
        return sig
    em.QuantStrategyCore.evaluate_signal=staticmethod(filtered)
    try:
        em.check_alignment({sym:part})
        audit=em.run_simulation_pass(e,{sym:part},[sym],data_label=f"{label} {filter_name} {sym}")
        ts=e.closed_trades
        return {"period":label,"filter":filter_name,"symbol":sym,"trades":len(ts),
          "net":sum(t.pnl_usdt for t in ts),"gross":sum(t.gross_pnl for t in ts),
          "fees":sum(t.exchange_fees_usdt for t in ts),"slip":sum(t.slippage_cost_usdt for t in ts),
          "pf":audit["pf"],"expR":audit["expectancy_r"]}
    finally:em.QuantStrategyCore.evaluate_signal=staticmethod(original)

def main():
    ds=read_zip_datasets(); eligible={};lo,hi=ms(WINDOWS[0][1]),ms(WINDOWS[1][2])
    for (sym,tf),(_,_,cs) in ds.items():
        if tf=="1h" and cs[0].ts<=lo and cs[-1].ts>=hi-HOUR:eligible[sym]=cs
    print(f"ELIGIBLE_SYMBOLS={len(eligible)}; FILTERS={','.join(FILTERS)}")
    results=[]
    for sym,full in sorted(eligible.items()):
        for label,start,end in WINDOWS:
            a,b=ms(start),ms(end);part=[x for x in full if a<=x.ts<b]
            if len(part)<200:continue
            for f in FILTERS:results.append(run_one(sym,part,label,f))
    print("period,filter,symbol,trades,net,gross,fees,slippage,pf,expectancy_r")
    for r in results:print(",".join(str(r[k]) for k in ("period","filter","symbol","trades","net","gross","fees","slip","pf","expR")))
    for label,_,_ in WINDOWS:
        for f in FILTERS:
            rs=[r for r in results if r["period"]==label and r["filter"]==f]
            if not rs:continue
            print(f"SUMMARY period={label} filter={f} symbols={len(rs)} trades={sum(x['trades'] for x in rs)} "
             f"profitable_symbols={sum(x['net']>0 for x in rs)} net_sum={sum(x['net'] for x in rs):.2f} "
             f"median_pf={sorted(x['pf'] for x in rs)[len(rs)//2]:.4f}")
if __name__=="__main__":main()
