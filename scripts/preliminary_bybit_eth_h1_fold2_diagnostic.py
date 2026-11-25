#!/usr/bin/env python3
"""Trade-level diagnosis of the fixed ETH H1 strategy's losing second fold."""
import csv, json
from collections import defaultdict
from pathlib import Path
import preliminary_bybit_btc_h1_backtest as base

base.DATA = Path("bybit_ethusdt_initial/trade_h1.csv")
base.VOL_THRESHOLD = 1.6
ARM = (48, True, "C_D48_EMA_FIXED_FROM_BTC")
OUT = Path("eth_fold2_diagnostic")
OUT.mkdir(exist_ok=True)

def indicators(rows):
    closes=[r[4] for r in rows]
    e50=[None]*len(rows); e200=[None]*len(rows)
    seg=0
    for k in range(1,len(rows)+1):
        if k==len(rows) or rows[k][0]-rows[k-1][0] != base.BAR_MS:
            e50[seg:k]=base.ema(closes[seg:k],50)
            e200[seg:k]=base.ema(closes[seg:k],200)
            seg=k
    return e50,e200

def terciles(values):
    a=sorted(v for v in values if v is not None)
    if not a: return (None,None)
    return (a[len(a)//3],a[(2*len(a))//3])

def bucket(v, cuts):
    if v is None or cuts[0] is None: return "unknown"
    return "low" if v<=cuts[0] else ("mid" if v<=cuts[1] else "high")

def main():
    rows=base.load()
    e50,e200=indicators(rows)
    byts={r[0]:i for i,r in enumerate(rows)}
    # Recreate exactly the fold-2 row interval used by the common engine.
    lo=int(len(rows)*.65); hi=max(lo+1,int(len(rows)*.80))
    entry_context=[]
    for i in range(lo,hi):
        a=base.atr_at(rows,i)
        atr_pct=(a/rows[i][4]) if a else None
        spread=((e50[i]-e200[i])/rows[i][4]) if e50[i] is not None and e200[i] is not None else None
        entry_context.append((atr_pct,spread))
    atr_cuts=terciles([x[0] for x in entry_context])
    spread_cuts=terciles([x[1] for x in entry_context])
    out=[]
    for cm in (1.0,2.0):
        result=base.backtest(rows,2,ARM,cm)
        trades=result.pop("trades_detail")
        months=defaultdict(lambda:{"trades":0,"net_pnl_usdt":0.0,"wins":0,"gross_pnl_usdt":0.0,"costs_usdt":0.0})
        exits=defaultdict(lambda:{"trades":0,"net_pnl_usdt":0.0})
        regimes=defaultdict(lambda:{"trades":0,"net_pnl_usdt":0.0,"wins":0})
        for t in trades:
            dt=base.utc(t["entry_ts"])
            month=dt[:7]
            m=months[month]; m["trades"]+=1; m["net_pnl_usdt"]+=t["net_pnl"]
            m["gross_pnl_usdt"]+=t["gross_pnl"]; m["costs_usdt"]+=t["costs"]
            m["wins"]+=int(t["net_pnl"]>0)
            x=exits[t["reason"]]; x["trades"]+=1; x["net_pnl_usdt"]+=t["net_pnl"]
            idx=byts.get(t["entry_ts"])
            if idx is None and t["entry_ts"]-base.BAR_MS in byts: idx=byts[t["entry_ts"]-base.BAR_MS]
            if idx is not None:
                a=base.atr_at(rows,idx); ap=a/rows[idx][4] if a else None
                sp=((e50[idx]-e200[idx])/rows[idx][4]) if e50[idx] is not None and e200[idx] is not None else None
                key=(bucket(ap,atr_cuts),bucket(sp,spread_cuts))
            else: key=("unknown","unknown")
            g=regimes["ATR_"+key[0]+"__EMAspread_"+key[1]]
            g["trades"]+=1; g["net_pnl_usdt"]+=t["net_pnl"]; g["wins"]+=int(t["net_pnl"]>0)
        for d in (months,exits,regimes):
            for v in d.values():
                for k in ("net_pnl_usdt","gross_pnl_usdt","costs_usdt"):
                    if k in v: v[k]=round(v[k],2)
        top=sorted(trades,key=lambda t:t["net_pnl"],reverse=True)
        out.append({"cost_multiplier":cm,"fold_result":{k:v for k,v in result.items() if k!="trades_detail"},
          "monthly":dict(sorted(months.items())),"exit_reasons":dict(exits),"entry_regimes":dict(regimes),
          "top5_net_pnl_sum":round(sum(t["net_pnl"] for t in top[:5]),2),
          "bottom5_net_pnl_sum":round(sum(t["net_pnl"] for t in sorted(trades,key=lambda t:t["net_pnl"])[:5]),2),
          "trades":trades})
    payload={"symbol":"ETHUSDT","fold":2,"strategy":"fixed BTC Arm C, volume threshold 1.6",
      "data_bars":len(rows),"data_start_utc":base.utc(rows[0][0]),"data_end_utc":base.utc(rows[-1][0]),
      "gaps":sum(rows[i][0]-rows[i-1][0]!=base.BAR_MS for i in range(1,len(rows))),
      "atr_tercile_cutoffs":atr_cuts,"ema_spread_tercile_cutoffs":spread_cuts,"cost_runs":out}
    (OUT/"diagnostic.json").write_text(json.dumps(payload,indent=2))
    with (OUT/"monthly.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["cost_multiplier","month","trades","wins","net_pnl_usdt","gross_pnl_usdt","costs_usdt"])
        for run in out:
            for month,v in run["monthly"].items(): w.writerow([run["cost_multiplier"],month,v["trades"],v["wins"],v["net_pnl_usdt"],v["gross_pnl_usdt"],v["costs_usdt"]])
    print("DIAGNOSTIC "+json.dumps({k:v for k,v in payload.items() if k!="cost_runs"},sort_keys=True))
    for run in out:
        print("FOLD2 "+json.dumps({k:v for k,v in run.items() if k!="trades"},sort_keys=True))
    print(f"OUTPUT {OUT}/diagnostic.json and monthly.csv; trade_rows={sum(len(x['trades']) for x in out)}")

if __name__=="__main__": main()
