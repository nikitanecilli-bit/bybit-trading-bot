#!/usr/bin/env python3
"""Volume-threshold sensitivity for the preregistered BTCUSDT H1 candidate.

The strategy rules are unchanged from preliminary_bybit_btc_h1_backtest.py.
Only min_volume_ratio changes. Fold 1+2 are the development sample; fold 3
is reported separately as a later-period diagnostic and is not used to rank
thresholds. This remains OHLCV-only preliminary research, not production PnL.
"""
import csv, json
from pathlib import Path
import preliminary_bybit_btc_h1_backtest as base

THRESHOLDS = [1.2, 1.6, 2.0, 2.5]
ARM = (48, True, "C_D48_EMA")
COSTS = [1.0, 1.5, 2.0]
OUT = Path("volume_sensitivity")
OUT.mkdir(exist_ok=True)

def main():
    rows=base.load()
    segments=1+sum(rows[i][0]-rows[i-1][0]!=base.BAR_MS for i in range(1,len(rows)))
    print(f"DATA source=Bybit official public archive; bars={len(rows)}; gaps={segments-1}; segments={segments}")
    summary=[]; details=[]
    for threshold in THRESHOLDS:
        base.VOL_THRESHOLD=threshold
        for fold in (1,2,3):
            for cm in COSTS:
                result=base.backtest(rows,fold,ARM,cm)
                trades=result.pop("trades_detail")
                summary.append(result)
                details.extend([{"fold":fold,"volume_threshold":threshold,"cost_multiplier":cm,**t} for t in trades])
                print("RESULT "+json.dumps(result,sort_keys=True))
    with (OUT/"summary.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    with (OUT/"trades.csv").open("w",newline="",encoding="utf-8") as f:
        fields=list(details[0]) if details else ["fold","volume_threshold","cost_multiplier","entry_ts","exit_ts","entry","exit","gross_pnl","costs","net_pnl","risk","reason","bars"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(details)
    print(f"OUTPUT {OUT}/summary.csv and {OUT}/trades.csv; configurations={len(summary)}; trades={len(details)}")

if __name__=="__main__": main()
