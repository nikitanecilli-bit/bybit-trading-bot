#!/usr/bin/env python3
"""Archive dated Bybit V5 risk-limit tiers; snapshots are point-in-time only."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

ENDPOINT = "/v5/market/risk-limit"
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


def _decimal(value: Any, field: str, *, allow_empty: bool = False) -> Decimal | None:
    if allow_empty and value in (None, ""):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite {field}")
    return result


def validate_tier(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("risk-limit row must be an object")
    symbol = str(row.get("symbol") or "").strip().upper()
    if not symbol:
        raise ValueError("risk-limit row is missing symbol")
    tier_id = row.get("id")
    if isinstance(tier_id, bool) or not isinstance(tier_id, int) or tier_id <= 0:
        raise ValueError(f"{symbol}: risk tier id must be a positive integer")
    for field in ("riskLimitValue", "maintenanceMargin", "initialMargin", "maxLeverage"):
        value = _decimal(row.get(field), f"{symbol}.{field}")
        if value is None or value <= 0:
            raise ValueError(f"{symbol}.{field} must be > 0")
    lowest = row.get("isLowestRisk")
    if isinstance(lowest, bool) or lowest not in (0, 1):
        raise ValueError(f"{symbol}.isLowestRisk must be integer 0 or 1")
    _decimal(row.get("mmDeduction", ""), f"{symbol}.mmDeduction", allow_empty=True)
    return dict(row)


def _request_page(base_url: str, category: str, cursor: str | None,
                  symbol: str | None = None, timeout: float = 20.0):
    _validate_base_url(base_url)
    params: dict[str, Any] = {"category": category}
    if symbol:
        params["symbol"] = symbol
    if cursor:
        params["cursor"] = cursor
    url = f"{base_url.rstrip('/')}{ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "bybit-trading-bot-research/1.0"})
    try:
        opener = urllib.request.build_opener(_NoRedirectHandler())
        with opener.open(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Bybit risk-limit HTTP status {exc.code}; body suppressed") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Bybit risk-limit request failed ({type(exc).__name__})") from exc
    if not isinstance(payload, dict):
        raise ValueError("Bybit risk-limit response root must be an object")
    code = payload.get("retCode")
    if isinstance(code, bool) or not isinstance(code, int) or code != 0:
        raise RuntimeError("Bybit risk-limit returned non-zero or invalid retCode")
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("list"), list):
        raise ValueError("unexpected Bybit risk-limit response shape")
    rows = result["list"]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("risk-limit list contains a non-object row")
    next_cursor = result.get("nextPageCursor")
    if next_cursor in (None, ""):
        next_cursor = None
    elif not isinstance(next_cursor, str):
        raise ValueError("Bybit risk-limit nextPageCursor must be a string")
    return rows, next_cursor


def fetch_all_tiers(category: str = "linear",
                    fetch_page: Callable[[str | None], tuple[list[dict[str, Any]], str | None]] | None = None
                    ) -> list[dict[str, Any]]:
    if category not in {"linear", "inverse"}:
        raise ValueError("risk-limit category must be linear or inverse")
    if fetch_page is None:
        fetch_page = lambda cursor: _request_page(DEFAULT_BASE_URL, category, cursor)
    rows: dict[tuple[str, int], dict[str, Any]] = {}
    seen_cursors: set[str] = set()
    cursor: str | None = None
    for _ in range(MAX_PAGES):
        page, next_cursor = fetch_page(cursor)
        for raw in page:
            row = validate_tier(raw)
            key = (row["symbol"], row["id"])
            if key in rows and rows[key] != row:
                raise ValueError(f"conflicting duplicate risk tier: {key[0]} id={key[1]}")
            if key in rows:
                raise ValueError(f"duplicate risk tier: {key[0]} id={key[1]}")
            rows[key] = row
        if not next_cursor:
            break
        if next_cursor == cursor or next_cursor in seen_cursors:
            raise RuntimeError("risk-limit pagination cursor repeated")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    else:
        raise RuntimeError("risk-limit pagination exceeded safety limit")
    if not rows:
        raise RuntimeError("Bybit returned an empty risk-limit universe")
    return [rows[key] for key in sorted(rows)]


def build_snapshot(rows: list[dict[str, Any]], category: str,
                   fetched_at: str | None = None) -> dict[str, Any]:
    timestamp = fetched_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    validated = [validate_tier(row) for row in rows]
    keys = [(row["symbol"], row["id"]) for row in validated]
    if not validated or len(keys) != len(set(keys)):
        raise ValueError("snapshot requires non-empty unique symbol/risk-tier rows")
    symbols = sorted({row["symbol"] for row in validated})
    return {
        "schema_version": 1,
        "source": "Bybit V5 GET /v5/market/risk-limit",
        "category": category,
        "fetched_at": timestamp,
        "symbol_count": len(symbols),
        "tier_count": len(validated),
        "tiers": validated,
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
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return path


DEFAULT_BASE_URL = "https://api.bybit.com"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=["linear", "inverse"], default="linear")
    parser.add_argument("--output-dir", default="data/instrument_specs/risk_limits")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--pause", type=float, default=0.1)
    args = parser.parse_args()
    if args.pause < 0:
        parser.error("--pause cannot be negative")

    def fetch(cursor: str | None):
        page, next_cursor = _request_page(args.base_url, args.category, cursor)
        if next_cursor and args.pause:
            time.sleep(args.pause)
        return page, next_cursor

    rows = fetch_all_tiers(args.category, fetch)
    snapshot = build_snapshot(rows, args.category)
    fetched = datetime.fromisoformat(snapshot["fetched_at"].replace("Z", "+00:00"))
    stamp = fetched.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    output = Path(args.output_dir) / args.category / f"{stamp}.json"
    write_snapshot(snapshot, output)
    print(f"Saved {len(rows)} risk tiers across {snapshot['symbol_count']} symbols to {output}")


if __name__ == "__main__":
    main()
