#!/usr/bin/env python3
"""Trade-level causal regime and loss attribution for the two H1 windows."""
from __future__ import annotations
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import Bybit_Trading_Engine_v14_research as engine_mod
from scripts.run_uploaded_dataset_backtests import read_zip_datasets

WINDOWS = (
    ("screen", "2025-10-27T00:00:00+00:00", "2026-04-29T00:00:00+00:00"),
    ("forward", "2026-04-29T00:00:00+00:00", "2026-10-27T00:00:00+00:00"),
)
HOUR = 3_600_000

def ms(s):
    return int(datetime.fromisoformat(s).timestamp()*1000)

def atr_pct(candles, i, period=14):
    if i < 2: return None
    tail=candles[max(1,i-period):i+1]
    trs=[]
    for j in range(1,len(tail)):
        c,p=tail[j],tail[j-1]
        trs.append(max(c.high-c.low,abs(c.high-p.close),abs(c.low-p.close)))
    if not trs or candles[i].close<=0:return None
    return sum(trs)/len(trs)/candles[i].close*100

def context(candles, ts, direction):
    # All values use candles strictly before the entry candle.
    idx=next((i for i,c in enumerate(candles) if c.ts==ts),None)
    if idx is None or idx<73:return None
    px=candles[idx-1].close
    r24=(px/candles[idx-25].close-1)*100
    r72=(px/candles[idx-73].close-1)*100
    ap=atr_pct(candles,idx-1)
    aligned=(r24>0 if direction=="long" else r24<0)
    return {"r24_pct":r24,"r72_pct":r72,"atr_pct":ap,"aligned24":aligned}

def run_one(symbol, full, sliced, label):
    e=engine_mod.UnifiedQuantEngine(journal_output_path="/tmp/ignored_regime_journal.json")
    c=e.cfg
    c.bot_version="h1-causal-regime-attribution"; c.timeframe="1h"
    c.active_trading_pool=[symbol]; c.capital_usdt=10000.0
    c.max_risk_trade_pct=1.0; c.max_portfolio_risk_pct=2.0
    c.max_concurrent_positions=1; c.daily_stop_loss_pct=5.0
    c.emergency_kill_switch_pct=30.0; c.donchian_period=20; c.atr_period=14
    c.min_volume_ratio=1.6; c.stop_atr_mult=2.5; c.tp1_r_multiple=2.0
    c.tp2_r_multiple=5.0; c.atr_trail_mult=3.0; c.max_hold_bars=32
    c.maker_entry_and_tp1=False; c.enable_h2_range_fade=False
    c.validate(); e.risk_mgr.cfg=c; e.tg.send_message=lambda *_a,**_k:None
    engine_mod.check_alignment({symbol:sliced})
    e_mod=engine_mod.run_simulation_pass(e,{symbol:sliced},[symbol],data_label=label)
    out=[]
    for t in e.closed_trades:
        entry_ts=int(datetime.strptime(t.entry_date,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()*1000)
        ctx=context(full,entry_ts,t.direction)
        if ctx is None: continue
        held=max(0,(datetime.strptime(t.exit_date,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)-datetime.strptime(t.entry_date,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds()/3600)
        out.append({"period":label,"symbol":symbol,"direction":t.direction,"session":t.session,
          "exit_reason":t.exit_reason,"net":t.pnl_usdt,"gross":t.gross_pnl,
          "fees":t.exchange_fees_usdt,"slippage":t.slippage_cost_usdt,
          "mfe_r":t.mfe,"mae_r":t.mae,"net_r":t.r_multiple,"held_h":held,**ctx})
    return out

def summarize(rows, key):
    groups=defaultdict(list)
    for r in rows: groups[r[key]].append(r)
    for k,rs in sorted(groups.items(),key=lambda x:str(x[0])):
        n=len(rs); net=sum(x["net"] for x in rs); gross=sum(x["gross"] for x in rs)
        wins=sum(x["net"]>0 for x in rs)
        print(f"GROUP {key}={k} trades={n} wins={wins} net={net:.2f} gross={gross:.2f} "
              f"mean_net={net/n:.2f} mean_R={sum(x['net_r'] for x in rs)/n:.4f} "
              f"mean_MFE={sum(x['mfe_r'] for x in rs)/n:.3f} mean_MAE={sum(x['mae_r'] for x in rs)/n:.3f} "
              f"fees={sum(x['fees'] for x in rs):.2f} slip={sum(x['slippage'] for x in rs):.2f}")

def main():
    ds=read_zip_datasets(); eligible={}
    lo,hi=ms(WINDOWS[0][1]),ms(WINDOWS[1][2])
    for (sym,tf),(_,_,candles) in ds.items():
        if tf=="1h" and candles[0].ts<=lo and candles[-1].ts>=hi-HOUR:
            eligible[sym]=candles
    print(f"ELIGIBLE_SYMBOLS={len(eligible)}")
    all_rows=[]
    for sym,full in sorted(eligible.items()):
        for label,start,end in WINDOWS:
            a,b=ms(start),ms(end)
            part=[c for c in full if a<=c.ts<b]
            if len(part)>=200: all_rows.extend(run_one(sym,full,part,label))
    for period in ("screen","forward"):
        rows=[r for r in all_rows if r["period"]==period]
        print(f"\\n=== PERIOD {period} trades_with_context={len(rows)} ===")
        summarize(rows,"exit_reason"); summarize(rows,"direction"); summarize(rows,"session")
        summarize(rows,"aligned24")
        # Causal market return regimes, based only on the prior completed 24 bars.
        for r in rows:
            r["trend24_regime"]="up" if r["r24_pct"]>=2 else ("down" if r["r24_pct"]<=-2 else "flat")
        summarize(rows,"trend24_regime")
        # ATR terciles are computed separately within each period, not using future period data.
        vals=sorted(r["atr_pct"] for r in rows if r["atr_pct"] is not None)
        if vals:
            q1,q2=vals[len(vals)//3],vals[(2*len(vals))//3]
            for r in rows:r["vol_regime"]="low" if r["atr_pct"]<=q1 else ("mid" if r["atr_pct"]<=q2 else "high")
            print(f"ATR_TERCILE_THRESHOLDS_PCT={q1:.4f},{q2:.4f}")
            summarize(rows,"vol_regime")
        # Trade-level aggregate metrics help distinguish poor entries from weak follow-through.
        for name,rs in (("all",rows),("net_losers",[x for x in rows if x["net"]<=0])):
            if rs:
                print(f"TRADE_DIAG {name}: n={len(rs)} mean_hold_h={sum(x['held_h'] for x in rs)/len(rs):.2f} "
                  f"mean_MFE_R={sum(x['mfe_r'] for x in rs)/len(rs):.3f} "
                  f"mean_MAE_R={sum(x['mae_r'] for x in rs)/len(rs):.3f} "
                  f"mean_R24={sum(x['r24_pct'] for x in rs)/len(rs):.3f}% "
                  f"mean_R72={sum(x['r72_pct'] for x in rs)/len(rs):.3f}% "
                  f"mean_ATR_pct={sum(x['atr_pct'] for x in rs if x['atr_pct'] is not None)/max(1,sum(x['atr_pct'] is not None for x in rs)):.3f}%")
if __name__=="__main__": main()
