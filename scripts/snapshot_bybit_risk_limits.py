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
    if isinstance(lowest, bool) or not isinstance(lowest, int) or lowest not in (0, 1):
        raise ValueError(f"{symbol}.isLowestRisk must be integer 0 or 1")
    _decimal(row.get("mmDeduction", ""), f"{symbol}.mmDeduction", allow_empty=True)
    return dict(row)


def validate_tier_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate per-symbol tier monotonicity and Bybit's MM deduction recurrence."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in rows:
        row = validate_tier(raw)
        grouped.setdefault(row["symbol"], []).append(row)
    if not grouped:
        raise ValueError("risk-limit snapshot has no tiers")

    tolerance = Decimal("0.00000001")
    for symbol, tiers in grouped.items():
        tiers.sort(key=lambda row: _decimal(row["riskLimitValue"], f"{symbol}.riskLimitValue"))
        lowest_flags = [row["isLowestRisk"] for row in tiers]
        if lowest_flags.count(1) != 1 or lowest_flags[0] != 1:
            raise ValueError(f"{symbol}: exactly the lowest risk tier must have isLowestRisk=1")
        previous = None
        for index, row in enumerate(tiers):
            risk_limit = _decimal(row["riskLimitValue"], f"{symbol}.riskLimitValue")
            mmr = _decimal(row["maintenanceMargin"], f"{symbol}.maintenanceMargin")
            imr = _decimal(row["initialMargin"], f"{symbol}.initialMargin")
            max_leverage = _decimal(row["maxLeverage"], f"{symbol}.maxLeverage")
            deduction_raw = row.get("mmDeduction")
            deduction = _decimal(
                deduction_raw, f"{symbol}.mmDeduction", allow_empty=True
            )
            deduction = deduction if deduction is not None else Decimal("0")
            if previous is not None:
                prev_limit, prev_mmr, prev_imr, prev_max_lev, prev_deduction = previous
                if risk_limit <= prev_limit:
                    raise ValueError(f"{symbol}: riskLimitValue must increase across tiers")
                if mmr < prev_mmr or imr < prev_imr:
                    raise ValueError(f"{symbol}: maintenance/initial margin rates cannot decrease")
                if max_leverage > prev_max_lev:
                    raise ValueError(f"{symbol}: maxLeverage cannot increase across tiers")
                if row.get("mmDeduction") in (None, ""):
                    raise ValueError(f"{symbol}: mmDeduction is required above the lowest tier")
                expected = prev_limit * (mmr - prev_mmr) + prev_deduction
                if abs(deduction - expected) > tolerance:
                    raise ValueError(
                        f"{symbol}: tier {row['id']} mmDeduction {deduction} "
                        f"does not match recurrence {expected}"
                    )
            elif row.get("mmDeduction") not in (None, "") and deduction < 0:
                raise ValueError(f"{symbol}: lowest-tier mmDeduction cannot be negative")
            previous = (risk_limit, mmr, imr, max_leverage, deduction)
    return rows


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
    return validate_tier_groups([rows[key] for key in sorted(rows)])


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



