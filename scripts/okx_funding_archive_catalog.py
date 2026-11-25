#!/usr/bin/env python3
"""Read-only catalog probe for OKX monthly public funding archives.

This deliberately lists official archive URLs only. It does not download files.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

HOST = "https://www.okx.com"
ENDPOINT = "/api/v5/public/market-data-history"
OUT = Path("data/archives/okx/funding-catalog/BTC-USDT-SWAP")
UTC8 = timezone(timedelta(hours=8))


def ms_at_utc8_midnight(date_text: str) -> str:
    dt = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=UTC8)
    return str(int(dt.timestamp() * 1000))


def get_catalog(begin: str, end: str) -> tuple[bytes, dict]:
    params = {
        "module": "3",
        "instType": "SWAP",
        "instFamilyList": "BTC-USDT",
        "dateAggrType": "monthly",
        "begin": ms_at_utc8_midnight(begin),
        "end": ms_at_utc8_midnight(end),
    }
    url = HOST + ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "bounded-okx-public-funding-catalog/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read()
        status = response.status
        final_url = response.geturl()
    if not final_url.startswith(HOST + "/"):
        raise RuntimeError(f"Unexpected response host: {final_url}")
    payload = json.loads(body)
    if status != 200 or payload.get("code") != "0":
        raise RuntimeError(f"OKX response not successful: HTTP {status}, body={payload}")
    return body, {
        "request_url": url,
        "http_status": status,
        "okx_code": payload.get("code"),
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "payload": payload,
    }


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite non-empty output directory: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)

    # Ten inclusive UTC+8 calendar months: the archive interval immediately
    # preceding the three-month REST history window.
    body, result = get_catalog("2025-11-01", "2026-08-31")
    raw_path = OUT / "funding_catalog_2025-11_to_2026-08.json"
    raw_path.write_bytes(body)

    groups = []
    for item in result["payload"].get("data", []):
        for detail in item.get("details", []):
            if detail.get("instType") != "SWAP" or detail.get("instFamily") != "BTC-USDT":
                raise RuntimeError(f"Unexpected instrument group: {detail}")
            for file_item in detail.get("groupDetails", []):
                url = file_item.get("url", "")
                if not url.startswith("https://static.okx.com/"):
                    raise RuntimeError(f"Non-OKX archive URL returned: {url}")
                groups.append({
                    "filename": file_item.get("filename"),
                    "date_ts": file_item.get("dateTs"),
                    "size_mb": file_item.get("sizeMB"),
                    "url": url,
                })

    manifest = {
        "purpose": "Read-only discovery of official OKX monthly funding archive files; no archive file downloaded.",
        "exchange": "OKX",
        "instrument_family": "BTC-USDT",
        "instrument": "BTC-USDT-SWAP",
        "module": "3",
        "date_aggregation": "monthly",
        "requested_begin_date_utc8_inclusive": "2025-11-01",
        "requested_end_date_utc8_inclusive": "2026-08-31",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": HOST,
        "raw_file": raw_path.name,
        "raw_bytes": result["bytes"],
        "raw_sha256": result["sha256"],
        "request_url": result["request_url"],
        "http_status": result["http_status"],
        "okx_code": result["okx_code"],
        "total_size_mb_reported": result["payload"].get("data", [{}])[0].get("totalSizeMB") if result["payload"].get("data") else None,
        "archive_files": groups,
        "archive_file_count": len(groups),
        "limitations": [
            "This is a catalog probe only; no returned ZIP URL is fetched.",
            "A listed file is not accepted until downloaded and independently checked.",
            "OKX states historical backfill is in progress and availability varies by module, instrument, and period.",
            "This does not establish historical instrument specifications, risk tiers, fee tiers, or Bybit execution conditions.",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "CATALOG_CAPTURED",
        "archive_file_count": len(groups),
        "reported_total_size_mb": manifest["total_size_mb_reported"],
        "files": [g["filename"] for g in groups],
        "manifest": str(OUT / "manifest.json"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

# Trigger catalog workflow after its initial registration.
