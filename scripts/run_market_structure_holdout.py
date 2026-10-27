#!/usr/bin/env python3
"""Compare baseline and causal trend/breakout filters on the same chronological holdout.

Research-only: does not alter production trading logic. Filters use completed bars only.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import Bybit_Trading_Engine_v14_research as engine_mod
from market_structure import breakout_quality, trend_direction
from run_uploaded_dataset_backtests import read_zip_datasets
from run_regime_analysis import summarize_trades

TEST_FRACTION = 0.30
TIMEFRAME_MS = {"15m": 900_000, "1h": 3_600_000}


def aggregate_4h(candles, source_step_ms):
    """Aggregate only complete 4h bars; timestamps represent candle open times."""
    target = 14_400_000
    buckets = defaultdict(list)
    for candle in candles:
        buckets[(candle.ts // target) * target].append(candle)
    expected = target // source_step_ms
    out = []
    for ts, group in sorted(buckets.items()):
        group.sort(key=lambda c: c.ts)
        if len(group) != expected:
            continue
        if any(group[i].ts - group[i-1].ts != source_step_ms for i in range(1, len(group))):
            continue
        out.append(engine_mod.Candle(
            ts, group[0].open, max(c.high for c in group),
            min(c.low for c in group), group[-1].close,
            sum(float(c.volume) for c in group)
        ))
    return out


def run_variant(symbol, timeframe, candles, cutoff_ts, variant):
    engine = engine_mod.UnifiedQuantEngine(
        journal_output_path="/tmp/ignored_market_structure_holdout_journal.json"
    )
    cfg = engine.cfg
    cfg.bot_version = f"market-structure-{variant}"
    cfg.timeframe = timeframe
    cfg.active_trading_pool = [symbol]
    cfg.capital_usdt = 10_000.0
    cfg.max_risk_trade_pct = 1.0
    cfg.max_portfolio_risk_pct = 2.0
    cfg.max_concurrent_positions = 1
    cfg.daily_stop_loss_pct = 5.0
    cfg.emergency_kill_switch_pct = 30.0
    cfg.donchian_period = 20
    cfg.atr_period = 14
    cfg.min_volume_ratio = 1.6
    cfg.stop_atr_mult = 2.5
    cfg.tp1_r_multiple = 2.0
    cfg.tp2_r_multiple = 5.0
    cfg.atr_trail_mult = 3.0
    cfg.max_hold_bars = 32
    cfg.maker_entry_and_tp1 = False
    cfg.enable_h2_range_fade = False
    cfg.validate()
    engine.risk_mgr.cfg = cfg
    engine.tg.send_message = lambda *_args, **_kwargs: None

    core = engine_mod.QuantStrategyCore
    original = core.evaluate_signal
    step_ms = TIMEFRAME_MS[timeframe]

    def wrapped(symbol_arg, history, cfg_arg):
        if not history or history[-1].ts < cutoff_ts:
            return None
        signal = original(symbol_arg, history, cfg_arg)
        if signal is None or variant == "baseline":
            return signal
        direction = str(signal.get("direction", "")).lower()
        # For 15m and 1h signals, only fully closed 4h candles define the trend.
        bars_4h = aggregate_4h(history, step_ms)
        trend = trend_direction(bars_4h)
        if variant in ("trend_gate", "trend_plus_breakout", "trend_plus_breakout_confirm"):
            if (direction == "long" and trend != "up") or (direction == "short" and trend != "down"):
                return None
        if variant in ("breakout_gate", "trend_plus_breakout", "trend_plus_breakout_confirm"):
            if not breakout_quality(history, direction, lookback=cfg_arg.donchian_period,
                                    min_volume_ratio=cfg_arg.min_volume_ratio):
                return None
        if variant == "trend_plus_breakout_confirm":
            # Require the preceding completed candle also to close beyond the current
            # Donchian boundary. This is a delayed-entry confirmation, not hindsight.
            prior = history[:-1]
            if len(prior) < cfg_arg.donchian_period + 1:
                return None
            window = prior[-cfg_arg.donchian_period:]
            level = max(c.high for c in window) if direction == "long" else min(c.low for c in window)
            if direction == "long" and prior[-1].close <= level:
                return None
            if direction == "short" and prior[-1].close >= level:
                return None
        return signal

    core.evaluate_signal = staticmethod(wrapped)
    try:
        engine_mod.check_alignment({symbol: candles})
        engine_mod.run_simulation_pass(
            engine, {symbol: candles}, [symbol],
            data_label=f"BINANCE_PROXY HOLDOUT {timeframe} {symbol} {variant}",
        )
        return list(engine.closed_trades)
    finally:
        core.evaluate_signal = staticmethod(original)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="market_structure_holdout.csv")
    args = parser.parse_args()
    datasets = read_zip_datasets()
    if not datasets:
        raise SystemExit("No valid OHLCV datasets found in uploaded ZIP archives.")
    report = []
    variants = ("baseline", "trend_gate", "breakout_gate",
                "trend_plus_breakout", "trend_plus_breakout_confirm")
    for (symbol, timeframe), (bar_count, archive, candles) in sorted(datasets.items()):
        if timeframe not in TIMEFRAME_MS or len(candles) < 200:
            continue
        split = max(1, min(len(candles)-1, int(len(candles) * (1.0-TEST_FRACTION))))
        cutoff_ts = candles[split].ts
        for variant in variants:
            trades = run_variant(symbol, timeframe, candles, cutoff_ts, variant)
            report.append({
                "symbol": symbol, "timeframe": timeframe, "archive": archive,
                "bars_total": bar_count, "test_bars": len(candles)-split,
                "test_start_utc": datetime.fromtimestamp(cutoff_ts/1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "variant": variant, **summarize_trades(trades),
            })
    if not report:
        raise SystemExit("No holdout report rows were produced.")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(report[0].keys()))
        writer.writeheader()
        writer.writerows(report)
    # Print compact aggregate view for quick comparison.
    by_variant = defaultdict(list)
    for row in report:
        by_variant[row["variant"]].append(row)
    print("variant,symbol_timeframes,trades,net_pnl_usdt,profitable_symbol_timeframes")
    for variant in variants:
        rows = by_variant[variant]
        trades = sum(int(r.get("trades", 0) or 0) for r in rows)
        pnl = sum(float(r.get("net_pnl_usdt", 0) or 0) for r in rows)
        winners = sum(float(r.get("net_pnl_usdt", 0) or 0) > 0 for r in rows)
        print(f"{variant},{len(rows)},{trades},{pnl:.2f},{winners}")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
