#!/usr/bin/env python3
"""Market-context diagnostics for the selected H1 universe and BTC/ETH benchmarks."""
from __future__ import annotations
import csv, os, sys, math
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT); sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import Bybit_Trading_Engine_v14_research as em
from run_uploaded_dataset_backtests import read_zip_datasets

SYMBOLS=["RAYUSDT","PUMPUSDT","TAOUSDT","AAVEUSDT","CAKEUSDT"]
BENCHMARKS=["BTCUSDT","ETHUSDT"]
FOLDS=[(1,"2026-04-27T12:00:00Z","2026-06-21T05:00:00Z"),(2,"2026-06-21T06:00:00Z","2026-08-14T23:00:00Z"),(3,"2026-08-15T00:00:00Z","2026-10-27T00:00:00Z")]

def calc(candles, start, end, symbol, fold):
    cs=candles[start:end+1]
    if len(cs)<80: return None
    closes=np.array([c.close for c in cs],float)
    highs=np.array([c.high for c in cs],float); lows=np.array([c.low for c in cs],float)
    opens=np.array([c.open for c in cs],float)
    rets=np.diff(np.log(closes))*100
    def ret(n):
        return (closes[-1]/closes[-1-n]-1)*100 if len(closes)>n else float("nan")
    def er(n):
        if len(closes)<=n: return float("nan")
        path=np.abs(np.diff(closes[-n-1:])).sum()
        return abs(closes[-1]-closes[-1-n])/path if path else 0.0
    # ATR14 using prior close, calculated without external libraries.
    prev=np.r_[closes[0],closes[:-1]]
    tr=np.maximum(highs-lows,np.maximum(np.abs(highs-prev),np.abs(lows-prev)))
    atr14=float(np.mean(tr[-14:]))
    # EMA20 trend persistence on hourly closes.
    alpha=2/21; ema=closes[0]
    emas=[]
    for x in closes:
        ema=alpha*x+(1-alpha)*ema; emas.append(ema)
    emas=np.array(emas)
    # Drawdown from rolling segment peak and close-to-close volatility.
    peak=np.maximum.accumulate(closes)
    dd=(closes/peak-1)*100
    # Candle volume ratio vs preceding 20 bars within full archive.
    vols=np.array([c.volume for c in cs],float)
    volratio=[]
    for j in range(20,len(cs)):
        mean=vols[j-20:j].mean()
        if mean>0: volratio.append(vols[j]/mean)
    return {
      "fold":fold,"symbol":symbol,"bars":len(cs),
      "start_ts":cs[0].ts,"end_ts":cs[-1].ts,
      "return_pct":(closes[-1]/closes[0]-1)*100,
      "return_24h_pct_end":ret(24),"return_72h_pct_end":ret(72),
      "hourly_volatility_pct":float(np.std(rets)) if len(rets) else 0,
      "mean_abs_hourly_return_pct":float(np.mean(np.abs(rets))) if len(rets) else 0,
      "atr14_pct_mean":float(np.mean(tr[-min(len(tr),1000):]/closes[-min(len(closes),1000):]*100)),
      "atr14_pct_end":atr14/closes[-1]*100,
      "efficiency_24h_end":er(24),"efficiency_72h_end":er(72),
      "ema20_above_pct":float(np.mean(closes>emas)*100),
      "max_drawdown_pct":float(dd.min()),
      "volume_ratio_median":float(np.median(volratio)) if volratio else float("nan"),
      "volume_ratio_p90":float(np.quantile(volratio,.9)) if volratio else float("nan"),
    }

def main():
    datasets=read_zip_datasets()
    wanted=set(SYMBOLS+BENCHMARKS)
    raw={s:datasets[(s,"1h")][2] for s in wanted if (s,"1h") in datasets}
    missing=sorted(wanted-set(raw))
    if missing: raise SystemExit(f"Missing required H1 market context: {missing}")
    common=set(c.ts for c in raw[BENCHMARKS[0]])
    for cs in raw.values(): common &= set(c.ts for c in cs)
    stamps=sorted(common)
    if len(stamps)<3000: raise SystemExit(f"Insufficient synchronized bars: {len(stamps)}")
    maps={s:{c.ts:c for c in cs} for s,cs in raw.items()}
    aligned={s:[m[t] for t in stamps] for s,m in maps.items()}
    rows=[]
    for fold,start_iso,end_iso in FOLDS:
      start_ts=int(datetime.strptime(start_iso,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()*1000)
      end_ts=int(datetime.strptime(end_iso,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()*1000)
      i0=next((i for i,t in enumerate(stamps) if t>=start_ts),None)
      i1=next((i for i in range(len(stamps)-1,-1,-1) if stamps[i]<=end_ts),None)
      if i0 is None or i1 is None or i1-i0<80:
        raise SystemExit(f"Invalid fold window {fold}: {start_iso}..{end_iso}; indices={i0},{i1}")
      print(f"fold={fold} window={start_iso}..{end_iso} bars={i1-i0+1}")
      for sym,cs in aligned.items():
        r=calc(cs,i0,i1,sym,fold)
        if r: rows.append(r)
      # Equal-weight basket of selected alt returns and breadth; contextual only, not portfolio PnL.
      for i in range(i0+72,i1+1):
        basket=[]
        for sym in SYMBOLS:
          cs=aligned[sym]
          basket.append(cs[i].close/cs[i-24].close-1)
        # benchmark momentum breadth on the same timestamp.
      # Append period-wide alt breadth computed from each coin's segment total return.
    dfout="h1_market_context_by_symbol.csv"
    fields=list(rows[0])
    with open(dfout,"w",newline="",encoding="utf-8") as f:
      w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"Wrote {dfout}: {len(rows)} rows")
    print("fold,symbol,return_pct,atr14_pct_mean,volatility_pct,ER24_end,ER72_end,EMA20_above_pct,maxDD_pct,median_volratio")
    for r in rows:
      print(f"{r['fold']},{r['symbol']},{r['return_pct']:.3f},{r['atr14_pct_mean']:.3f},{r['hourly_volatility_pct']:.4f},{r['efficiency_24h_end']:.3f},{r['efficiency_72h_end']:.3f},{r['ema20_above_pct']:.1f},{r['max_drawdown_pct']:.2f},{r['volume_ratio_median']:.3f}")
    print("CAVEAT: segment descriptors are descriptive, not predictive filters; BTC/ETH and selected altcoin candles are Binance OHLCV proxies.")

if __name__=="__main__": main()
