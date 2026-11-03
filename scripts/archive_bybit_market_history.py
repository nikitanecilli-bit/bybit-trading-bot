#!/usr/bin/env python3
"""Archive official Bybit V5 trade OHLCV, funding settlements and mark-price klines.

The requested end timestamp is exclusive. Funding requests use bounded
5-day windows (both startTime and endTime are always sent); a full 200-row
page triggers recursive window subdivision to avoid silent truncation. Mark klines are fetched in bounded
900-candle windows and must form a complete timestamp grid. CSVs are written
atomically and are compatible with scripts/validate_funding_coverage.py.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

DEFAULT_BASE_URL = "https://api.bybit.com"
ALLOWED_API_HOSTS = {
    "api.bybit.com", "api.bytick.com", "api.bybit.kz", "api.bybit.tr",
    "api.bybitgeorgia.ge", "api.bybit.ae", "api.bybit.eu", "api.bybit.id",
}
FUNDING_ENDPOINT = "/v5/market/funding/history"
KLINE_ENDPOINT = "/v5/market/kline"
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
                          base_url: str = DEFAULT_BASE_URL, pause: float = 0.1,
                          audit_pages: list[dict[str, Any]] | None = None
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

    def fetch_window(window_start: int, window_end: int) -> None:
        page = parse_funding_rows(fetch_page(window_start, window_end - 1), symbol)
        saturated = len(page) >= FUNDING_LIMIT
        if audit_pages is not None:
            page_timestamps = [row["funding_timestamp_ms"] for row in page]
            audit_pages.append({
                "request_start_ms": int(window_start),
                "request_end_ms": int(window_end - 1),
                "response_rows": len(page),
                "first_ts": min(page_timestamps) if page_timestamps else None,
                "last_ts": max(page_timestamps) if page_timestamps else None,
                "complete": not saturated,
                "saturated": saturated,
            })
        if saturated:
            if window_end - window_start <= 1:
                raise RuntimeError("funding page remains saturated at minimum window width")
            midpoint = window_start + (window_end - window_start) // 2
            fetch_window(window_start, midpoint)
            if pause:
                time.sleep(pause)
            fetch_window(midpoint, window_end)
            return
        for row in page:
            ts = row["funding_timestamp_ms"]
            if not (window_start <= ts < window_end):
                raise ValueError("funding timestamp outside requested window")
            if ts in events:
                if events[ts] != row:
                    raise ValueError(f"conflicting duplicate funding timestamp: {ts}")
                raise ValueError(f"duplicate funding timestamp returned by Bybit: {ts}")
            events[ts] = row

    window_start = start_ms
    while window_start < end_ms:
        window_end = min(window_start + FUNDING_WINDOW_MS, end_ms)
        fetch_window(window_start, window_end)
        if pause and window_end < end_ms:
            time.sleep(pause)
        window_start = window_end
    if not events:
        raise RuntimeError(f"Bybit returned no funding events for {symbol} in requested range")
    return [events[ts] for ts in sorted(events)]


def parse_trade_rows(rows: Any, symbol: str, interval_ms: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("trade kline list must be an array")
    parsed = []
    for raw in rows:
        if not isinstance(raw, (list, tuple)) or len(raw) < 7:
            raise ValueError("trade kline row must contain timestamp, OHLC, volume and turnover")
        try:
            ts = int(raw[0])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid trade kline timestamp") from exc
        o, h, low, c = [_decimal(raw[i], "trade OHLC", positive=True) for i in range(1, 5)]
        volume = _decimal(raw[5], "trade volume")
        turnover = _decimal(raw[6], "trade turnover")
        if ts <= 0 or ts % interval_ms != 0:
            raise ValueError("trade kline timestamp is not interval-aligned")
        if volume < 0 or turnover < 0:
            raise ValueError("trade kline volume and turnover must be non-negative")
        if h < max(o, low, c) or low > min(o, h, c):
            raise ValueError("invalid trade OHLC ordering")
        parsed.append({
            "symbol": symbol, "timestamp_ms": ts,
            "open": str(o), "high": str(h), "low": str(low), "close": str(c),
            "volume": str(volume), "turnover": str(turnover),
        })
    return parsed


def fetch_trade_klines(symbol: str, start_ms: int, end_ms: int, interval: str = "60",
                       fetch_page: Callable[[int, int, int], list[Any]] | None = None,
                       base_url: str = DEFAULT_BASE_URL, pause: float = 0.1
                       ) -> list[dict[str, Any]]:
    symbol = normalize_symbol(symbol)
    if interval not in INTERVALS or start_ms <= 0 or end_ms <= start_ms or pause < 0:
        raise ValueError("valid symbol, interval, range and non-negative pause are required")
    interval_ms = int(interval) * 60_000
    if start_ms % interval_ms or end_ms % interval_ms:
        raise ValueError("trade kline range boundaries must align to the selected interval")
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    last_closed_boundary = (now_ms // interval_ms) * interval_ms
    if end_ms > last_closed_boundary:
        raise ValueError("trade kline range end includes an unclosed candle or future interval")
    if fetch_page is None:
        fetch_page = lambda start, end, limit: _request_json(
            base_url, KLINE_ENDPOINT,
            {"category": "linear", "symbol": symbol, "interval": interval,
             "start": start, "end": end, "limit": limit},
        ).get("list")
    candles: dict[int, dict[str, Any]] = {}
    cursor = start_ms
    chunk_ms = (MARK_LIMIT - 1) * interval_ms
    while cursor < end_ms:
        chunk_end = min(cursor + chunk_ms, end_ms)
        page = parse_trade_rows(fetch_page(cursor, chunk_end - 1, MARK_LIMIT), symbol, interval_ms)
        if pause and chunk_end < end_ms:
            time.sleep(pause)
        if len(page) >= MARK_LIMIT:
            raise RuntimeError("trade kline chunk reached API page limit; reduce chunk size")
        for row in page:
            ts = row["timestamp_ms"]
            if not (cursor <= ts < chunk_end):
                raise ValueError("trade candle outside requested chunk")
            if ts in candles and candles[ts] != row:
                raise ValueError(f"conflicting duplicate trade candle: {ts}")
            candles[ts] = row
        cursor = chunk_end
    expected = range(start_ms, end_ms, interval_ms)
    missing = [ts for ts in expected if ts not in candles]
    if missing:
        raise RuntimeError(
            f"incomplete trade kline coverage: {len(missing)} missing; first={missing[:5]}"
        )
    return [candles[ts] for ts in sorted(candles)]


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
    symbol = normalize_symbol(symbol)
    if interval not in INTERVALS or start_ms <= 0 or end_ms <= start_ms or pause < 0:
        raise ValueError("valid symbol, interval, range and non-negative pause are required")
    interval_ms = int(interval) * 60_000
    if start_ms % interval_ms or end_ms % interval_ms:
        raise ValueError("mark range boundaries must align to the selected interval")
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    last_closed_boundary = (now_ms // interval_ms) * interval_ms
    if end_ms > last_closed_boundary:
        raise ValueError("mark range end includes an unclosed candle or future interval")
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


def load_universe_lifecycle(path: str | Path) -> tuple[dict[str, dict[str, Any]], str, str]:
    """Load and validate a dated Bybit linear-universe snapshot."""
    snapshot_path = Path(path).resolve()
    try:
        snapshot_path.relative_to(Path.cwd().resolve())
    except ValueError as exc:
        raise ValueError("universe snapshot must be inside the repository checkout") from exc
    raw_bytes = snapshot_path.read_bytes()
    snapshot = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(snapshot, dict) or snapshot.get("category") != "linear":
        raise ValueError("universe snapshot must be a Bybit linear snapshot")
    instruments = snapshot.get("instruments")
    if not isinstance(instruments, list) or not instruments:
        raise ValueError("universe snapshot must contain a non-empty instruments list")
    fetched_at = snapshot.get("fetched_at")
    if not isinstance(fetched_at, str) or not fetched_at:
        raise ValueError("universe snapshot is missing fetched_at provenance")
    by_symbol: dict[str, dict[str, Any]] = {}
    seen_symbols: set[str] = set()
    for row in instruments:
        if not isinstance(row, dict):
            raise ValueError("universe snapshot instrument must be an object")
        symbol = normalize_symbol(row.get("symbol"))
        if symbol in seen_symbols:
            raise ValueError(f"duplicate symbol in universe snapshot: {symbol}")
        seen_symbols.add(symbol)
        if row.get("contractType") != "LinearPerpetual" or row.get("quoteCoin") != "USDT" or row.get("settleCoin") != "USDT":
            continue
        status = row.get("status")
        if status in {"PreLaunch", "PendingOpen"}:
            continue
        if status not in {"Trading", "Settling", "Delivering", "Closed"}:
            raise ValueError(f"unsupported lifecycle status for {symbol}: {status!r}")
        try:
            launch_ms = int(str(row.get("launchTime")))
            delivery_ms = int(str(row.get("deliveryTime", "0")))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid lifecycle timestamps for {symbol}") from exc
        if launch_ms <= 0 or delivery_ms < 0 or (delivery_ms and delivery_ms < launch_ms):
            raise ValueError(f"invalid lifecycle bounds for {symbol}")
        if status in {"Settling", "Delivering", "Closed"} and delivery_ms == 0:
            raise ValueError(f"{status} instrument {symbol} has no deliveryTime; lifecycle end is unknown")
        by_symbol[symbol] = {"launch_ms": launch_ms, "delivery_ms": delivery_ms, "status": status}
    if not by_symbol:
        raise ValueError("universe snapshot contains no USDT linear perpetual instruments")
    return by_symbol, hashlib.sha256(raw_bytes).hexdigest(), fetched_at


def validate_archive_range(start_ms: int, end_ms: int, interval_ms: int) -> None:
    if interval_ms <= 0 or start_ms <= 0 or end_ms <= start_ms:
        raise ValueError("valid archive range and interval are required")
    if start_ms % interval_ms or end_ms % interval_ms:
        raise ValueError("requested archive range boundaries must align to the selected interval")


def clip_range_to_lifecycle(symbol: str, start_ms: int, end_ms: int, interval_ms: int,
                            lifecycle: dict[str, dict[str, Any]]) -> tuple[int, int]:
    """Clip to complete candles fully inside the instrument's launch/delivery lifecycle."""
    symbol = normalize_symbol(symbol)
    if interval_ms <= 0 or start_ms <= 0 or end_ms <= start_ms:
        raise ValueError("valid range and interval are required")
    if symbol not in lifecycle:
        raise ValueError(f"{symbol} is absent from the supplied Bybit lifecycle snapshot")
    item = lifecycle[symbol]
    launch_ms = item["launch_ms"]
    delivery_ms = item["delivery_ms"]
    first_full_candle = ((launch_ms + interval_ms - 1) // interval_ms) * interval_ms
    last_full_end = (delivery_ms // interval_ms) * interval_ms if delivery_ms else end_ms
    clipped_start = max(start_ms, first_full_candle)
    clipped_end = min(end_ms, last_full_end)
    if clipped_end <= clipped_start:
        raise ValueError(f"requested range has no complete {interval_ms // 60000}-minute candles inside {symbol} lifecycle")
    return clipped_start, clipped_end


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
    funding_pages: list[dict[str, Any]] = []
    funding = fetch_funding_history(
        symbol, start_ms, end_ms, base_url=base_url, pause=pause,
        audit_pages=funding_pages,
    )
    klines = fetch_trade_klines(symbol, start_ms, end_ms, interval, base_url=base_url, pause=pause)
    marks = fetch_mark_klines(symbol, start_ms, end_ms, interval, base_url=base_url, pause=pause)
    root = Path(output_root)
    funding_path = root / "funding" / f"{symbol.upper()}.csv"
    kline_path = root / "kline" / f"{symbol.upper()}.csv"
    mark_path = root / "mark_price" / f"{symbol.upper()}.csv"
    _atomic_csv(funding_path, ["symbol", "funding_timestamp_ms", "funding_rate"], funding)
    from funding_archive_manifest import record_funding_collection
    funding_manifest_path = funding_path.with_suffix(funding_path.suffix + ".audit.json")
    funding_manifest = record_funding_collection(
        funding_path, funding_manifest_path, symbol=symbol, category="linear",
        api_base=base_url, requested_start_ms=start_ms,
        requested_end_ms=end_ms - 1, pages=funding_pages,
        collected_at_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
    )
    _atomic_csv(kline_path, ["symbol", "timestamp_ms", "open", "high", "low", "close", "volume", "turnover"], klines)
    _atomic_csv(mark_path, ["symbol", "timestamp_ms", "open", "high", "low", "close"], marks)
    return {
        "symbol": symbol.upper(), "funding_events": len(funding), "trade_candles": len(klines), "mark_candles": len(marks),
        "start_ms": start_ms, "end_exclusive_ms": end_ms,
        "funding_file": str(funding_path), "funding_manifest_file": str(funding_manifest_path),
        "funding_file_sha256": funding_manifest["csv_sha256"],
        "funding_manifest_sha256": hashlib.sha256(funding_manifest_path.read_bytes()).hexdigest(),
        "funding_query_pages": len(funding_pages),
        "funding_complete_query_pages": sum(1 for page in funding_pages if page.get("complete")),
        "trade_kline_file": str(kline_path), "mark_file": str(mark_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", required=True, help="Comma-separated linear symbols")
    parser.add_argument("--start-ms", required=True, type=int)
    parser.add_argument("--end-ms", required=True, type=int, help="Exclusive end timestamp")
    parser.add_argument("--universe-snapshot", required=True, help="Repository-relative Bybit linear universe snapshot JSON")
    parser.add_argument("--interval", default="60", choices=sorted(INTERVALS))
    parser.add_argument("--output-root", default="data/archives/bybit")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--pause", type=float, default=0.1)
    args = parser.parse_args()
    symbols = [normalize_symbol(s) for s in args.symbols.split(",") if s.strip()]
    if not symbols or len(symbols) != len(set(symbols)):
        parser.error("--symbols must contain unique non-empty symbols")
    lifecycle, universe_sha256, universe_fetched_at = load_universe_lifecycle(args.universe_snapshot)
    interval_ms = int(args.interval) * 60_000
    try:
        validate_archive_range(args.start_ms, args.end_ms, interval_ms)
    except ValueError as exc:
        parser.error(str(exc))
    prepared = []
    for symbol in symbols:
        effective_start, effective_end = clip_range_to_lifecycle(
            symbol, args.start_ms, args.end_ms, interval_ms, lifecycle,
        )
        prepared.append((symbol, effective_start, effective_end))
    results = []
    for symbol, effective_start, effective_end in prepared:
        result = archive_symbol(
            symbol, effective_start, effective_end, args.output_root,
            args.interval, args.base_url, args.pause,
        )
        result.update({
            "requested_start_ms": args.start_ms,
            "requested_end_exclusive_ms": args.end_ms,
            "lifecycle_launch_ms": lifecycle[symbol]["launch_ms"],
            "lifecycle_delivery_ms": lifecycle[symbol]["delivery_ms"],
            "lifecycle_status_at_snapshot": lifecycle[symbol]["status"],
            "lifecycle_clipped": effective_start != args.start_ms or effective_end != args.end_ms,
        })
        results.append(result)
    collector_path = Path(__file__).resolve()
    report = {
        "source": "Bybit V5 trade kline + funding history + mark price kline",
        "collector_script": collector_path.name,
        "collector_script_sha256": hashlib.sha256(collector_path.read_bytes()).hexdigest(),
        "universe_snapshot": args.universe_snapshot,
        "universe_snapshot_sha256": universe_sha256,
        "universe_snapshot_fetched_at": universe_fetched_at,
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
