#!/usr/bin/env python3
"""Trade/signal diagnostics for the selected H1 universe. Research branch only.

Exports long Donchian breakout candidates (including rejected/unfilled signals),
market features at signal close, forward OHLC outcomes, and actual engine trades.
IMPORTANT: BotConfig.max_max_signal_body_pct actually caps the absolute signal-candle body
percentage, not distance from the breakout level or entry. CSV labels use that meaning.
Binance OHLCV proxy; research only; no production strategy changes.
"""
from __future__ import annotations
import csv, os, sys
import statistics
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Bybit_Trading_Engine_v14_research as em
from run_uploaded_dataset_backtests import read_zip_datasets

SYMBOLS = ["RAYUSDT", "PUMPUSDT", "TAOUSDT", "AAVEUSDT", "CAKEUSDT"]
CONTEXT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
FOLDS = [(1, "2026-04-27T12:00:00Z", "2026-06-21T05:00:00Z"), (2, "2026-06-21T06:00:00Z", "2026-08-14T23:00:00Z"), (3, "2026-08-15T00:00:00Z", "2026-10-27T00:00:00Z")]
VOL_MIN = 1.6
BREAKOUT_ATR_MIN = .25
ENTRY_OFFSET_BPS = 20.0
ENTRY_PENETRATION_BPS = 5.0
WAIT_BARS = 3
COST_MULTIPLIER = 2.0
CHASE_LIMITS = [1.5, 2.0, 2.5, 3.0, 100.0]

def iso(ts):
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def features(candles, i):
    if i < 22:
        return None
    core = em.QuantStrategyCore
    hist, c = candles[:i], candles[i]
    hi, lo, avg_vol = core.compute_donchian_and_volume(hist, 20)
    atr = core.compute_atr(hist, 14)
    if atr <= 0 or avg_vol <= 0:
        return None
    vr = c.volume / avg_vol
    # Market context from completed candles only.
    close = c.close
    def ret(n):
        return (close / candles[i-n].close - 1) * 100 if i >= n else ""
    def efficiency(n):
        if i < n: return ""
        net = abs(close - candles[i-n].close)
        path = sum(abs(candles[k].close - candles[k-1].close) for k in range(i-n+1, i+1))
        return net / path if path else 0.0
    prev_peak = max(x.high for x in candles[i-20:i])
    prev_trough = min(x.low for x in candles[i-20:i])
    return {
        "close": close, "donchian_high": hi, "donchian_low": lo,
        "atr": atr, "atr_pct": atr / close * 100, "volume_ratio": vr,
        "breakout_atr": (close-hi)/atr, "candle_body_pct": (c.close-c.open)/c.open*100 if c.open else 0,
        "range_atr": (c.high-c.low)/atr,
        "ret_6h_pct": ret(6), "ret_24h_pct": ret(24), "ret_72h_pct": ret(72),
        "efficiency_24h": efficiency(24), "efficiency_72h": efficiency(72),
        "dist_20h_high_pct": (close/prev_peak-1)*100 if prev_peak else 0,
        "dist_20h_low_pct": (close/prev_trough-1)*100 if prev_trough else 0,
    }

def synchronized_data():
    all_data = read_zip_datasets()
    targets = set(SYMBOLS + CONTEXT_SYMBOLS)
    raw = {sym: item for (sym, tf), item in all_data.items()
           if tf == "1h" and sym in targets and len(item[2]) >= 500}
    missing = sorted(set(SYMBOLS)-set(raw))
    if missing:
        raise SystemExit(f"Missing selected H1 datasets: {missing}")
    missing_context = sorted(set(CONTEXT_SYMBOLS)-set(raw))
    if missing_context:
        print(f"WARNING: market context unavailable for: {missing_context}")
    # Fold boundaries are based ONLY on the five trading symbols. Context data
    # must not shorten the experiment window if BTC/ETH history starts later.
    common = None
    for sym in SYMBOLS:
        stamps_set = {c.ts for c in raw[sym][2]}
        common = stamps_set if common is None else common.intersection(stamps_set)
    stamps = sorted(common or [])
    if len(stamps) < 3000:
        raise SystemExit(f"Insufficient synchronized selected-symbol history: {len(stamps)} bars")
    data = {s: [dict_by_ts[t] for t in stamps]
            for s in SYMBOLS
            for dict_by_ts in [{c.ts:c for c in raw[s][2]}]}
    context_data = {s: raw[s][2] for s in CONTEXT_SYMBOLS if s in raw}
    context_index = {s: {c.ts:i for i,c in enumerate(candles)}
                     for s,candles in context_data.items()}
    # Broad market breadth uses every valid H1 symbol available in the uploaded
    # archives, not just the five symbols selected for trading.
    market_universe_data = {sym: item[2] for (sym, tf), item in all_data.items()
                            if tf == "1h" and len(item[2]) >= 500}
    market_universe_index = {sym: {c.ts:i for i,c in enumerate(candles)}
                             for sym,candles in market_universe_data.items()}
    em.check_alignment(data)
    print(f"Selected symbols={len(data)}; broad H1 context symbols={len(market_universe_data)}; selected bars={len(stamps)}")
    return data, stamps, context_data, context_index, market_universe_data, market_universe_index

