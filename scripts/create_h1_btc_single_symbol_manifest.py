#!/usr/bin/env python3
"""Create a provenance-frozen BTCUSDT-only H1 selection manifest; never runs PnL."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scripts.run_h1_shared_capital_portfolio_validation import (
    BTC_H1_REPLAY_CODE_PATHS,
    _directory_file_manifest,
    _file_manifest_record,
    load_bybit_h1_datasets,
    resolve_h1_replay_code_paths,
)
from scripts.snapshot_bybit_linear_universe import is_linear_usdt_perpetual_within_lifecycle_at


def build_manifest(*, kline_dir, funding_dir, mark_price_dir, instrument_specs_dir,
                   risk_tiers_dir, universe_snapshot, output):
    raw = load_bybit_h1_datasets(kline_dir)
    if set(raw) != {"BTCUSDT"}:
        raise SystemExit("BTC-only manifest requires exactly one H1 kline symbol: BTCUSDT")
    candles = list(raw["BTCUSDT"][1])
    timestamps = [int(candle.ts) for candle in candles]
    if len(timestamps) < 6001:
        raise SystemExit("BTC-only manifest requires at least 6,001 H1 bars")
    if any(b - a != 3_600_000 for a, b in zip(timestamps, timestamps[1:])):
        raise SystemExit("BTC H1 archive contains gaps; refusing to freeze a misleading contiguous training window")
    first_validation_index = int(len(timestamps) * 0.50)
    if first_validation_index < 3000 or first_validation_index >= len(timestamps):
        raise SystemExit("BTC H1 archive does not provide at least 3,000 training bars plus validation data")
    cutoff = timestamps[first_validation_index - 1]

    universe_path = Path(universe_snapshot)
    try:
        payload = json.loads(universe_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read Bybit linear universe snapshot: {exc}") from exc
    if (payload.get("schema_version") != 1 or payload.get("category") != "linear"
            or payload.get("source") != "Bybit V5 GET /v5/market/instruments-info"
            or not isinstance(payload.get("instruments"), list)):
        raise SystemExit("Unsupported or incomplete official Bybit linear universe snapshot")
    matches = [row for row in payload["instruments"]
               if isinstance(row, dict) and row.get("symbol") == "BTCUSDT"]
    if len(matches) != 1 or not is_linear_usdt_perpetual_within_lifecycle_at(matches[0], cutoff):
        raise SystemExit("Bybit lifecycle snapshot does not prove BTCUSDT was a live USDT perpetual at the frozen cutoff")
    launch = int(matches[0]["launchTime"])
    delivery = int(matches[0].get("deliveryTime") or 0)
    if timestamps[0] < launch or (delivery and timestamps[-1] >= delivery):
        raise SystemExit("BTC H1 archive extends outside the lifecycle bounds in the Bybit snapshot")

    input_files = {
        "kline": _directory_file_manifest(kline_dir, {".csv"}),
        "funding": _directory_file_manifest(funding_dir, {".csv"}),
        "mark_price": _directory_file_manifest(mark_price_dir, {".csv"}),
        "instrument_specs": _directory_file_manifest(instrument_specs_dir, {".json"}),
        "risk_tiers": _directory_file_manifest(risk_tiers_dir, {".json"}),
        "universe_snapshot": [_file_manifest_record(universe_path)],
    }
    for key in ("kline", "funding", "mark_price"):
        rows = input_files[key]
        if len(rows) != 1 or Path(rows[0]["path"]).stem != "BTCUSDT":
            raise SystemExit(f"{key} archive must contain exactly BTCUSDT data")
    for key in ("instrument_specs", "risk_tiers"):
        if not input_files[key]:
            raise SystemExit(f"Missing dated Bybit {key} archive")
    root = Path(__file__).resolve().parents[1]
    code_files = [_file_manifest_record(root / item)
                  for item in resolve_h1_replay_code_paths(root, BTC_H1_REPLAY_CODE_PATHS)]
    manifest = {
        "schema_version": 1,
        "selection_protocol": "h1-btc-single-symbol-v1",
        "selection_status": "ok",
        "selection_method": "fixed_single_symbol_no_ranking",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "research_git_commit": os.getenv("H1_RESEARCH_CHECKOUT_SHA") or os.getenv("GITHUB_SHA"),
        "strategy_config": {"direction": "long_only", "symbol": "BTCUSDT"},
        "training_window": {
            "definition": "first 50 percent of the contiguous BTCUSDT Bybit H1 archive",
            "start_timestamp_ms": timestamps[0],
            "cutoff_timestamp_ms": cutoff,
            "first_validation_timestamp_ms": timestamps[first_validation_index],
            "training_bar_count": first_validation_index,
        },
        "primary": ["BTCUSDT"],
        "input_files": input_files,
        "code_files": code_files,
    }
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\\n", encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kline-dir", required=True)
    parser.add_argument("--funding-dir", required=True)
    parser.add_argument("--mark-price-dir", required=True)
    parser.add_argument("--instrument-specs-dir", required=True)
    parser.add_argument("--risk-tiers-dir", required=True)
    parser.add_argument("--universe-snapshot", required=True)
    parser.add_argument("--output", default="h1_btc_single_selection_manifest.json")
    args = parser.parse_args()
    target = build_manifest(
        kline_dir=args.kline_dir, funding_dir=args.funding_dir,
        mark_price_dir=args.mark_price_dir, instrument_specs_dir=args.instrument_specs_dir,
        risk_tiers_dir=args.risk_tiers_dir, universe_snapshot=args.universe_snapshot,
        output=args.output,
    )
    print(f"BTCUSDT-only manifest prepared (no PnL): {target}")


if __name__ == "__main__":
    main()
