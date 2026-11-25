#!/usr/bin/env python3
"""Preliminary BTCUSDT H1 Bybit-only replay; OHLCV-only, explicitly non-final.

Uses the already archived official Bybit public H1 trade candles. Gaps reset
indicator warm-up and positions; no synthetic candles are inserted. Taker
fees/slippage are stressed at 1x/1.5x/2x. Funding, mark-price liquidation,
dated specs/risk tiers and queue/fill effects are excluded and disclosed.
"""
from __future__ import annotations
import csv, json, math, os
from pathlib import Path
from datetime import datetime, timezone
from bisect import bisect_left, bisect_right

DATA = Path(os.getenv("BYBIT_H1_CSV", "bybit_btcusdt_initial/trade_h1.csv"))
OUT = Path("preliminary_backtest")
OUT.mkdir(exist_ok=True)
START_CAPITAL = 10_000.0
RISK_FRACTION = 0.01
DONCHIAN_ARMS = [(20, False, "A_D20"), (48, False, "B_D48"), (48, True, "C_D48_EMA")]
VOL_THRESHOLD = 1.6
COSTS = [1.0, 1.5, 2.0]
TAKER_FEE = 0.00055
SLIPPAGE = 0.000225
BAR_MS = 3_600_000

def utc(ts):
    return datetime.fromtimestamp(ts/1000, timezone.utc).isoformat()

def ema(values, period):
    out=[None]*len(values)
    if len(values)<period: return out
    alpha=2.0/(period+1)
    seed=sum(values[:period])/period
    out[period-1]=seed
    prev=seed
    for i in range(period,len(values)):
        prev=values[i]*alpha+prev*(1-alpha)
        out[i]=prev
    return out

def load():
    if not DATA.is_file(): raise SystemExit(f"Missing Bybit H1 CSV: {DATA}")
    rows=[]
    with DATA.open(newline="",encoding="utf-8-sig") as f:
        rd=csv.DictReader(f)
        required={"start_ms","open","high","low","close","volume"}
        if not rd.fieldnames or not required.issubset(rd.fieldnames):
            raise SystemExit(f"Unexpected Bybit CSV schema: {rd.fieldnames}")
        for r in rd:
            ts=int(r["start_ms"]); o,h,l,c,v=[float(r[k]) for k in ("open","high","low","close","volume")]
            if min(o,h,l,c)<=0 or v<0 or h<max(o,c,l) or l>min(o,c,h): raise SystemExit(f"Invalid OHLCV at {ts}")
            rows.append((ts,o,h,l,c,v))
    rows.sort()
    if len({r[0] for r in rows})!=len(rows): raise SystemExit("Duplicate H1 timestamps")
    return rows

def atr_at(rows, i, period=14):
    if i<period: return None
    tr=[]
    for j in range(i-period+1,i+1):
        prev=rows[j-1][4]
        tr.append(max(rows[j][2]-rows[j][3],abs(rows[j][2]-prev),abs(rows[j][3]-prev)))
    return sum(tr)/period

