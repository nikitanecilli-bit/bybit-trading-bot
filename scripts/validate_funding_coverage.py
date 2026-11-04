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


def _read_trade_klines(path: Path) -> set[int]:
    timestamps: set[int] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp_ms", "open", "high", "low", "close", "volume", "turnover"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path}: required trade kline columns are missing")
        for line, row in enumerate(reader, start=2):
            try:
                row_symbol = str(row.get("symbol") or path.stem).upper()
                ts = int(row["timestamp_ms"])
                o, h, low, c = (float(row[key]) for key in ("open", "high", "low", "close"))
                volume, turnover = float(row["volume"]), float(row["turnover"])
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"{path}:{line}: invalid trade kline row") from exc
            if row_symbol != path.stem.upper():
                raise ValueError(f"{path}:{line}: symbol does not match filename")
            if (ts <= 0 or not all(math.isfinite(x) and x > 0 for x in (o,h,low,c))
                    or not all(math.isfinite(x) and x >= 0 for x in (volume,turnover))
                    or h < max(o,low,c) or low > min(o,h,c)):
                raise ValueError(f"{path}:{line}: invalid trade OHLCV values")
            if ts in timestamps:
                raise ValueError(f"{path}:{line}: duplicate trade kline timestamp {ts}")
            timestamps.add(ts)
    return timestamps


def validate_coverage(
    funding_dir: str | Path,
    mark_dir: str | Path,
    required_symbols: Iterable[str] | None = None,
    trade_kline_dir: str | Path | None = None,
) -> dict:
    funding_root, mark_root = Path(funding_dir), Path(mark_dir)
    trade_root = Path(trade_kline_dir) if trade_kline_dir is not None else None
    if not funding_root.is_dir() or not mark_root.is_dir() or (trade_root is not None and not trade_root.is_dir()):
        raise ValueError("funding_dir, mark_dir and optional trade_kline_dir must exist")
    funding_files = {p.stem.upper(): p for p in funding_root.glob("*.csv")}
    symbols = sorted({s.upper() for s in required_symbols} if required_symbols else funding_files)
    if not symbols:
        raise ValueError("no funding symbols found or requested")

    results = []
    failed = False
    for symbol in symbols:
        funding_path = funding_files.get(symbol)
        mark_path = mark_root / f"{symbol}.csv"
        trade_path = trade_root / f"{symbol}.csv" if trade_root is not None else None
        if funding_path is None:
            results.append({"symbol": symbol, "status": "missing_funding_file"})
            failed = True
            continue
        if not mark_path.is_file():
            results.append({"symbol": symbol, "status": "missing_mark_file"})
            failed = True
            continue
        if trade_path is not None and not trade_path.is_file():
            results.append({"symbol": symbol, "status": "missing_trade_kline_file"})
            failed = True
            continue
        funding_ts = _read_funding(funding_path)
        mark_ts = _read_marks(mark_path)
        trade_ts = _read_trade_klines(trade_path) if trade_path is not None else None
        missing = sorted(funding_ts - mark_ts)
        trade_mark_missing = set()
        unexpected_extra_marks = set()
        terminal_boundary_marks = set()
        if trade_ts is not None:
            trade_mark_missing = trade_ts - mark_ts
            extra_marks = mark_ts - trade_ts
            ordered_trade_ts = sorted(trade_ts)
            if len(ordered_trade_ts) >= 2:
                steps = {
                    right - left
                    for left, right in zip(ordered_trade_ts, ordered_trade_ts[1:])
                }
                if len(steps) == 1:
                    terminal_boundary = ordered_trade_ts[-1] + next(iter(steps))
                    terminal_boundary_marks = extra_marks & {terminal_boundary}
            # One extra Mark candle is permitted only at the exact close
            # boundary after the final trade H1 candle. It supplies the
            # settlement mark at that instant without extending trade OHLCV.
            unexpected_extra_marks = extra_marks - terminal_boundary_marks
        trade_mark_mismatch = sorted(trade_mark_missing | unexpected_extra_marks)
        row = {
            "symbol": symbol,
            "funding_events": len(funding_ts),
            "mark_candles": len(mark_ts),
            "matched_events": len(funding_ts) - len(missing),
            "missing_events": len(missing),
            "trade_candles": len(trade_ts) if trade_ts is not None else None,
            "trade_mark_timestamp_mismatch": len(trade_mark_mismatch),
            "terminal_boundary_mark_candles": len(terminal_boundary_marks),
            "first_funding_ts": min(funding_ts) if funding_ts else None,
            "last_funding_ts": max(funding_ts) if funding_ts else None,
            "status": "ok" if funding_ts and not missing and not trade_mark_mismatch else "incomplete",
        }
        if not funding_ts or missing or trade_mark_mismatch:
            failed = True
            row["missing_timestamps_sample"] = missing[:10]
            if trade_mark_mismatch:
                row["trade_mark_mismatch_sample"] = trade_mark_mismatch[:10]
        results.append(row)
    return {"ok": not failed, "symbols_checked": len(symbols), "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funding-dir", required=True)
    parser.add_argument("--mark-dir", required=True)
    parser.add_argument("--trade-kline-dir", default=None,
                        help="Optional Bybit trade OHLCV directory; timestamps must match mark candles")
    parser.add_argument("--symbols", default=None,
                        help="Optional comma-separated required symbol list")
    args = parser.parse_args()
    required = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] if args.symbols else None
    report = validate_coverage(args.funding_dir, args.mark_dir, required, args.trade_kline_dir)
    print(json.dumps(report, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
