#!/usr/bin/env python3
"""Frozen H-C reverse-time robustness check on the existing CryptoFetch H1 proxy.

This is not Bybit data, not forward OOS, and not a claim of funding-inclusive net PnL.
No API access, network downloads, or orders are performed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

from scripts.run_h_a_relative_strength_replay import (
    COST_MULTIPLIER,
    ROOT,
    STARTING_CAPITAL,
    em,
    iso,
    run_variant,
    to_ms,
)
from scripts.cryptofetch_sparse_loader import load_cryptofetch_h1_sparse

H1_MS = 3_600_000
START_UTC = "2025-10-30T00:00:00Z"
END_UTC = "2026-04-26T23:00:00Z"
EXPECTED_SYMBOLS = [
    "AAVEUSDT", "ASTERUSDT", "BCHUSDT", "CAKEUSDT", "DASHUSDT",
    "DOTUSDT", "ENAUSDT", "ETCUSDT", "GMXUSDT", "HBARUSDT",
    "ICPUSDT", "JSTUSDT", "MORPHOUSDT", "ONDOUSDT", "PAXGUSDT",
    "PUMPUSDT", "QNTUSDT", "RAYUSDT", "RENDERUSDT", "SHIBUSDT",
    "SKYUSDT", "TAOUSDT", "WLDUSDT", "WLFIUSDT", "XLMUSDT",
]
CODE_PATHS = [
    "Bybit_Trading_Engine_v14_research.py",
    "scripts/run_h_a_relative_strength_replay.py",
    "scripts/run_h_c_reverse_time_robustness.py",
    "scripts/cryptofetch_sparse_loader.py",
    "scripts/audit_cryptofetch_archives.py",
]


def prepare_fold(data, start_ts: int, end_ts: int, expected_symbols=EXPECTED_SYMBOLS):
    """Freeze the date-available archive universe; never select by PnL."""
    missing = sorted(set(expected_symbols).difference(data))
    if missing:
        raise ValueError(f"missing preregistered archive symbols: {missing}")
    fold_data = {}
    for symbol in expected_symbols:
        rows = [candle for candle in data[symbol] if candle.ts <= end_ts]
        if not rows or rows[-1].ts != end_ts:
            raise ValueError(f"{symbol}: missing exact terminal H1 candle {end_ts}")
        if rows[0].ts + 72 * H1_MS > start_ts:
            raise ValueError(f"{symbol}: less than 72 H1 warmup bars before scoring start")
        if any(b.ts - a.ts != H1_MS for a, b in zip(rows, rows[1:])):
            raise ValueError(f"{symbol}: non-contiguous H1 history in reverse-time window")
        fold_data[symbol] = rows
    if set(fold_data) != set(expected_symbols):
        raise AssertionError("frozen reverse-time symbol universe changed")
    return fold_data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_reverse_time(data, start_ts: int, end_ts: int):
    original_costs = (em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP)
    em.TAKER_FEE *= COST_MULTIPLIER
    em.MAKER_FEE *= COST_MULTIPLIER
    em.TAKER_SLIP *= COST_MULTIPLIER
    try:
        baseline = run_variant(
            data, start_ts, end_ts, "H-C-reverse-time-baseline",
            use_h_a=False, use_h_c=False,
        )
        h_c = run_variant(
            data, start_ts, end_ts, "H-C-reverse-time-invalidation",
            use_h_a=False, use_h_c=True,
        )
    finally:
        em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP = original_costs

    duration_ms = end_ts - start_ts + H1_MS
    average_month_ms = 365.2425 / 12.0 * 86_400_000.0

    def monthly_equivalent(net_pnl):
        final_equity = STARTING_CAPITAL + float(net_pnl)
        if final_equity <= 0:
            return -100.0
        return (pow(final_equity / STARTING_CAPITAL,
                    average_month_ms / duration_ms) - 1.0) * 100.0

    baseline_net = float(baseline["metrics"]["net_pnl_usdt"])
    h_c_net = float(h_c["metrics"]["net_pnl_usdt"])
    return {
        "baseline": baseline,
        "h_c": h_c,
        "comparison": {
            "h_c_minus_baseline_net_proxy_usdt": round(h_c_net - baseline_net, 6),
            "h_c_beats_baseline_net_proxy": h_c_net > baseline_net,
            "h_c_net_proxy_positive_before_funding": h_c_net > 0,
            "baseline_geometric_monthly_proxy_pct": round(monthly_equivalent(baseline_net), 6),
            "h_c_geometric_monthly_proxy_pct": round(monthly_equivalent(h_c_net), 6),
            "duration_days": duration_ms / 86_400_000.0,
            "duration_months": duration_ms / average_month_ms,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir", type=Path, default=ROOT / "data" / "archives" / "cryptofetch",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "artifacts" / "h_c_reverse_time",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Run the frozen baseline/H-C reverse-time proxy replay; default is prepare only.",
    )
    args = parser.parse_args()

    start_ts, end_ts = to_ms(START_UTC), to_ms(END_UTC)
    if end_ts < start_ts or start_ts % H1_MS or end_ts % H1_MS:
        raise ValueError("preregistered H1 boundaries must be ordered and H1-aligned")

    data, archive_manifest, archive_summary = load_cryptofetch_h1_sparse(args.archive_dir)
    fold_data = prepare_fold(data, start_ts, end_ts)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    selected_archives = [
        row for row in archive_manifest if row["symbol"] in EXPECTED_SYMBOLS
    ]
    if len(selected_archives) != len(EXPECTED_SYMBOLS):
        raise ValueError("archive provenance manifest does not cover the frozen symbol set")

    payload = {
        "schema_version": 1,
        "hypothesis": "H-C post-break invalidation versus frozen H1 Donchian-volume baseline",
        "test_type": "reverse_time_robustness_proxy_not_forward_oos",
        "data_source": "existing CryptoFetch Binance-style H1 OHLCV archive",
        "bybit_native": False,
        "funding_included": False,
        "mark_price_included": False,
        "point_in_time_universe_confirmed": False,
        "blind_holdout": False,
        "start_utc": START_UTC,
        "end_utc": END_UTC,
        "start_ts_ms": start_ts,
        "end_ts_ms": end_ts,
        "symbols": EXPECTED_SYMBOLS,
        "symbol_count": len(fold_data),
        "starting_capital_usdt": STARTING_CAPITAL,
        "risk_per_trade_pct": 0.5,
        "portfolio_risk_cap_pct": 2.0,
        "max_concurrent_positions": 5,
        "leverage": 5.0,
        "daily_stop_loss_pct": 5.0,
        "emergency_kill_switch_pct": 30.0,
        "max_chase_limit_pct": 1.5,
        "strategy_config": {
            "timeframe": "1h",
            "donchian_period": 20,
            "atr_period": 14,
            "min_volume_ratio": 1.6,
            "stop_atr_mult": 2.5,
            "tp1_r_multiple": 2.0,
            "tp2_r_multiple": 5.0,
            "atr_trail_mult": 3.0,
            "max_hold_bars": 32,
            "maker_entry_and_tp1": false,
            "maker_tp1_and_target": false,
            "enable_post_break_invalidation_bars": 3,
        },
        "entry_and_exit_model": "market; no maker credit",
        "cost_multiplier": COST_MULTIPLIER,
        "funding_note": "funding is omitted, not assumed economically zero",
        "archive_summary": archive_summary,
        "archive_manifest": selected_archives,
        "research_git_sha": os.environ.get("GITHUB_SHA"),
        "code_sha256": {
            path: sha256(ROOT / path) for path in CODE_PATHS
        },
        "execution_performed": False,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "symbols": len(fold_data), "start_utc": START_UTC,
        "end_utc": END_UTC, "common_terminal_bar": iso(end_ts),
        "archive_summary": archive_summary,
    }, sort_keys=True))

    if not args.execute:
        print("PREPARE ONLY: no market PnL replay was run.")
        return 0

    results = run_reverse_time(fold_data, start_ts, end_ts)
    payload["execution_performed"] = True
    payload["baseline"] = results["baseline"]
    payload["h_c"] = results["h_c"]
    payload["comparison"] = results["comparison"]
    (args.output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )

    with (args.output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = [
            "variant", "symbols", "trades", "gross_pnl_usdt", "fees_usdt",
            "slippage_usdt", "net_proxy_before_funding_usdt", "profit_factor",
            "expectancy_r", "max_drawdown_pct", "geometric_monthly_proxy_pct",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for key in ("baseline", "h_c"):
            item = results[key]
            metrics = item["metrics"]
            writer.writerow({
                "variant": item["variant"],
                "symbols": item["symbols_in_fold"],
                "trades": metrics["trades"],
                "gross_pnl_usdt": metrics["gross_pnl_usdt"],
                "fees_usdt": metrics["fees_usdt"],
                "slippage_usdt": metrics["slippage_usdt"],
                "net_proxy_before_funding_usdt": metrics["net_pnl_usdt"],
                "profit_factor": metrics["profit_factor"],
                "expectancy_r": metrics["expectancy_r"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "geometric_monthly_proxy_pct": (
                    results["comparison"]["baseline_geometric_monthly_proxy_pct"]
                    if key == "baseline"
                    else results["comparison"]["h_c_geometric_monthly_proxy_pct"]
                ),
            })

    print(json.dumps(results["comparison"], sort_keys=True))
    print("Completed reverse-time CryptoFetch proxy replay; not Bybit net PnL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
