#!/usr/bin/env python3
"""Cross-venue robustness check for frozen H1 long-only candidates using Bybit public data.

Candidate symbols were selected from the earlier Binance train segment and are
frozen here. This script evaluates only the latest 30% of downloaded Bybit H1
bars; earlier bars are indicator warm-up only. Engine fees/slippage are modeled.
Positive funding payments are charged conservatively; negative funding receipts
are ignored. Mark-price candles are used for basis diagnostics only, not exits.
"""
from __future__ import annotations

import csv
import math
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import Bybit_Trading_Engine_v14_research as engine_mod

FROZEN_CANDIDATES = [
    "BNBUSDT", "CAKEUSDT", "DASHUSDT", "DOTUSDT", "ICPUSDT", "JSTUSDT",
    "LINKUSDT", "RAYUSDT", "SOLUSDT", "WLDUSDT", "XLMUSDT",
]
STEP_MS = 3_600_000


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_candles(path):
    rows = read_csv(path)
    candles = []
    for row in rows:
        ts = int(row["timestamp"])
        candles.append(engine_mod.Candle(
            ts, float(row["open"]), float(row["high"]), float(row["low"]),
            float(row["close"]), float(row["volume"])
        ))
    candles.sort(key=lambda c: c.ts)
    if len(candles) < 500:
        raise ValueError(f"{path}: only {len(candles)} bars")
    if len({c.ts for c in candles}) != len(candles):
        raise ValueError(f"{path}: duplicate timestamps")
    gaps = sum(1 for a, b in zip(candles, candles[1:]) if b.ts - a.ts != STEP_MS)
    if gaps:
        raise ValueError(f"{path}: {gaps} missing/irregular hourly intervals")
    return candles


def ms(value):
    return int(datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)


def funding_records(path):
    return [(int(r["timestamp"]), float(r["funding_rate"])) for r in read_csv(path)]


def funding_cost_for_trade(trade, funding):
    entry, exit_ = ms(trade.entry_date), ms(trade.exit_date)
    # Conservative long-only accounting: charge positive funding on full initial
    # notional, ignore negative-rate receipts and partial TP1 notional reductions.
    return sum(max(0.0, rate) * float(trade.size_usdt)
               for ts, rate in funding if entry < ts <= exit_)


def run_holdout(symbol, candles, cutoff_ts):
    engine = engine_mod.UnifiedQuantEngine(
        journal_output_path=f"/tmp/bybit_h1_{symbol}_journal.json"
    )
    cfg = engine.cfg
    cfg.bot_version = "bybit-h1-long-only-cross-venue"
    cfg.timeframe = "1h"
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

    def frozen_long_only(symbol_arg, history, cfg_arg):
        if not history or history[-1].ts < cutoff_ts:
            return None
        signal = original(symbol_arg, history, cfg_arg)
        if not signal:
            return None
        return signal if str(signal.get("direction", "")).lower() == "long" else None

    core.evaluate_signal = staticmethod(frozen_long_only)
    try:
        data = {symbol: candles}
        engine_mod.check_alignment(data)
        audit = engine_mod.run_simulation_pass(
            engine, data, [symbol], data_label=f"BYBIT_PUBLIC_H1_HOLDOUT {symbol}"
        )
        return engine, audit
    finally:
        core.evaluate_signal = staticmethod(original)


def pf(values):
    gains = sum(x for x in values if x > 0)
    losses = -sum(x for x in values if x < 0)
    return gains / losses if losses > 0 else (float("inf") if gains > 0 else 0.0)


def max_dd_pct(values, capital=10_000.0):
    equity = peak = capital
    worst = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak * 100)
    return worst


