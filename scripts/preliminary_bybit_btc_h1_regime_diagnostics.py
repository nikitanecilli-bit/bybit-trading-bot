#!/usr/bin/env python3
"""Descriptive regime and trade-concentration diagnostics for BTC H1 candidate C.

No strategy parameters are optimized. Uses fixed volume threshold 1.6 and
reports trade outcomes by entry-time ATR% tercile and EMA spread tercile.
"""
import csv, json, math
from pathlib import Path
import preliminary_bybit_btc_h1_backtest as base

OUT=Path("regime_diagnostics"); OUT.mkdir(exist_ok=True)
THRESHOLD=1.6
ARM=(48,True,"C_D48_EMA")
COSTS=[1.0,2.0]

def quantile(values,p):
    s=sorted(values)
    if not s: return 0.0
    x=(len(s)-1)*p; lo=int(x); hi=min(lo+1,len(s)-1); w=x-lo
    return s[lo]*(1-w)+s[hi]*w

def bucket(v,a,b):
    return "low" if v<=a else ("mid" if v<=b else "high")

def ema_arrays(rows):
    e50=[None]*len(rows); e200=[None]*len(rows); start=0
    for k in range(1,len(rows)+1):
        if k==len(rows) or rows[k][0]-rows[k-1][0]!=base.BAR_MS:
            closes=[r[4] for r in rows[start:k]]
            e50[start:k]=base.ema(closes,50); e200[start:k]=base.ema(closes,200)
            start=k
    return e50,e200

def summarize(items):
    pnl=[x["net_pnl"] for x in items]
    wins=[x for x in pnl if x>0]; losses=[x for x in pnl if x<0]
    gross_win=sum(wins); gross_loss=-sum(losses)
    return {"trades":len(items),"net_pnl_usdt":round(sum(pnl),2),
            "avg_pnl_usdt":round(sum(pnl)/len(pnl),2) if pnl else 0,
            "win_rate_pct":round(len(wins)/len(items)*100,2) if items else 0,
            "profit_factor":round(gross_win/gross_loss,3) if gross_loss else (999 if gross_win else 0),
            "expectancy_r":round(sum(x["r"] for x in items)/len(items),4) if items else 0}

def main():
    rows=base.load(); base.VOL_THRESHOLD=THRESHOLD
    e50,e200=ema_arrays(rows)
    ix={r[0]:i for i,r in enumerate(rows)}
    out=[]; concentration=[]
    for fold in (1,2,3):
      for cm in COSTS:
        result=base.backtest(rows,fold,ARM,cm)
        trades=result.pop("trades_detail")
        enriched=[]
        for t in trades:
            i=ix.get(t["entry_ts"],-1); sig=i-1
            if sig<0: continue
            atr=base.atr_at(rows,sig)
            spread=((e50[sig]-e200[sig])/rows[sig][4]) if e50[sig] is not None and e200[sig] is not None else None
            enriched.append({**t,"atr_pct":(atr/rows[sig][4]*100) if atr else None,"ema_spread_pct":spread*100 if spread is not None else None,"r":t["net_pnl"]/t["risk"] if t["risk"] else 0})
        valid_atr=[x["atr_pct"] for x in enriched if x["atr_pct"] is not None]
        valid_spread=[x["ema_spread_pct"] for x in enriched if x["ema_spread_pct"] is not None]
        aq1,aq2=quantile(valid_atr,1/3),quantile(valid_atr,2/3)
        sq1,sq2=quantile(valid_spread,1/3),quantile(valid_spread,2/3)
        for field,qs in [("atr_pct",(aq1,aq2)),("ema_spread_pct",(sq1,sq2))]:
            for label in ("low","mid","high"):
                group=[x for x in enriched if x[field] is not None and bucket(x[field],*qs)==label]
                out.append({"fold":fold,"cost_multiplier":cm,"dimension":field,"bucket":label,
                            "lower_cut":round(qs[0],5),"upper_cut":round(qs[1],5),**summarize(group)})
        ranked=sorted(enriched,key=lambda x:x["net_pnl"],reverse=True)
        positive=sum(max(0,x["net_pnl"]) for x in enriched)
        concentration.append({"fold":fold,"cost_multiplier":cm,"trades":len(enriched),
            "top5_share_of_positive_pnl_pct":round(sum(max(0,x["net_pnl"]) for x in ranked[:5])/positive*100,2) if positive else 0,
            "top10_share_of_positive_pnl_pct":round(sum(max(0,x["net_pnl"]) for x in ranked[:10])/positive*100,2) if positive else 0,
            "best_trade_usdt":round(max((x["net_pnl"] for x in enriched),default=0),2),
            "worst_trade_usdt":round(min((x["net_pnl"] for x in enriched),default=0),2),
            "total_net_pnl_usdt":round(sum(x["net_pnl"] for x in enriched),2)})
        print("FOLD "+json.dumps({"fold":fold,"cost_multiplier":cm,**{k:v for k,v in result.items() if k!="trades_detail"}},sort_keys=True))
    with (OUT/"regimes.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    with (OUT/"concentration.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(concentration[0]));w.writeheader();w.writerows(concentration)
    print("REGIME_RESULTS "+json.dumps(out,sort_keys=True))
    print("CONCENTRATION "+json.dumps(concentration,sort_keys=True))
    print(f"OUTPUT {OUT}/regimes.csv and {OUT}/concentration.csv")

if __name__=="__main__": main()
