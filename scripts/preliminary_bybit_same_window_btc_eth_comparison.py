#!/usr/bin/env python3
"""Same-calendar-window replication: compare fixed BTC candidate on BTC and ETH."""
import csv, json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import preliminary_bybit_btc_h1_backtest as base

START="2024-04-11T13:00:00+00:00"
END="2024-12-12T02:00:00+00:00"
DATE_RANGE=(int(datetime.fromisoformat(START).timestamp()*1000),
            int(datetime.fromisoformat(END).timestamp()*1000))
ARM=(48,True,"C_D48_EMA_FIXED_FROM_BTC")
COSTS=(1.0,1.5,2.0)
OUT=Path("same_window_comparison"); OUT.mkdir(exist_ok=True)

def main():
    summaries=[]; trades_out=[]; monthly=defaultdict(lambda:{"trades":0,"net_pnl_usdt":0.0,"wins":0})
    for symbol in ("BTCUSDT","ETHUSDT"):
        base.DATA=Path(f"bybit_{symbol.lower()}_initial/trade_h1.csv")
        rows=base.load()
        gaps=sum(rows[i][0]-rows[i-1][0]!=base.BAR_MS for i in range(1,len(rows)))
        first=next((r[0] for r in rows if r[0]>=DATE_RANGE[0]),None)
        last=next((r[0] for r in reversed(rows) if r[0]<=DATE_RANGE[1]),None)
        if first is None or last is None: raise SystemExit(f"{symbol}: requested range not covered")
        print("DATA "+json.dumps({"symbol":symbol,"bars_total":len(rows),"gaps_total":gaps,
          "window_first_utc":base.utc(first),"window_last_utc":base.utc(last)},sort_keys=True))
        for cm in COSTS:
            result=base.backtest(rows,2,ARM,cm,date_range=DATE_RANGE)
            trades=result.pop("trades_detail")
            summaries.append({"symbol":symbol,**result})
            for t in trades:
                trades_out.append({"symbol":symbol,"cost_multiplier":cm,**t})
                month=base.utc(t["entry_ts"])[:7]
                m=monthly[(symbol,cm,month)]
                m["trades"]+=1; m["net_pnl_usdt"]+=t["net_pnl"]; m["wins"]+=int(t["net_pnl"]>0)
            print("RESULT "+json.dumps({"symbol":symbol,**result},sort_keys=True))
    with (OUT/"summary.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
    with (OUT/"trades.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(trades_out[0]));w.writeheader();w.writerows(trades_out)
    with (OUT/"monthly.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["symbol","cost_multiplier","month","trades","wins","net_pnl_usdt"])
        for (symbol,cm,month),v in sorted(monthly.items()):
            w.writerow([symbol,cm,month,v["trades"],v["wins"],round(v["net_pnl_usdt"],2)])
    (OUT/"methodology.json").write_text(json.dumps({"source":"Bybit official public H1 archives only",
      "symbols":["BTCUSDT","ETHUSDT"],"window_start_utc":START,"window_end_utc":END,
      "strategy":"Fixed BTC Arm C; Donchian 48, EMA50>EMA200, EMA200 rising over 5 bars, close>EMA200, volume ratio 1.6",
      "cost_multipliers":COSTS,"other_parameters":"Identical stop/target/trailing/time exit/risk/fee assumptions from common engine",
      "purpose":"Compare assets on the exact calendar period that was ETH fold 2; no parameter fitting",
      "limitations":"OHLCV-only preliminary replay; no funding, mark price, liquidation model, dated specs/risk tiers or spread"},indent=2))
    print(f"OUTPUT {OUT}; configurations={len(summaries)} trade_rows={len(trades_out)}")

if __name__=="__main__": main()
