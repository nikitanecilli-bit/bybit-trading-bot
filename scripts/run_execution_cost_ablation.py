#!/usr/bin/env python3
"""Chronological holdout for limit-entry offsets and order timeouts.

All exits are modeled as taker to isolate the entry policy. Limit fills use OHLC
touches and fixed-price resting orders, optimistic without queue priority, spread,
partial fills, and adverse selection.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Bybit_Trading_Engine_v14_research as engine_mod
from run_uploaded_dataset_backtests import read_zip_datasets


def run_one(symbol, timeframe, candles, archive, mode, offset_bps=0.0, max_wait_bars=1):
    split_idx = int(len(candles) * 0.70)
    if split_idx < 200 or split_idx >= len(candles):
        return None
    cutoff_ts = candles[split_idx].ts

    engine = engine_mod.UnifiedQuantEngine(
        journal_output_path="/tmp/ignored_execution_cost_ablation_journal.json"
    )
    cfg = engine.cfg
    cfg.bot_version = f"execution-cost-{mode}"
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
    cfg.maker_entry_and_tp1 = (mode != "market")
    # Isolate maker entry: all exits remain taker in this experiment.
    cfg.maker_tp1_and_target = False
    cfg.enable_h2_range_fade = False
    cfg.validate()
    engine.risk_mgr.cfg = cfg
    engine.tg.send_message = lambda *_args, **_kwargs: None

    counts = {"signals": 0, "filled": 0, "unfilled": 0}
    pending_meta = {}
    original_eval = engine_mod.QuantStrategyCore.evaluate_signal

    def wrapped_eval(symbol_arg, history, cfg_arg):
        if not history or history[-1].ts < cutoff_ts:
            return None
        signal = original_eval(symbol_arg, history, cfg_arg)
        if signal is not None:
            counts["signals"] += 1
        return signal

    engine_mod.QuantStrategyCore.evaluate_signal = staticmethod(wrapped_eval)
    original_try_fill = engine._try_fill_pending

    def counted_try_fill(symbol_arg, candle):
        if symbol_arg not in engine.pending:
            return original_try_fill(symbol_arg, candle)

        if mode == "market":
            filled = original_try_fill(symbol_arg, candle)
            counts["filled" if filled else "unfilled"] += 1
            return filled

        sig = engine.pending[symbol_arg]
        meta = pending_meta.get(symbol_arg)
        if meta is None:
            direction = sig["direction"]
            ref = float(sig["entry_price"])
            signed_offset = -offset_bps if direction == "long" else offset_bps
            sig["entry_price"] = ref * (1.0 + signed_offset / 10_000.0)
            sig["order_type"] = "limit"
            meta = {"age": 0}
            pending_meta[symbol_arg] = meta

        meta["age"] += 1
        ref = float(sig["entry_price"])
        is_long = sig["direction"] == "long"
        touched = candle.low <= ref if is_long else candle.high >= ref
        filled = original_try_fill(symbol_arg, candle)

        if filled:
            counts["filled"] += 1
            pending_meta.pop(symbol_arg, None)
            return True

        if not touched and meta["age"] < max_wait_bars:
            engine.pending[symbol_arg] = sig
            return False

        counts["unfilled"] += 1
        pending_meta.pop(symbol_arg, None)
        return False

    engine._try_fill_pending = counted_try_fill
    try:
        candles_by_symbol = {symbol: candles}
        engine_mod.check_alignment(candles_by_symbol)
        audit = engine_mod.run_simulation_pass(
            engine, candles_by_symbol, [symbol],
            data_label=f"BINANCE_PROXY {timeframe} {symbol} {mode}",
        )
    finally:
        engine_mod.QuantStrategyCore.evaluate_signal = staticmethod(original_eval)

    trades = engine.closed_trades
    costs = sum(t.exchange_fees_usdt + t.slippage_cost_usdt for t in trades)
    fees = sum(t.exchange_fees_usdt for t in trades)
    slip = sum(t.slippage_cost_usdt for t in trades)
    return {
        "timeframe": timeframe,
        "symbol": symbol,
        "mode": mode,
        "limit_offset_bps": offset_bps if mode != "market" else 0.0,
        "max_wait_bars": max_wait_bars if mode != "market" else 0,
        "bars_total": len(candles),
        "holdout_start_utc": engine_mod.datetime.fromtimestamp(
            cutoff_ts / 1000, tz=engine_mod.timezone.utc
        ).isoformat(),
        "holdout_bars": len(candles) - split_idx,
        "signals": counts["signals"],
        "filled_pending_orders": counts["filled"],
        "unfilled_or_cancelled_pending_orders": counts["unfilled"],
        "trades": audit["total_trades"],
        "gross_pnl_usdt": round(sum(t.gross_pnl for t in trades), 2),
        "fees_usdt": round(fees, 2),
        "slippage_usdt": round(slip, 2),
        "total_costs_usdt": round(costs, 2),
        "net_pnl_usdt": round(audit["net_pnl"], 2),
        "net_pf": round(audit["pf"], 4),
        "expectancy_r": round(audit["expectancy_r"], 4),
        "max_dd_pct": round(audit["max_dd_pct"], 2),
        "source_archive": archive,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="execution_cost_ablation.csv")
    args = parser.parse_args()

    datasets = read_zip_datasets()
    if not datasets:
        raise SystemExit("No valid OHLCV datasets found in ZIP archives.")

    rows = []
    variants = [("market", 0.0, 0)]
    variants += [
        (f"limit_{offset:g}bps_wait{wait}", offset, wait)
        for offset in (0.0, 5.0, 10.0, 20.0)
        for wait in (1, 3, 5)
    ]
    for (symbol, timeframe), (bar_count, archive, candles) in sorted(datasets.items()):
        for mode, offset_bps, max_wait_bars in variants:
            result = run_one(
                symbol, timeframe, candles, archive, mode,
                offset_bps=offset_bps, max_wait_bars=max_wait_bars,
            )
            if result:
                rows.append(result)
                print(
                    f"{timeframe} {symbol} {mode}: trades={result['trades']} "
                    f"signals={result['signals']} fills={result['filled_pending_orders']} "
                    f"unfilled={result['unfilled_or_cancelled_pending_orders']} "
                    f"gross={result['gross_pnl_usdt']:+.2f} costs={result['total_costs_usdt']:.2f} "
                    f"net={result['net_pnl_usdt']:+.2f} PF={result['net_pf']:.3f}"
                )

    fields = list(rows[0].keys()) if rows else []
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print("\nSUMMARY: independent per-symbol holdout runs; not a combined portfolio.")
    for timeframe in ("15m", "1h"):
        for mode, _offset, _wait in variants:
            group = [r for r in rows if r["timeframe"] == timeframe and r["mode"] == mode]
            if not group:
                continue
            trades = sum(r["trades"] for r in group)
            costs = sum(r["total_costs_usdt"] for r in group)
            print(
                f"SUMMARY {timeframe} {mode}: symbols={len(group)} trades={trades} "
                f"signals={sum(r['signals'] for r in group)} "
                f"filled={sum(r['filled_pending_orders'] for r in group)} "
                f"unfilled={sum(r['unfilled_or_cancelled_pending_orders'] for r in group)} "
                f"gross_pnl_sum={sum(r['gross_pnl_usdt'] for r in group):+.2f} "
                f"fees_sum={sum(r['fees_usdt'] for r in group):.2f} "
                f"slippage_sum={sum(r['slippage_usdt'] for r in group):.2f} "
                f"costs_sum={costs:.2f} "
                f"net_pnl_sum={sum(r['net_pnl_usdt'] for r in group):+.2f} "
                f"profitable_symbols={sum(r['net_pnl_usdt'] > 0 for r in group)}"
            )
    print(f"\nWrote {args.output}")
    print("CAVEAT: OHLC touches do not model queue priority, bid/ask spread, adverse selection, or partial fills.")
    print("CAVEAT: limit orders rest at a fixed price for 1/3/5 bars; no live order-book data.")


if __name__ == "__main__":
    main()