def market_context(data, context_data, context_index, market_universe_data, market_universe_index, i):
    """Completed-bar BTC/ETH and broad cross-sectional context; no lookahead."""
    out = {}
    ts = data[SYMBOLS[0]][i].ts
    for sym, prefix in (("BTCUSDT", "btc"), ("ETHUSDT", "eth")):
        ctx_i = context_index.get(sym, {}).get(ts)
        f = features(context_data[sym], ctx_i) if ctx_i is not None else None
        for src, dst in (
            ("ret_24h_pct", "ret_24h_pct"), ("ret_72h_pct", "ret_72h_pct"),
            ("atr_pct", "atr_pct"), ("efficiency_24h", "efficiency_24h"),
            ("efficiency_72h", "efficiency_72h"),
        ):
            out[f"{prefix}_{dst}"] = f[src] if f else ""
    cross = [features(data[sym], i) for sym in SYMBOLS]
    r24 = [f["ret_24h_pct"] for f in cross if f and f["ret_24h_pct"] != ""]
    r72 = [f["ret_72h_pct"] for f in cross if f and f["ret_72h_pct"] != ""]
    e24 = [f["efficiency_24h"] for f in cross if f and f["efficiency_24h"] != ""]
    out["universe_positive_24h_share"] = sum(x > 0 for x in r24) / len(r24) if r24 else ""
    out["universe_median_ret_24h_pct"] = float(__import__("statistics").median(r24)) if r24 else ""
    out["universe_median_ret_72h_pct"] = float(__import__("statistics").median(r72)) if r72 else ""
    out["universe_median_efficiency_24h"] = float(__import__("statistics").median(e24)) if e24 else ""

    broad_r24, broad_r72, broad_e24 = [], [], []
    for sym, candles in market_universe_data.items():
        j = market_universe_index[sym].get(ts)
        if j is None or j < 72:
            continue
        close = candles[j].close
        r24_value = (close / candles[j-24].close - 1.0) * 100.0
        r72_value = (close / candles[j-72].close - 1.0) * 100.0
        path24 = sum(abs(candles[k].close-candles[k-1].close) for k in range(j-23, j+1))
        eff24_value = abs(close-candles[j-24].close) / path24 if path24 else 0.0
        broad_r24.append(r24_value); broad_r72.append(r72_value); broad_e24.append(eff24_value)
    out["broad_universe_coverage_count"] = len(broad_r24)
    out["broad_positive_24h_share"] = sum(x > 0 for x in broad_r24) / len(broad_r24) if broad_r24 else ""
    out["broad_positive_72h_share"] = sum(x > 0 for x in broad_r72) / len(broad_r72) if broad_r72 else ""
    out["broad_median_ret_24h_pct"] = float(__import__("statistics").median(broad_r24)) if broad_r24 else ""
    out["broad_median_ret_72h_pct"] = float(__import__("statistics").median(broad_r72)) if broad_r72 else ""
    out["broad_median_efficiency_24h"] = float(__import__("statistics").median(broad_e24)) if broad_e24 else ""
    return out