def validate_page_observations(
    observations: Any, *, expected_symbols: set[str],
    collection_started_at: str, fetched_at: str,
) -> list[dict[str, Any]]:
    if not isinstance(observations, list) or not observations:
        raise ValueError("page_observations must be a non-empty list")
    started_collection = _snapshot_timestamp(collection_started_at)
    completed_collection = _snapshot_timestamp(fetched_at)
    validated = []
    observed_symbols: set[str] = set()
    previous_completed: str | None = None
    for expected_index, item in enumerate(observations, start=1):
        if not isinstance(item, dict) or set(item) != {
            "page_index", "request_started_at", "request_completed_at",
            "tier_count", "symbol_count", "symbols", "has_next_page",
        }:
            raise ValueError("risk page observation fields do not match schema")
        if type(item["page_index"]) is not int or item["page_index"] != expected_index:
            raise ValueError("risk page indexes must be sequential")
        request_started = _snapshot_timestamp(item["request_started_at"])
        request_completed = _snapshot_timestamp(item["request_completed_at"])
        if request_started > request_completed:
            raise ValueError("risk page request starts after completion")
        if request_started < started_collection or request_completed > completed_collection:
            raise ValueError("risk page request is outside collection bounds")
        if previous_completed is not None and request_started < previous_completed:
            raise ValueError("risk page observations are not chronological")
        if type(item["tier_count"]) is not int or item["tier_count"] < 0:
            raise ValueError("risk page tier_count must be a non-negative integer")
        symbols = item["symbols"]
        if not isinstance(symbols, list) or any(
            not isinstance(symbol, str) or not symbol.strip() for symbol in symbols
        ):
            raise ValueError("risk page symbols must be non-empty strings")
        normalized_symbols = [symbol.strip().upper() for symbol in symbols]
        if normalized_symbols != sorted(set(normalized_symbols)):
            raise ValueError("risk page symbols must be unique and sorted")
        if type(item["symbol_count"]) is not int or item["symbol_count"] != len(normalized_symbols):
            raise ValueError("risk page symbol_count does not match symbols")
        if item["symbol_count"] > item["tier_count"]:
            raise ValueError("risk page symbol_count cannot exceed tier_count")
        if type(item["has_next_page"]) is not bool:
            raise ValueError("risk page has_next_page must be boolean")
        if expected_index < len(observations) and not item["has_next_page"]:
            raise ValueError("risk page is missing continuation link")
        if expected_index == len(observations) and item["has_next_page"]:
            raise ValueError("last risk page cannot have continuation")
        observed_symbols.update(normalized_symbols)
        validated.append({
            **item, "request_started_at": request_started,
            "request_completed_at": request_completed,
            "symbols": normalized_symbols,
        })
        previous_completed = request_completed
    if observed_symbols != expected_symbols:
        raise ValueError("risk page symbols do not match snapshot tiers")
    if sum(item["tier_count"] for item in validated) != sum(
        item["tier_count"] for item in observations
    ):
        raise ValueError("risk page tier counts do not match snapshot tiers")
    return validated


def build_snapshot(
    rows: list[dict[str, Any]], category: str,
    fetched_at: str | None = None, *,
    collection_started_at: str | None = None,
    page_observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    timestamp = _snapshot_timestamp(fetched_at)
    individually_validated = [validate_tier(row) for row in rows]
    keys = [(row["symbol"], row["id"]) for row in individually_validated]
    if not individually_validated or len(keys) != len(set(keys)):
        raise ValueError("snapshot requires non-empty unique symbol/risk-tier rows")
    validated = validate_tier_groups(individually_validated)
    symbols = sorted({row["symbol"] for row in validated})
    snapshot = {
        "schema_version": 1,
        "source": "Bybit V5 GET /v5/market/risk-limit",
        "category": category,
        "fetched_at": timestamp,
        "symbol_count": len(symbols),
        "tier_count": len(validated),
        "tiers": validated,
    }
    if collection_started_at is not None:
        started = _snapshot_timestamp(collection_started_at)
        if started > timestamp:
            raise ValueError("collection_started_at cannot be after fetched_at")
        snapshot["collection_started_at"] = started
    if page_observations is not None:
        if collection_started_at is None:
            raise ValueError("page observations require collection_started_at")
        snapshot["page_observations"] = validate_page_observations(
            page_observations, expected_symbols=set(symbols),
            collection_started_at=collection_started_at, fetched_at=timestamp,
        )
    return snapshot


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

    collection_started_at = _snapshot_timestamp(None)
    page_observations: list[dict[str, Any]] = []

    def fetch(cursor: str | None):
        request_started_at = _snapshot_timestamp(None)
        page, next_cursor = _request_page(args.base_url, args.category, cursor)
        request_completed_at = _snapshot_timestamp(None)
        symbols = sorted({str(row["symbol"]).strip().upper() for row in page})
        page_observations.append({
            "page_index": len(page_observations) + 1,
            "request_started_at": request_started_at,
            "request_completed_at": request_completed_at,
            "tier_count": len(page),
            "symbol_count": len(symbols),
            "symbols": symbols,
            "has_next_page": next_cursor is not None,
        })
        if next_cursor and args.pause:
            time.sleep(args.pause)
        return page, next_cursor

    rows = fetch_all_tiers(args.category, fetch)
    snapshot = build_snapshot(
        rows, args.category,
        collection_started_at=collection_started_at,
        page_observations=page_observations,
    )
    fetched = datetime.fromisoformat(snapshot["fetched_at"].replace("Z", "+00:00"))
    stamp = fetched.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    output = Path(args.output_dir) / args.category / f"{stamp}.json"
    write_snapshot(snapshot, output)
    print(f"Saved {len(rows)} risk tiers across {snapshot['symbol_count']} symbols to {output}")


if __name__ == "__main__":
    main()
