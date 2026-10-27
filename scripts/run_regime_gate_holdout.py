#!/usr/bin/env python3
"""Chronological holdout comparison: baseline vs a frozen trend-alignment gate.

The final 30% of each dataset is the evaluation window. No new entries are
allowed before its start; indicator history remains available from earlier bars.
The candidate gate is predeclared and simple: long signals only in trend_up,
short signals only in trend_down. This is an experiment, not a live-bot change.
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

import Bybit_Trading_Engine_v14_research as engine_mod
from market_regime import classify_candles
from scripts.run_uploaded_dataset_backtests import read_zip_datasets
from scripts.run_regime_analysis import summarize_trades, trade_signal_regime

TIMEFRAME_MS = {"15m": 900_000, "1h": 3_600_000}
TEST_FRACTION = 0.30


def gate_allows(direction: str, regime: str) -> bool:
    """Frozen, theory-driven trend-alignment rule; not fitted to holdout PnL."""
    side = direction.lower()
    if side == "long":
        return regime == "trend_up"
    if side == "short":
        return regime == "trend_down"
    return False


def run_variant(symbol, timeframe, candles, cutoff_ts, labels_by_ts, variant):
    engine = engine_mod.UnifiedQuantEngine(
        journal_output_path="/tmp/ignored_regime_gate_holdout_journal.json"
    )
    cfg = engine.cfg
    cfg.bot_version = f"regime-holdout-{variant}"
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

    def wrapped(symbol_arg, history, cfg_arg):
        if not history or history[-1].ts < cutoff_ts:
            return None
        signal = original(symbol_arg, history, cfg_arg)
        if signal is None or variant == "baseline":
            return signal
        regime = labels_by_ts.get(history[-1].ts, "unknown")
        return signal if gate_allows(signal.get("direction", ""), regime) else None

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


def run(output_path):
    datasets = read_zip_datasets()
    if not datasets:
        raise SystemExit("No valid OHLCV datasets found in uploaded ZIP archives.")
    report = []

    for (symbol, timeframe), (bar_count, archive, candles) in sorted(datasets.items()):
        if timeframe not in TIMEFRAME_MS or len(candles) < 100:
            continue
        split_index = max(1, min(len(candles) - 1, int(len(candles) * (1.0 - TEST_FRACTION))))
        cutoff_ts = candles[split_index].ts
        rows = [
            {"ts": c.ts, "open": c.open, "high": c.high, "low": c.low,
             "close": c.close, "volume": c.volume}
            for c in candles
        ]
        labelled = classify_candles(rows)
        labels_by_ts = {int(row["ts"]): str(row["regime"]) for row in labelled}

        for variant in ("baseline", "trend_aligned_gate"):
            trades = run_variant(symbol, timeframe, candles, cutoff_ts, labels_by_ts, variant)
            groups = defaultdict(list)
            for trade in trades:
                regime = trade_signal_regime(trade, labels_by_ts, TIMEFRAME_MS[timeframe])
                direction = trade.direction.lower()
                groups[(regime, direction)].append(trade)
                groups[(regime, "both")].append(trade)
                groups[("all_test", direction)].append(trade)
                groups[("all_test", "both")].append(trade)

            for (regime, direction), subset in sorted(groups.items()):
                report.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "archive": archive,
                    "bars_total": bar_count,
                    "test_bars": len(candles) - split_index,
                    "test_start_utc": datetime.fromtimestamp(cutoff_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "variant": variant,
                    "regime": regime,
                    "direction": direction,
                    **summarize_trades(subset),
                })

    if not report:
        raise SystemExit("No holdout report rows were produced.")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report[0].keys()))
        writer.writeheader()
        writer.writerows(report)
    print(f"Wrote {len(report)} holdout comparison rows to {output_path}")
    print("Caveat: this is a chronological split of the currently available data, not a truly untouched future period.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="regime_gate_holdout.csv")
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
