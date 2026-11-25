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
import shutil
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


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def validate_raw_response_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Verify raw bodies, one-to-one page links, and normalized archive outputs."""
    manifest_path = Path(manifest_path)
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"ok": False, "errors": ["manifest_missing_or_invalid"], "records": 0}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("source") != "Bybit V5 public GET raw responses":
        return {"ok": False, "errors": ["manifest_identity_invalid"], "records": 0}

    records = manifest.get("records")
    pages_by_stream = manifest.get("collection_pages")
    normalized = manifest.get("normalized_outputs")
    if not isinstance(records, list) or not records:
        errors.append("records_missing")
        records = []
    required_streams = ("funding", "trade_kline", "mark_price")
    if not isinstance(pages_by_stream, dict) or set(pages_by_stream) != set(required_streams):
        errors.append("collection_streams_invalid")
        pages_by_stream = {}
    if not isinstance(normalized, dict) or set(normalized) != {"funding_csv", "trade_kline_csv", "mark_price_csv"}:
        errors.append("normalized_outputs_invalid")
        normalized = {}

    raw_root = manifest_path.parent.resolve()
    archive_root = raw_root.parent.parent
    records_by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            errors.append("record_invalid")
            continue
        request_id = record.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            errors.append("request_id_missing")
            continue
        if request_id in records_by_id:
            errors.append("duplicate_request_id")
        records_by_id[request_id] = record
        request = record.get("request")
        if not isinstance(request, dict) or request.get("method") != "GET":
            errors.append("request_identity_invalid")
        if type(record.get("http_status")) is not int or record["http_status"] != 200:
            errors.append("http_status_not_200")
        digest = record.get("body_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            errors.append("body_hash_invalid")
        if type(record.get("body_bytes")) is not int or record["body_bytes"] < 0:
            errors.append("body_size_invalid")
        for key in ("body_file", "audit_file"):
            relative = record.get(key)
            if not isinstance(relative, str) or not relative:
                errors.append(f"{key}_missing")
                continue
            target = (raw_root / relative).resolve()
            try:
                target.relative_to(raw_root)
            except ValueError:
                errors.append(f"{key}_escapes_manifest_root")
                continue
            if not target.is_file():
                errors.append(f"{key}_not_found")
                continue
            if key == "body_file":
                body = target.read_bytes()
                if hashlib.sha256(body).hexdigest() != digest:
                    errors.append("raw_body_hash_mismatch")
                if len(body) != record.get("body_bytes"):
                    errors.append("raw_body_size_mismatch")
            else:
                try:
                    audit = json.loads(target.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    errors.append("audit_record_invalid")
                    continue
                if audit != record:
                    errors.append("audit_record_content_mismatch")

    referenced: list[str] = []
    for stream in required_streams:
        pages = pages_by_stream.get(stream)
        if not isinstance(pages, list) or not pages:
            errors.append(f"{stream}_pages_missing")
            continue
        for page in pages:
            if not isinstance(page, dict):
                errors.append("collection_page_invalid")
                continue
            request_id = page.get("raw_response_request_id")
            body_hash = page.get("raw_response_body_sha256")
            audit_file = page.get("raw_response_audit_file")
            if not isinstance(request_id, str) or not request_id:
                errors.append("collection_page_request_id_missing")
                continue
            referenced.append(request_id)
            record = records_by_id.get(request_id)
            if record is None:
                errors.append("collection_page_raw_record_missing")
                continue
            if record.get("body_sha256") != body_hash:
                errors.append("collection_page_raw_hash_mismatch")
            if audit_file != record.get("audit_file"):
                errors.append("collection_page_audit_path_mismatch")
            for field in ("request_start_ms", "request_end_ms", "response_rows"):
                value = page.get(field)
                if type(value) is not int or value < 0:
                    errors.append(f"collection_page_{field}_invalid")
            if type(page.get("request_start_ms")) is int and type(page.get("request_end_ms")) is int:
                if page["request_end_ms"] < page["request_start_ms"]:
                    errors.append("collection_page_time_range_invalid")
            if stream == "funding":
                if type(page.get("complete")) is not bool or type(page.get("saturated")) is not bool:
                    errors.append("funding_page_saturation_metadata_invalid")

    if len(referenced) != len(set(referenced)):
        errors.append("raw_response_referenced_more_than_once")
    if set(referenced) != set(records_by_id):
        errors.append("raw_response_record_unreferenced")

    for key, item in normalized.items():
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append(f"{key}_path_missing")
            continue
        target = (raw_root / item["path"]).resolve()
        try:
            target.relative_to(archive_root.resolve())
        except ValueError:
            errors.append(f"{key}_escapes_archive_root")
            continue
        if not target.is_file():
            errors.append(f"{key}_not_found")
            continue
        if hashlib.sha256(target.read_bytes()).hexdigest() != item.get("sha256"):
            errors.append(f"{key}_hash_mismatch")
        if type(item.get("rows")) is not int or item["rows"] < 1:
            errors.append(f"{key}_row_count_invalid")
        else:
            with target.open("r", encoding="utf-8", newline="") as handle:
                actual_rows = max(0, sum(1 for _ in csv.reader(handle)) - 1)
            if actual_rows != item["rows"]:
                errors.append(f"{key}_row_count_mismatch")

    return {"ok": not errors, "errors": errors, "records": len(records)}


def _request_json(base_url: str, endpoint: str, params: dict[str, Any],
                  timeout: float = 20.0,
                  raw_evidence_dir: str | Path | None = None,
                  raw_records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    validate_base_url(base_url)
    url = f"{base_url.rstrip('/')}{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "bybit-trading-bot-research/1.0"})
    try:
        with urllib.request.build_opener(_NoRedirectHandler()).open(req, timeout=timeout) as response:
            raw_body = response.read()
            status = int(getattr(response, "status", 200))
            response_headers = {
                name: response.headers.get(name)
                for name in ("Date", "Content-Type", "Content-Length", "Server")
                if response.headers.get(name) is not None
            }
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Bybit market-history HTTP status {exc.code}; body suppressed") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Bybit market-history request failed ({type(exc).__name__})") from exc

    if raw_evidence_dir is not None:
        root = Path(raw_evidence_dir)
        body_sha256 = hashlib.sha256(raw_body).hexdigest()
        body_relative = f"bodies/{body_sha256}.json"
        request_identity = {
            "method": "GET", "base_url": base_url.rstrip("/"),
            "endpoint": endpoint, "params": params,
        }
        request_id = hashlib.sha256(json.dumps(
            request_identity, sort_keys=True, separators=(",", ":")
        ).encode("utf-8") + body_sha256.encode("ascii")).hexdigest()
        audit_relative = f"requests/{request_id}.json"
        record = {
            "schema_version": 1,
            "request_id": request_id,
            "request": request_identity,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "http_status": status,
            "response_headers": response_headers,
            "body_bytes": len(raw_body),
            "body_sha256": body_sha256,
            "body_file": body_relative,
            "audit_file": audit_relative,
        }
        body_path = root / body_relative
        if body_path.exists() and hashlib.sha256(body_path.read_bytes()).hexdigest() != body_sha256:
            raise RuntimeError("existing raw response body failed its content-addressed hash")
        if not body_path.exists():
            _atomic_write_bytes(body_path, raw_body)
        audit_path = root / audit_relative
        if audit_path.exists():
            try:
                existing = json.loads(audit_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError("existing raw response audit record is invalid") from exc
            if existing != record:
                # A repeated identical request may be captured at a different time.
                # Keep each observation distinct without overwriting prior evidence.
                request_id = hashlib.sha256(
                    (request_id + record["retrieved_at_utc"]).encode("utf-8")
                ).hexdigest()
                record["request_id"] = request_id
                record["audit_file"] = f"requests/{request_id}.json"
                audit_path = root / record["audit_file"]
        _atomic_write_bytes(audit_path, (json.dumps(
            record, ensure_ascii=False, sort_keys=True, indent=2
        ) + "\n").encode("utf-8"))
        if raw_records is not None:
            raw_records.append(record)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Bybit response body is not valid UTF-8 JSON") from exc
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
            raw_ts = raw["fundingRateTimestamp"]
            if isinstance(raw_ts, bool):
                raise ValueError("boolean timestamp")
            if isinstance(raw_ts, int):
                ts = raw_ts
            elif isinstance(raw_ts, str) and raw_ts.isascii() and raw_ts.isdigit():
                ts = int(raw_ts)
            else:
                raise ValueError("timestamp must be an integer or digit string")
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
                          audit_pages: list[dict[str, Any]] | None = None,
                          raw_evidence_dir: str | Path | None = None,
                          raw_records: list[dict[str, Any]] | None = None
                          ) -> list[dict[str, Any]]:
    symbol = normalize_symbol(symbol)
    if start_ms <= 0 or end_ms <= start_ms or pause < 0:
        raise ValueError("valid symbol, range and non-negative pause are required")
    if fetch_page is None:
        fetch_page = lambda start, end: _request_json(
            base_url, FUNDING_ENDPOINT,
            {"category": "linear", "symbol": symbol, "startTime": start,
             "endTime": end, "limit": FUNDING_LIMIT},
            raw_evidence_dir=raw_evidence_dir, raw_records=raw_records,
        ).get("list")
    events: dict[int, dict[str, Any]] = {}

    def fetch_window(window_start: int, window_end: int) -> None:
        raw_count_before = len(raw_records) if raw_records is not None else 0
        page = parse_funding_rows(fetch_page(window_start, window_end - 1), symbol)
        raw_record = (raw_records[-1] if raw_records is not None
                      and len(raw_records) > raw_count_before else None)
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
                "raw_response_request_id": raw_record.get("request_id") if raw_record else None,
                "raw_response_body_sha256": raw_record.get("body_sha256") if raw_record else None,
                "raw_response_audit_file": raw_record.get("audit_file") if raw_record else None,
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
                       base_url: str = DEFAULT_BASE_URL, pause: float = 0.1,
                       raw_evidence_dir: str | Path | None = None,
                       raw_records: list[dict[str, Any]] | None = None,
                       audit_pages: list[dict[str, Any]] | None = None
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
            raw_evidence_dir=raw_evidence_dir, raw_records=raw_records,
        ).get("list")
    candles: dict[int, dict[str, Any]] = {}
    cursor = start_ms
    chunk_ms = (MARK_LIMIT - 1) * interval_ms
    while cursor < end_ms:
        chunk_end = min(cursor + chunk_ms, end_ms)
        raw_count_before = len(raw_records) if raw_records is not None else 0
        page = parse_trade_rows(fetch_page(cursor, chunk_end - 1, MARK_LIMIT), symbol, interval_ms)
        raw_record = (raw_records[-1] if raw_records is not None
                      and len(raw_records) > raw_count_before else None)
        if audit_pages is not None:
            audit_pages.append({
                "request_start_ms": cursor, "request_end_ms": chunk_end - 1,
                "response_rows": len(page),
                "first_ts": min((row["timestamp_ms"] for row in page), default=None),
                "last_ts": max((row["timestamp_ms"] for row in page), default=None),
                "raw_response_request_id": raw_record.get("request_id") if raw_record else None,
                "raw_response_body_sha256": raw_record.get("body_sha256") if raw_record else None,
                "raw_response_audit_file": raw_record.get("audit_file") if raw_record else None,
            })
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
                      base_url: str = DEFAULT_BASE_URL, pause: float = 0.1,
                      raw_evidence_dir: str | Path | None = None,
                      raw_records: list[dict[str, Any]] | None = None,
                      audit_pages: list[dict[str, Any]] | None = None
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
            raw_evidence_dir=raw_evidence_dir, raw_records=raw_records,
        ).get("list")
    candles: dict[int, dict[str, Any]] = {}
    cursor = start_ms
    chunk_ms = (MARK_LIMIT - 1) * interval_ms
    while cursor < end_ms:
        chunk_end = min(cursor + chunk_ms, end_ms)
        raw_count_before = len(raw_records) if raw_records is not None else 0
        page = parse_mark_rows(fetch_page(cursor, chunk_end - 1, MARK_LIMIT), symbol, interval_ms)
        raw_record = (raw_records[-1] if raw_records is not None
                      and len(raw_records) > raw_count_before else None)
        if audit_pages is not None:
            audit_pages.append({
                "request_start_ms": cursor, "request_end_ms": chunk_end - 1,
                "response_rows": len(page),
                "first_ts": min((row["timestamp_ms"] for row in page), default=None),
                "last_ts": max((row["timestamp_ms"] for row in page), default=None),
                "raw_response_request_id": raw_record.get("request_id") if raw_record else None,
                "raw_response_body_sha256": raw_record.get("body_sha256") if raw_record else None,
                "raw_response_audit_file": raw_record.get("audit_file") if raw_record else None,
            })
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
                   pause: float = 0.1,
                   instrument_snapshot_paths: list[str | Path] | None = None) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    validate_base_url(base_url)
    if pause < 0:
        raise ValueError("pause cannot be negative")
    if not instrument_snapshot_paths:
        raise ValueError("dated instrument snapshots are required for Funding schedule evidence")
    root = Path(output_root)
    funding_path = root / "funding" / f"{symbol.upper()}.csv"
    funding_manifest_path = funding_path.with_suffix(funding_path.suffix + ".audit.json")
    kline_path = root / "kline" / f"{symbol.upper()}.csv"
    mark_path = root / "mark_price" / f"{symbol.upper()}.csv"
    schedule_path = funding_path.parent / f"{symbol}.schedule.json"
    raw_evidence_root = root / "raw_responses" / symbol.upper()
    raw_manifest_path = raw_evidence_root / "manifest.json"
    existing_outputs = [
        funding_path, funding_manifest_path, schedule_path, kline_path, mark_path,
        raw_evidence_root,
    ]
    if any(path.exists() for path in existing_outputs):
        raise FileExistsError(
            f"Bybit archive output already exists for {symbol} in {root}; "
            "use a fresh output root rather than overwriting provenance."
        )
    interval_ms = int(interval) * 60_000
    funding_pages: list[dict[str, Any]] = []
    trade_pages: list[dict[str, Any]] = []
    mark_pages: list[dict[str, Any]] = []
    raw_records: list[dict[str, Any]] = []
    # Funding is settled at the final H1 candle CLOSE boundary. Its endpoint
    # uses inclusive endTime, so query through end_ms (exclusive API helper
    # boundary is end_ms + 1) rather than stopping at end_ms - 1.
    try:
        funding = fetch_funding_history(
            symbol, start_ms, end_ms + 1, base_url=base_url, pause=pause,
            audit_pages=funding_pages, raw_evidence_dir=raw_evidence_root,
            raw_records=raw_records,
        )
        klines = fetch_trade_klines(
            symbol, start_ms, end_ms, interval, base_url=base_url, pause=pause,
            raw_evidence_dir=raw_evidence_root, raw_records=raw_records,
            audit_pages=trade_pages,
        )
    except Exception:
        shutil.rmtree(raw_evidence_root, ignore_errors=True)
        raise
    _atomic_csv(funding_path, ["symbol", "funding_timestamp_ms", "funding_rate"], funding)
    from funding_archive_manifest import record_funding_collection
    funding_manifest = record_funding_collection(
        funding_path, funding_manifest_path, symbol=symbol, category="linear",
        api_base=base_url, requested_start_ms=start_ms,
        requested_end_ms=end_ms, pages=funding_pages,
        collected_at_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
    )
    from funding_archive_manifest import attach_funding_settlement_schedule
    schedule = attach_funding_settlement_schedule(
        funding_path, funding_manifest_path, symbol=symbol, category="linear",
        required_start_ms=start_ms, required_end_ms=end_ms,
        snapshot_paths=instrument_snapshot_paths,
        snapshot_copy_dir=root / "instrument_snapshots",
    )
    # A settlement exactly at end_ms needs the Mark candle whose OPEN is at
    # that boundary. Keep trade OHLCV end-exclusive, and fetch one additional
    # closed Mark candle only when the dated settlement grid requires it.
    terminal_settlement = end_ms in set(schedule["expected_settlement_timestamps_ms"])
    mark_end_exclusive = end_ms + interval_ms if terminal_settlement else end_ms
    try:
        marks = fetch_mark_klines(
            symbol, start_ms, mark_end_exclusive, interval, base_url=base_url, pause=pause,
            raw_evidence_dir=raw_evidence_root, raw_records=raw_records,
            audit_pages=mark_pages,
        )
        _atomic_csv(kline_path, ["symbol", "timestamp_ms", "open", "high", "low", "close", "volume", "turnover"], klines)
        _atomic_csv(mark_path, ["symbol", "timestamp_ms", "open", "high", "low", "close"], marks)
    except Exception:
        # Do not strand a partially written archive when the extra terminal
        # Mark candle is not yet closed or unavailable. Snapshot copies are
        # content-addressed and safe to reuse on a retry in the same output root.
        for path in (funding_path, funding_manifest_path, schedule_path, kline_path, mark_path):
            path.unlink(missing_ok=True)
        shutil.rmtree(raw_evidence_root, ignore_errors=True)
        raise

    raw_manifest = {
        "schema_version": 1,
        "source": "Bybit V5 public GET raw responses",
        "symbol": symbol.upper(),
        "category": "linear",
        "interval": interval,
        "normalized_outputs": {
            "funding_csv": {
                "path": os.path.relpath(funding_path, raw_evidence_root).replace(os.sep, "/"),
                "sha256": hashlib.sha256(funding_path.read_bytes()).hexdigest(),
                "rows": len(funding),
            },
            "trade_kline_csv": {
                "path": os.path.relpath(kline_path, raw_evidence_root).replace(os.sep, "/"),
                "sha256": hashlib.sha256(kline_path.read_bytes()).hexdigest(),
                "rows": len(klines),
            },
            "mark_price_csv": {
                "path": os.path.relpath(mark_path, raw_evidence_root).replace(os.sep, "/"),
                "sha256": hashlib.sha256(mark_path.read_bytes()).hexdigest(),
                "rows": len(marks),
            },
        },
        "collection_pages": {
            "funding": funding_pages,
            "trade_kline": trade_pages,
            "mark_price": mark_pages,
        },
        "records": raw_records,
    }
    raw_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_bytes(
        raw_manifest_path,
        (json.dumps(raw_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
    )
    raw_validation = validate_raw_response_manifest(raw_manifest_path)
    if not raw_validation["ok"]:
        raise RuntimeError(f"raw response evidence validation failed: {raw_validation['errors']}")
    return {
        "symbol": symbol.upper(), "funding_events": len(funding), "trade_candles": len(klines), "mark_candles": len(marks),
        "start_ms": start_ms, "end_exclusive_ms": end_ms,
        "funding_file": str(funding_path), "funding_manifest_file": str(funding_manifest_path),
        "funding_file_sha256": funding_manifest["csv_sha256"],
        "funding_manifest_sha256": hashlib.sha256(funding_manifest_path.read_bytes()).hexdigest(),
        "funding_schedule_file": str(funding_path.parent / f"{symbol}.schedule.json"),
        "funding_schedule_sha256": hashlib.sha256(
            (funding_path.parent / f"{symbol}.schedule.json").read_bytes()
        ).hexdigest(),
        "funding_schedule_events": len(schedule["expected_settlement_timestamps_ms"]),
        "funding_query_pages": len(funding_pages),
        "funding_complete_query_pages": sum(1 for page in funding_pages if page.get("complete")),
        "trade_kline_file": str(kline_path), "mark_file": str(mark_path),
        "raw_response_manifest_file": str(raw_manifest_path),
        "raw_response_manifest_sha256": hashlib.sha256(raw_manifest_path.read_bytes()).hexdigest(),
        "raw_response_count": len(raw_records),
        "raw_response_manifest_valid": raw_validation["ok"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", required=True, help="Comma-separated linear symbols")
    parser.add_argument("--start-ms", required=True, type=int)
    parser.add_argument("--end-ms", required=True, type=int, help="Exclusive end timestamp")
    parser.add_argument("--universe-snapshot", required=True, help="Repository-relative Bybit linear universe snapshot JSON")
    parser.add_argument("--interval", default="60", choices=sorted(INTERVALS))
    parser.add_argument("--output-root", default="data/archives/bybit")
    parser.add_argument(
        "--instrument-snapshot-dir", default="data/instrument_specs/linear",
        help="Directory of dated Bybit instruments-info snapshots used to evidence Funding interval",
    )
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
    snapshot_dir = Path(args.instrument_snapshot_dir)
    snapshot_paths = sorted(snapshot_dir.glob("*.json")) if snapshot_dir.is_dir() else []
    if not snapshot_paths:
        parser.error(
            f"no dated Bybit instrument snapshots found in {snapshot_dir}; "
            "Funding schedule completeness cannot be evidenced"
        )
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
            args.interval, args.base_url, args.pause, snapshot_paths,
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