def backtest(rows, fold, arm, cost_mult, date_range=None, stop_atr=2.5):
    period, use_ema, arm_name=arm
    # Folds are indexed over the complete chronological archive. Segment breaks
    # are respected; indicators only use bars from the current contiguous segment.
    n=len(rows)
    if date_range is None:
        lo,hi={1:(.50,.65),2:(.65,.80),3:(.80,1.00)}[fold]
        start_idx=int(n*lo); end_idx=max(start_idx+1,int(n*hi))
    else:
        timestamps=[r[0] for r in rows]
        start_idx=bisect_left(timestamps,date_range[0])
        end_idx=bisect_right(timestamps,date_range[1])
        if start_idx>=end_idx:
            raise ValueError(f"No rows in requested date range: {date_range}")
    score_start=rows[start_idx][0]; score_end=rows[min(end_idx-1,n-1)][0]
    volumes=[r[5] for r in rows]
    ema50=[None]*len(rows); ema200=[None]*len(rows)
    seg_start=0
    for k in range(1,len(rows)+1):
        if k==len(rows) or rows[k][0]-rows[k-1][0]!=BAR_MS:
            local_close=[r[4] for r in rows[seg_start:k]]
            e50=ema(local_close,50); e200=ema(local_close,200)
            ema50[seg_start:k]=e50; ema200[seg_start:k]=e200
            seg_start=k
    equity=START_CAPITAL; peak=equity; max_dd=0.0
    trades=[]; pos=None; segment_start=0; i=0
    while i<len(rows):
        if i==end_idx and pos:
            _close_position(pos,rows[i-1][4],rows[i-1][0]+BAR_MS,"fold_end",cost_mult,trades); equity+=trades[-1]["net_pnl"]; pos=None
        if i>0 and rows[i][0]-rows[i-1][0]!=BAR_MS:
            if pos:
                _close_position(pos, rows[i-1][4], rows[i-1][0]+BAR_MS, "data_gap", cost_mult, trades)
                equity += trades[-1]["net_pnl"]
                pos=None
            segment_start=i
        ts,o,h,l,c,v=rows[i]
        # Exit logic only inside the scored fold. Existing position never crosses
        # fold boundaries: folds are independent out-of-sample slices.
        if i==start_idx and pos:
            _close_position(pos,o,ts,"fold_boundary",cost_mult,trades); equity+=trades[-1]["net_pnl"]; pos=None
        if pos and score_start<=ts<=score_end:
            pos["bars"]+=1
            stop=pos["stop"]
            # Conservative OHLC ordering: stop is assumed before profit targets.
            if l<=stop:
                px=min(o,stop) if o<stop else stop
                stop_reason = "trailing_stop" if pos["tp1"] else "initial_stop"
                _close_position(pos,px,ts,stop_reason,cost_mult,trades); equity+=trades[-1]["net_pnl"]; pos=None
            else:
                if not pos["tp1"] and h>=pos["tp1_price"]:
                    _partial_exit(pos,pos["tp1_price"],0.5,cost_mult)
                    pos["tp1"]=True
                    # Trailing level becomes active from the next candle.
                    a=atr_at(rows,i)
                    if a: pos["next_trail"]=max(pos["stop"],c-3*a)
                elif pos["tp1"] and h>=pos["tp2_price"]:
                    _close_position(pos,pos["tp2_price"],ts,"tp2",cost_mult,trades); equity+=trades[-1]["net_pnl"]; pos=None
                if pos:
                    if pos.get("next_trail") is not None:
                        pos["stop"]=max(pos["stop"],pos["next_trail"]); pos["next_trail"]=None
                    a=atr_at(rows,i)
                    if pos["tp1"] and a: pos["next_trail"]=max(pos["stop"],c-3*a)
                    if pos and pos["bars"]>=32:
                        _close_position(pos,c,ts+BAR_MS,"time_exit",cost_mult,trades); equity+=trades[-1]["net_pnl"]; pos=None
        # Signal close -> market entry at next bar open. Do not enter outside fold.
        if pos is None and start_idx < i < end_idx-1 and ts>=score_start:
            warm=max(segment_start+period,segment_start+14,199 if use_ema else 0)
            if i>=warm:
                prior_high=max(rows[j][2] for j in range(i-period,i))
                vol_base=sum(volumes[i-period:i])/period
                vr=v/vol_base if vol_base>0 else 0
                a=atr_at(rows,i)
                signal=(c>prior_high and vr>=VOL_THRESHOLD and a and a>0)
                if use_ema:
                    signal=signal and ema50[i] is not None and ema200[i] is not None and ema200[i-5] is not None and ema50[i]>ema200[i] and ema200[i]>ema200[i-5] and c>ema200[i]
                if signal:
                    en=rows[i+1][1]
                    stop=en-stop_atr*a
                    risk_per_unit=en-stop
                    qty=(equity*RISK_FRACTION)/risk_per_unit if risk_per_unit>0 else 0
                    if qty>0:
                        pos={"entry":en,"entry_ts":rows[i+1][0],"qty":qty,"remaining":qty,"initial_qty":qty,
                             "stop":stop,"initial_stop":stop,"risk":risk_per_unit*qty,
                             "tp1_price":en+2*risk_per_unit,"tp2_price":en+5*risk_per_unit,
                             "tp1":False,"bars":0,"gross":0.0,"fees":0.0,"next_trail":None,
                             "signal_ts":ts,"signal_close":c,"signal_atr":a,"signal_volume_ratio":vr,
                             "signal_breakout_atr":(c-prior_high)/a,
                             "signal_ema_spread_pct":((ema50[i]/ema200[i])-1)*100 if use_ema and ema50[i] and ema200[i] else None,
                             "signal_ema_slope_atr":(ema200[i]-ema200[i-5])/a if use_ema and ema200[i] is not None and ema200[i-5] is not None else None,
                             "signal_atr_pct":a/c*100,
                             "signal_candle_range_atr":(h-l)/a,
                             "signal_body_fraction":abs(c-o)/(h-l) if h>l else 0,
                             "signal_close_location":(c-l)/(h-l) if h>l else 0.5,
                             "signal_close_vs_ema200_pct":((c/ema200[i])-1)*100 if use_ema and ema200[i] else None}
        i+=1
    if pos:
        _close_position(pos,rows[end_idx-1][4],rows[end_idx-1][0]+BAR_MS,"fold_end",cost_mult,trades)
        equity+=trades[-1]["net_pnl"]; pos=None
    wins=sum(t["net_pnl"]>0 for t in trades)
    gross=sum(t["gross_pnl"] for t in trades); costs=sum(t["costs"] for t in trades)
    net=sum(t["net_pnl"] for t in trades)
    gp=sum(t["net_pnl"] for t in trades if t["net_pnl"]>0)
    gl=-sum(t["net_pnl"] for t in trades if t["net_pnl"]<0)
    pf=gp/gl if gl else (999.0 if gp else 0.0)
    # Equity curve DD is approximated at closed-trade granularity.
    eq=START_CAPITAL; peak=eq; maxdd=0
    for t in trades:
        eq+=t["net_pnl"]; peak=max(peak,eq); maxdd=max(maxdd,(peak-eq)/peak*100 if peak else 0)
    return {"fold":fold,"arm":arm_name,"donchian":period,"ema_gate":use_ema,"volume_lookback":period,
            "volume_threshold":VOL_THRESHOLD,"stop_atr":stop_atr,"cost_multiplier":cost_mult,"start_utc":utc(score_start),
            "end_utc":utc(score_end),"bars_in_fold":end_idx-start_idx,"trades":len(trades),
            "wins":wins,"win_rate_pct":round(wins/len(trades)*100,2) if trades else 0,
            "gross_pnl_usdt":round(gross,2),"costs_usdt":round(costs,2),"net_pnl_usdt":round(net,2),
            "return_pct":round(net/START_CAPITAL*100,2),"profit_factor":round(pf,3),
            "max_drawdown_closed_trade_pct":round(maxdd,2),
            "expectancy_r":round(sum(t["net_pnl"]/t["risk"] for t in trades)/len(trades),4) if trades else 0,
            "trades_detail":trades}

