#!/usr/bin/env python3
"""Shared-capital H1 portfolio validation for signal-quality variants.

Uses synchronized Binance OHLCV as a Bybit market-data proxy. Each fold is a
portfolio simulation with one shared 10,000 USDT account, not 10,000 USDT per
symbol. Limit fills require OHLC penetration, but queue position, spread,
partial fills, and adverse selection are not modelled.
"""
from __future__ import annotations
import csv
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Bybit_Trading_Engine_v14_research as em
from run_uploaded_dataset_backtests import read_zip_datasets

FOLDS = [(1, 0.50, 0.65), (2, 0.65, 0.80), (3, 0.80, 1.00)]
VOL_THRESHOLDS = [1.2, 1.6, 2.0, 2.5]
BREAKOUT_ATR_THRESHOLDS = [0.0, 0.10, 0.25]
ENTRY_OFFSET_BPS = 20.0
ENTRY_PENETRATION_BPS = 5.0
WAIT_BARS = 3
STARTING_CAPITAL = 10_000.0
MAX_CONCURRENT_POSITIONS = 5
COST_MULTIPLIERS = [1.0, 1.5, 2.0]
BASE_TAKER_FEE = em.TAKER_FEE
BASE_MAKER_FEE = em.MAKER_FEE
BASE_TAKER_SLIP = em.TAKER_SLIP


def aligned_h1_datasets():
    raw = {symbol: item for (symbol, tf), item in read_zip_datasets().items()
           if tf == "1h" and len(item[2]) >= 500}
    if len(raw) < 2:
        raise SystemExit(f"Need at least 2 H1 symbols, found {len(raw)}")

    # Use the longest available H1 history as the reference window. Exclude
    # newly listed/short-history symbols that would shrink the shared period.
    ref_symbol, (_, _, ref_candles) = max(
        raw.items(), key=lambda kv: kv[1][2][-1].ts - kv[1][2][0].ts
    )
    ref_start, ref_end = ref_candles[0].ts, ref_candles[-1].ts
    span = ref_end - ref_start
    selected = {}
    coverage = {}
    for symbol, item in raw.items():
        candles = item[2]
        start_ts, end_ts = candles[0].ts, candles[-1].ts
        start_lag = max(0.0, (start_ts - ref_start) / span)
        end_lag = max(0.0, (ref_end - end_ts) / span)
        covered = (end_ts - start_ts) / span
        coverage[symbol] = {"coverage_pct": round(covered * 100, 1),
                            "start_lag_pct": round(start_lag * 100, 1),
                            "end_lag_pct": round(end_lag * 100, 1)}
        if covered >= 0.70 and start_lag <= 0.15 and end_lag <= 0.15:
            selected[symbol] = item

    if len(selected) < 10:
        raise SystemExit(
            f"Only {len(selected)} symbols have >=70% reference-history coverage "
            f"with <=15% start/end lag; refusing to run a misleading short-overlap portfolio."
        )

    common = None
    for _, _, candles in selected.values():
        ts = {c.ts for c in candles}
        common = ts if common is None else common.intersection(ts)
    timestamps = sorted(common or [])
    overlap_pct = (len(timestamps) / max(1, len(ref_candles))) * 100
    if len(timestamps) < 500 or overlap_pct < 65:
        raise SystemExit(
            f"Insufficient synchronized overlap: {len(timestamps)} bars "
            f"({overlap_pct:.1f}% of reference); refusing to run."
        )

    aligned = {}
    archives = {}
    for symbol, (_, archive, candles) in selected.items():
        by_ts = {c.ts: c for c in candles}
        aligned[symbol] = [by_ts[t] for t in timestamps]
        archives[symbol] = archive
    em.check_alignment(aligned)
    print(f"Reference={ref_symbol}; selected {len(aligned)}/{len(raw)} symbols; "
          f"common overlap={overlap_pct:.1f}% ({len(timestamps)} H1 bars)")
    print("Selected symbol coverage: " + ", ".join(
        f"{s}:{coverage[s]['coverage_pct']}%" for s in sorted(aligned)
    ))
    return aligned, archives, timestamps

