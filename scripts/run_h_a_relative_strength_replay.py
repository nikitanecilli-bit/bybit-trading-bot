#!/usr/bin/env python3
"""Preregistered H-A vs frozen H1 breakout baseline on existing CryptoFetch OHLCV.

No exchange/API access, new downloads, self-hosted runner, or live orders.
This is an OHLCV proxy experiment; funding/mark-price and Bybit-native
point-in-time instrument metadata are not available in these archives.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from statistics import median
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import Bybit_Trading_Engine_v14_research as em
from relative_strength_breakout import (
    build_strength_context, evaluate_relative_strength_breakout,
)
from scripts.cryptofetch_sparse_loader import load_cryptofetch_h1_sparse

STARTING_CAPITAL = 10_000.0
COST_MULTIPLIER = 2.0
# Same chronological windows used by the E11/E13 H1 research. They are
# already researched and must not be described as blind holdout.
FOLDS = (
    (1, "2026-04-27T12:00:00Z", "2026-06-21T05:00:00Z"),
    (2, "2026-06-21T06:00:00Z", "2026-08-14T23:00:00Z"),
    (3, "2026-08-15T00:00:00Z", "2026-10-27T00:00:00Z"),
)


def to_ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def configure_engine(symbols: list[str], label: str, enable_post_break_invalidation: bool = False):
    engine = em.UnifiedQuantEngine(
        journal_output_path=f"/tmp/{label.replace('/', '_')}_journal.json",
        persist_state=False,
    )
    cfg = engine.cfg
    cfg.bot_version = label
    cfg.timeframe = "1h"
    cfg.active_trading_pool = sorted(symbols)
    cfg.disabled_instruments = []
    cfg.capital_usdt = STARTING_CAPITAL
    # Balanced portfolio risk; frozen identically for baseline and H-A.
    cfg.max_risk_trade_pct = 0.5
    cfg.max_portfolio_risk_pct = 2.0
    cfg.max_concurrent_positions = 5
    cfg.leverage_val = 5.0
    cfg.daily_stop_loss_pct = 5.0
    cfg.emergency_kill_switch_pct = 30.0
    cfg.max_chase_limit_pct = 1.5
    cfg.donchian_period = 20
    cfg.atr_period = 14
    cfg.min_volume_ratio = 1.6
    cfg.stop_atr_mult = 2.5
    cfg.tp1_r_multiple = 2.0
    cfg.tp2_r_multiple = 5.0
    cfg.atr_trail_mult = 3.0
    cfg.max_hold_bars = 32
    cfg.maker_entry_and_tp1 = False
    cfg.maker_tp1_and_target = False
    cfg.enable_h2_range_fade = False
    cfg.enable_post_break_invalidation = enable_post_break_invalidation
    cfg.validate()
    engine.risk_mgr.cfg = cfg
    engine.tg.send_message = lambda *_args, **_kwargs: None
    return engine


def monthly_returns(equity_path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    last_by_month = {}
    for row in equity_path:
        dt = datetime.fromtimestamp(row["timestamp_ms"] / 1000, tz=timezone.utc)
        key = dt.strftime("%Y-%m")
        if key not in last_by_month or row["timestamp_ms"] >= last_by_month[key]["timestamp_ms"]:
            last_by_month[key] = row
    previous_equity = STARTING_CAPITAL
    result = []
    for month, row in sorted(last_by_month.items()):
        equity = float(row["equity"])
        result.append({
            "month_utc": month,
            "month_end_equity": round(equity, 4),
            "return_pct_from_previous_month_end": round(
                (equity / previous_equity - 1.0) * 100.0, 4
            ) if previous_equity else None,
        })
        previous_equity = equity
    return result


def run_variant(
    data: dict[str, list[em.Candle]], start_ts: int, end_ts: int,
    label: str, use_h_a: bool, use_h_c: bool = False,
) -> dict[str, Any]:
    if use_h_a and use_h_c:
        raise ValueError("H-A and H-C variants are mutually exclusive")
    engine = configure_engine(
        list(data), label, enable_post_break_invalidation=use_h_c,
    )
    equity_path: list[dict[str, Any]] = []
    active_by_close_ts = {
        candle.ts + 3_600_000: sum(
            1 for rows in data.values()
            if rows[0].ts <= candle.ts <= rows[-1].ts
        )
        for candles in data.values() for candle in candles
    }
    active_counts: list[int] = []
    eligible_counts: list[int] = []

    def capture_bar(ts_ms, current_engine):
        if ts_ms < start_ts:
            return
        risk = current_engine.risk_mgr
        active_counts.append(active_by_close_ts.get(ts_ms, 0))
        equity_path.append({
            "timestamp_ms": ts_ms,
            "equity": round(risk.current_equity, 6),
            "realized_equity": round(risk.realized_equity, 6),
            "unrealized_pnl": round(risk.unrealized_pnl, 6),
            "open_positions": len(current_engine.open_positions),
            "pending_entries": len(current_engine.pending),
            "daily_stop": bool(risk.daily_stop_triggered),
            "kill_switch": bool(risk.kill_switch_triggered),
        })

    if use_h_a:
        def context_provider(ts_ms, histories, cfg):
            context = build_strength_context(ts_ms, histories, cfg)
            if ts_ms >= start_ts + 3_600_000:
                eligible_counts.append(context["cross_section_size"])
            return context

        def evaluator(symbol, history, cfg, context):
            if not history or not (start_ts <= history[-1].ts <= end_ts):
                return None
            return evaluate_relative_strength_breakout(symbol, history, cfg, context)
    else:
        baseline_evaluator = em.QuantStrategyCore.evaluate_signal

        def evaluator(symbol, history, cfg, _context):
            if not history or not (start_ts <= history[-1].ts <= end_ts):
                return None
            return baseline_evaluator(symbol, history, cfg)
        context_provider = None

    audit = em.run_simulation_pass(
        engine, data, sorted(data), data_label="CRYPTOFETCH_BINANCE_OHLCV_PROXY",
        allow_sparse_data=True, signal_evaluator=evaluator,
        signal_context_provider=context_provider,
        bar_complete_callback=capture_bar,
    )
    # Include the finalized end-of-fold state, after open positions are closed.
    equity_path.append({
        "timestamp_ms": end_ts + 3_600_000,
        "equity": round(engine.risk_mgr.current_equity, 6),
        "realized_equity": round(engine.risk_mgr.realized_equity, 6),
        "unrealized_pnl": round(engine.risk_mgr.unrealized_pnl, 6),
        "open_positions": len(engine.open_positions),
        "pending_entries": len(engine.pending),
        "daily_stop": bool(engine.risk_mgr.daily_stop_triggered),
        "kill_switch": bool(engine.risk_mgr.kill_switch_triggered),
        "finalized": True,
    })

    trades = []
    by_symbol = {
        symbol: {
            "trades": 0, "gross_pnl": 0.0, "fees": 0.0,
            "slippage": 0.0, "funding": 0.0, "net_pnl": 0.0,
        }
        for symbol in data
    }
    for trade in engine.closed_trades:
        row = {
            "symbol": trade.token,
            "direction": trade.direction,
            "strategy": trade.strategy,
            "entry_date": trade.entry_date,
            "exit_date": trade.exit_date,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "size_usdt": trade.size_usdt,
            "gross_pnl": trade.gross_pnl,
            "fees": trade.exchange_fees_usdt,
            "slippage": trade.slippage_cost_usdt,
            "funding": trade.funding_cost_usdt,
            "net_pnl": trade.pnl_usdt,
            "r_multiple": trade.r_multiple,
            "gross_r_multiple": trade.gross_r_multiple,
            "risk_usdt": trade.risk_usdt,
            "risk_pct": trade.risk_pct,
            "mae_r": trade.mae,
            "mfe_r": trade.mfe,
            "session": trade.session,
            "order_type": trade.order_type,
            "exit_reason": trade.exit_reason,
            "initial_stop_dist": trade.initial_stop_dist,
            "initial_stop_price": trade.initial_stop_price,
            "tp1_price": trade.tp1_price,
            "tp2_price": trade.tp2_price,
            "tp1_hit": trade.tp1_hit,
            "tp1_ts_ms": trade.tp1_ts_ms,
            "realized_tp1_gross_usdt": trade.realized_tp1_gross_usdt,
            "remaining_fraction_at_exit": trade.remaining_fraction_at_exit,
            "final_stop_price": trade.final_stop_price,
            "breakout_level": trade.breakout_level,
            "tp1_maker": trade.tp1_maker,
            "final_exit_maker": trade.final_exit_maker,
        }
        trades.append(row)
        symbol = by_symbol[trade.token]
        symbol["trades"] += 1
        for key, value in (
            ("gross_pnl", trade.gross_pnl),
            ("fees", trade.exchange_fees_usdt),
            ("slippage", trade.slippage_cost_usdt),
            ("funding", trade.funding_cost_usdt),
            ("net_pnl", trade.pnl_usdt),
        ):
            symbol[key] += float(value)

    peak_exposure = max((row["open_positions"] for row in equity_path), default=0)

    def distribution(values):
        if not values:
            return {"samples": 0, "min": None, "median": None, "max": None}
        return {
            "samples": len(values), "min": min(values),
            "median": median(values), "max": max(values),
        }

    result = {
        "variant": ("H-A_relative_strength_breakout" if use_h_a else
                       "H-C_post_break_invalidation" if use_h_c else
                       "baseline_H1_Donchian_volume"),
        "fold_start_utc": iso(start_ts),
        "fold_end_utc": iso(end_ts),
        "symbols_in_fold": len(data),
        "metrics": {
            "trades": audit["total_trades"],
            "net_pnl_usdt": audit["net_pnl"],
            "return_pct": audit["ret_pct"],
            "profit_factor": audit["pf"],
            "expectancy_r": audit["expectancy_r"],
            "max_drawdown_pct": audit["max_dd_pct"],
            "gross_pnl_usdt": round(sum(t.gross_pnl for t in engine.closed_trades), 6),
            "fees_usdt": round(sum(t.exchange_fees_usdt for t in engine.closed_trades), 6),
            "slippage_usdt": round(sum(t.slippage_cost_usdt for t in engine.closed_trades), 6),
            "funding_usdt": round(sum(t.funding_cost_usdt for t in engine.closed_trades), 6),
            "peak_concurrent_positions": peak_exposure,
        },
        "monthly_returns": monthly_returns(equity_path),
        "active_universe_size_by_bar": distribution(active_counts),
        "eligible_cross_section_size_by_bar": distribution(eligible_counts),
        "symbol_attribution": {
            symbol: {key: round(value, 6) if isinstance(value, float) else value
                     for key, value in values.items()}
            for symbol, values in sorted(by_symbol.items())
        },
        "trades_ledger": trades,
        "equity_path": equity_path,
    }
    return result


def run_fold(data, fold, start_text, end_text, common_end_ts):
    requested_start, requested_end = to_ms(start_text), to_ms(end_text)
    end_ts = min(requested_end, common_end_ts)
    if end_ts < requested_start:
        raise SystemExit(f"Fold {fold}: no data in requested date window")
    fold_data = {
        symbol: [c for c in rows if c.ts <= end_ts]
        for symbol, rows in data.items()
        if rows[0].ts <= end_ts
    }
    fold_data = {
        symbol: rows for symbol, rows in fold_data.items()
        if len(rows) >= 73 and rows[-1].ts == end_ts
    }
    if len(fold_data) < 5:
        raise SystemExit(f"Fold {fold}: only {len(fold_data)} symbols at terminal boundary")
    if any(rows[0].ts + 72 * 3_600_000 > end_ts for rows in fold_data.values()):
        raise SystemExit(f"Fold {fold}: a symbol lacks required 72h warmup")
    print(
        f"FOLD {fold}: signal_window={start_text}..{iso(end_ts)}, "
        f"dynamic_symbols={len(fold_data)}, bars={sum(map(len, fold_data.values()))}"
    )

    original_fees = (em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP)
    em.TAKER_FEE *= COST_MULTIPLIER
    em.MAKER_FEE *= COST_MULTIPLIER
    em.TAKER_SLIP *= COST_MULTIPLIER
    try:
        baseline = run_variant(
            fold_data, requested_start, end_ts, f"H-A-baseline-fold-{fold}", False,
        )
        h_a = run_variant(
            fold_data, requested_start, end_ts, f"H-A-relative-strength-fold-{fold}", True,
        )
    finally:
        em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP = original_fees
    return {
        "fold": fold,
        "requested_start_utc": start_text,
        "requested_end_utc": end_text,
        "actual_end_utc": iso(end_ts),
        "symbols": sorted(fold_data),
        "baseline": baseline,
        "h_a": h_a,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir", type=Path, default=ROOT / "data" / "archives" / "cryptofetch",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "artifacts" / "h_a_relative_strength",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Run the preregistered OHLCV-only portfolio replays (default is audit/prepare only).",
    )
    args = parser.parse_args()
    data, manifest, archive_summary = load_cryptofetch_h1_sparse(args.archive_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "archive_manifest.json").write_text(
        json.dumps({"summary": archive_summary, "symbols": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(archive_summary, sort_keys=True))
    if not args.execute:
        print("PREPARE ONLY: no market PnL replay was run. Pass --execute after audit gate closure.")
        return 0

    results = [
        run_fold(data, fold, start, end, archive_summary["common_end_ts"])
        for fold, start, end in FOLDS
    ]
    payload = {
        "schema_version": 1,
        "hypothesis": "H-A relative-strength breakout",
        "data_source": "existing CryptoFetch Binance-style OHLCV archives",
        "cost_multiplier": COST_MULTIPLIER,
        "funding_included": False,
        "bybit_point_in_time_universe_confirmed": False,
        "blind_holdout": False,
        "starting_capital_usdt": STARTING_CAPITAL,
        "risk_per_trade_pct": 0.5,
        "portfolio_risk_cap_pct": 2.0,
        "results": results,
    }
    (args.output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with (args.output_dir / "fold_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "fold", "variant", "symbols", "trades", "net_pnl_usdt",
            "return_pct", "profit_factor", "expectancy_r", "max_drawdown_pct",
            "gross_pnl_usdt", "fees_usdt", "slippage_usdt",
        ])
        writer.writeheader()
        for fold_result in results:
            for variant in ("baseline", "h_a"):
                item = fold_result[variant]
                metrics = item["metrics"]
                writer.writerow({
                    "fold": fold_result["fold"],
                    "variant": item["variant"],
                    "symbols": item["symbols_in_fold"],
                    "trades": metrics["trades"],
                    "net_pnl_usdt": metrics["net_pnl_usdt"],
                    "return_pct": metrics["return_pct"],
                    "profit_factor": metrics["profit_factor"],
                    "expectancy_r": metrics["expectancy_r"],
                    "max_drawdown_pct": metrics["max_drawdown_pct"],
                    "gross_pnl_usdt": metrics["gross_pnl_usdt"],
                    "fees_usdt": metrics["fees_usdt"],
                    "slippage_usdt": metrics["slippage_usdt"],
                })
    print("Wrote preregistered baseline/H-A results. Funding is omitted; not Bybit net PnL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
