#!/usr/bin/env python3
"""Download Bybit V5 historical mark-price klines for funding settlement timestamps.

For linear perpetuals, funding timestamps usually align to minute boundaries.
The engine uses the open of the 1-minute mark-price candle whose start timestamp
matches the settlement timestamp. No API key is required.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

BASE_URL = "https://api.bybit.com/v5/market/mark-price-kline"
MAX_LIMIT = 1000


def _request_page(symbol: str, start_ms: int, end_ms: int, limit: int = MAX_LIMIT,
                  timeout: float = 20.0) -> list[list[Any]]:
    params = urllib.parse.urlencode({
        "category": "linear", "symbol": symbol.upper(), "interval": "1",
        "start": start_ms, "end": end_ms, "limit": limit,
    })
    req = urllib.request.Request(
        f"{BASE_URL}?{params}",
        headers={"User-Agent": "bybit-trading-bot-research/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("retCode") != 0:
        raise RuntimeError(
            f"Bybit API error {payload.get('retCode')}: {payload.get('retMsg', 'unknown error')}"
        )
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("list"), list):
        raise ValueError("Unexpected Bybit mark-price-kline response shape")
    return result["list"]


def fetch_mark_price_klines(symbol: str, start_ms: int, end_ms: int,
                            pause_seconds: float = 0.1) -> list[dict[str, Any]]:
    """Fetch 1-minute mark candles in [start_ms, end_ms], sorted and deduplicated."""
    symbol = symbol.strip().upper()
    if not symbol or not symbol.endswith("USDT") or not symbol.isalnum():
        raise ValueError("symbol must be a USDT linear perpetual symbol, e.g. BTCUSDT")
    if start_ms <= 0 or end_ms < start_ms:
        raise ValueError("timestamps must be positive and start_ms <= end_ms")
    if pause_seconds < 0:
        raise ValueError("pause_seconds cannot be negative")

    by_ts: dict[int, dict[str, Any]] = {}
    cursor_end = end_ms
    while cursor_end >= start_ms:
        page = _request_page(symbol, start_ms, cursor_end)
        if not page:
            break
        page_ts: list[int] = []
        for item in page:
            if not isinstance(item, (list, tuple)) or len(item) < 5:
                raise ValueError(f"Invalid mark-price kline: {item!r}")
            try:
                ts = int(item[0])
                op, high, low, close = (float(item[i]) for i in range(1, 5))
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"Invalid mark-price kline: {item!r}") from exc
            if ts <= 0 or not all(math.isfinite(x) and x > 0 for x in (op, high, low, close)):
                raise ValueError(f"Invalid mark-price timestamp/prices: {item!r}")
            if high < max(op, low, close) or low > min(op, high, close):
                raise ValueError(f"Invalid mark-price OHLC boundaries: {item!r}")
            if start_ms <= ts <= cursor_end:
                by_ts[ts] = {
                    "symbol": symbol,
                    "timestamp_ms": ts,
                    "time_utc": datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                    .isoformat().replace("+00:00", "Z"),
                    "open": op, "high": high, "low": low, "close": close,
                }
                page_ts.append(ts)
        if not page_ts:
            break
        next_end = min(page_ts) - 1
        if next_end >= cursor_end:
            raise RuntimeError("Mark-price pagination did not move backwards; aborting")
        cursor_end = next_end
        if cursor_end >= start_ms and pause_seconds:
            time.sleep(pause_seconds)
    return [by_ts[ts] for ts in sorted(by_ts)]


def write_csv(rows: list[dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fields = ["symbol", "timestamp_ms", "time_utc", "open", "high", "low", "close"]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="USDT linear perpetual symbol, e.g. BTCUSDT")
    parser.add_argument("--start-ms", required=True, type=int, help="Inclusive UTC epoch milliseconds")
    parser.add_argument("--end-ms", required=True, type=int, help="Inclusive UTC epoch milliseconds")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument("--pause", type=float, default=0.1, help="Pause between API pages in seconds")
    args = parser.parse_args()

    rows = fetch_mark_price_klines(args.symbol, args.start_ms, args.end_ms, args.pause)
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} mark-price candles to {args.output}")
    if not rows:
        print("WARNING: no mark-price rows returned; funding-adjusted backtests will fail on missing timestamps.")


if __name__ == "__main__":
    main()
