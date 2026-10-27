#!/usr/bin/env python3
"""Convert Bybit downloader kline CSVs into the research engine's strict CSV format.

Input:  <SYMBOL>_<category>_kline_<interval>.csv
Output: <SYMBOL>.csv with ts,open,high,low,close,volume

Only closed candles should be supplied (the downloader already drops the current bar).
The engine requires every symbol to have the exact same timestamps and no interval gaps;
this adapter checks that contract rather than silently repairing bad data.
"""
import argparse
import csv
import math
from pathlib import Path

INTERVAL_MS = {
    "1": 60_000, "3": 180_000, "5": 300_000, "15": 900_000,
    "30": 1_800_000, "60": 3_600_000, "120": 7_200_000,
    "240": 14_400_000, "360": 21_600_000, "720": 43_200_000,
    "D": 86_400_000,
}


def read_klines(path: Path, interval_ms: int):
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    rows = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path}: required input columns: {sorted(required)}")
        for line_no, row in enumerate(reader, start=2):
            try:
                raw_ts = float(row["timestamp"])
                values = [float(row[k]) for k in ("open", "high", "low", "close", "volume")]
                if not math.isfinite(raw_ts) or not raw_ts.is_integer() or raw_ts <= 0:
                    raise ValueError("timestamp must be a positive integer in milliseconds")
                if not all(math.isfinite(v) for v in values):
                    raise ValueError("NaN/Inf OHLCV value")
                ts = int(raw_ts)
                op, hi, lo, cl, vol = values
                if min(op, hi, lo, cl) <= 0 or vol < 0:
                    raise ValueError("prices must be positive and volume non-negative")
                if hi < max(op, cl, lo) or lo > min(op, cl, hi):
                    raise ValueError("invalid OHLC bounds")
                if ts in rows:
                    raise ValueError(f"duplicate timestamp {ts}")
                rows[ts] = (op, hi, lo, cl, vol)
            except (TypeError, KeyError, ValueError, OverflowError) as exc:
                raise ValueError(f"{path}:{line_no}: invalid candle: {exc}") from exc
    if len(rows) < 2:
        raise ValueError(f"{path}: need at least two candles")
    timestamps = sorted(rows)
    deltas = [b - a for a, b in zip(timestamps, timestamps[1:])]
    if any(delta != interval_ms for delta in deltas):
        bad = [(timestamps[i], timestamps[i + 1], timestamps[i + 1] - timestamps[i])
               for i in range(len(timestamps) - 1) if timestamps[i + 1] - timestamps[i] != interval_ms]
        raise ValueError(
            f"{path}: missing/irregular candles for interval {interval_ms} ms; "
            f"first issues (previous_ts,next_ts,delta_ms): {bad[:5]}"
        )
    return rows


def adapt(symbols, category, interval, input_dir, output_dir, start_ms=None, end_ms=None):
    if len(set(symbols)) != len(symbols):
        raise ValueError("duplicate symbols supplied")
    interval_ms = INTERVAL_MS[interval]
    datasets = {}
    for symbol in symbols:
        path = input_dir / f"{symbol}_{category}_kline_{interval}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"missing kline file: {path}")
        datasets[symbol] = read_klines(path, interval_ms)

    common = set.intersection(*(set(rows) for rows in datasets.values()))
    if start_ms is not None:
        common = {ts for ts in common if ts >= start_ms}
    if end_ms is not None:
        common = {ts for ts in common if ts <= end_ms}
    common_ts = sorted(common)
    if len(common_ts) < 2:
        raise ValueError("symbols have fewer than two common timestamps in the selected date range")
    if any(b - a != interval_ms for a, b in zip(common_ts, common_ts[1:])):
        raise ValueError("common timestamp intersection contains gaps; refusing to produce engine input")

    output_dir.mkdir(parents=True, exist_ok=True)
    for symbol, rows in datasets.items():
        path = output_dir / f"{symbol}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ts", "open", "high", "low", "close", "volume"])
            for ts in common_ts:
                writer.writerow([ts, *rows[ts]])
        print(f"{symbol}: {len(common_ts)} aligned candles -> {path}; "
              f"excluded {len(rows) - len(common_ts)} non-common/out-of-range candles")
    print(f"OK: {len(symbols)} symbols aligned on {len(common_ts)} bars "
          f"({common_ts[0]}..{common_ts[-1]} UTC milliseconds)")
    return len(common_ts)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbols", nargs="+", required=True, help="symbols to include, e.g. BTCUSDT ETHUSDT")
    p.add_argument("--category", default="linear", choices=["linear", "inverse", "spot"])
    p.add_argument("--interval", required=True, choices=list(INTERVAL_MS))
    p.add_argument("--input-dir", type=Path, default=Path("data"))
    p.add_argument("--output-dir", type=Path, default=Path("engine_data"))
    p.add_argument("--start", help="optional inclusive UTC date YYYY-MM-DD")
    p.add_argument("--end", help="optional inclusive UTC date YYYY-MM-DD")
    args = p.parse_args()

    from datetime import datetime, timezone
    def parse_date(value):
        if value is None:
            return None
        return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    start_ms, end_ms = parse_date(args.start), parse_date(args.end)
    if start_ms is not None and end_ms is not None and start_ms > end_ms:
        p.error("--start must not be after --end")
    adapt([s.upper() for s in args.symbols], args.category, args.interval,
          args.input_dir, args.output_dir, start_ms, end_ms)


if __name__ == "__main__":
    main()