def _partial_exit(pos, raw_px, fraction, mult):
    q=pos["remaining"]*fraction
    pos["gross"]+=(raw_px-pos["entry"])*q
    pos["fees"]+=(pos["entry"]+raw_px)*q*(TAKER_FEE+SLIPPAGE)*mult
    pos["remaining"]-=q

def _close_position(pos, raw_px, ts, reason, mult, out):
    q=pos["remaining"]
    if q>0:
        pos["gross"]+=(raw_px-pos["entry"])*q
        pos["fees"]+=(pos["entry"]+raw_px)*q*(TAKER_FEE+SLIPPAGE)*mult
        pos["remaining"]=0
    net=pos["gross"]-pos["fees"]
    out.append({"entry_ts":pos["entry_ts"],"exit_ts":ts,"entry":pos["entry"],"exit":raw_px,
                "gross_pnl":pos["gross"],"costs":pos["fees"],"net_pnl":net,"risk":pos["risk"],
                "reason":reason,"bars":pos["bars"],
                "signal_ts":pos.get("signal_ts"),"signal_close":pos.get("signal_close"),
                "signal_atr":pos.get("signal_atr"),"signal_volume_ratio":pos.get("signal_volume_ratio"),
                "signal_breakout_atr":pos.get("signal_breakout_atr"),
                "signal_ema_spread_pct":pos.get("signal_ema_spread_pct"),
                "signal_ema_slope_atr":pos.get("signal_ema_slope_atr"),
                "signal_atr_pct":pos.get("signal_atr_pct"),
                "signal_candle_range_atr":pos.get("signal_candle_range_atr"),
                "signal_body_fraction":pos.get("signal_body_fraction"),
                "signal_close_location":pos.get("signal_close_location"),
                "signal_close_vs_ema200_pct":pos.get("signal_close_vs_ema200_pct")})

