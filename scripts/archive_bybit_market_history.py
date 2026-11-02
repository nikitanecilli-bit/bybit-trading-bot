#!/usr/bin/env python3
"""Archive official Bybit V5 funding settlements and mark-price klines.

The requested end timestamp is exclusive. Funding requests use bounded
5-day windows (both startTime and endTime are always sent); a full 200-row
page is treated as possibly truncated. Mark klines are fetched in bounded
900-candle windows and must form a complete timestamp grid. CSVs are written
atomically and are compatible with scripts/validate_funding_coverage.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

DEFAULT_BASE_URL = "https://api.bybit.com"
ALLOWED_API_HOSTS = {
    "api.bybit.com", "api.bytick.com", "api.bybit.kz", "api.bybit.tr",
    "api.bybitgeorgia.ge", "api.bybit.ae", "api.bybit.eu", "api.bybit.id",
    "api.bybit.nl", "api.bybit-tr.com",
}
FUNDING_ENDPOINT = "/v5/market/funding/history"
MARK_ENDPOINT = "/v5/market/mark-price-kline"
FUNDING_WINDOW_MS = 5 * 24 * 60 * 60 * 1000
FUNDING_LIMIT = 200
MARK_LIMIT = 900
INTERVALS = {"1", "3", "5", "15", "30", "60", "120", "240", "360", "720"}


def normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,30}", symbol):
        raise ValueError("symbol must contain only 2-30 ASCII letters or digits")
    return symbol


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_base_url(base_url: str) -> None:
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_API_HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("base URL must be an official HTTPS Bybit API host")


def _decimal(value: Any, field: str, *, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not result.is_finite() or (positive and result <= 0):
        raise ValueError(f"invalid {field}")
    return result


def _request_json(base_url: str, endpoint: str, params: dict[str, Any],
                  timeout: float = 20.0) -> dict[str, Any]:
    validate_base_url(base_url)
    url = f"{base_url.rstrip('/')}{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "bybit-trading-bot-research/1.0"})
    try:
        with urllib.request.build_opener(_NoRedirectHandler()).open(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Bybit market-history HTTP status {exc.code}; body suppressed") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Bybit market-history request failed ({type(exc).__name__})") from exc
    if not isinstance(payload, dict):
        raise ValueError("Bybit response root must be an object")
    code = payload.get("retCode")
    if isinstance(code, bool) or not isinstance(code, int) or code != 0:
        raise RuntimeError("Bybit market-history returned non-zero or invalid retCode")
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("list"), list):
        raise ValueError("unexpected Bybit market-history response shape")
    return result


def parse_funding_rows(rows: Any, symbol: str) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("funding list must be an array")
    parsed = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("funding row must be an object")
        row_symbol = str(raw.get("symbol") or "").upper()
        if row_symbol != symbol:
            raise ValueError(f"funding symbol mismatch: expected {symbol}, got {row_symbol}")
        try:
            ts = int(raw["fundingRateTimestamp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid funding timestamp") from exc
        rate = _decimal(raw.get("fundingRate"), "funding rate")
        if ts <= 0:
            raise ValueError("funding timestamp must be positive")
        parsed.append({"symbol": symbol, "funding_timestamp_ms": ts, "funding_rate": str(rate)})
    return parsed


def fetch_funding_history(symbol: str, start_ms: int, end_ms: int,
                          fetch_page: Callable[[int, int], list[dict[str, Any]]] | None = None,
                          base_url: str = DEFAULT_BASE_URL, pause: float = 0.1
                          ) -> list[dict[str, Any]]:
    symbol = normalize_symbol(symbol)
    if start_ms <= 0 or end_ms <= start_ms or pause < 0:
        raise ValueError("valid symbol, range and non-negative pause are required")
    if fetch_page is None:
        fetch_page = lambda start, end: _request_json(
            base_url, FUNDING_ENDPOINT,
            {"category": "linear", "symbol": symbol, "startTime": start,
             "endTime": end, "limit": FUNDING_LIMIT},
        ).get("list")
    events: dict[int, dict[str, Any]] = {}
    window_start = start_ms
    while window_start < end_ms:
        window_end = min(window_start + FUNDING_WINDOW_MS, end_ms)
        page = parse_funding_rows(fetch_page(window_start, window_end - 1), symbol)
        if pause and window_end < end_ms:
            time.sleep(pause)
        if len(page) >= FUNDING_LIMIT:
            raise RuntimeError("funding window reached API page limit; reduce window size")
        for row in page:
            ts = row["funding_timestamp_ms"]
            if not (window_start <= ts < window_end):
                raise ValueError("funding timestamp outside requested window")
            if ts in events and events[ts] != row:
                raise ValueError(f"conflicting duplicate funding timestamp: {ts}")
            events[ts] = row
        window_start = window_end
    if not events:
        raise RuntimeError(f"Bybit returned no funding events for {symbol} in requested range")
    return [events[ts] for ts in sorted(events)]


def parse_mark_rows(rows: Any, symbol: str, interval_ms: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("mark kline list must be an array")
    parsed = []
    for raw in rows:
        if not isinstance(raw, (list, tuple)) or len(raw) < 5:
            raise ValueError("mark kline row must contain timestamp and OHLC")
        try:
            ts = int(raw[0])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid mark kline timestamp") from exc
        o, h, low, c = [_decimal(raw[i], "mark OHLC", positive=True) for i in range(1, 5)]
        if ts <= 0 or ts % interval_ms != 0:
            raise ValueError("mark kline timestamp is not interval-aligned")
        if h < max(o, low, c) or low > min(o, h, c):
            raise ValueError("invalid mark OHLC ordering")
        parsed.append({
            "symbol": symbol, "timestamp_ms": ts,
            "open": str(o), "high": str(h), "low": str(low), "close": str(c),
        })
    return parsed


def fetch_mark_klines(symbol: str, start_ms: int, end_ms: int, interval: str = "60",
                      fetch_page: Callable[[int, int, int], list[Any]] | None = None,
                      base_url: str = DEFAULT_BASE_URL, pause: float = 0.1
                      ) -> list[dict[str, Any]]:
    symbol = symbol.strip().upper()
    if not symbol or interval not in INTERVALS or start_ms <= 0 or end_ms <= start_ms or pause < 0:
        raise ValueError("valid symbol, interval, range and non-negative pause are required")
    interval_ms = int(interval) * 60_000
    if start_ms % interval_ms or end_ms % interval_ms:
        raise ValueError("mark range boundaries must align to the selected interval")
    if fetch_page is None:
        fetch_page = lambda start, end, limit: _request_json(
            base_url, MARK_ENDPOINT,
            {"category": "linear", "symbol": symbol, "interval": interval,
             "start": start, "end": end, "limit": limit},
        ).get("list")
    candles: dict[int, dict[str, Any]] = {}
    cursor = start_ms
    chunk_ms = (MARK_LIMIT - 1) * interval_ms
    while cursor < end_ms:
        chunk_end = min(cursor + chunk_ms, end_ms)
        page = parse_mark_rows(fetch_page(cursor, chunk_end - 1, MARK_LIMIT), symbol, interval_ms)
        if pause and chunk_end < end_ms:
            time.sleep(pause)
        if len(page) >= MARK_LIMIT:
            raise RuntimeError("mark kline chunk reached API page limit; reduce chunk size")
        for row in page:
            ts = row["timestamp_ms"]
            if not (cursor <= ts < chunk_end):
                raise ValueError("mark candle outside requested chunk")
            if ts in candles and candles[ts] != row:
                raise ValueError(f"conflicting duplicate mark candle: {ts}")
            candles[ts] = row
        cursor = chunk_end
    expected = range(start_ms, end_ms, interval_ms)
    missing = [ts for ts in expected if ts not in candles]
    if missing:
        raise RuntimeError(
            f"incomplete mark kline coverage: {len(missing)} missing; first={missing[:5]}"
        )
    return [candles[ts] for ts in sorted(candles)]


def _atomic_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
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


def archive_symbol(symbol: str, start_ms: int, end_ms: int, output_root: str | Path,
                   interval: str = "60", base_url: str = DEFAULT_BASE_URL,
                   pause: float = 0.1) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    validate_base_url(base_url)
    if pause < 0:
        raise ValueError("pause cannot be negative")
    funding = fetch_funding_history(symbol, start_ms, end_ms, base_url=base_url, pause=pause)
    marks = fetch_mark_klines(symbol, start_ms, end_ms, interval, base_url=base_url, pause=pause)
    root = Path(output_root)
    funding_path = root / "funding" / f"{symbol.upper()}.csv"
    mark_path = root / "mark_price" / f"{symbol.upper()}.csv"
    _atomic_csv(funding_path, ["symbol", "funding_timestamp_ms", "funding_rate"], funding)
    _atomic_csv(mark_path, ["symbol", "timestamp_ms", "open", "high", "low", "close"], marks)
    return {
        "symbol": symbol.upper(), "funding_events": len(funding), "mark_candles": len(marks),
        "start_ms": start_ms, "end_exclusive_ms": end_ms,
        "funding_file": str(funding_path), "mark_file": str(mark_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", required=True, help="Comma-separated linear symbols")
    parser.add_argument("--start-ms", required=True, type=int)
    parser.add_argument("--end-ms", required=True, type=int, help="Exclusive end timestamp")
    parser.add_argument("--interval", default="60", choices=sorted(INTERVALS))
    parser.add_argument("--output-root", default="data/archives/bybit")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--pause", type=float, default=0.1)
    args = parser.parse_args()
    symbols = [normalize_symbol(s) for s in args.symbols.split(",") if s.strip()]
    if not symbols or len(symbols) != len(set(symbols)):
        parser.error("--symbols must contain unique non-empty symbols")
    results = []
    for symbol in symbols:
        results.append(archive_symbol(
            symbol, args.start_ms, args.end_ms, args.output_root,
            args.interval, args.base_url, args.pause,
        ))
    report = {
        "source": "Bybit V5 funding history + mark price kline",
        "category": "linear", "interval": args.interval,
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "results": results,
    }
    report_path = Path(args.output_root) / "archive_manifest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = report_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, report_path)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
