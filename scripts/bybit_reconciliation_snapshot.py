#!/usr/bin/env python3
"""Capture a fail-closed, read-only Bybit V5 linear/USDT reconciliation snapshot.

No order, position, wallet, transfer, or withdrawal mutation endpoints exist here.
The API key must be explicitly marked read-only by /v5/user/query-api before any
account snapshot endpoint is requested. Network access is injectable for tests.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from bybit_reconciliation import (
    SnapshotValidationError,
    parse_active_order_pages,
    parse_execution_pages,
    parse_position_pages,
)

DEFAULT_BASE_URL = "https://api.bybit.kz"
RECV_WINDOW = "5000"
MAX_EXECUTION_WINDOW_MS = 7 * 24 * 60 * 60 * 1000
TIMEOUT_SECONDS = 20


class CollectorError(RuntimeError):
    """Collection failed or cannot be proven complete."""


def _utc_ms() -> int:
    return int(time.time() * 1000)


def _parse_utc_ms(value: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("saved_at_utc must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("saved_at_utc must include an explicit UTC offset")
    return int(parsed.astimezone(timezone.utc).timestamp() * 1000)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _signature(timestamp: str, api_key: str, secret: str,
               query_string: str = "") -> str:
    payload = f"{timestamp}{api_key}{RECV_WINDOW}{query_string}"
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _headers(api_key: str, secret: str, query_string: str = "",
             timestamp: str | None = None) -> dict[str, str]:
    stamp = timestamp or str(_utc_ms())
    return {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": stamp,
        "X-BAPI-RECV-WINDOW": RECV_WINDOW,
        "X-BAPI-SIGN": _signature(stamp, api_key, secret, query_string),
        "Content-Type": "application/json",
        "User-Agent": "bybit-trading-bot-readonly-reconciliation/1.0",
    }


def _http_json(url: str, headers: dict[str, str] | None = None,
               timeout: float = TIMEOUT_SECONDS) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise CollectorError(
            f"Bybit HTTP request failed with status {exc.code}; body suppressed"
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise CollectorError(
            f"Bybit request failed ({type(exc).__name__}); details suppressed"
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectorError("Bybit returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise CollectorError("Bybit response root is not an object")
    return payload


def _check_success(payload: dict[str, Any], endpoint: str) -> dict[str, Any]:
    code = payload.get("retCode")
    if isinstance(code, bool) or not isinstance(code, int) or code != 0:
        raise CollectorError(
            f"{endpoint} failed: retCode must be integer zero "
            f"(received {code!r}); response body suppressed"
        )
    result = payload.get("result")
    if not isinstance(result, dict):
        raise CollectorError(f"{endpoint} returned no result object")
    return result


def _query_string(params: dict[str, Any]) -> str:
    return urllib.parse.urlencode(sorted(
        (key, str(value)) for key, value in params.items() if value is not None
    ))


def _get(
    base_url: str, endpoint: str, params: dict[str, Any],
    api_key: str, secret: str,
    request_json: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    query = _query_string(params)
    url = f"{base_url.rstrip('/')}{endpoint}?{query}" if query else f"{base_url.rstrip('/')}{endpoint}"
    return request_json(url, _headers(api_key, secret, query))


def _read_only_key_check(base_url: str, api_key: str, secret: str,
                         request_json: Callable[..., dict[str, Any]]) -> None:
    payload = _get(base_url, "/v5/user/query-api", {}, api_key, secret, request_json)
    result = _check_success(payload, "/v5/user/query-api")
    if result.get("apiKey") != api_key:
        raise CollectorError("Authenticated API-key identity mismatch")
    if isinstance(result.get("readOnly"), bool) or result.get("readOnly") != 1:
        raise CollectorError("SECURITY BLOCK: API key is not explicitly read-only")


def _server_time(base_url: str, request_json: Callable[..., dict[str, Any]]) -> int:
    payload = request_json(f"{base_url.rstrip('/')}/v5/market/time", {})
    _check_success(payload, "/v5/market/time")
    value = payload.get("time")
    if isinstance(value, bool):
        raise CollectorError("Bybit server time is invalid")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CollectorError("Bybit server time is missing or invalid") from exc
    if parsed <= 0:
        raise CollectorError("Bybit server time must be positive")
    return parsed


def _collect_pages(
    base_url: str, endpoint: str, params: dict[str, Any],
    api_key: str, secret: str,
    request_json: Callable[..., dict[str, Any]],
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    cursor = ""
    seen: set[str] = set()
    while True:
        page_params = dict(params)
        if cursor:
            page_params["cursor"] = cursor
        payload = _get(base_url, endpoint, page_params, api_key, secret, request_json)
        result = _check_success(payload, endpoint)
        rows = result.get("list")
        next_cursor = result.get("nextPageCursor", "")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise CollectorError(f"{endpoint} returned malformed result.list")
        if not isinstance(next_cursor, str):
            raise CollectorError(f"{endpoint} returned malformed nextPageCursor")
        pages.append({
            "requested_cursor": cursor,
            "response": payload,
        })
        if not next_cursor:
            return pages
        if next_cursor == cursor or next_cursor in seen:
            raise CollectorError(f"{endpoint} pagination cursor repeated")
        seen.add(next_cursor)
        cursor = next_cursor


def _execution_intervals(start_ms: int, end_ms: int) -> list[tuple[int, int]]:
    if start_ms <= 0 or end_ms <= start_ms:
        raise ValueError("execution window must have positive start and end > start")
    intervals = []
    cursor = start_ms
    while cursor < end_ms:
        finish = min(cursor + MAX_EXECUTION_WINDOW_MS, end_ms)
        intervals.append((cursor, finish))
        cursor = finish
    return intervals


def collect_snapshot(
    api_key: str,
    secret: str,
    saved_at_utc: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    request_json: Callable[..., dict[str, Any]] = _http_json,
) -> dict[str, Any]:
    if not api_key or not secret:
        raise CollectorError("API credentials are missing")
    if not base_url.startswith("https://"):
        raise ValueError("HTTPS is required")
    saved_ms = _parse_utc_ms(saved_at_utc)
    capture_started_ms = _utc_ms()
    _read_only_key_check(base_url, api_key, secret, request_json)
    server_time_before_ms = _server_time(base_url, request_json)
    if server_time_before_ms <= saved_ms:
        raise CollectorError("saved_at_utc is not earlier than Bybit server time")
    capture_now_ms = server_time_before_ms

    position_pages = _collect_pages(
        base_url, "/v5/position/list",
        {"category": "linear", "settleCoin": "USDT", "limit": 200},
        api_key, secret, request_json,
    )
    order_pages = _collect_pages(
        base_url, "/v5/order/realtime",
        {"category": "linear", "settleCoin": "USDT", "openOnly": 0, "limit": 50},
        api_key, secret, request_json,
    )

    execution_pages: list[dict[str, Any]] = []
    for start_ms, end_ms in _execution_intervals(saved_ms, capture_now_ms):
        interval_pages = _collect_pages(
            base_url, "/v5/execution/list",
            {"category": "linear", "startTime": start_ms,
             "endTime": end_ms, "limit": 100},
            api_key, secret, request_json,
        )
        for page in interval_pages:
            execution_pages.append({
                "interval_start_ms": start_ms,
                "interval_end_ms": end_ms,
                **page,
            })

    try:
        parsed_positions = parse_position_pages(
            (p["requested_cursor"], p["response"]) for p in position_pages
        )
        parsed_orders = parse_active_order_pages(
            (p["requested_cursor"], p["response"]) for p in order_pages
        )
        # Validate each execution interval independently: each has its own cursor chain.
        parsed_executions = []
        for start_ms, end_ms in _execution_intervals(saved_ms, capture_now_ms):
            interval = [p for p in execution_pages
                        if p["interval_start_ms"] == start_ms and p["interval_end_ms"] == end_ms]
            parsed_executions.extend(parse_execution_pages(
                (p["requested_cursor"], p["response"]) for p in interval
            ))
    except SnapshotValidationError as exc:
        raise CollectorError(f"Snapshot validation failed: {exc}") from exc

    server_time_after_ms = _server_time(base_url, request_json)
    if server_time_after_ms < server_time_before_ms:
        raise CollectorError("Bybit server time moved backwards during snapshot")
    if server_time_after_ms - server_time_before_ms > 120_000:
        raise CollectorError("Snapshot collection exceeded 120 seconds; capture is not coherent")
    capture_now_ms = server_time_after_ms
    capture_finished_ms = _utc_ms()
    unique_executions = {item.exec_id: item for item in parsed_executions}
    parsed_executions = list(unique_executions.values())
    raw = {
        "positions": position_pages,
        "active_orders": order_pages,
        "executions": execution_pages,
    }
    digest = hashlib.sha256(_canonical_json_bytes(raw)).hexdigest()
    return {
        "schema_version": 1,
        "status": "CAPTURED_READ_ONLY_NOT_RECONCILED",
        "source": "Bybit V5 authenticated read-only endpoints",
        "base_url": base_url,
        "category": "linear",
        "settle_coin": "USDT",
        "saved_at_utc": saved_at_utc,
        "capture_started_utc": datetime.fromtimestamp(
            capture_started_ms / 1000, timezone.utc).isoformat(),
        "capture_finished_utc": datetime.fromtimestamp(
            capture_finished_ms / 1000, timezone.utc).isoformat(),
        "capture_now_ms": capture_now_ms,
        "bybit_server_time_before_ms": server_time_before_ms,
        "bybit_server_time_after_ms": server_time_after_ms,
        "counts": {
            "positions": len(parsed_positions),
            "active_orders": len(parsed_orders),
            "executions": len(parsed_executions),
            "position_pages": len(position_pages),
            "active_order_pages": len(order_pages),
            "execution_pages": len(execution_pages),
        },
        "raw_sha256": digest,
        "raw": raw,
        "limitations": [
            "Capture is not a reconciliation verdict.",
            "Local model lacks exact exchange quantity and order/execution identity.",
            "No order history or exchange-side stop/TP verification is included.",
            "Execution interval boundaries may overlap semantically; consumers must deduplicate by execId.",
        ],
    }


def write_snapshot(snapshot: dict[str, Any], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                      indent=2, allow_nan=False) + "\n"
    path.write_text(data, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved-at-utc", required=True,
                        help="UTC ISO-8601 timestamp from the local backup")
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-url", default=os.environ.get(
        "BYBIT_API_BASE_URL", DEFAULT_BASE_URL))
    args = parser.parse_args()
    try:
        snapshot = collect_snapshot(
            os.environ.get("BYBIT_API_KEY", ""),
            os.environ.get("BYBIT_API_SECRET", ""),
            args.saved_at_utc,
            base_url=args.base_url,
        )
        path = write_snapshot(snapshot, args.output)
    except (CollectorError, ValueError, OSError) as exc:
        print(f"BLOCKED: {exc}")
        return 1
    print(f"Saved read-only snapshot to {path}; SHA256={snapshot['raw_sha256']}")
    print("Status is CAPTURED_READ_ONLY_NOT_RECONCILED; live resume remains blocked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
