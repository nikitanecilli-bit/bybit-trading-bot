#!/usr/bin/env python3
"""Independent semantic audit of Bybit D1-D3 raw-response manifests.

This validator re-opens every captured HTTP body and checks that the endpoint,
request identity, symbol/category, row count, and timestamp bounds agree with
the page inventory. It is offline and never calls an exchange API.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

STREAM_ENDPOINTS = {
    "funding": "/v5/market/funding/history",
    "trade_kline": "/v5/market/kline",
    "mark_price": "/v5/market/mark-price-kline",
}


def _timestamp(stream: str, row: Any) -> int:
    if stream == "funding":
        if not isinstance(row, dict):
            raise ValueError("funding_row_not_object")
        value = row.get("fundingRateTimestamp")
    else:
        if not isinstance(row, list) or not row:
            raise ValueError("kline_row_not_array")
        value = row[0]
    if isinstance(value, bool):
        raise ValueError("timestamp_invalid")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError("timestamp_invalid") from None
    if result <= 0:
        raise ValueError("timestamp_not_positive")
    return result


def validate_semantics(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    errors: list[str] = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"ok": False, "errors": ["manifest_missing_or_invalid"], "pages_checked": 0}

    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return {"ok": False, "errors": ["manifest_schema_invalid"], "pages_checked": 0}
    symbol = manifest.get("symbol")
    category = manifest.get("category")
    records = manifest.get("records")
    streams = manifest.get("collection_pages")
    if not isinstance(symbol, str) or not symbol:
        errors.append("manifest_symbol_invalid")
    if category != "linear":
        errors.append("manifest_category_invalid")
    if not isinstance(records, list) or not isinstance(streams, dict):
        return {"ok": False, "errors": errors + ["manifest_inventory_invalid"], "pages_checked": 0}

    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("request_id"), str):
            errors.append("record_identity_invalid")
            continue
        if record["request_id"] in by_id:
            errors.append("record_id_duplicate")
        by_id[record["request_id"]] = record

    used: list[str] = []
    checked = 0
    for stream, endpoint in STREAM_ENDPOINTS.items():
        pages = streams.get(stream)
        if not isinstance(pages, list) or not pages:
            errors.append(f"{stream}_pages_missing")
            continue
        for page_index, page in enumerate(pages):
            if not isinstance(page, dict):
                errors.append(f"{stream}_page_invalid")
                continue
            request_id = page.get("raw_response_request_id")
            record = by_id.get(request_id)
            if record is None:
                errors.append(f"{stream}_record_missing")
                continue
            used.append(request_id)
            request = record.get("request")
            if not isinstance(request, dict):
                errors.append(f"{stream}_request_invalid")
                continue
            if request.get("method") != "GET" or request.get("endpoint") != endpoint:
                errors.append(f"{stream}_endpoint_mismatch")
            params = request.get("params")
            if not isinstance(params, dict):
                errors.append(f"{stream}_params_invalid")
                continue
            if str(params.get("symbol", "")).upper() != symbol.upper():
                errors.append(f"{stream}_symbol_mismatch")
            if params.get("category") != category:
                errors.append(f"{stream}_category_mismatch")
            body_file = record.get("body_file")
            if not isinstance(body_file, str):
                errors.append(f"{stream}_body_path_missing")
                continue
            body_path = (path.parent / body_file).resolve()
            try:
                body_path.relative_to(path.parent.resolve())
                payload = json.loads(body_path.read_text(encoding="utf-8"))
            except (ValueError, OSError, json.JSONDecodeError):
                errors.append(f"{stream}_body_unreadable")
                continue
            if not isinstance(payload, dict) or payload.get("retCode") != 0:
                errors.append(f"{stream}_api_envelope_invalid")
                continue
            result = payload.get("result")
            rows = result.get("list") if isinstance(result, dict) else None
            if not isinstance(rows, list):
                errors.append(f"{stream}_rows_invalid")
                continue
            if len(rows) != page.get("response_rows"):
                errors.append(f"{stream}_row_count_mismatch")
            if not rows:
                errors.append(f"{stream}_empty_page")
                continue
            try:
                timestamps = [_timestamp(stream, row) for row in rows]
            except ValueError as exc:
                errors.append(f"{stream}_{exc}")
                continue
            if len(timestamps) != len(set(timestamps)):
                errors.append(f"{stream}_duplicate_timestamp_in_page")
            if page.get("first_ts") != min(timestamps):
                errors.append(f"{stream}_first_timestamp_mismatch")
            if page.get("last_ts") != max(timestamps):
                errors.append(f"{stream}_last_timestamp_mismatch")
            lo = page.get("request_start_ms")
            hi = page.get("request_end_ms")
            if type(lo) is not int or type(hi) is not int or hi < lo:
                errors.append(f"{stream}_request_window_invalid")
            elif any(ts < lo or ts > hi for ts in timestamps):
                errors.append(f"{stream}_timestamp_outside_request")
            if page.get("raw_response_body_sha256") != record.get("body_sha256"):
                errors.append(f"{stream}_body_hash_link_mismatch")
            checked += 1

    if len(used) != len(set(used)):
        errors.append("response_referenced_multiple_times")
    if set(used) != set(by_id):
        errors.append("unreferenced_or_missing_response_record")
    return {"ok": not errors, "errors": errors, "pages_checked": checked}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    result = validate_semantics(args.manifest)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
