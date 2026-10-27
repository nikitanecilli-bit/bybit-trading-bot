#!/usr/bin/env python3
"""Convert bybit_downloader.py kline CSVs into the v14 research engine format.

Input:  <SYMBOL>_<category>_kline_<interval>.csv
Output: <SYMBOL>.csv with ts,open,high,low,close,volume

This adapter does not fill missing candles or alter prices. It rejects duplicate
timestamps, invalid OHLCV values, and irregular intervals so bad data cannot be
silently passed into the backtest.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Iterable

REQUIRED_INPUT = {"timestamp", "open", "high", "low", "close", "volume"}
OUTPUT_FIELDS = ["ts", "open", "high", "low", "close", "volume"]


def convert_file(source: Path, destination: Path, expected_step_ms: int | None) -> dict:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not REQUIRED_INPUT.issubset(reader.fieldnames):
            raise ValueError(
                f"{source}: required columns are {sorted(REQUIRED_INPUT)}; "
                f"found {reader.fieldnames}"
            )
        rows: list[dict[str, float | int]] = []
        for line_no, row in enumerate(reader, start=2):
            try:
                ts_raw = float(row["timestamp"])
                values = {key: float(row[key]) for key in ("open", "high", "low", "close", "volume")}
                if not math.isfinite(ts_raw) or not ts_raw.is_integer() or ts_raw <= 0:
                    raise ValueError("timestamp must be a positive integer in milliseconds")
                if not all(math.isfinite(value) for value in values.values()):
                    raise ValueError("NaN/Inf value")
                op, hi, lo, cl, vol = (values[k] for k in ("open", "high", "low", "close", "volume"))
                if min(op, hi, lo, cl) <= 0:
                    raise ValueError("OHLC prices must be positive")
                if vol < 0:
                    raise ValueError("volume cannot be negative")
                if hi < max(op, cl, lo) or lo > min(op, cl, hi):
                    raise ValueError("invalid OHLC boundaries")
                rows.append({"ts": int(ts_raw), **values})
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"{source}:{line_no}: invalid candle: {exc}") from exc

    rows.sort(key=lambda item: int(item["ts"]))
    timestamps = [int(row["ts"]) for row in rows]
    if len(rows) < 2:
        raise ValueError(f"{source}: need at least two candles")
    if len(set(timestamps)) != len(timestamps):
        raise ValueError(f"{source}: duplicate timestamps found")
    deltas = [b - a for a, b in zip(timestamps, timestamps[1:])]
    if any(delta <= 0 for delta in deltas):
        raise ValueError(f"{source}: timestamps are not strictly increasing")
    if len(set(deltas)) != 1:
        raise ValueError(f"{source}: irregular candle intervals: {sorted(set(deltas))[:8]}")
    actual_step = deltas[0]
    if expected_step_ms is not None and actual_step != expected_step_ms:
        raise ValueError(
            f"{source}: expected {expected_step_ms} ms interval, found {actual_step} ms"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "symbol": source.name.split("_", 1)[0],
        "rows": len(rows),
        "first_ts": timestamps[0],
        "last_ts": timestamps[-1],
        "step_ms": actual_step,
        "output": str(destination),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True, help="Downloader output directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for engine-ready CSVs")
    parser.add_argument("--symbols", nargs="*", help="Optional symbols, e.g. BTCUSDT ETHUSDT")
    parser.add_argument("--category", default="linear", choices=("linear", "inverse", "spot"))
    parser.add_argument("--interval", default="15", help="Bybit interval code: 1, 5, 15, 60, 240, D, etc.")
    args = parser.parse_args()

    interval_ms = {
        "1": 60_000, "3": 180_000, "5": 300_000, "15": 900_000,
        "30": 1_800_000, "60": 3_600_000, "120": 7_200_000,
        "240": 14_400_000, "360": 21_600_000, "720": 43_200_000,
        "D": 86_400_000,
    }
    expected_step = interval_ms.get(args.interval)
    if args.interval not in interval_ms and args.interval not in {"W", "M"}:
        parser.error(f"unsupported interval code: {args.interval}")

    if args.symbols:
        symbols = list(dict.fromkeys(symbol.upper() for symbol in args.symbols))
    else:
        suffix = f"_{args.category}_kline_{args.interval}.csv"
        symbols = sorted(
            path.name[:-len(suffix)]
            for path in args.input_dir.glob(f"*{suffix}")
            if path.name.endswith(suffix)
        )

    if not symbols:
        parser.error("no matching input files found")

    failures = 0
    for symbol in symbols:
        source = args.input_dir / f"{symbol}_{args.category}_kline_{args.interval}.csv"
        if not source.is_file():
            print(f"SKIP {symbol}: missing {source}")
            failures += 1
            continue
        try:
            result = convert_file(source, args.output_dir / f"{symbol}.csv", expected_step)
            print(
                f"OK {result['symbol']}: {result['rows']} candles, "
                f"{result['step_ms']} ms, {result['first_ts']}..{result['last_ts']} "
                f"-> {result['output']}"
            )
        except (OSError, ValueError, csv.Error) as exc:
            print(f"ERROR {symbol}: {exc}")
            failures += 1

    print(f"Finished: {len(symbols) - failures} converted, {failures} failed/skipped.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
