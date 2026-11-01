#!/usr/bin/env python3
"""Archive dated public Bybit V5 instrument-info snapshots.

Snapshots are point-in-time observations, not proof that a specification was
valid before/after fetched_at. Keep each UTC-day file immutable in Git history.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

DEFAULT_BASE_URL = "https://api.bybit.com"
ENDPOINT = "/v5/market/instruments-info"
SCHEMA_VERSION = 1


def _request_page(base_url: str, category: str, cursor: str | None,
                  timeout: float = 20.0) -> tuple[list[dict[str, Any]], str | None]:
    params: dict[str, Any] = {"category": category, "limit": 1000}
    if cursor:
        params["cursor"] = cursor
    url = f"{base_url.rstrip('/')}{ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url, headers={"User-Agent": "bybit-trading-bot-research/1.0"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("retCode") != 0:
        raise RuntimeError(
            f"Bybit instruments-info error {payload.get('retCode')}: "
            f"{payload.get('retMsg', 'unknown error')}"
        )
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("list"), list):
        raise ValueError("Unexpected Bybit instruments-info response shape")
    rows = result["list"]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Instrument list contains a non-object row")
    next_cursor = result.get("nextPageCursor") or None
    return rows, next_cursor


def fetch_all_instruments(
    category: str = "linear",
    fetch_page: Callable[[str | None], tuple[list[dict[str, Any]], str | None]] | None = None,
) -> list[dict[str, Any]]:
    if category not in {"linear", "inverse", "spot", "option"}:
        raise ValueError(f"unsupported category: {category}")
    if fetch_page is None:
        fetch_page = lambda cursor: _request_page(DEFAULT_BASE_URL, category, cursor)

    by_symbol: dict[str, dict[str, Any]] = {}
    seen_cursors: set[str] = set()
    cursor: str | None = None
    while True:
        rows, next_cursor = fetch_page(cursor)
        for row in rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol:
                raise ValueError("instrument row is missing symbol")
            if symbol in by_symbol and by_symbol[symbol] != row:
                raise ValueError(f"conflicting duplicate instrument row: {symbol}")
            by_symbol[symbol] = row
        if not next_cursor:
            break
        if next_cursor == cursor or next_cursor in seen_cursors:
            raise RuntimeError("Bybit instrument pagination cursor repeated")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    if not by_symbol:
        raise RuntimeError("Bybit returned an empty instrument universe")
    return [by_symbol[symbol] for symbol in sorted(by_symbol)]


def build_snapshot(rows: list[dict[str, Any]], category: str,
                   fetched_at: str | None = None) -> dict[str, Any]:
    timestamp = fetched_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    symbols = [str(row.get("symbol") or "").strip().upper() for row in rows]
    if not rows or any(not symbol for symbol in symbols):
        raise ValueError("snapshot requires non-empty rows with symbols")
    if len(symbols) != len(set(symbols)):
        raise ValueError("snapshot contains duplicate symbols")
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "Bybit V5 GET /v5/market/instruments-info",
        "category": category,
        "fetched_at": timestamp,
        "count": len(rows),
        "instruments": rows,
    }


def write_snapshot(snapshot: dict[str, Any], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", default="linear",
                        choices=["linear", "inverse", "spot", "option"])
    parser.add_argument("--output-dir", default="data/instrument_specs")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help="Bybit public API base URL; supports regional hosts")
    parser.add_argument("--pause", type=float, default=0.1,
                        help="Pause between API pages in seconds")
    args = parser.parse_args()
    if args.pause < 0:
        parser.error("--pause cannot be negative")

    def fetch(cursor: str | None):
        page, next_cursor = _request_page(args.base_url, args.category, cursor)
        if next_cursor and args.pause:
            time.sleep(args.pause)
        return page, next_cursor

    rows = fetch_all_instruments(args.category, fetch)
    snapshot = build_snapshot(rows, args.category)
    fetched = datetime.fromisoformat(snapshot["fetched_at"].replace("Z", "+00:00"))
    stamp = fetched.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    output = Path(args.output_dir) / args.category / f"{stamp}.json"
    write_snapshot(snapshot, output)
    print(f"Saved {len(rows)} {args.category} instruments to {output}")


if __name__ == "__main__":
    main()
