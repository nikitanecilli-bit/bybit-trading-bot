#!/usr/bin/env python3
"""Archive dated public Bybit V5 instrument-info snapshots.

Snapshots are point-in-time observations, not proof that a specification was
valid before/after fetched_at. Keep each UTC-day file immutable in Git history.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
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
MAX_PAGES = 1000
ALLOWED_API_HOSTS = {
    "api.bybit.com", "api.bytick.com", "api.bybit.kz", "api.bybit.tr",
    "api.bybitgeorgia.ge", "api.bybit.ae", "api.bybit.eu", "api.bybit.id",
}


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_base_url(base_url: str) -> None:
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_API_HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("base URL must be an official HTTPS Bybit API host")


def _validate_next_cursor(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("Bybit instrument nextPageCursor must be a string")
    return value


def _check_ret_code(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Bybit response root must be an object")
    code = payload.get("retCode")
    if isinstance(code, bool) or not isinstance(code, int) or code != 0:
        raise RuntimeError("Bybit instruments-info returned non-zero or invalid retCode")


def _request_page(base_url: str, category: str, cursor: str | None,
                  timeout: float = 20.0, status: str | None = None
                  ) -> tuple[list[dict[str, Any]], str | None]:
    _validate_base_url(base_url)
    params: dict[str, Any] = {"category": category, "limit": 1000}
    if status is not None:
        if status not in {"PreLaunch", "Trading", "Settling", "Delivering", "Closed"}:
            raise ValueError("unsupported instrument status")
        params["status"] = status
    if cursor:
        params["cursor"] = cursor
    url = f"{base_url.rstrip('/')}{ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url, headers={"User-Agent": "bybit-trading-bot-research/1.0"}
    )
    try:
        opener = urllib.request.build_opener(_NoRedirectHandler())
        with opener.open(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Bybit instruments-info HTTP status {exc.code}; body suppressed") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Bybit instruments-info request failed ({type(exc).__name__})") from exc
    _check_ret_code(payload)
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("list"), list):
        raise ValueError("Unexpected Bybit instruments-info response shape")
    rows = result["list"]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Instrument list contains a non-object row")
    next_cursor = _validate_next_cursor(result.get("nextPageCursor"))
    return rows, next_cursor


# Query each lifecycle status explicitly: Bybit's unfiltered linear endpoint
# defaults to Trading and PendingOpen, which is not a complete lifecycle snapshot.
INSTRUMENT_STATUS_FILTERS = {
    "linear": ("PreLaunch", "Trading", "Settling", "Delivering", "Closed"),
    "inverse": ("PreLaunch", "Trading", "Settling", "Delivering", "Closed"),
    "spot": ("Trading",),
    "option": ("PreLaunch", "Trading", "Delivering", "Closed"),
}


def fetch_all_instruments(
    category: str = "linear",
    fetch_page: Callable[[str | None, str], tuple[list[dict[str, Any]], str | None]] | None = None,
) -> list[dict[str, Any]]:
    if category not in INSTRUMENT_STATUS_FILTERS:
        raise ValueError(f"unsupported category: {category}")
    if fetch_page is None:
        fetch_page = lambda cursor, status: _request_page(
            DEFAULT_BASE_URL, category, cursor, status=status
        )

    by_symbol: dict[str, dict[str, Any]] = {}
    for status in INSTRUMENT_STATUS_FILTERS[category]:
        seen_cursors: set[str] = set()
        cursor: str | None = None
        page_count = 0
        while True:
            page_count += 1
            if page_count > MAX_PAGES:
                raise RuntimeError("Bybit instrument pagination exceeded safety limit")
            rows, next_cursor = fetch_page(cursor, status)
            for row in rows:
                raw_symbol = row.get("symbol")
                if not isinstance(raw_symbol, str) or not raw_symbol.strip():
                    raise ValueError("instrument row is missing or has invalid symbol")
                symbol = raw_symbol.strip().upper()
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

def _snapshot_timestamp(value: str | None) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    else:
        if not isinstance(value, str):
            raise ValueError("snapshot fetched_at must be an ISO-8601 string")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("snapshot fetched_at must be a valid ISO-8601 timestamp") from exc
        if parsed.tzinfo is None:
            raise ValueError("snapshot fetched_at must include timezone")
        if parsed.microsecond % 1000:
            raise ValueError("snapshot fetched_at must have millisecond precision")
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_snapshot(rows: list[dict[str, Any]], category: str,
                   fetched_at: str | None = None) -> dict[str, Any]:
    timestamp = _snapshot_timestamp(fetched_at)
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("snapshot requires non-empty instrument objects")
    raw_symbols = [row.get("symbol") for row in rows]
    if any(not isinstance(symbol, str) or not symbol.strip() for symbol in raw_symbols):
        raise ValueError("snapshot requires non-empty string symbols")
    symbols = [symbol.strip().upper() for symbol in raw_symbols]
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

    def fetch(cursor: str | None, status: str):
        page, next_cursor = _request_page(
            args.base_url, args.category, cursor, status=status
        )
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
