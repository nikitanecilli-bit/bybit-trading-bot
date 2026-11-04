#!/usr/bin/env python3
"""Cross-sectional replication of the E09 candle-body gate on all valid H1 symbols. Research branch only.

Exports long Donchian breakout candidates (including rejected/unfilled signals),
market features at signal close, forward OHLC outcomes, and actual engine trades.
IMPORTANT: max_chase_limit_pct acts as the absolute signal-candle body cap in this engine.
The experiment holds market execution fixed and disables the next-open gap gate.
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
from multibar_limit_wait import prepare_signal_for_next_bar_fill

SYMBOLS = []  # populated from every valid H1 dataset in the uploaded archive universe
CONTEXT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
CONTEXT_BY_TS = {}
FOLDS = [(1, "2026-04-27T12:00:00Z", "2026-06-21T05:00:00Z"), (2, "2026-06-21T06:00:00Z", "2026-08-14T23:00:00Z"), (3, "2026-08-15T00:00:00Z", "2026-10-27T00:00:00Z")]
VOL_MIN = 1.6
BREAKOUT_ATR_MIN = .25
ENTRY_OFFSET_BPS = 20.0
ENTRY_PENETRATION_BPS = 5.0
WAIT_BARS = 3
COST_MULTIPLIER = 2.0
GAP_THRESHOLD_PCT = 2.0

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
    global SYMBOLS
    all_data = read_zip_datasets()
    selected = {
        sym: item for (sym, tf), item in all_data.items()
        if tf == "1h" and len(item[2]) >= 500
    }
    SYMBOLS = sorted(selected)
    if len(SYMBOLS) < 10:
        raise SystemExit(f"Refusing portfolio test: only {len(SYMBOLS)} valid H1 symbols found")
    manifest = []
    eligible = {}
    fold_bounds = [
        (int(datetime.strptime(a, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()*1000),
         int(datetime.strptime(b, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()*1000))
        for _, a, b in FOLDS
    ]
    for sym in SYMBOLS:
        count, archive, candles = selected[sym]
        stamps_sym = [c.ts for c in candles]
        fold_counts = [sum(lo <= ts <= hi for ts in stamps_sym) for lo, hi in fold_bounds]
        covers = all(n >= 100 for n in fold_counts)
        manifest.append({
            "symbol": sym, "bars": count, "start_utc": iso(stamps_sym[0]),
            "end_utc": iso(stamps_sym[-1]), "source_archive": os.path.basename(archive),
            "fold1_bars": fold_counts[0], "fold2_bars": fold_counts[1],
            "fold3_bars": fold_counts[2], "included": int(covers),
            "exclusion_reason": "" if covers else "less_than_100_bars_in_one_or_more_folds",
        })
        if covers:
            eligible[sym] = (count, archive, candles)
    SYMBOLS = sorted(eligible)
    if len(SYMBOLS) < 10:
        raise SystemExit(f"Refusing portfolio test: only {len(SYMBOLS)} symbols cover all folds")
    common = None
    for sym in SYMBOLS:
        stamps_set = {c.ts for c in eligible[sym][2]}
        common = stamps_set if common is None else common.intersection(stamps_set)
    stamps = sorted(common or [])
    print(f"Valid H1 symbols={len(selected)}; fold-eligible symbols={len(SYMBOLS)}; common aligned bars={len(stamps)}")
    if len(stamps) < 3000:
        raise SystemExit(f"Insufficient common aligned history for shared-capital portfolio: {len(stamps)} bars")
    timestamp_index = {
        sym: {c.ts: c for c in eligible[sym][2]}
        for sym in SYMBOLS
    }
    data = {
        sym: [timestamp_index[sym][ts] for ts in stamps]
        for sym in SYMBOLS
    }
    em.check_alignment(data)
    build_causal_context(data, stamps)
    with open("e13_h1_compression_gate_universe_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader(); w.writerows(manifest)
    for row in manifest:
        if row["included"]:
            print(f"UNIVERSE {row['symbol']} bars={row['bars']} folds={row['fold1_bars']}/{row['fold2_bars']}/{row['fold3_bars']}")
    print(f"SHARED PORTFOLIO: symbols={len(data)} common_bars={len(stamps)}")
    return data, stamps


def percentile(values, q):
    vals = sorted(values)
    if not vals:
        return None
    pos = (len(vals)-1)*q
    lo = int(pos); hi = min(lo+1, len(vals))
    frac = pos-lo
    return vals[lo] + (vals[hi]-vals[lo])*frac


def build_causal_context(data, stamps):
    global CONTEXT_BY_TS
    CONTEXT_BY_TS = {}
    prior_atr = []
    prior_iqr = []
    for i, ts in enumerate(stamps):
        if i < 72:
            continue
        r24, r72, eff24, atrp = [], [], [], []
        for sym in SYMBOLS:
            f = features(data[sym], i)
            if not f:
                continue
            r24.append(float(f["ret_24h_pct"]))
            r72.append(float(f["ret_72h_pct"]))
            eff24.append(float(f["efficiency_24h"]))
            atrp.append(float(f["atr_pct"]))
        if len(r72) < 10:
            continue
        sr24, sr72 = sorted(r24), sorted(r72)
        iqr24 = sr24[int(.75*(len(sr24)-1))] - sr24[int(.25*(len(sr24)-1))]
        iqr72 = sr72[int(.75*(len(sr72)-1))] - sr72[int(.25*(len(sr72)-1))]
        atr_med = statistics.median(atrp)
        atr_q25 = percentile(prior_atr, .25) if len(prior_atr) >= 336 else None
        iqr_q25 = percentile(prior_iqr, .25) if len(prior_iqr) >= 336 else None
        compression = bool(atr_q25 is not None and iqr_q25 is not None
                           and atr_med < atr_q25 and iqr72 < iqr_q25)
        out = {
            "broad_positive_24h_share": sum(x > 0 for x in r24)/len(r24),
            "broad_positive_72h_share": sum(x > 0 for x in r72)/len(r72),
            "broad_median_ret_24h_pct": statistics.median(r24),
            "broad_median_ret_72h_pct": statistics.median(r72),
            "broad_median_efficiency_24h": statistics.median(eff24),
            "broad_median_atr_pct": atr_med,
            "broad_iqr_ret_24h_pct": iqr24,
            "broad_iqr_ret_72h_pct": iqr72,
            "broad_std_ret_72h_pct": statistics.pstdev(r72),
            "compression_atr_q25_prev": atr_q25 if atr_q25 is not None else "",
            "compression_iqr72_q25_prev": iqr_q25 if iqr_q25 is not None else "",
            "compression_regime": int(compression),
        }
        CONTEXT_BY_TS[ts] = out
        prior_atr.append(atr_med)
        prior_iqr.append(iqr72)
    print(f"Causal context timestamps={len(CONTEXT_BY_TS)}; compression hours={sum(x['compression_regime'] for x in CONTEXT_BY_TS.values())}")


def market_context(data, context_data, context_index, market_universe_data, market_universe_index, i):
    ts = data[SYMBOLS[0]][i].ts
    return CONTEXT_BY_TS.get(ts, {})


def run_fold(data, stamps, context_data, context_index, market_universe_data, market_universe_index, fold, start_time, end_time, gap_threshold, execution_mode, body_gate, gap_gate, compression_gate):
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
            row = {"fold":fold, "gap_threshold_pct":gap_threshold,"body_gate":int(body_gate),"gap_gate":int(gap_gate),"compression_gate":int(compression_gate), "symbol":sym, "signal_ts":c.ts, "signal_time_utc":iso(c.ts),
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
    cfg.bot_version=f"gate-decoupling-{execution_mode}-v{VOL_MIN:g}-b{BREAKOUT_ATR_MIN:g}-cost{COST_MULTIPLIER:g}"
    cfg.timeframe="1h"; cfg.active_trading_pool=sorted(data); cfg.capital_usdt=10000.0
    cfg.max_risk_trade_pct=1.0; cfg.max_portfolio_risk_pct=2.0; cfg.max_concurrent_positions=5
    cfg.daily_stop_loss_pct=5.0; cfg.emergency_kill_switch_pct=30.0; cfg.max_chase_limit_pct=gap_threshold if body_gate else 100.0
    cfg.donchian_period=20; cfg.atr_period=14; cfg.min_volume_ratio=VOL_MIN
    cfg.stop_atr_mult=2.5; cfg.tp1_r_multiple=2.0; cfg.tp2_r_multiple=5.0
    cfg.atr_trail_mult=3.0; cfg.max_hold_bars=32
    cfg.maker_entry_and_tp1=(execution_mode == "limit"); cfg.maker_tp1_and_target=False; cfg.enable_h2_range_fade=False
    cfg.validate(); engine.risk_mgr.cfg=cfg; engine.tg.send_message=lambda *_a,**_k:None
    core=em.QuantStrategyCore; original_eval=core.evaluate_signal
    emitted={}
    def wrapped_eval(sym,bars,conf):
        if not bars or not (start_ts <= bars[-1].ts <= end_ts): return None
        sig = original_eval(sym,bars,conf)
        if sig is None or str(sig.get("direction","")).lower()!="long": return None
        if float(sig.get("vol_ratio", 0.0)) < VOL_MIN: return None
        prev=bars[:-1]
        hi,_,_=core.compute_donchian_and_volume(prev,conf.donchian_period)
        atr=float(sig.get("atr",0))
        if atr<=0 or (float(bars[-1].close)-hi)/atr < BREAKOUT_ATR_MIN: return None
        row=signal_lookup.get((sym,int(sig["signal_ts"])))
        if compression_gate and CONTEXT_BY_TS.get(int(sig["signal_ts"]),{}).get("compression_regime",0):
            if row:
                row["engine_skip_reason"]="compression_regime"
                row["signal_status"]="rejected_compression_regime"
            return None
        emitted[(sym,int(sig["signal_ts"]))]=sig
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
            if row.get("engine_skip_reason") == "compression_regime":
                pass
            elif row.get("engine_emitted_signal",0):
                row["engine_skip_reason"] = "signal_emitted"
            elif reason == "evaluate_signal":
                c = bars[-1]
                body_pct = abs(c.close-c.open)/c.open*100 if c.open else 0
                row["engine_skip_reason"] = "max_chase_candle_body" if body_gate and body_pct > gap_threshold else "other_signal_rejection"
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
        original_ref=float(sig.get("entry_price",0.0))
        gap_pct=abs(float(candle.open)-original_ref)/original_ref*100.0 if original_ref>0 else 0.0
        # The gap gate is explicitly NEXT-open only. Limit orders may remain pending
        # for later bars; later opens must not be re-tested against the original signal.
        first_attempt = execution_mode == "market" or meta is None
        if row and first_attempt:
            row["next_open_gap_pct"]=round(gap_pct,6)
            row["body_gate"]=int(body_gate); row["gap_gate"]=int(gap_gate)
        if gap_gate and first_attempt and gap_pct > gap_threshold:
            engine.pending.pop(sym,None); order_age.pop(sym,None)
            if row:
                row["fill_status"]="gap_rejected"; row["signal_status"]="gap_rejected"; row["cancel_ts"]=candle.ts
            return False
        if execution_mode == "market":
            # Engine's own market fill gate shares the candle-body config field.
            # Disable that internal check here; the independently toggled gap gate
            # above is the sole authority for next-open rejection.
            saved_cap=engine.cfg.max_chase_limit_pct
            engine.cfg.max_chase_limit_pct=100.0
            try:
                filled=original_fill(sym,candle)
            finally:
                engine.cfg.max_chase_limit_pct=saved_cap
            if row:
                row["fill_status"]="market_filled" if filled else "market_not_filled_risk_or_capacity"
                row["signal_status"]="filled" if filled else "not_filled"
                if filled:
                    row["fill_ts"]=candle.ts; row["fill_time_utc"]=iso(candle.ts)
            return filled
        if meta is None:
            sig["entry_price"]=original_ref*(1-ENTRY_OFFSET_BPS/10000)
            sig["order_type"]="limit"; meta={"age":0}; order_age[sym]=meta
            if row: row["limit_order_price"]=sig["entry_price"]
        meta["age"]+=1
        ref=float(sig["entry_price"]); required=ref*(1-ENTRY_PENETRATION_BPS/10000)
        if float(candle.low)<=required:
            prepare_signal_for_next_bar_fill(sig,int(candle.ts),3_600_000)
            filled=original_fill(sym,candle); order_age.pop(sym,None)
            if filled and row:
                row["fill_status"]="filled"; row["fill_ts"]=candle.ts; row["fill_time_utc"]=iso(candle.ts)
                row["fill_price"]=engine.open_positions[sym].entry_price if sym in engine.open_positions else ""
                row["signal_status"]="filled"
            elif row:
                row["fill_status"]="penetrated_but_rejected_risk_or_capacity"; row["signal_status"]="not_filled"
            return filled
        engine.pending.pop(sym,None)
        if meta["age"] < WAIT_BARS:
            engine.pending[sym]=sig
            if row: row["fill_status"]="waiting"
            return False
        order_age.pop(sym,None)
        if row:
            row["fill_status"]="expired_unfilled"; row["signal_status"]="expired_unfilled"; row["cancel_ts"]=candle.ts
        return False
    engine._try_fill_pending=wrapped_fill
    try:
        em.check_alignment(fold_data)
        em.run_simulation_pass(engine,fold_data,sorted(data),
            data_label=f"BINANCE_PROXY H1 {sorted(data)[0]} independent diagnostic fold={fold}")
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
            "fold":fold,"execution_mode":execution_mode,"gap_threshold_pct":gap_threshold,"body_gate":int(body_gate),"gap_gate":int(gap_gate),"compression_gate":int(compression_gate),"symbol":t.token,"trade_id":t.id,"direction":t.direction,
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
               if k.startswith(("btc_","eth_","universe_","broad_","compression_"))},
        })
    for row in signal_rows:
        row.setdefault("execution_mode",execution_mode)
        row.setdefault("body_gate",int(body_gate)); row.setdefault("gap_gate",int(gap_gate))
        row.setdefault("next_open_gap_pct","")
        row.setdefault("engine_emitted_signal",0)
        row.setdefault("fill_status","not_emitted_or_not_attempted")
        row.setdefault("signal_status","rejected_by_selected_filter" if not row["passes_selected_filter"] else "selected_but_not_emitted")
        row.setdefault("limit_order_price",""); row.setdefault("fill_ts",""); row.setdefault("fill_time_utc","")
        row.setdefault("fill_price",""); row.setdefault("cancel_ts",""); row.setdefault("engine_skip_reason","")
    return signal_rows,trades_out

def main():
    data, stamps = synchronized_data()
    signals = []
    trades = []
    summaries = []
    per_symbol = []
    for compression_gate in (False, True):
        for fold, a, b in FOLDS:
            sr, tr = run_fold(
                data, stamps, {}, {}, {}, {}, fold, a, b,
                gap_threshold=GAP_THRESHOLD_PCT,
                execution_mode="market", body_gate=False, gap_gate=False,
                compression_gate=compression_gate,
            )
            signals.extend(sr)
            trades.extend(tr)
            pnl = sum(float(t["pnl_net_usdt"]) for t in tr)
            gross = sum(float(t["pnl_gross_usdt"]) for t in tr)
            fees = sum(float(t["fees_usdt"]) for t in tr)
            slip = sum(float(t["slippage_usdt"]) for t in tr)
            wins = sum(float(t["pnl_net_usdt"]) > 0 for t in tr)
            pos = sum(max(0.0, float(t["pnl_net_usdt"])) for t in tr)
            neg = -sum(min(0.0, float(t["pnl_net_usdt"])) for t in tr)
            by_symbol = {}
            for t in tr:
                by_symbol.setdefault(t["symbol"], []).append(t)
            positive_symbols = 0
            for sym, rows in sorted(by_symbol.items()):
                sym_net = sum(float(x["pnl_net_usdt"]) for x in rows)
                positive_symbols += int(sym_net > 0)
                per_symbol.append({
                    "fold": fold, "compression_gate": int(compression_gate), "symbol": sym,
                    "trades": len(rows), "net_pnl_usdt": round(sym_net, 2),
                    "gross_pnl_usdt": round(sum(float(x["pnl_gross_usdt"]) for x in rows), 2),
                    "fees_usdt": round(sum(float(x["fees_usdt"]) for x in rows), 2),
                    "slippage_usdt": round(sum(float(x["slippage_usdt"]) for x in rows), 2),
                })
            summaries.append({
                "fold": fold, "execution_mode": "market",
                "compression_gate": int(compression_gate), "body_gate": 0, "gap_gate": 0,
                "universe_symbols": len(SYMBOLS), "common_bars": len(stamps),
                "trades": len(tr), "symbols_traded": len(by_symbol),
                "positive_symbols": positive_symbols,
                "compression_rejected_candidates": sum(r.get("engine_skip_reason")=="compression_regime" for r in sr),
                "net_pnl_usdt": round(pnl, 2), "gross_pnl_usdt": round(gross, 2),
                "fees_usdt": round(fees, 2), "slippage_usdt": round(slip, 2),
                "win_rate_pct": round(100*wins/len(tr), 2) if tr else 0,
                "profit_factor": round(pos/neg, 3) if neg else "",
                "mean_net_R": round(statistics.mean([float(t["net_R"]) for t in tr]), 4) if tr else "",
                "median_MFE_R": round(float(statistics.median([float(t["MFE_R"]) for t in tr])), 3) if tr else "",
                "median_MAE_R": round(float(statistics.median([float(t["MAE_R"]) for t in tr])), 3) if tr else "",
            })
            print(f"E13 fold={fold} compression={int(compression_gate)} trades={len(tr)} net={pnl:+.2f} PF={pos/neg if neg else 0:.2f} symbols={positive_symbols}/{len(by_symbol)}")
    for path, rows in [
        ("e13_h1_compression_summary.csv", summaries),
        ("e13_h1_compression_trades.csv", trades),
        ("e13_h1_compression_signals.csv", signals),
        ("e13_h1_compression_per_symbol.csv", per_symbol),
    ]:
        if rows:
            fields = []
            for row in rows:
                for key in row:
                    if key not in fields:
                        fields.append(key)
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader(); writer.writerows(rows)
            print(f"Wrote {path}: {len(rows)} rows")
    print("CAVEATS: fixed expanding-q25 compression gate on prior completed bars; one shared 10,000 USDT account per fold; 47-symbol synchronized universe; max 5 concurrent positions; market execution; costs x2; Binance OHLCV proxy; funding omitted. No production changes.")


if __name__ == "__main__":
    main()
