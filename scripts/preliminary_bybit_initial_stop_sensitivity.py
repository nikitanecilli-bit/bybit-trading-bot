#!/usr/bin/env python3
"""Initial-stop ATR sensitivity across BTC/ETH chronological folds; no parameter fitting."""
import csv, json
from pathlib import Path
import preliminary_bybit_btc_h1_backtest as base

ARM=(48,True,"C_D48_EMA_FIXED_FROM_BTC")
STOPS=(2.5,3.0,3.5)
COSTS=(1.0,1.5,2.0)
OUT=Path("stop_sensitivity"); OUT.mkdir(exist_ok=True)

def main():
    summaries=[]; trades_out=[]
    for symbol in ("BTCUSDT","ETHUSDT"):
        base.DATA=Path(f"bybit_{symbol.lower()}_initial/trade_h1.csv")
        rows=base.load()
        gaps=sum(rows[i][0]-rows[i-1][0]!=base.BAR_MS for i in range(1,len(rows)))
        print("DATA "+json.dumps({"symbol":symbol,"bars":len(rows),"gaps":gaps},sort_keys=True))
        for fold in (1,2,3):
            for stop in STOPS:
                for cm in COSTS:
                    result=base.backtest(rows,fold,ARM,cm,stop_atr=stop)
                    details=result.pop("trades_detail")
                    summaries.append({"symbol":symbol,**result})
                    for t in details:
                        trades_out.append({"symbol":symbol,"fold":fold,"stop_atr":stop,
                                           "cost_multiplier":cm,**t})
                    print("RESULT "+json.dumps({"symbol":symbol,"fold":fold,"stop_atr":stop,
                          "cost_multiplier":cm,**result},sort_keys=True))
    with (OUT/"summary.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
    with (OUT/"trades.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(trades_out[0]));w.writeheader();w.writerows(trades_out)
    (OUT/"methodology.json").write_text(json.dumps({
      "source":"Official Bybit public H1 archives only","symbols":["BTCUSDT","ETHUSDT"],
      "folds":"Same chronological folds as existing preliminary engine (50-65%, 65-80%, 80-100%)",
      "fixed_strategy":"Arm C, Donchian 48, EMA50>EMA200, EMA200 rising over 5 bars, close>EMA200, volume ratio 1.6",
      "tested_initial_stop_atr":STOPS,"cost_multipliers":COSTS,
      "risk":"Position quantity recalculated to keep initial nominal risk at 1% equity; TP1=2R, TP2=5R, trailing=3 ATR after TP1",
      "purpose":"Test whether wider initial stop improves out-of-sample results across multiple folds/assets; no fitting",
      "limitations":"OHLCV-only; no funding, mark price, liquidation model, dated specs/risk tiers or spread"
    },indent=2))
    print(f"OUTPUT {OUT}; configurations={len(summaries)} trade_rows={len(trades_out)}")

if __name__=="__main__": main()