def run_fold(data, stamps, context_data, context_index, market_universe_data, market_universe_index, fold, start_time, end_time, chase_limit):
    requested_start = int(datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()*1000)
    requested_end = int(datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()*1000)
    start_idx = next((i for i, ts in enumerate(stamps) if ts >= requested_start), None)
    end_idx = next((i for i, ts in enumerate(stamps) if ts > requested_end), len(stamps))
    if start_idx is None or end_idx <= start_idx:
        raise SystemExit(f"Fold {fold} has no data in requested range {start_time}..{end_time}")
    start_ts, end_ts = stamps[start_idx], stamps[end_idx-1]
    print(f"fold={fold} actual_window={iso(start_ts)}..{iso(end_ts)} bars={end_idx-start_idx}")
    # Candidate table includes every long Donchian breakout, even if it fails the
    # selected volume/strength filter or is never filled.
    signal_rows = []
    signal_lookup = {}
    context_cache = {}
    def cached_context(i):
        if i not in context_cache:
            context_cache[i] = market_context(data, context_data, context_index, market_universe_data, market_universe_index, i)
        return context_cache[i]
    for sym, candles in data.items():
        for i, c in enumerate(candles):
            if not (start_ts <= c.ts <= end_ts):
                continue
            f = features(candles, i)
            if not f or c.close <= f["donchian_high"]:
                continue
            accepted = f["volume_ratio"] >= VOL_MIN and f["breakout_atr"] >= BREAKOUT_ATR_MIN
            row = {"fold":fold, "chase_limit_pct":chase_limit, "symbol":sym, "signal_ts":c.ts, "signal_time_utc":iso(c.ts),
                   "candidate_type":"long_donchian_breakout", "passes_selected_filter":int(accepted),
                   **{k:round(v,6) if isinstance(v,(int,float)) else v for k,v in f.items()},
                   **{k:round(v,6) if isinstance(v,(int,float)) else v for k,v in cached_context(i).items()}}
            for h in (6,12,24,48):
                j=i+h
                if j < len(candles):
                    row[f"fwd_{h}h_return_pct"]=round((candles[j].close/c.close-1)*100,6)
                    row[f"fwd_{h}h_max_up_pct"]=round((max(x.high for x in candles[i+1:j+1])/c.close-1)*100,6)
                    row[f"fwd_{h}h_max_down_pct"]=round((min(x.low for x in candles[i+1:j+1])/c.close-1)*100,6)
                else:
                    row[f"fwd_{h}h_return_pct"]=""
                    row[f"fwd_{h}h_max_up_pct"]=""
                    row[f"fwd_{h}h_max_down_pct"]=""
            signal_rows.append(row)
            signal_lookup[(sym,c.ts)] = row

    # Exact selected portfolio setup, instrumented to mark signal/fill/cancel outcomes.
    base_taker, base_maker, base_slip = em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP
    em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP = base_taker*COST_MULTIPLIER, base_maker*COST_MULTIPLIER, base_slip*COST_MULTIPLIER
    fold_data = {s: cs[:end_idx] for s,cs in data.items()}
    engine = em.UnifiedQuantEngine(journal_output_path="/tmp/ignored_signal_diagnostic.json")
    cfg=engine.cfg
    cfg.bot_version=f"diagnostic-v{VOL_MIN:g}-b{BREAKOUT_ATR_MIN:g}-cost{COST_MULTIPLIER:g}"
    cfg.timeframe="1h"; cfg.active_trading_pool=sorted(data); cfg.capital_usdt=10000.0
    cfg.max_risk_trade_pct=1.0; cfg.max_portfolio_risk_pct=2.0; cfg.max_concurrent_positions=5
    cfg.daily_stop_loss_pct=5.0; cfg.emergency_kill_switch_pct=30.0; cfg.max_chase_limit_pct=chase_limit; cfg.max_chase_limit_pct=chase_limit
    cfg.donchian_period=20; cfg.atr_period=14; cfg.min_volume_ratio=VOL_MIN
    cfg.stop_atr_mult=2.5; cfg.tp1_r_multiple=2.0; cfg.tp2_r_multiple=5.0
    cfg.atr_trail_mult=3.0; cfg.max_hold_bars=32
    cfg.maker_entry_and_tp1=True; cfg.maker_tp1_and_target=False; cfg.enable_h2_range_fade=False
    cfg.validate(); engine.risk_mgr.cfg=cfg; engine.tg.send_message=lambda *_a,**_k:None
    core=em.QuantStrategyCore; original_eval=core.evaluate_signal
    emitted={}
    def wrapped_eval(sym,bars,conf):
        if not bars or not (start_ts <= bars[-1].ts <= end_ts): return None
        sig=original_eval(sym,bars,conf)
        if sig is None or str(sig.get("direction","")).lower()!="long": return None
        if float(sig.get("vol_ratio", 0.0)) < VOL_MIN: return None
        prev=bars[:-1]
        hi,_,_=core.compute_donchian_and_volume(prev,conf.donchian_period)
        atr=float(sig.get("atr",0))
        if atr<=0 or (float(bars[-1].close)-hi)/atr < BREAKOUT_ATR_MIN: return None
        emitted[(sym,int(sig["signal_ts"]))]=sig
        row=signal_lookup.get((sym,int(sig["signal_ts"])))
        if row:
            row["engine_emitted_signal"]=1
            row["signal_status"]="pending"
        return sig
    core.evaluate_signal=staticmethod(wrapped_eval)
    # Record why each candidate is not evaluated by the engine. This separates
    # candle-body chase rejection from same-symbol position/pending state and
    # portfolio-level risk/capacity gates without changing engine decisions.
    original_step=engine.step_candle
    def wrapped_step(sym,bars):
        row = signal_lookup.get((sym, int(bars[-1].ts))) if bars else None
        reason = ""
        if row and row["passes_selected_filter"]:
            if sym in engine.open_positions:
                reason = "same_symbol_position_open"
            elif sym in engine.pending:
                reason = "same_symbol_pending_order"
            else:
                can_open, gate = engine.risk_mgr.can_open_new_trade(len(engine.open_positions) + len(engine.pending))
                reason = "evaluate_signal" if can_open else f"risk_gate:{gate}"
        original_step(sym,bars)
        if row and row["passes_selected_filter"]:
            if row.get("engine_emitted_signal",0):
                row["engine_skip_reason"] = "signal_emitted"
            elif reason == "evaluate_signal":
                c = bars[-1]
                body_pct = abs(c.close-c.open)/c.open*100 if c.open else 0
                row["engine_skip_reason"] = "max_chase_candle_body" if body_pct > chase_limit else "other_signal_rejection"
            else:
                row["engine_skip_reason"] = reason
    engine.step_candle=wrapped_step
    original_fill=engine._try_fill_pending
    order_age={}
    def wrapped_fill(sym,candle):
        if sym not in engine.pending: return original_fill(sym,candle)
        sig=engine.pending[sym]
        signal_ts=int(sig.get("signal_ts",0)); row=signal_lookup.get((sym,signal_ts))
        meta=order_age.get(sym)
        if meta is None:
            sig["entry_price"]=float(sig["entry_price"])*(1-ENTRY_OFFSET_BPS/10000)
            sig["order_type"]="limit"; meta={"age":0}; order_age[sym]=meta
            if row: row["limit_order_price"]=sig["entry_price"]
        meta["age"]+=1
        ref=float(sig["entry_price"]); required=ref*(1-ENTRY_PENETRATION_BPS/10000)
        if float(candle.low)<=required:
            before=len(engine.closed_trades)
            filled=original_fill(sym,candle)
            order_age.pop(sym,None)
            if filled:
                if row:
                    row["fill_status"]="filled"; row["fill_ts"]=candle.ts; row["fill_time_utc"]=iso(candle.ts)
                    row["fill_price"]=engine.open_positions[sym].entry_price if sym in engine.open_positions else ""
                    row["signal_status"]="filled"
            elif row:
                row["fill_status"]="penetrated_but_rejected_risk_or_capacity"
                row["signal_status"]="not_filled"
            return filled
        engine.pending.pop(sym,None)
        if meta["age"] < WAIT_BARS:
            engine.pending[sym]=sig
            if row: row["fill_status"]="waiting"
            return False
        order_age.pop(sym,None)
        if row:
            row["fill_status"]="expired_unfilled"; row["signal_status"]="expired_unfilled"
            row["cancel_ts"]=candle.ts
        return False
    engine._try_fill_pending=wrapped_fill
    try:
        em.check_alignment(fold_data)
        em.run_simulation_pass(engine,fold_data,sorted(data),
            data_label=f"BINANCE_PROXY H1 selected universe diagnostic fold={fold}")
    finally:
        core.evaluate_signal=staticmethod(original_eval)
        engine.step_candle=original_step
        em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP = base_taker, base_maker, base_slip

    # Finalize candidate status and map trades to originating signal by fill timestamp.
    trade_by_entry={(t.token,t.entry_date):t for t in engine.closed_trades}
    trades_out=[]
    for t in engine.closed_trades:
        entry_dt=datetime.strptime(t.entry_date,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        entry_ts=int(entry_dt.timestamp()*1000)
        matched=None
        for (sym,sts),sig in emitted.items():
            if sym==t.token and sts < entry_ts <= sts+WAIT_BARS*3600000:
                if matched is None or sts>matched[0]: matched=(sts,sig)
        feat=features(data[t.token], next((i for i,c in enumerate(data[t.token]) if c.ts==matched[0]),0)) if matched else None
        trades_out.append({
            "fold":fold,"chase_limit_pct":chase_limit,"symbol":t.token,"trade_id":t.id,"direction":t.direction,
            "signal_ts":matched[0] if matched else "", "signal_time_utc":iso(matched[0]) if matched else "",
            "entry_time_utc":t.entry_date,"exit_time_utc":t.exit_date,
            "entry_price":t.entry_price,"exit_price":t.exit_price,"order_type":t.order_type,
            "exit_reason":t.exit_reason,"pnl_net_usdt":t.pnl_usdt,"pnl_gross_usdt":t.gross_pnl,
            "net_R":t.r_multiple,"gross_R":t.gross_r_multiple,"risk_usdt":t.risk_usdt,
            "risk_pct":t.risk_pct,"fees_usdt":t.exchange_fees_usdt,"slippage_usdt":t.slippage_cost_usdt,
            "MAE_R":t.mae,"MFE_R":t.mfe,"duration_hours":round((datetime.strptime(t.exit_date,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)-entry_dt).total_seconds()/3600,2),
            "signal_candle_body_pct":feat["candle_body_pct"] if feat else "",
            "signal_volume_ratio":feat["volume_ratio"] if feat else "",
            "signal_breakout_atr":feat["breakout_atr"] if feat else "",
            "signal_candle_body_pct":feat["candle_body_pct"] if feat else "",
            "signal_abs_candle_body_pct":abs(feat["candle_body_pct"]) if feat else "",
            "signal_atr_pct":feat["atr_pct"] if feat else "",
            "signal_ret_24h_pct":feat["ret_24h_pct"] if feat else "",
            "signal_efficiency_24h":feat["efficiency_24h"] if feat else "",
            **{k:v for k,v in (signal_lookup.get((t.token,matched[0]),{}).items() if matched else [])
               if k.startswith(("btc_","eth_","universe_","broad_"))},
        })
    for row in signal_rows:
        row.setdefault("engine_emitted_signal",0)
        row.setdefault("fill_status","not_emitted_or_not_attempted")
        row.setdefault("signal_status","rejected_by_selected_filter" if not row["passes_selected_filter"] else "selected_but_not_emitted")
        row.setdefault("limit_order_price",""); row.setdefault("fill_ts",""); row.setdefault("fill_time_utc","")
        row.setdefault("fill_price",""); row.setdefault("cancel_ts",""); row.setdefault("engine_skip_reason","")
    return signal_rows,trades_out

def main():
    data,stamps,context_data,context_index,market_universe_data,market_universe_index=synchronized_data()
    signals=[]; trades=[]; summaries=[]
    for chase in CHASE_LIMITS:
        for fold,a,b in FOLDS:
            sr,tr=run_fold(data,stamps,context_data,context_index,market_universe_data,market_universe_index,fold,a,b,chase_limit=chase)
            signals.extend(sr); trades.extend(tr)
            pnl=sum(float(t["pnl_net_usdt"]) for t in tr)
            wins=sum(float(t["pnl_net_usdt"])>0 for t in tr)
            gross=sum(float(t["pnl_gross_usdt"]) for t in tr)
            fees=sum(float(t["fees_usdt"]) for t in tr)
            slip=sum(float(t["slippage_usdt"]) for t in tr)
            pos=sum(max(0.0,float(t["pnl_net_usdt"])) for t in tr)
            neg=-sum(min(0.0,float(t["pnl_net_usdt"])) for t in tr)
            summaries.append({
                "max_chase_pct":chase,"fold":fold,"trades":len(tr),"net_pnl_usdt":round(pnl,2),
                "gross_pnl_usdt":round(gross,2),"fees_usdt":round(fees,2),"slippage_usdt":round(slip,2),
                "win_rate_pct":round(100*wins/len(tr),2) if tr else 0,
                "profit_factor":round(pos/neg,3) if neg else "",
                "mean_net_R":round(statistics.mean([float(t["net_R"]) for t in tr]),4) if tr else "",
                "median_MFE_R":round(float(statistics.median([float(t["MFE_R"]) for t in tr])),3) if tr else "",
                "median_MAE_R":round(float(statistics.median([float(t["MAE_R"]) for t in tr])),3) if tr else "",
                "max_abs_body_filled_pct":round(max([abs(float(t.get("signal_candle_body_pct",0) or 0)) for t in tr],default=0),3)
            })
            print(f"chase={chase:.1f}% fold={fold}: trades={len(tr)}, net={pnl:+.2f}, PF={pos/neg if neg else 0:.2f}")
    for path,rows in [
        ("h1_chase_limit_ablation.csv",summaries),
        ("h1_chase_limit_trades.csv",trades),
        ("h1_chase_limit_signals.csv",signals)
    ]:
        if rows:
            fields=[]
            for row in rows:
                for k in row:
                    if k not in fields: fields.append(k)
            with open(path,"w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
            print(f"Wrote {path}: {len(rows)} rows")
    print("CAVEATS: Binance OHLCV proxy, modelled fees/slippage, OHLC limit penetration is not queue/fill simulation. Research ablation only; no production changes.")

if __name__ == "__main__":
    main()
