#!/usr/bin/env python3
"""Capture, merge, and audit one year of official OKX BTC-USDT-SWAP funding data."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

HOST = "https://www.okx.com"
CDN_HOST = "static.okx.com"
ENDPOINT = "/api/v5/public/market-data-history"
FUNDING_HISTORY_ENDPOINT = "/api/v5/public/funding-rate-history"
OUT = Path("data/archives/okx/funding-monthly/BTC-USDT-SWAP")
UTC8 = timezone(timedelta(hours=8))
EXPECTED_MONTHS = [
    "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
    "2026-04", "2026-05", "2026-06", "2026-07", "2026-08",
]
START_UTC = "2025-11-25T08:00:00Z"
END_UTC = "2026-11-25T08:00:00Z"
START_MS = 1764057600000
END_MS = 1795593600000
EIGHT_HOURS_MS = 28_800_000


def request_bytes(url: str, allowed_host: str, timeout: int = 60) -> tuple[bytes, str, int]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "bounded-okx-public-funding-archive/1.1"},
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


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite non-empty output directory: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)

    catalog_params = {
        "module": "3",
        "instType": "SWAP",
        "instFamilyList": "BTC-USDT",
        "dateAggrType": "monthly",
        "begin": "1761926400000",  # 2025-11-01 00:00 UTC+8
        "end": "1788105600000",    # 2026-08-31 00:00 UTC+8, inclusive date
    }
    catalog_url = HOST + ENDPOINT + "?" + urllib.parse.urlencode(catalog_params)
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
        stem = filename.removesuffix(".zip")
        month = "-".join(stem.split("-")[-2:])
        if not filename.startswith("BTC-USDT-SWAP-fundingrates-") or month not in EXPECTED_MONTHS:
            raise RuntimeError(f"Unexpected archive filename: {filename}")
        if month in by_month:
            raise RuntimeError(f"Duplicate monthly archive: {month}")
        parsed = urlparse(item.get("url", ""))
        if parsed.scheme != "https" or parsed.hostname != CDN_HOST:
            raise RuntimeError(f"Non-official OKX CDN URL: {item.get('url')}")
        if not parsed.path.startswith("/cdn/okex/traderecords/swaprates/monthly/"):
            raise RuntimeError(f"Unexpected archive path: {item.get('url')}")
        by_month[month] = item

    if sorted(by_month) != EXPECTED_MONTHS:
        raise RuntimeError(f"Monthly coverage mismatch. Expected {EXPECTED_MONTHS}; got {sorted(by_month)}")

    archive_rows: dict[int, str] = {}
    archive_files = []
    for index, month in enumerate(EXPECTED_MONTHS, start=1):
        item = by_month[month]
        filename = item["filename"]
        body, final_url, status = request_bytes(item["url"], CDN_HOST)
        path = OUT / filename
        path.write_bytes(body)
        digest = sha256(body)
        try:
            with zipfile.ZipFile(path) as archive:
                bad_member = archive.testzip()
                if bad_member:
                    raise RuntimeError(f"ZIP CRC failure in {filename}: {bad_member}")
                csv_members = [x for x in archive.namelist() if x.lower().endswith(".csv")]
                if len(csv_members) != 1:
                    raise RuntimeError(f"Expected one CSV in {filename}; got {csv_members}")
                csv_bytes = archive.read(csv_members[0])
                parsed_rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
                if not parsed_rows or set(parsed_rows[0]) != {"instrument_name", "funding_rate", "funding_time"}:
                    raise RuntimeError(f"Unexpected CSV schema in {filename}: {list(parsed_rows[0]) if parsed_rows else []}")
                for row in parsed_rows:
                    if row["instrument_name"] != "BTC-USDT-SWAP":
                        raise RuntimeError(f"Unexpected instrument in {filename}: {row['instrument_name']}")
                    ts = int(row["funding_time"])
                    rate = row["funding_rate"]
                    if ts in archive_rows:
                        raise RuntimeError(f"Duplicate archive funding timestamp: {ts}")
                    Decimal(rate)
                    archive_rows[ts] = rate
                members = [{
                    "name": info.filename,
                    "bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                } for info in archive.infolist() if not info.is_dir()]
        except zipfile.BadZipFile as exc:
            raise RuntimeError(f"Invalid ZIP archive {filename}: {exc}") from exc
        archive_files.append({
            "month": month,
            "filename": filename,
            "url": item["url"],
            "final_url": final_url,
            "http_status": status,
            "bytes": len(body),
            "sha256": digest,
            "zip_crc_check": "PASS",
            "row_count": len(parsed_rows),
            "members": members,
        })
        print(f"[archive {index}/{len(EXPECTED_MONTHS)}] {month}: {len(parsed_rows)} rows; ZIP CRC PASS")
        time.sleep(0.25)

    # The REST history endpoint provides the recent window and metadata fields.
    rest_url = HOST + FUNDING_HISTORY_ENDPOINT + "?" + urllib.parse.urlencode({
        "instId": "BTC-USDT-SWAP",
        "limit": "400",
    })
    rest_raw, rest_final, rest_status = request_bytes(rest_url, "www.okx.com", timeout=30)
    rest_payload = json.loads(rest_raw)
    if rest_payload.get("code") != "0":
        raise RuntimeError(f"OKX funding history error: {rest_payload}")
    (OUT / "funding_rate_history_rest.json").write_bytes(rest_raw)

    rest_rows: dict[int, dict] = {}
    for row in rest_payload.get("data", []):
        ts = int(row["fundingTime"])
        if ts in rest_rows:
            raise RuntimeError(f"Duplicate REST funding timestamp: {ts}")
        rest_rows[ts] = row
        Decimal(row["realizedRate"])
        Decimal(row["fundingRate"])

    # Merge only the exact one-year half-open interval requested by the H1 archive.
    timestamps = sorted(
        {t for t in archive_rows if START_MS <= t < END_MS}
        | {t for t in rest_rows if START_MS <= t < END_MS}
    )
    expected = list(range(START_MS, END_MS, EIGHT_HOURS_MS))
    if timestamps != expected:
        missing = sorted(set(expected) - set(timestamps))
        extra = sorted(set(timestamps) - set(expected))
        raise RuntimeError(
            f"Funding grid mismatch: got {len(timestamps)} rows, expected {len(expected)}; "
            f"missing={missing[:5]}, extra={extra[:5]}"
        )

    overlap = sorted(set(archive_rows) & set(rest_rows))
    if not overlap:
        raise RuntimeError("No archive/REST overlap available for semantic cross-check")
    mismatches = []
    for ts in overlap:
        if Decimal(archive_rows[ts]) != Decimal(rest_rows[ts]["realizedRate"]):
            mismatches.append({
                "funding_time_ms": ts,
                "archive_funding_rate": archive_rows[ts],
                "rest_realized_rate": rest_rows[ts]["realizedRate"],
            })
    if mismatches:
        raise RuntimeError(f"Archive vs REST realizedRate mismatch: {mismatches[:5]}")

    merged_path = OUT / "funding_history_1y.csv"
    fields = [
        "funding_time_ms", "funding_time_utc", "selected_rate", "selected_rate_source",
        "archive_funding_rate", "rest_funding_rate", "rest_realized_rate",
        "formula_type", "method", "archive_rest_overlap_match",
    ]
    with merged_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for ts in timestamps:
            archive_rate = archive_rows.get(ts, "")
            rest = rest_rows.get(ts)
            if rest:
                selected_rate = rest["realizedRate"]
                selected_source = "rest_realizedRate"
                rest_funding_rate = rest.get("fundingRate", "")
                realized_rate = rest.get("realizedRate", "")
                formula_type = rest.get("formulaType", "")
                method = rest.get("method", "")
                overlap_match = str(bool(archive_rate and Decimal(archive_rate) == Decimal(realized_rate))).lower() if archive_rate else ""
            else:
                selected_rate = archive_rate
                selected_source = "monthly_archive_funding_rate"
                rest_funding_rate = ""
                realized_rate = ""
                formula_type = ""
                method = ""
                overlap_match = ""
            writer.writerow({
                "funding_time_ms": ts,
                "funding_time_utc": datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
                "selected_rate": selected_rate,
                "selected_rate_source": selected_source,
                "archive_funding_rate": archive_rate,
                "rest_funding_rate": rest_funding_rate,
                "rest_realized_rate": realized_rate,
                "formula_type": formula_type,
                "method": method,
                "archive_rest_overlap_match": overlap_match,
            })

    merged_bytes = merged_path.read_bytes()
    rest_in_range = [t for t in rest_rows if START_MS <= t < END_MS]
    archive_in_range = [t for t in archive_rows if START_MS <= t < END_MS]
    intervals = [b - a for a, b in zip(timestamps, timestamps[1:])]
    formula_types = sorted({r.get("formulaType", "") for r in rest_rows.values()})
    methods = sorted({r.get("method", "") for r in rest_rows.values()})

    manifest = {
        "purpose": "One-year realized-funding event archive assembled from official OKX monthly public files plus public REST overlap/recent history.",
        "exchange": "OKX",
        "instrument": "BTC-USDT-SWAP",
        "requested_start_utc_inclusive": START_UTC,
        "requested_end_utc_exclusive": END_UTC,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "catalog": {
            "request_url": catalog_url,
            "final_url": catalog_final,
            "http_status": 200,
            "sha256": sha256(catalog_raw),
            "bytes": len(catalog_raw),
        },
        "monthly_archives": archive_files,
        "monthly_archive_rows_total": len(archive_rows),
        "monthly_archive_rows_in_requested_interval": len(archive_in_range),
        "rest_history": {
            "request_url": rest_url,
            "final_url": rest_final,
            "http_status": rest_status,
            "sha256": sha256(rest_raw),
            "bytes": len(rest_raw),
            "rows_total": len(rest_rows),
            "rows_in_requested_interval": len(rest_in_range),
            "oldest_event_utc": datetime.fromtimestamp(min(rest_rows) / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
            "newest_event_utc": datetime.fromtimestamp(max(rest_rows) / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
            "formula_types_observed": formula_types,
            "methods_observed": methods,
        },
        "merge": {
            "rows": len(timestamps),
            "unique_timestamps": len(set(timestamps)),
            "archive_rest_overlap_rows": len(overlap),
            "archive_rest_overlap_exact_realized_rate_matches": len(overlap) - len(mismatches),
            "mismatches": mismatches,
            "interval_ms_counts": {str(k): v for k, v in sorted({x: intervals.count(x) for x in set(intervals)}.items())},
            "first_event_utc": datetime.fromtimestamp(timestamps[0] / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
            "last_event_utc": datetime.fromtimestamp(timestamps[-1] / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
            "grid_complete_for_requested_half_open_interval": timestamps == expected,
            "formula_metadata_limitation": "formulaType and method are present only on the REST-sourced recent rows; monthly archive CSVs do not include these fields.",
        },
        "normalized_file": {
            "name": merged_path.name,
            "bytes": len(merged_bytes),
            "sha256": sha256(merged_bytes),
        },
        "status": "ONE_YEAR_FUNDING_EVENT_GRID_COMPLETE_OVERLAP_MATCHED_FORMULA_METADATA_PARTIAL",
        "limitations": [
            "Monthly archive rates are preserved as published; in the 21-row overlap they match REST realizedRate exactly.",
            "formulaType and method are not present in the monthly CSV files, so their historical values are not reconstructed for archive-only rows.",
            "This validates the observed event grid and rate source, not a strategy or trading edge.",
            "No strategy, PnL, backtest, order, account endpoint, API key, proxy, or mirror is used.",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": manifest["status"],
        "rows": len(timestamps),
        "archive_rows": len(archive_in_range),
        "rest_rows": len(rest_in_range),
        "overlap_rows": len(overlap),
        "first_event_utc": manifest["merge"]["first_event_utc"],
        "last_event_utc": manifest["merge"]["last_event_utc"],
        "interval_ms_counts": manifest["merge"]["interval_ms_counts"],
        "formula_types_observed": formula_types,
        "methods_observed": methods,
        "manifest": str(OUT / "manifest.json"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

# Trigger final merged funding capture after the merge logic update.