def run_portfolio_variant(base_candles, symbols, timestamps, fold, start_frac, end_frac,
                          min_vol, min_breakout_atr, cost_multiplier):
    # Explicit cost stress: scale fees and taker slippage from engine defaults.
    em.TAKER_FEE = BASE_TAKER_FEE * cost_multiplier
    em.MAKER_FEE = BASE_MAKER_FEE * cost_multiplier
    em.TAKER_SLIP = BASE_TAKER_SLIP * cost_multiplier
    n = len(timestamps)
    start_idx, end_idx = int(n * start_frac), int(n * end_frac)
    start_ts, end_ts = timestamps[start_idx], timestamps[end_idx - 1]
    # Truncate at fold end, while allowing pre-fold candles for indicator warm-up.
    fold_data = {sym: candles[:end_idx] for sym, candles in base_candles.items()}

    engine = em.UnifiedQuantEngine(journal_output_path="/tmp/ignored_h1_portfolio_quality.json")
    cfg = engine.cfg
    cfg.bot_version = f"h1-portfolio-v{min_vol:g}-b{min_breakout_atr:g}-cost{cost_multiplier:g}"
    cfg.timeframe = "1h"
    cfg.active_trading_pool = list(symbols)
    cfg.capital_usdt = STARTING_CAPITAL
    cfg.max_risk_trade_pct = 1.0
    cfg.max_portfolio_risk_pct = 2.0
    cfg.max_concurrent_positions = MAX_CONCURRENT_POSITIONS
    cfg.daily_stop_loss_pct = 5.0
    cfg.emergency_kill_switch_pct = 30.0
    cfg.donchian_period = 20
    cfg.atr_period = 14
    cfg.min_volume_ratio = min_vol
    cfg.stop_atr_mult = 2.5
    cfg.tp1_r_multiple = 2.0
    cfg.tp2_r_multiple = 5.0
    cfg.atr_trail_mult = 3.0
    cfg.max_hold_bars = 32
    cfg.maker_entry_and_tp1 = True
    cfg.maker_tp1_and_target = False
    cfg.enable_h2_range_fade = False
    cfg.validate()
    engine.risk_mgr.cfg = cfg
    engine.tg.send_message = lambda *_args, **_kwargs: None

    core = em.QuantStrategyCore
    original_eval = core.evaluate_signal

    def wrapped_eval(sym, bars, conf):
        if not bars or not (start_ts <= bars[-1].ts <= end_ts):
            return None
        sig = original_eval(sym, bars, conf)
        if sig is None or str(sig.get("direction", "")).lower() != "long":
            return None
        if float(sig.get("vol_ratio", 0.0)) < min_vol:
            return None
        if min_breakout_atr > 0:
            prev = bars[:-1]
            hi_ch, _, _ = core.compute_donchian_and_volume(prev, conf.donchian_period)
            atr = float(sig.get("atr", 0.0))
            if atr <= 0 or (float(bars[-1].close) - hi_ch) / atr < min_breakout_atr:
                return None
        return sig

    core.evaluate_signal = staticmethod(wrapped_eval)
    original_fill = engine._try_fill_pending
    order_age = {}

    def wrapped_fill(sym, candle):
        if sym not in engine.pending:
            return original_fill(sym, candle)
        sig = engine.pending[sym]
        meta = order_age.get(sym)
        if meta is None:
            sig["entry_price"] = float(sig["entry_price"]) * (1.0 - ENTRY_OFFSET_BPS / 10000.0)
            sig["order_type"] = "limit"
            meta = {"age": 0}
            order_age[sym] = meta
        meta["age"] += 1
        ref = float(sig["entry_price"])
        required_low = ref * (1.0 - ENTRY_PENETRATION_BPS / 10000.0)
        if float(candle.low) <= required_low:
            filled = original_fill(sym, candle)
            order_age.pop(sym, None)
            return filled
        # No qualifying penetration: age the order without allowing the engine
        # to treat a mere touch as a fill. Cancel cleanly after WAIT_BARS.
        engine.pending.pop(sym, None)
        if meta["age"] < WAIT_BARS:
            engine.pending[sym] = sig
            return False
        order_age.pop(sym, None)
        return False

    engine._try_fill_pending = wrapped_fill
    try:
        em.check_alignment(fold_data)
        audit = em.run_simulation_pass(
            engine, fold_data, list(symbols),
            data_label=f"BINANCE_PROXY H1 portfolio fold={fold} vol>={min_vol} breakoutATR>={min_breakout_atr}",
        )
    finally:
        core.evaluate_signal = staticmethod(original_eval)

    trades = engine.closed_trades
    costs = sum(t.exchange_fees_usdt + t.slippage_cost_usdt for t in trades)
    return {
        "timeframe": "1h",
        "fold": fold,
        "variant": f"vol{min_vol:g}_breakATR{min_breakout_atr:g}_cost{cost_multiplier:g}",
        "cost_multiplier": cost_multiplier,
        "min_volume_ratio": min_vol,
        "min_breakout_atr": min_breakout_atr,
        "symbols": len(symbols),
        "shared_starting_capital": STARTING_CAPITAL,
        "max_concurrent_positions": MAX_CONCURRENT_POSITIONS,
        "trades": int(audit["total_trades"]),
        "net_pnl": round(float(audit["net_pnl"]), 2),
        "return_pct": round(float(audit["ret_pct"]), 3),
        "profit_factor": round(float(audit["pf"]), 4),
        "expectancy_r": round(float(audit["expectancy_r"]), 4),
        "max_drawdown_pct": round(float(audit["max_dd_pct"]), 2),
        "costs": round(float(costs), 2),
        "test_start_ts": start_ts,
        "test_end_ts": end_ts,
    }


def main():
    datasets, archives, timestamps = aligned_h1_datasets()
    symbols = sorted(datasets)
    print(f"Aligned H1 portfolio: {len(symbols)} symbols, {len(timestamps)} common bars")
    print(f"Archive sources: {len(set(archives.values()))}; starting capital={STARTING_CAPITAL:.0f} USDT")
    rows = []
    for fold, start_frac, end_frac in FOLDS:
        for min_vol in VOL_THRESHOLDS:
            for min_breakout in BREAKOUT_ATR_THRESHOLDS:
                for cost_multiplier in COST_MULTIPLIERS:
                    result = run_portfolio_variant(
                        datasets, symbols, timestamps, fold, start_frac, end_frac,
                        min_vol, min_breakout, cost_multiplier
                    )
                    rows.append(result)
                    print(f"fold={fold} {result['variant']} trades={result['trades']} "
                          f"net={result['net_pnl']:+.2f} ({result['return_pct']:+.2f}%) "
                          f"PF={result['profit_factor']:.3f} DD={result['max_drawdown_pct']:.2f}% "
                          f"costs={result['costs']:.2f}")
    path = "h1_shared_capital_portfolio_validation.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {path}; {len(rows)} portfolio-fold-cost runs. Cost multipliers={COST_MULTIPLIERS}.")
    print("CAVEAT: Binance OHLCV proxy; modelled costs; limit penetration is not a real queue/fill model.")


if __name__ == "__main__":
    main()
