#!/usr/bin/env python3
"""Archive Bybit V5 linear instrument records across documented statuses."""
from __future__ import annotations

import argparse
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.snapshot_bybit_instruments import (
    DEFAULT_BASE_URL, _request_page, _snapshot_timestamp, _validate_base_url,
    build_page_observation, validate_page_observations, write_snapshot,
)

# API Explorer status filters; the default query additionally returns PendingOpen.
STATUSES = ("PreLaunch", "Settling", "Delivering", "Closed")
DEFAULT_STATUSES = ("Trading", "PendingOpen")
CAPTURED_STATUSES = (*DEFAULT_STATUSES, *STATUSES)
MAX_PAGES = 1000
SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,30}$")


def _timestamp_ms(value: Any, field: str, *, allow_zero: bool) -> int:
    # Bybit returns millisecond timestamps as decimal strings. Accept integer
    # JSON values for offline fixtures, but reject bools, floats and coercions
    # such as whitespace or a leading plus sign.
    if isinstance(value, bool):
        raise ValueError(f"invalid {field}")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        parsed = int(value)
    else:
        raise ValueError(f"invalid {field}")
    if parsed < 0 or (parsed == 0 and not allow_zero):
        raise ValueError(f"invalid {field}")
    return parsed


def validate_instrument_row(row: Any, requested_status: str | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("instrument row must be an object")
    raw_symbol = row.get("symbol")
    if not isinstance(raw_symbol, str) or not raw_symbol.strip():
        raise ValueError("instrument row has invalid symbol")
    symbol = raw_symbol.strip().upper()
    if not SYMBOL_RE.fullmatch(symbol):
        raise ValueError("instrument row has invalid symbol")
    actual_status = row.get("status")
    expected = set(DEFAULT_STATUSES) if requested_status is None else {requested_status}
    if actual_status not in expected:
        raise ValueError(
            f"instrument status mismatch for {symbol}: "
            f"requested {requested_status or 'default'}, got {actual_status!r}"
        )
    launch_ms = _timestamp_ms(row.get("launchTime"), "launchTime", allow_zero=False)
    delivery_ms = _timestamp_ms(row.get("deliveryTime"), "deliveryTime", allow_zero=True)
    if delivery_ms and delivery_ms < launch_ms:
        raise ValueError(f"deliveryTime precedes launchTime for {symbol}")
    if not row.get("contractType") or not row.get("quoteCoin") or not row.get("settleCoin"):
        raise ValueError(f"instrument row lacks contract identity fields: {symbol}")
    return dict(row)


def fetch_status(
    status: str | None,
    fetch_page: Callable[[str | None], tuple[list[dict[str, Any]], str | None]],
) -> list[dict[str, Any]]:
    if status is not None and status not in STATUSES:
        raise ValueError(f"unsupported instrument status: {status}")
    by_symbol: dict[str, dict[str, Any]] = {}
    seen_cursors: set[str] = set()
    cursor: str | None = None
    page_count = 0
    while True:
        page_count += 1
        if page_count > MAX_PAGES:
            raise RuntimeError(f"Bybit {status or 'default'} pagination exceeded safety limit")
        rows, next_cursor = fetch_page(cursor)
        if not isinstance(rows, list):
            raise ValueError(f"Bybit {status or 'default'} instrument page must be a list")
        for raw in rows:
            row = validate_instrument_row(raw, status)
            symbol = row["symbol"]
            if symbol in by_symbol and by_symbol[symbol] != row:
                raise ValueError(f"conflicting duplicate {status or 'default'} instrument: {symbol}")
            by_symbol[symbol] = row
        if next_cursor in (None, ""):
            break
        if not isinstance(next_cursor, str):
            raise ValueError("Bybit instrument nextPageCursor must be a string")
        if next_cursor == cursor or next_cursor in seen_cursors:
            raise RuntimeError(f"Bybit {status or 'default'} pagination cursor repeated")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    return [by_symbol[symbol] for symbol in sorted(by_symbol)]


def fetch_linear_universe(
    fetch_page_for_status: Callable[[str | None, str | None], tuple[list[dict[str, Any]], str | None]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    all_rows: dict[str, dict[str, Any]] = {}
    for status in (None, *STATUSES):
        rows = fetch_status(status, lambda cursor, status=status: fetch_page_for_status(status, cursor))
        for row in rows:
            symbol = row["symbol"]
            if symbol in all_rows and all_rows[symbol] != row:
                raise ValueError(f"instrument appears with conflicting statuses: {symbol}")
            all_rows[symbol] = row
    if not all_rows:
        raise RuntimeError("Bybit returned an empty linear instrument universe across all statuses")
    status_counts_raw = Counter(row["status"] for row in all_rows.values())
    counts = {status: status_counts_raw.get(status, 0) for status in CAPTURED_STATUSES}
    return [all_rows[symbol] for symbol in sorted(all_rows)], counts


def is_linear_usdt_perpetual_within_lifecycle_at(row: dict[str, Any], timestamp_ms: int) -> bool:
    """Check lifecycle bounds, not current tradability.

    Bybit documents deliveryTime=0 for perpetuals without a scheduled
    delivery/delisting boundary. Treat that as open-ended only for a Trading
    perpetual. A terminal/in-progress terminal status with no positive
    boundary is ambiguous and is excluded rather than assigned an invented
    historical end time.
    """
    if timestamp_ms < 0:
        raise ValueError("timestamp_ms must be non-negative")
    if row.get("contractType") != "LinearPerpetual":
        return False
    if row.get("quoteCoin") != "USDT" or row.get("settleCoin") != "USDT":
        return False
    status = row.get("status")
    if status not in CAPTURED_STATUSES or status in {"PreLaunch", "PendingOpen"}:
        return False
    launch_ms = _timestamp_ms(row.get("launchTime"), "launchTime", allow_zero=False)
    delivery_ms = _timestamp_ms(row.get("deliveryTime"), "deliveryTime", allow_zero=True)
    if status in {"Closed", "Settling", "Delivering"} and delivery_ms == 0:
        return False
    return launch_ms <= timestamp_ms and (delivery_ms == 0 or timestamp_ms < delivery_ms)


def build_universe_snapshot(
    rows: list[dict[str, Any]], status_counts: dict[str, int], fetched_at: str | None = None,
    collection_started_at: str | None = None,
    page_observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("universe snapshot requires non-empty instrument objects")
    symbols = [row.get("symbol") for row in rows]
    if any(not isinstance(symbol, str) or not SYMBOL_RE.fullmatch(symbol) for symbol in symbols):
        raise ValueError("universe snapshot contains invalid symbols")
    if len(symbols) != len(set(symbols)):
        raise ValueError("universe snapshot contains duplicate symbols")
    if not isinstance(status_counts, dict) or set(status_counts) != set(CAPTURED_STATUSES):
        raise ValueError("status counts do not match the captured universe")
    if any(type(count) is not int or count < 0 for count in status_counts.values()):
        raise ValueError("status counts must be non-negative integers")
    observed_counts = Counter(row.get("status") for row in rows)
    expected_counts = {status: observed_counts.get(status, 0) for status in CAPTURED_STATUSES}
    if status_counts != expected_counts or sum(status_counts.values()) != len(rows):
        raise ValueError("status counts do not match the captured universe")
    timestamp = _snapshot_timestamp(fetched_at)
    started_at = (_snapshot_timestamp(collection_started_at)
                  if collection_started_at is not None else None)
    if started_at is not None and started_at > timestamp:
        raise ValueError("snapshot collection_started_at cannot be after fetched_at")
    snapshot = {
        "schema_version": 1,
        "source": "Bybit V5 GET /v5/market/instruments-info",
        "category": "linear",
        "fetched_at": timestamp,
        "queried_statuses": ["default(Trading,PendingOpen)", *STATUSES],
        "status_counts": status_counts,
        "count": len(rows),
        "instruments": rows,
    }
    if started_at is not None:
        snapshot["collection_started_at"] = started_at
    if page_observations is not None:
        snapshot["page_observations"] = validate_page_observations(page_observations)
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/universe_history")
    parser.add_argument("--base-url", default=os.environ.get("BYBIT_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--pause", type=float, default=0.1)
    args = parser.parse_args()
    if args.pause < 0:
        parser.error("--pause cannot be negative")
    _validate_base_url(args.base_url)

    page_observations: list[dict[str, Any]] = []
    page_counts: Counter[str] = Counter()

    def fetch_page(status: str | None, cursor: str | None):
        status_filter = status or "default"
        page_counts[status_filter] += 1
        request_started_at = _snapshot_timestamp(None)
        rows, next_cursor = _request_page(args.base_url, "linear", cursor, status=status)
        response_received_at = _snapshot_timestamp(None)
        page_observations.append(build_page_observation(
            status_filter, page_counts[status_filter], request_started_at,
            response_received_at, rows, next_cursor,
        ))
        if next_cursor and args.pause:
            time.sleep(args.pause)
        return rows, next_cursor

    collection_started_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    rows, counts = fetch_linear_universe(fetch_page)
    snapshot = build_universe_snapshot(
        rows, counts, collection_started_at=collection_started_at,
        page_observations=page_observations,
    )
    fetched = datetime.fromisoformat(snapshot["fetched_at"].replace("Z", "+00:00"))
    stamp = fetched.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    output = Path(args.output_dir) / "linear" / f"{stamp}.json"
    write_snapshot(snapshot, output)
    now_ms = int(fetched.timestamp() * 1000)
    active = sum(is_linear_usdt_perpetual_within_lifecycle_at(row, now_ms) for row in rows)
    print(f"Saved {len(rows)} linear instruments ({active} USDT perpetuals within launch/delivery bounds) to {output}")
    print("Status counts: " + ", ".join(f"{key}={counts[key]}" for key in CAPTURED_STATUSES))


if __name__ == "__main__":
    main()
