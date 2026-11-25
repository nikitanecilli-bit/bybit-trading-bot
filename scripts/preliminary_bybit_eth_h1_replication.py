#!/usr/bin/env python3
"""Cross-asset replication of fixed BTC H1 candidate on Bybit ETHUSDT.

No parameters are optimized on ETH. Reuses Donchian48 + EMA50/200, volume
ratio 1.6 and identical stop/target/time-exit and fee/slippage assumptions.
"""
import csv, json
from pathlib import Path
import preliminary_bybit_btc_h1_backtest as base

base.DATA=Path("bybit_ethusdt_initial/trade_h1.csv")
base.VOL_THRESHOLD=1.6
ARM=(48,True,"C_D48_EMA_FIXED_FROM_BTC")
COSTS=[1.0,1.5,2.0]
OUT=Path("eth_replication"); OUT.mkdir(exist_ok=True)

def main():
    rows=base.load()
    gaps=[rows[i][0]-rows[i-1][0] for i in range(1,len(rows)) if rows[i][0]-rows[i-1][0]!=base.BAR_MS]
    segments=1+len(gaps)
    print("DATA "+json.dumps({"source":"Bybit official public H1 archive","symbol":"ETHUSDT","bars":len(rows),
      "start_utc":base.utc(rows[0][0]),"end_utc":base.utc(rows[-1][0]),"gaps":len(gaps),
      "missing_h1_bars":sum(max(0,g//base.BAR_MS-1) for g in gaps),"segments":segments},sort_keys=True))
    summary=[]; details=[]
    for fold in (1,2,3):
      for cm in COSTS:
        result=base.backtest(rows,fold,ARM,cm)
        trades=result.pop("trades_detail")
        summary.append(result)
        details.extend([{"fold":fold,"cost_multiplier":cm,**t} for t in trades])
        print("RESULT "+json.dumps(result,sort_keys=True))
    with (OUT/"summary.csv").open("w",newline="",encoding="utf-8") as f:
      w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    with (OUT/"trades.csv").open("w",newline="",encoding="utf-8") as f:
      fields=list(details[0]) if details else ["fold","cost_multiplier","entry_ts","exit_ts","entry","exit","gross_pnl","costs","net_pnl","risk","reason","bars"]
      w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(details)
    print(f"OUTPUT {OUT}/summary.csv and {OUT}/trades.csv; configurations={len(summary)}; trades={len(details)}")

if __name__=="__main__": main()
