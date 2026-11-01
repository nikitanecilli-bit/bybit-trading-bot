#!/usr/bin/env python3
"""Preflight funding-history and timestamp-aligned mark-candle coverage."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from typing import Iterable


def _read_funding(path: Path) -> set[int]:
    timestamps: set[int] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"funding_timestamp_ms", "funding_rate"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path}: required columns funding_timestamp_ms,funding_rate")
        for line, row in enumerate(reader, start=2):
            try:
                row_symbol = str(row.get("symbol") or path.stem).upper()
                ts = int(row["funding_timestamp_ms"])
                rate = float(row["funding_rate"])
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"{path}:{line}: invalid funding row") from exc
            if row_symbol != path.stem.upper():
                raise ValueError(f"{path}:{line}: symbol does not match filename")
            if ts <= 0 or not math.isfinite(rate):
                raise ValueError(f"{path}:{line}: invalid funding timestamp/rate")
            if ts in timestamps:
                raise ValueError(f"{path}:{line}: duplicate funding timestamp {ts}")
            timestamps.add(ts)
    return timestamps


def _read_marks(path: Path) -> set[int]:
    timestamps: set[int] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp_ms", "open"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path}: required columns timestamp_ms,open")
        for line, row in enumerate(reader, start=2):
            try:
                row_symbol = str(row.get("symbol") or path.stem).upper()
                ts = int(row["timestamp_ms"])
                mark = float(row["open"])
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"{path}:{line}: invalid mark row") from exc
            if row_symbol != path.stem.upper():
                raise ValueError(f"{path}:{line}: symbol does not match filename")
            if ts <= 0 or not math.isfinite(mark) or mark <= 0:
                raise ValueError(f"{path}:{line}: invalid mark timestamp/price")
            if ts in timestamps:
                raise ValueError(f"{path}:{line}: duplicate mark timestamp {ts}")
            timestamps.add(ts)
    return timestamps


def validate_coverage(
    funding_dir: str | Path,
    mark_dir: str | Path,
    required_symbols: Iterable[str] | None = None,
) -> dict:
    funding_root, mark_root = Path(funding_dir), Path(mark_dir)
    if not funding_root.is_dir() or not mark_root.is_dir():
        raise ValueError("funding_dir and mark_dir must both exist")
    funding_files = {p.stem.upper(): p for p in funding_root.glob("*.csv")}
    symbols = sorted({s.upper() for s in required_symbols} if required_symbols else funding_files)
    if not symbols:
        raise ValueError("no funding symbols found or requested")

    results = []
    failed = False
    for symbol in symbols:
        funding_path = funding_files.get(symbol)
        mark_path = mark_root / f"{symbol}.csv"
        if funding_path is None:
            results.append({"symbol": symbol, "status": "missing_funding_file"})
            failed = True
            continue
        if not mark_path.is_file():
            results.append({"symbol": symbol, "status": "missing_mark_file"})
            failed = True
            continue
        funding_ts = _read_funding(funding_path)
        mark_ts = _read_marks(mark_path)
        missing = sorted(funding_ts - mark_ts)
        row = {
            "symbol": symbol,
            "funding_events": len(funding_ts),
            "mark_candles": len(mark_ts),
            "matched_events": len(funding_ts) - len(missing),
            "missing_events": len(missing),
            "first_funding_ts": min(funding_ts) if funding_ts else None,
            "last_funding_ts": max(funding_ts) if funding_ts else None,
            "status": "ok" if funding_ts and not missing else "incomplete",
        }
        if not funding_ts or missing:
            failed = True
            row["missing_timestamps_sample"] = missing[:10]
        results.append(row)
    return {"ok": not failed, "symbols_checked": len(symbols), "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funding-dir", required=True)
    parser.add_argument("--mark-dir", required=True)
    parser.add_argument("--symbols", default=None,
                        help="Optional comma-separated required symbol list")
    args = parser.parse_args()
    required = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] if args.symbols else None
    report = validate_coverage(args.funding_dir, args.mark_dir, required)
    print(json.dumps(report, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