def main():
    rows=load()
    segments=1+sum(rows[i][0]-rows[i-1][0]!=BAR_MS for i in range(1,len(rows)))
    print(f"DATA source=Bybit official public archive; bars={len(rows)}; start={utc(rows[0][0])}; end={utc(rows[-1][0])}; gaps={segments-1}; segments={segments}")
    summary=[]; details=[]
    for fold in (1,2,3):
        for arm in DONCHIAN_ARMS:
            for cm in COSTS:
                r=backtest(rows,fold,arm,cm)
                details.extend([{"fold":fold,"arm":arm[2],"cost_multiplier":cm,**t} for t in r.pop("trades_detail")])
                summary.append(r)
                print("RESULT "+json.dumps(r,sort_keys=True))
    with (OUT/"summary.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    with (OUT/"trades.csv").open("w",newline="",encoding="utf-8") as f:
        fields=list(details[0]) if details else ["fold","arm","cost_multiplier","entry_ts","exit_ts","entry","exit","gross_pnl","costs","net_pnl","risk","reason","bars"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(details)
    (OUT/"methodology.json").write_text(json.dumps({
      "data":"Official Bybit public BTCUSDT H1 trade candles; no synthetic bars; gaps reset positions and indicators",
      "arms":[{"name":n,"donchian":p,"volume_lookback":p,"ema_gate":e} for p,e,n in DONCHIAN_ARMS],
      "folds":{"1":"50%-65%","2":"65%-80%","3":"80%-100%"},
      "entry":"signal at candle close, taker entry next candle open",
      "risk":"1% of 10,000 USDT starting capital per trade; one position at a time",
      "stop":"2.5 ATR(14); TP1 2R 50%; TP2 5R remaining; ATR(14)*3 trailing after TP1; time exit 32 bars",
      "costs":"Bybit base taker fee 5.5 bps + 2.25 bps slippage per side, stressed 1x/1.5x/2x",
      "intrabar":"stop-first conservative OHLC assumption; trailing updated from close and active next bar",
      "excluded":["funding","mark-price liquidation","dated instrument specs/risk tiers","maker queue/spread/partial fill","portfolio concurrent positions"],
      "status":"PRELIMINARY_DIAGNOSTIC_NOT_EDGE_PROOF"
    },indent=2))
    print(f"OUTPUT {OUT}/summary.csv and {OUT}/trades.csv; rows={len(summary)} trades={len(details)}")

if __name__=="__main__": main()