def run(data_dir="data/bybit_recent", output="bybit_h1_long_only_holdout.csv",
        trades_output="bybit_h1_long_only_holdout_trades.csv"):
    data_dir = Path(data_dir)
    results, all_trades = [], []
    for symbol in FROZEN_CANDIDATES:
        kline_path = data_dir / f"{symbol}_linear_kline_60.csv"
        mark_path = data_dir / f"{symbol}_linear_mark_60.csv"
        funding_path = data_dir / f"{symbol}_linear_funding.csv"
        for path in (kline_path, mark_path, funding_path):
            if not path.exists():
                raise FileNotFoundError(f"Required Bybit dataset missing: {path}")

        candles = read_candles(kline_path)
        split = int(len(candles) * 0.70)
        cutoff_ts = candles[split].ts
        funding = funding_records(funding_path)
        mark_rows = read_csv(mark_path)
        mark_by_ts = {int(r["timestamp"]): float(r["close"]) for r in mark_rows}
        common = [(c.close, mark_by_ts[c.ts]) for c in candles[split:] if c.ts in mark_by_ts]
        basis = [abs(last - mark) / last * 100 for last, mark in common if last > 0]

        engine, audit = run_holdout(symbol, candles, cutoff_ts)
        trades = list(engine.closed_trades)
        funding_costs = []
        adjusted_pnls = []
        for trade in trades:
            fcost = funding_cost_for_trade(trade, funding)
            adjusted = float(trade.pnl_usdt) - fcost
            funding_costs.append(fcost)
            adjusted_pnls.append(adjusted)
            all_trades.append({
                "symbol": symbol, "direction": trade.direction,
                "entry_date": trade.entry_date, "exit_date": trade.exit_date,
                "entry_price": trade.entry_price, "exit_price": trade.exit_price,
                "size_usdt": round(float(trade.size_usdt), 2),
                "gross_pnl_usdt": round(float(trade.gross_pnl), 2),
                "fees_usdt": round(float(trade.exchange_fees_usdt), 2),
                "slippage_usdt": round(float(trade.slippage_cost_usdt), 2),
                "funding_cost_upper_bound_usdt": round(fcost, 4),
                "net_after_funding_upper_bound_usdt": round(adjusted, 4),
                "r_after_funding_upper_bound": round(adjusted / max(float(trade.risk_usdt), 1e-9), 5),
                "exit_reason": trade.exit_reason,
            })

        results.append({
            "symbol": symbol,
            "data_start_utc": datetime.fromtimestamp(candles[0].ts/1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "holdout_start_utc": datetime.fromtimestamp(cutoff_ts/1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data_end_utc": datetime.fromtimestamp(candles[-1].ts/1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bars_total": len(candles),
            "holdout_bars": len(candles)-split,
            "funding_records": len(funding),
            "mark_holdout_coverage_pct": round(len(common)/max(1, len(candles)-split)*100, 2),
            "mean_abs_mark_last_basis_pct": round(statistics.mean(basis), 5) if basis else "",
            "p99_abs_mark_last_basis_pct": round(sorted(basis)[min(len(basis)-1, math.ceil(0.99*len(basis))-1)], 5) if basis else "",
            "trades": len(trades),
            "gross_pnl_usdt": round(sum(float(t.gross_pnl) for t in trades), 2),
            "fees_usdt": round(sum(float(t.exchange_fees_usdt) for t in trades), 2),
            "slippage_usdt": round(sum(float(t.slippage_cost_usdt) for t in trades), 2),
            "engine_net_before_funding_usdt": round(sum(float(t.pnl_usdt) for t in trades), 2),
            "positive_funding_cost_upper_bound_usdt": round(sum(funding_costs), 2),
            "net_after_funding_upper_bound_usdt": round(sum(adjusted_pnls), 2),
            "profit_factor_after_funding_upper_bound": round(pf(adjusted_pnls), 4),
            "expectancy_r_after_funding_upper_bound": round(statistics.mean(adjusted_pnls) / 100.0, 5) if adjusted_pnls else 0.0,
            "max_trade_sequence_dd_pct_after_funding_upper_bound": round(max_dd_pct(adjusted_pnls), 2),
            "source": "Bybit public linear-perpetual API",
        })

    for path, rows in ((output, results), (trades_output, all_trades)):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    print("BYBIT H1 LONG-ONLY CROSS-VENUE HOLDOUT — frozen 11 candidates from prior train-only selection")
    print("The latest 30% of each Bybit dataset is tested; earlier bars are indicator warm-up only.")
    print("Funding is a conservative upper bound: positive funding charged on full initial notional; negative receipts and partial TP1 reductions ignored.")
    print("Mark candles are downloaded and basis-checked, but current engine exits still use last-price OHLC; this is NOT mark-triggered stop/liquidation simulation.")
    print("symbol,holdout_start_utc,trades,engine_net_before_funding_usdt,funding_cost_upper_bound_usdt,net_after_funding_upper_bound_usdt,pf_after_funding,mean_abs_basis_pct,p99_abs_basis_pct")
    for r in results:
        print(",".join(str(r[k]) for k in (
            "symbol", "holdout_start_utc", "trades", "engine_net_before_funding_usdt",
            "positive_funding_cost_upper_bound_usdt", "net_after_funding_upper_bound_usdt",
            "profit_factor_after_funding_upper_bound", "mean_abs_mark_last_basis_pct",
            "p99_abs_mark_last_basis_pct"
        )))
    print(
        f"SUMMARY: symbols={len(results)}, trades={sum(r['trades'] for r in results)}, "
        f"sum_net_before_funding={sum(r['engine_net_before_funding_usdt'] for r in results):.2f} USDT, "
        f"positive_funding_cost_upper_bound={sum(r['positive_funding_cost_upper_bound_usdt'] for r in results):.2f} USDT, "
        f"sum_net_after_funding_upper_bound={sum(r['net_after_funding_upper_bound_usdt'] for r in results):.2f} USDT, "
        f"profitable_symbols_after_funding={sum(r['net_after_funding_upper_bound_usdt'] > 0 for r in results)}"
    )
    print("CAVEAT: Bybit dates overlap the earlier Binance study period; this is cross-venue robustness, not a later untouched time-period test.")
    print("CAVEAT: per-symbol runs each start with 10,000 USDT; summed PnL is not a combined portfolio curve.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data/bybit_recent")
    parser.add_argument("--output", default="bybit_h1_long_only_holdout.csv")
    parser.add_argument("--trades-output", default="bybit_h1_long_only_holdout_trades.csv")
    args = parser.parse_args()
    run(args.data_dir, args.output, args.trades_output)
