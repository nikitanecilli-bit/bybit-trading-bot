#!/usr/bin/env python3
"""Select a frozen H1 top-five universe using training data only.

This is a Bybit-native screening workflow. It does not use future folds,
CryptoFetch/Binance proxy candles, or per-symbol historical PnL from prior
screening runs. It requires official H1, funding, mark, dated instrument/risk
archives and a Bybit linear lifecycle snapshot. Each candidate is replayed
independently on the same fixed training cutoff; the resulting top five must
then pass shared-capital exploration and a one-shot final holdout.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_h1_shared_capital_portfolio_validation import (
    _directory_file_manifest,
    _file_manifest_record,
    _manifest_path,
    load_bybit_h1_datasets,
    resolve_bybit_kline_dir,
    resolve_execution_snapshot_dirs,
    resolve_funding_dirs,
    run_portfolio_variant,
)
from scripts.snapshot_bybit_linear_universe import is_linear_usdt_perpetual_within_lifecycle_at

TRAIN_FRACTION = 0.50
MIN_TRAIN_BARS = 500
MIN_TRADES = 30
MIN_VOLUME_RATIO = 1.6
MIN_BREAKOUT_ATR = 0.10
COST_MULTIPLIER = 2.0
PROTOCOL = "h1-top5-train-only-v1"


def rank_candidates(rows, min_trades=MIN_TRADES):
    """Rank only robust positive-net candidates; no forced top-five on weak data."""
    evaluated = []
    for source in rows:
        row = dict(source)
        reasons = []
        trades = int(row.get("trades", 0))
        net = float(row.get("net_pnl", 0.0))
        pf = float(row.get("profit_factor", 0.0))
        expectancy = float(row.get("expectancy_r", 0.0))
        if trades < min_trades:
            reasons.append("insufficient_trades")
        if net <= 0:
            reasons.append("non_positive_net")
        if pf <= 1.0:
            reasons.append("profit_factor_not_above_1")
        if expectancy <= 0:
            reasons.append("non_positive_expectancy")
        row["eligible"] = not reasons
        row["exclusion_reasons"] = reasons
        evaluated.append(row)
    eligible = [row for row in evaluated if row["eligible"]]
    eligible.sort(key=lambda row: (
        -float(row["expectancy_r"]),
        -float(row["profit_factor"]),
        float(row["max_drawdown_pct"]),
        -int(row["trades"]),
        str(row["symbol"]),
    ))
    return evaluated, eligible


def _read_universe_snapshot(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read Bybit linear universe snapshot: {exc}") from exc
    if (
        payload.get("schema_version") != 1
        or payload.get("category") != "linear"
        or payload.get("source") != "Bybit V5 GET /v5/market/instruments-info"
        or not isinstance(payload.get("instruments"), list)
    ):
        raise SystemExit("Unsupported or incomplete Bybit linear universe snapshot")
    try:
        fetched = datetime.fromisoformat(str(payload["fetched_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit("Bybit universe snapshot requires timezone-aware fetched_at") from exc
    if fetched.tzinfo is None:
        raise SystemExit("Bybit universe snapshot fetched_at must include timezone")
    rows = {}
    for row in payload["instruments"]:
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol or symbol in rows:
            raise SystemExit(f"Invalid or duplicate symbol in Bybit universe snapshot: {symbol!r}")
        rows[symbol] = row
    if not rows:
        raise SystemExit("Bybit linear universe snapshot is empty")
    return payload, rows


def _utc(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def select_train_only(
    *,
    kline_dir,
    universe_snapshot_path,
    instrument_specs_dir,
    risk_tiers_dir,
    funding_dir,
    mark_price_dir,
):
    universe_payload, universe = _read_universe_snapshot(universe_snapshot_path)
    raw = load_bybit_h1_datasets(kline_dir)
    if not raw:
        raise SystemExit("No Bybit H1 candidates passed the archive loader")
    reference_symbol, (_, reference_candles) = max(
        raw.items(), key=lambda item: item[1][1][-1].ts - item[1][1][0].ts
    )
    reference_start = reference_candles[0].ts
    reference_end = reference_candles[-1].ts
    cutoff = reference_start + int((reference_end - reference_start) * TRAIN_FRACTION)
    train_start = reference_start

    results = []
    exclusions = []
    for symbol, (source_path, candles) in sorted(raw.items()):
        instrument = universe.get(symbol)
        if instrument is None:
            exclusions.append({"symbol": symbol, "reason": "missing_from_lifecycle_snapshot"})
            continue
        train_candles = [c for c in candles if train_start <= c.ts <= cutoff]
        if len(train_candles) < MIN_TRAIN_BARS:
            exclusions.append({
                "symbol": symbol, "reason": "insufficient_train_history",
                "train_bars": len(train_candles),
            })
            continue
        if not is_linear_usdt_perpetual_within_lifecycle_at(instrument, cutoff):
            exclusions.append({"symbol": symbol, "reason": "not_active_usdt_perpetual_at_train_cutoff"})
            continue
        launch_ms = int(instrument["launchTime"])
        delivery_ms = int(instrument.get("deliveryTime") or 0)
        if train_candles[0].ts < launch_ms:
            raise SystemExit(f"{symbol}: Bybit H1 archive begins before recorded launchTime")
        if delivery_ms and train_candles[-1].ts >= delivery_ms:
            raise SystemExit(f"{symbol}: Bybit H1 archive extends to/after recorded deliveryTime")
        train_ts = [c.ts for c in train_candles]
        result = run_portfolio_variant(
            {symbol: train_candles}, [symbol], train_ts,
            0, 0.0, 1.0,
            MIN_VOLUME_RATIO, MIN_BREAKOUT_ATR, COST_MULTIPLIER,
            instrument_specs_dir, risk_tiers_dir,
            funding_dir, mark_price_dir, kline_dir,
        )
        result.update({
            "symbol": symbol,
            "training_bars": len(train_candles),
            "training_start_timestamp_ms": train_candles[0].ts,
            "training_end_timestamp_ms": train_candles[-1].ts,
            "source_kline": _file_manifest_record(source_path),
        })
        results.append(result)
        print(
            f"TRAIN {symbol}: trades={result['trades']} net={result['net_pnl']:+.2f} "
            f"PF={result['profit_factor']:.3f} expR={result['expectancy_r']:+.4f} "
            f"DD={result['max_drawdown_pct']:.2f}%"
        )

    evaluated, eligible = rank_candidates(results)
    primary = [row["symbol"] for row in eligible[:5]]
    reserve = [row["symbol"] for row in eligible[5:10]]
    status = "ok" if len(primary) == 5 else "insufficient_candidates"
    kline_files = _directory_file_manifest(kline_dir, {".csv"})
    input_files = {
        "kline": kline_files,
        "funding": _directory_file_manifest(funding_dir, {".csv"}),
        "mark_price": _directory_file_manifest(mark_price_dir, {".csv"}),
        "instrument_specs": _directory_file_manifest(instrument_specs_dir, {".json"}),
        "risk_tiers": _directory_file_manifest(risk_tiers_dir, {".json"}),
        "universe_snapshot": _file_manifest_record(universe_snapshot_path),
    }
    code_files = [
        _file_manifest_record(ROOT / path)
        for path in (
            "Bybit_Trading_Engine_v14_research.py",
            "scripts/run_h1_shared_capital_portfolio_validation.py",
            "scripts/select_h1_top5_train_only.py",
            "scripts/snapshot_bybit_linear_universe.py",
        )
    ]
    manifest = {
        "schema_version": 1,
        "selection_protocol": PROTOCOL,
        "selection_status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "training_window": {
            "definition": "first 50% of the longest archived instrument's launch-to-last-candle span",
            "reference_symbol": reference_symbol,
            "start_timestamp_ms": train_start,
            "cutoff_timestamp_ms": cutoff,
            "start_utc": _utc(train_start),
            "cutoff_utc": _utc(cutoff),
            "train_fraction": TRAIN_FRACTION,
        },
        "strategy_config": {
            "direction": "long_only",
            "min_volume_ratio": MIN_VOLUME_RATIO,
            "min_breakout_atr": MIN_BREAKOUT_ATR,
            "cost_multiplier": COST_MULTIPLIER,
            "risk_per_trade_pct": 1.0,
            "entry_offset_bps": 20.0,
            "entry_penetration_bps": 5.0,
            "limit_wait_bars": 3,
            "capital_per_screen": 10000.0,
            "screening_mode": "one-symbol isolated portfolio per candidate; ranking metrics are not a shared-capital portfolio",
        },
        "eligibility_rule": {
            "minimum_closed_trades": MIN_TRADES,
            "net_pnl_usdt": "strictly_positive",
            "profit_factor": "strictly_greater_than_1",
            "expectancy_r": "strictly_positive",
        },
        "ranking_rule": [
            "expectancy_r descending",
            "profit_factor descending",
            "max_drawdown_pct ascending",
            "trades descending",
            "symbol ascending",
        ],
        "universe_provenance": {
            "source": universe_payload["source"],
            "snapshot_fetched_at": universe_payload["fetched_at"],
            "limitation": "snapshot lifecycle bounds do not prove temporary trading availability or complete historical closed-contract retention",
            "archived_symbols": len(raw),
            "screened_symbols": len(results),
            "excluded_symbols": exclusions,
        },
        "primary": primary,
        "reserve": reserve,
        "eligible_candidate_count": len(eligible),
        "candidate_results": evaluated,
        "input_files": input_files,
        "code_files": code_files,
        "selection_note": (
            "The selected top five are frozen using training data only. Explore and confirm must use "
            "the exact primary list and this unchanged manifest. If fewer than five candidates pass, "
            "the selection is invalid; do not fill slots with negative or weak candidates."
        ),
    }
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="h1_top5_selection")
    parser.add_argument("--kline-dir", default=os.getenv("BYBIT_KLINE_DIR", ""))
    parser.add_argument("--funding-dir", default=os.getenv("BYBIT_FUNDING_DIR", ""))
    parser.add_argument("--mark-price-dir", default=os.getenv("BYBIT_MARK_PRICE_DIR", ""))
    parser.add_argument(
        "--universe-snapshot",
        default=os.getenv("BYBIT_UNIVERSE_SNAPSHOT_FILE", ""),
    )
    args = parser.parse_args()
    if not args.universe_snapshot:
        parser.error("--universe-snapshot / BYBIT_UNIVERSE_SNAPSHOT_FILE is required")
    kline_dir = args.kline_dir or resolve_bybit_kline_dir()
    funding_dir = args.funding_dir or os.getenv("BYBIT_FUNDING_DIR", "")
    mark_price_dir = args.mark_price_dir or os.getenv("BYBIT_MARK_PRICE_DIR", "")
    if not funding_dir or not mark_price_dir:
        parser.error("Bybit funding and mark-price directories are required")
    instrument_specs_dir, risk_tiers_dir = resolve_execution_snapshot_dirs()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = select_train_only(
        kline_dir=kline_dir,
        universe_snapshot_path=args.universe_snapshot,
        instrument_specs_dir=instrument_specs_dir,
        risk_tiers_dir=risk_tiers_dir,
        funding_dir=funding_dir,
        mark_price_dir=mark_price_dir,
    )
    manifest_path = output_dir / "h1_top5_selection_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = manifest["candidate_results"]
    if rows:
        fields = list(rows[0].keys())
        with (output_dir / "h1_top5_candidate_ranking.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    print(f"Selection status={manifest['selection_status']}; eligible={manifest['eligible_candidate_count']}; primary={manifest['primary']}; reserve={manifest['reserve']}")
    print(f"Saved immutable selection manifest: {manifest_path}")
    if manifest["selection_status"] != "ok":
        raise SystemExit("Fewer than five candidates passed the preregistered positive-net eligibility gate")


if __name__ == "__main__":
    main()
