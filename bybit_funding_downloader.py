#!/usr/bin/env python3
"""Download public Bybit V5 funding history for reproducible backtests.

No API key is required. The tool downloads settled funding rates only; it does
not itself apply funding to PnL. See the report/engine integration before using
any backtest result as funding-adjusted.
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

BASE_URL = "https://api.bybit.com/v5/market/funding/history"
MAX_LIMIT = 200


def _request_page(symbol: str, start_ms: int, end_ms: int, limit: int = MAX_LIMIT,
                  timeout: float = 20.0) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({
        "category": "linear",
        "symbol": symbol.upper(),
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit,
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
        raise ValueError("Unexpected Bybit funding-history response shape")
    return result["list"]


def fetch_funding_history(symbol: str, start_ms: int, end_ms: int,
                          pause_seconds: float = 0.1) -> list[dict[str, Any]]:
    """Fetch all funding settlements in [start_ms, end_ms], deduplicated by timestamp."""
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
        page_ts = []
        for item in page:
            try:
                ts = int(item["fundingRateTimestamp"])
                rate = float(item["fundingRate"])
                row_symbol = str(item["symbol"]).upper()
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"Invalid funding record: {item!r}") from exc
            if row_symbol != symbol:
                raise ValueError(f"API returned unexpected symbol {row_symbol!r}")
            if ts <= 0 or not math.isfinite(rate):
                raise ValueError(f"Invalid funding timestamp/rate: {item!r}")
            if start_ms <= ts <= end_ms:
                by_ts[ts] = {
                    "symbol": symbol,
                    "funding_timestamp_ms": ts,
                    "funding_time_utc": datetime.fromtimestamp(
                        ts / 1000, tz=timezone.utc
                    ).isoformat().replace("+00:00", "Z"),
                    "funding_rate": rate,
                }
                page_ts.append(ts)
        if not page_ts:
            break
        next_end = min(page_ts) - 1
        if next_end >= cursor_end:
            raise RuntimeError("Funding pagination did not move backwards; aborting")
        cursor_end = next_end
        if cursor_end >= start_ms and pause_seconds:
            time.sleep(pause_seconds)
    return [by_ts[ts] for ts in sorted(by_ts)]


def write_csv(rows: list[dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fields = ["symbol", "funding_timestamp_ms", "funding_time_utc", "funding_rate"]
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

    rows = fetch_funding_history(args.symbol, args.start_ms, args.end_ms, args.pause)
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} settled funding records to {args.output}")
    if not rows:
        print("WARNING: no funding rows returned; do not silently treat missing data as zero funding.")


if __name__ == "__main__":
    main()
