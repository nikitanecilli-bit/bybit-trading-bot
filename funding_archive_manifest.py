"""Provenance manifest helpers for Bybit funding archive collection.

This records what the collector requested and what the API returned. It does
not claim that an API response itself contains every exchange settlement;
that requires an independently evidenced dated settlement schedule.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone


SCHEMA_VERSION = 1


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_data_row_count(path: str | Path) -> int:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in csv.DictReader(handle)))


def record_funding_collection(
    csv_path: str | Path,
    manifest_path: str | Path,
    *,
    symbol: str,
    category: str,
    api_base: str,
    requested_start_ms: int,
    requested_end_ms: int,
    pages: list[dict],
    collected_at_ms: int,
) -> dict:
    csv_path, manifest_path = Path(csv_path), Path(manifest_path)
    previous = None
    if manifest_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid existing funding manifest: {manifest_path}") from exc
        if previous.get("schema_version") != SCHEMA_VERSION or previous.get("symbol") != symbol.upper():
            raise ValueError("existing funding manifest schema/symbol mismatch")
    runs = list(previous.get("runs", [])) if previous else []
    runs.append({
        "requested_start_ms": int(requested_start_ms),
        "requested_end_ms": int(requested_end_ms),
        "pages": pages,
        "collected_at_ms": int(collected_at_ms),
    })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "symbol": symbol.upper(),
        "category": category,
        "endpoint": "/v5/market/funding/history",
        "api_base": api_base.rstrip("/"),
        "csv_file": csv_path.name,
        "csv_sha256": sha256_file(csv_path),
        "csv_data_rows": csv_data_row_count(csv_path),
        "runs": runs,
        "settlement_schedule_verified": False,
        "note": "Query provenance only; a dated authoritative settlement schedule is still required to prove event completeness.",
        "updated_at_utc": datetime.fromtimestamp(collected_at_ms / 1000, tz=timezone.utc).isoformat(),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, manifest_path)
    return payload


def validate_funding_manifest(
    csv_path: str | Path,
    manifest_path: str | Path,
    *,
    symbol: str,
    required_start_ms: int,
    required_end_ms: int,
) -> dict:
    csv_path, manifest_path = Path(csv_path), Path(manifest_path)
    if not csv_path.is_file() or not manifest_path.is_file():
        return {"ok": False, "status": "missing_csv_or_manifest"}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"ok": False, "status": "invalid_manifest"}
    errors = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported_schema")
    if payload.get("symbol") != symbol.upper():
        errors.append("symbol_mismatch")
    if payload.get("csv_sha256") != sha256_file(csv_path):
        errors.append("csv_hash_mismatch")
    if payload.get("csv_data_rows") != csv_data_row_count(csv_path):
        errors.append("csv_row_count_mismatch")
    intervals = []
    for run in payload.get("runs", []):
        start, end = run.get("requested_start_ms"), run.get("requested_end_ms")
        pages = run.get("pages")
        if not isinstance(start, int) or not isinstance(end, int) or end < start or not isinstance(pages, list):
            errors.append("invalid_run_metadata")
            continue
        page_intervals = []
        for page in pages:
            lo, hi = page.get("request_start_ms"), page.get("request_end_ms")
            if not isinstance(lo, int) or not isinstance(hi, int) or hi < lo:
                errors.append("invalid_page_metadata")
                continue
            page_intervals.append((lo, hi))
        page_intervals.sort()
        cursor = start
        for lo, hi in page_intervals:
            if hi < cursor:
                continue
            if lo > cursor:
                break
            cursor = max(cursor, hi + 1)
        if cursor <= end:
            errors.append("query_window_not_fully_covered")
        else:
            intervals.append((start, end))
    intervals.sort()
    cursor = int(required_start_ms)
    for lo, hi in intervals:
        if hi < cursor:
            continue
        if lo > cursor:
            break
        cursor = max(cursor, hi + 1)
    query_coverage_ok = cursor > int(required_end_ms)
    if not query_coverage_ok:
        errors.append("required_query_interval_not_covered")
    schedule_verified = payload.get("settlement_schedule_verified") is True
    if not schedule_verified:
        errors.append("dated_settlement_schedule_not_verified")
    return {
        "ok": not errors,
        "status": "ok" if not errors else "incomplete",
        "errors": errors,
        "query_coverage_ok": query_coverage_ok,
        "settlement_schedule_verified": schedule_verified,
        "csv_sha256": payload.get("csv_sha256"),
        "runs": len(payload.get("runs", [])),
    }
