#!/usr/bin/env python3
"""Bounded reachability probe for public Tardis Bybit monthly CSV samples.

Sends HEAD and a one-byte Range GET only. It never downloads archive bodies.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SAMPLES = (
    ("2026-11-01", "BTCUSDT"),
    ("2026-11-01", "BTCUSD"),
    ("2020-01-01", "BTCUSD"),  # exact historical sample linked from Tardis docs
)
DATASETS = ("trades", "incremental_book_L2")
BASE = "https://datasets.tardis.dev/v1/bybit"


def request_once(url: str, method: str) -> dict:
    headers = {"User-Agent": "bybit-tardis-sample-probe/1.0"}
    if method == "GET":
        headers["Range"] = "bytes=0-4095"
    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = {
                "status": response.status,
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type"),
                "content_length": response.headers.get("Content-Length"),
                "content_range": response.headers.get("Content-Range"),
                "accept_ranges": response.headers.get("Accept-Ranges"),
                "bytes_read": 0,
            }
            if method == "GET" and response.status == 206:
                result["bytes_read"] = len(response.read(1))
            return result
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "final_url": exc.geturl(),
            "content_type": exc.headers.get("Content-Type"),
            "content_length": exc.headers.get("Content-Length"),
            "content_range": exc.headers.get("Content-Range"),
            "error": str(exc),
            "bytes_read": 0,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "bytes_read": 0}


def main() -> int:
    results = []
    for date, symbol in SAMPLES:
        for dataset in DATASETS:
            year, month, day = date.split("-")
            url = f"{BASE}/{dataset}/{year}/{month}/{day}/{symbol}.csv.gz"
            head = request_once(url, "HEAD")
            ranged = request_once(url, "GET")  # HEAD support is not assumed by the dataset host
            results.append({"date": date, "symbol": symbol, "dataset": dataset, "url": url,
                            "head": head, "range_get": ranged})
    pairs = {}
    for item in results:
        pairs.setdefault(item["date"] + ":" + item["symbol"], {})[item["dataset"]] = (
            item["range_get"].get("status") == 206
            and item["range_get"].get("bytes_read") == 1
        )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Tardis.dev",
        "samples": [{"date": date, "symbol": symbol} for date, symbol in SAMPLES],
        "scope": "HEAD + one-byte Range GET; no archive body downloaded",
        "results": results,
        "symbols_with_both_feeds": sorted(
            sample for sample, feeds in pairs.items()
            if all(feeds.get(dataset, False) for dataset in DATASETS)
        ),
    }
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "tardis_bybit_probe.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["symbols_with_both_feeds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
