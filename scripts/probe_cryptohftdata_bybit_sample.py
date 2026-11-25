#!/usr/bin/env python3
"""Bounded public CryptoHFTData endpoint probe for paired Bybit files."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATE = "2026-11-01"
HOUR = "12"
SYMBOL = "BTCUSDT"
DATASETS = ("trades", "orderbook", "mark_price")
BASES = ("https://api.cryptohftdata.com/download",
         "https://api.cryptohftdata.com/v1/download")


def probe(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "bybit-cryptohftdata-sample-probe/1.0",
            "Range": "bytes=0-4095",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = {
                "status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "content_range": response.headers.get("Content-Range"),
                "content_length": response.headers.get("Content-Length"),
                "accept_ranges": response.headers.get("Accept-Ranges"),
                "bytes_read": 0,
            }
            if response.status == 206:
                result["bytes_read"] = len(response.read(1))
            return result
    except urllib.error.HTTPError as exc:
        body = exc.read(1024).decode("utf-8", errors="replace")
        return {"status": exc.code, "content_type": exc.headers.get("Content-Type"),
                "error": str(exc), "body_preview": body, "bytes_read": 0}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "bytes_read": 0}


def main() -> int:
    results = []
    for base in BASES:
        for dataset in DATASETS:
            file_path = f"bybit/{DATE}/{HOUR}/{SYMBOL}_{dataset}.parquet"
            url = base + "?" + urllib.parse.urlencode({"file": file_path})
            results.append({"base": base, "dataset": dataset, "file": file_path,
                            "url": url, "probe": probe(url)})
    valid_bases = []
    for base in BASES:
        subset = [item for item in results if item["base"] == base]
        if all(item["probe"].get("status") == 206
               and item["probe"].get("bytes_read") == 1 for item in subset):
            valid_bases.append(base)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "CryptoHFTData",
        "date": DATE,
        "hour_utc": HOUR,
        "symbol": SYMBOL,
        "scope": "GET Range probe only; no archive body downloaded",
        "results": results,
        "base_urls_with_all_three_files": valid_bases,
    }
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "cryptohftdata_bybit_probe.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if valid_bases else 1


if __name__ == "__main__":
    raise SystemExit(main())
