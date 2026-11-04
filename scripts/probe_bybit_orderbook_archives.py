#!/usr/bin/env python3
"""Probe Bybit public historical order-book archive URLs without downloading archives.

Only sends HEAD and a byte-range GET. If a server ignores Range and returns 200,
the response body is not read. The report contains no credentials or private data.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS = ["RAYUSDT", "PUMPUSDT", "TAOUSDT", "AAVEUSDT", "CAKEUSDT", "DASHUSDT", "HBARUSDT", "ENAUSDT", "GMXUSDT", "ONDOUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT", "SUIUSDT", "1000PEPEUSDT"]
URLS = [
    f"https://quote-saver.bycsi.com/orderbook/linear/{symbol}/{date}_{symbol}_{depth}.data.zip"
    for date, depth in (("2024-12-01", "ob500"), ("2025-09-02", "ob200"), ("2026-09-02", "ob200"))
    for symbol in SYMBOLS
]

def request_once(url: str, method: str) -> dict:
    headers = {"User-Agent": "bybit-orderbook-archive-probe/1.0"}
    if method == "GET":
        headers["Range"] = "bytes=0-4095"
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            result = {
                "status": response.status,
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type"),
                "content_length": response.headers.get("Content-Length"),
                "content_range": response.headers.get("Content-Range"),
                "accept_ranges": response.headers.get("Accept-Ranges"),
                "server": response.headers.get("Server"),
                "bytes_read": 0,
            }
            # Read only a single byte when the server explicitly honours Range.
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
            "accept_ranges": exc.headers.get("Accept-Ranges"),
            "server": exc.headers.get("Server"),
            "error": str(exc),
            "bytes_read": 0,
        }
    except Exception as exc:  # network and TLS errors are part of the probe result
        return {"error": f"{type(exc).__name__}: {exc}", "bytes_read": 0}

def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "HEAD + bounded Range GET; no archive body download",
        "results": [],
    }
    for url in URLS:
        head = request_once(url, "HEAD")
        ranged = request_once(url, "GET") if head.get("status") == 200 else {
            "status": "skipped_after_head_failure", "bytes_read": 0
        }
        report["results"].append({"url": url, "head": head, "range_get": ranged})
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "bybit_orderbook_archive_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    reachable = sum(
        1 for item in report["results"]
        if item["range_get"].get("status") == 206
        and item["range_get"].get("bytes_read") == 1
    )
    print(f"\nRange-capable archives: {reachable}/{len(URLS)}")
    return 0 if reachable else 1

if __name__ == "__main__":
    raise SystemExit(main())
