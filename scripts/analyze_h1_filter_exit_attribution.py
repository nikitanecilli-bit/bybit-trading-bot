#!/usr/bin/env python3
"""Compare trade/exit attribution for baseline and causal H1 session filters."""
from __future__ import annotations
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import Bybit_Trading_Engine_v14_research as em
from scripts.run_uploaded_dataset_backtests import read_zip_datasets

WINDOWS = (
    ("screen", "2025-10-27T00:00:00+00:00", "2026-04-29T00:00:00+00:00"),
    ("forward", "2026-04-29T00:00:00+00:00", "2026-10-27T00:00:00+00:00"),
)
HOUR = 3_600_000
VARIANTS = ("baseline", "entry_us_block", "aligned_entry_us_block")

def ms(s):
    return int(datetime.fromisoformat(s).timestamp()*1000)

def run_one(symbol, sliced, period, variant):
    e=em.UnifiedQuantEngine(journal_output_path="/tmp/ignored_h1_filter_attribution.json")
    c=e.cfg
    c.bot_version="h1-filter-exit-attribution"; c.timeframe="1h"
    c.active_trading_pool=[symbol]; c.capital_usdt=10000.0
    c.max_risk_trade_pct=1.0; c.max_portfolio_risk_pct=2.0
    c.max_concurrent_positions=1; c.daily_stop_loss_pct=5.0
    c.emergency_kill_switch_pct=30.0; c.donchian_period=20; c.atr_period=14
    c.min_volume_ratio=1.6; c.stop_atr_mult=2.5; c.tp1_r_multiple=2.0
    c.tp2_r_multiple=5.0; c.atr_trail_mult=3.0; c.max_hold_bars=32
    c.maker_entry_and_tp1=False; c.enable_h2_range_fade=False
    c.validate(); e.risk_mgr.cfg=c; e.tg.send_message=lambda *_a,**_k:None
    original=em.QuantStrategyCore.evaluate_signal
    def filtered(sym, candles, cfg):
        sig=original(sym,candles,cfg)
        if sig is None or variant=="baseline": return sig
        entry_ts=candles[-1].ts+HOUR
        if em.QuantStrategyCore.get_utc_session(entry_ts)=="us": return None
        if variant=="aligned_entry_us_block":
            prior=candles[:-1]
            if len(prior)<25:return None
            ret24=prior[-1].close/prior[-25].close-1.0
            if not (ret24>0 if sig["direction"]=="long" else ret24<0): return None
        return sig
    em.QuantStrategyCore.evaluate_signal=staticmethod(filtered)
    try:
        em.check_alignment({symbol:sliced})
        em.run_simulation_pass(e,{symbol:sliced},[symbol],data_label=f"{period} {variant} {symbol}")
        return [{
            "period":period,"variant":variant,"symbol":symbol,
            "direction":t.direction,"session":t.session,"exit_reason":t.exit_reason,
            "net":t.pnl_usdt,"gross":t.gross_pnl,"fees":t.exchange_fees_usdt,
            "slippage":t.slippage_cost_usdt,"net_r":t.r_multiple,
            "mfe_r":t.mfe,"mae_r":t.mae,
        } for t in e.closed_trades]
    finally:
        em.QuantStrategyCore.evaluate_signal=staticmethod(original)

def main():
    ds=read_zip_datasets(); eligible={}
    lo,hi=ms(WINDOWS[0][1]),ms(WINDOWS[1][2])
    for (sym,tf),(_,_,candles) in ds.items():
        if tf=="1h" and candles[0].ts<=lo and candles[-1].ts>=hi-HOUR: eligible[sym]=candles
    print(f"ELIGIBLE_SYMBOLS={len(eligible)}")
    rows=[]
    for sym,full in sorted(eligible.items()):
        for period,start,end in WINDOWS:
            a,b=ms(start),ms(end); sliced=[c for c in full if a<=c.ts<b]
            if len(sliced)<200:continue
            for variant in VARIANTS: rows.extend(run_one(sym,sliced,period,variant))
    for period,_,_ in WINDOWS:
        for variant in VARIANTS:
            group=[r for r in rows if r["period"]==period and r["variant"]==variant]
            if not group:continue
            print(f"SUMMARY period={period} variant={variant} trades={len(group)} "
                  f"net={sum(r['net'] for r in group):.2f} gross={sum(r['gross'] for r in group):.2f} "
                  f"fees={sum(r['fees'] for r in group):.2f} slippage={sum(r['slippage'] for r in group):.2f} "
                  f"wins={sum(r['net']>0 for r in group)}")
            for key in ("exit_reason","session","direction"):
                buckets=defaultdict(list)
                for r in group:buckets[r[key]].append(r)
                for k,rs in sorted(buckets.items(),key=lambda x:str(x[0])):
                    n=len(rs); net=sum(x["net"] for x in rs)
                    print(f"GROUP period={period} variant={variant} {key}={k} n={n} "
                          f"net={net:.2f} mean_net={net/n:.2f} wins={sum(x['net']>0 for x in rs)} "
                          f"mean_MFE_R={sum(x['mfe_r'] for x in rs)/n:.3f} "
                          f"mean_MAE_R={sum(x['mae_r'] for x in rs)/n:.3f}")
if __name__=="__main__":main()
