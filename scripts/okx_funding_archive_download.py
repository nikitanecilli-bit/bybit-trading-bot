#!/usr/bin/env python3
"""Download and integrity-check only the 10 catalogued OKX BTC-USDT funding ZIPs."""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

HOST = "https://www.okx.com"
CDN_HOST = "static.okx.com"
ENDPOINT = "/api/v5/public/market-data-history"
OUT = Path("data/archives/okx/funding-monthly/BTC-USDT-SWAP")
UTC8 = timezone(timedelta(hours=8))
EXPECTED_MONTHS = [
    "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
    "2026-04", "2026-05", "2026-06", "2026-07", "2026-08",
]


def ms_at_utc8_midnight(date_text: str) -> str:
    dt = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=UTC8)
    return str(int(dt.timestamp() * 1000))


def request_bytes(url: str, allowed_host: str, timeout: int = 60) -> tuple[bytes, str, int]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "bounded-okx-public-funding-archive/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read()
        final_url = response.geturl()
        status = response.status
    parsed = urlparse(final_url)
    if parsed.scheme != "https" or parsed.hostname != allowed_host:
        raise RuntimeError(f"Unexpected redirect destination: {final_url}")
    if status != 200:
        raise RuntimeError(f"Unexpected HTTP status {status} for {url}")
    return body, final_url, status


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite non-empty output directory: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)

    params = {
        "module": "3",
        "instType": "SWAP",
        "instFamilyList": "BTC-USDT",
        "dateAggrType": "monthly",
        "begin": ms_at_utc8_midnight("2025-11-01"),
        "end": ms_at_utc8_midnight("2026-08-31"),
    }
    catalog_url = HOST + ENDPOINT + "?" + urllib.parse.urlencode(params)
    catalog_raw, catalog_final, _ = request_bytes(catalog_url, "www.okx.com", timeout=30)
    catalog = json.loads(catalog_raw)
    if catalog.get("code") != "0":
        raise RuntimeError(f"OKX catalog error: {catalog}")
    (OUT / "catalog_response.json").write_bytes(catalog_raw)

    files = []
    for item in catalog.get("data", []):
        for detail in item.get("details", []):
            if detail.get("instType") != "SWAP" or detail.get("instFamily") != "BTC-USDT":
                raise RuntimeError(f"Unexpected catalog group: {detail}")
            files.extend(detail.get("groupDetails", []))

    by_month = {}
    for item in files:
        filename = item.get("filename", "")
        month = filename.removesuffix(".zip").split("-")[-2] + "-" + filename.removesuffix(".zip").split("-")[-1]
        # Expected filename: BTC-USDT-SWAP-fundingrates-YYYY-MM.zip
        if not filename.startswith("BTC-USDT-SWAP-fundingrates-") or month not in EXPECTED_MONTHS:
            raise RuntimeError(f"Unexpected archive filename: {filename}")
        if month in by_month:
            raise RuntimeError(f"Duplicate monthly archive: {month}")
        url = item.get("url", "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != CDN_HOST:
            raise RuntimeError(f"Non-official OKX CDN URL: {url}")
        if not parsed.path.startswith("/cdn/okex/traderecords/swaprates/monthly/"):
            raise RuntimeError(f"Unexpected archive path: {url}")
        by_month[month] = item

    if sorted(by_month) != EXPECTED_MONTHS:
        raise RuntimeError(f"Monthly coverage mismatch. Expected {EXPECTED_MONTHS}; got {sorted(by_month)}")

    entries = []
    for index, month in enumerate(EXPECTED_MONTHS, start=1):
        item = by_month[month]
        filename = item["filename"]
        body, final_url, status = request_bytes(item["url"], CDN_HOST)
        path = OUT / filename
        path.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        try:
            with zipfile.ZipFile(path) as archive:
                bad_member = archive.testzip()
                if bad_member:
                    raise RuntimeError(f"ZIP CRC failure in {filename}: {bad_member}")
                members = []
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    if info.filename.startswith("/") or ".." in Path(info.filename).parts:
                        raise RuntimeError(f"Unsafe ZIP member path in {filename}: {info.filename}")
                    members.append({
                        "name": info.filename,
                        "bytes": info.file_size,
                        "compressed_bytes": info.compress_size,
                    })
        except zipfile.BadZipFile as exc:
            raise RuntimeError(f"Invalid ZIP archive {filename}: {exc}") from exc
        entries.append({
            "month": month,
            "filename": filename,
            "url": item["url"],
            "final_url": final_url,
            "http_status": status,
            "bytes": len(body),
            "sha256": digest,
            "zip_crc_check": "PASS",
            "members": members,
        })
        print(f"[{index}/{len(EXPECTED_MONTHS)}] {month}: {len(body)} bytes; ZIP CRC PASS")
        time.sleep(0.25)

    manifest = {
        "purpose": "Bounded acquisition of official OKX monthly BTC-USDT-SWAP funding archives.",
        "exchange": "OKX",
        "instrument": "BTC-USDT-SWAP",
        "instrument_family": "BTC-USDT",
        "module": "3",
        "date_aggregation": "monthly",
        "requested_begin_date_utc8_inclusive": "2025-11-01",
        "requested_end_date_utc8_inclusive": "2026-08-31",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_request_url": catalog_url,
        "catalog_final_url": catalog_final,
        "catalog_sha256": hashlib.sha256(catalog_raw).hexdigest(),
        "download_host": CDN_HOST,
        "archive_count": len(entries),
        "archives": entries,
        "limitations": [
            "This archive supplements the REST funding history; do not concatenate until row-level schema, timestamp coverage, duplicates, and overlap are audited.",
            "The request window is ten inclusive UTC+8 calendar months, as required by the official API limit.",
            "This does not establish historical instrument specifications, risk tiers, fee tiers, or Bybit execution conditions.",
            "No strategy, PnL, backtest, order, account endpoint, API key, proxy, or mirror is used.",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "ARCHIVES_DOWNLOADED_AND_ZIP_CHECKED",
        "archive_count": len(entries),
        "total_bytes": sum(x["bytes"] for x in entries),
        "manifest": str(OUT / "manifest.json"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

# Trigger the dedicated cloud capture after workflow registration.
