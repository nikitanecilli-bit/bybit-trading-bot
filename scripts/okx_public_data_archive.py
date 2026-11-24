#!/usr/bin/env python3
"""Read-only OKX public market-data archive for one linear swap.

No credentials, account endpoints, order endpoints, proxies, or alternate hosts.
Raw response bodies are preserved alongside normalized CSVs and a SHA-256 manifest.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://www.okx.com"
INSTRUMENT = "BTC-USDT-SWAP"
BAR = "1H"
HOUR_MS = 3_600_000
PAGE_LIMIT = 100
USER_AGENT = "research-okx-public-data-archive/1.0"
ENDPOINTS = {
    "candles": "/api/v5/market/history-candles",
    "mark_price": "/api/v5/market/history-mark-price-candles",
    "funding": "/api/v5/public/funding-rate-history",
    "instrument": "/api/v5/public/instruments",
}


def utc_now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def iso_utc(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> int:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("timestamps must include a timezone, preferably Z")
    stamp = int(dt.astimezone(timezone.utc).timestamp() * 1000)
    if stamp % HOUR_MS:
        raise ValueError("H1 range boundaries must align to an exact UTC hour")
    return stamp


def request_json(url: str, timeout: int = 25) -> tuple[bytes, dict[str, Any]]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(
            f"OKX public API request failed for {url}: {exc}. "
            "No proxy, mirror, or alternate host is configured; check direct access from this machine."
        ) from exc
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"OKX returned non-JSON content for {url}") from exc
    if not isinstance(payload, dict) or payload.get("code") != "0":
        code = payload.get("code") if isinstance(payload, dict) else "invalid response"
        message = payload.get("msg", "") if isinstance(payload, dict) else ""
        raise RuntimeError(f"OKX API error code={code!r} msg={message!r} url={url}")
    return body, payload


def build_url(endpoint: str, params: dict[str, Any]) -> str:
    return f"{BASE_URL}{endpoint}?{urlencode({k: str(v) for k, v in params.items()})}"


def parse_candle(row: Any, source: str) -> dict[str, Any]:
    if not isinstance(row, list) or len(row) < 5:
        raise ValueError(f"{source}: candle row must contain timestamp and OHLC")
    try:
        ts = int(row[0])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source}: invalid candle timestamp {row[0]!r}") from exc
    if ts <= 0 or ts % HOUR_MS:
        raise ValueError(f"{source}: timestamp is not aligned to UTC H1: {ts}")
    values = [str(x) for x in row[1:5]]
    try:
        o, h, low, c = map(float, values)
    except ValueError as exc:
        raise ValueError(f"{source}: non-numeric OHLC at {ts}") from exc
    if not all(map(lambda x: x > 0 and x < float("inf"), (o, h, low, c))):
        raise ValueError(f"{source}: non-finite or non-positive OHLC at {ts}")
    if h < max(o, low, c) or low > min(o, h, c):
        raise ValueError(f"{source}: invalid OHLC ordering at {ts}")
    result = {
        "timestamp_ms": ts, "timestamp_utc": iso_utc(ts),
        "open": values[0], "high": values[1], "low": values[2], "close": values[3],
    }
    if len(row) > 5:
        result["confirm"] = str(row[8]) if len(row) > 8 else str(row[5])
    if source == "candles":
        result.update({
            "volume": str(row[5]) if len(row) > 5 else "",
            "volume_currency": str(row[6]) if len(row) > 6 else "",
            "volume_quote": str(row[7]) if len(row) > 7 else "",
            "confirm": str(row[8]) if len(row) > 8 else "",
        })
    return result


def parse_funding(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("funding row must be an object")
    try:
        ts = int(row["fundingTime"])
        rate = float(row["fundingRate"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("funding row has invalid fundingTime/fundingRate") from exc
    if ts <= 0 or not (rate == rate and abs(rate) != float("inf")):
        raise ValueError("funding row has invalid timestamp or non-finite rate")
    return {
        "funding_time_ms": ts, "funding_time_utc": iso_utc(ts),
        "funding_rate": str(row["fundingRate"]),
        "realized_rate": str(row.get("realizedRate", "")),
        "formula_type": str(row.get("formulaType", "")),
        "method": str(row.get("method", "")),
    }


def _save_raw(root: Path, dataset: str, page_number: int, url: str,
              body: bytes, payload: dict[str, Any]) -> dict[str, Any]:
    folder = root / "raw" / dataset
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"page_{page_number:05d}.json"
    path.write_bytes(body)
    rows = payload.get("data", [])
    timestamps: list[int] = []
    for row in rows if isinstance(rows, list) else []:
        raw_ts = row.get("fundingTime") if isinstance(row, dict) else (row[0] if isinstance(row, list) and row else None)
        try:
            if raw_ts is not None:
                timestamps.append(int(raw_ts))
        except (TypeError, ValueError):
            pass
    return {
        "page": page_number, "url": url, "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_file": str(path.relative_to(root)), "raw_bytes": len(body),
        "raw_sha256": hashlib.sha256(body).hexdigest(), "response_rows": len(rows) if isinstance(rows, list) else 0,
        "min_timestamp_ms": min(timestamps) if timestamps else None,
        "max_timestamp_ms": max(timestamps) if timestamps else None,
    }


def fetch_paged(dataset: str, endpoint: str, base_params: dict[str, Any], start_ms: int,
                end_ms: int, root: Path, fetch: Callable[[str], tuple[bytes, dict[str, Any]]],
                pause: float, max_pages: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cursor: int | None = None
    seen: set[int] = set()
    rows_by_ts: dict[int, dict[str, Any]] = {}
    pages: list[dict[str, Any]] = []
    for page_number in range(1, max_pages + 1):
        params = dict(base_params)
        if cursor is not None:
            params["after"] = cursor
        url = build_url(endpoint, params)
        body, payload = fetch(url)
        raw_meta = _save_raw(root, dataset, page_number, url, body, payload)
        raw_rows = payload.get("data")
        if not isinstance(raw_rows, list):
            raise ValueError(f"{dataset}: response data is not an array")
        parsed = [parse_funding(x) if dataset == "funding" else parse_candle(x, dataset) for x in raw_rows]
        ts_key = "funding_time_ms" if dataset == "funding" else "timestamp_ms"
        timestamps = [int(x[ts_key]) for x in parsed]
        if any(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1)):
            raise ValueError(f"{dataset}: page timestamps are not strictly newest-first")
        if timestamps and cursor is not None and timestamps[0] >= cursor:
            raise ValueError(f"{dataset}: pagination did not move strictly into older data")
        for item in parsed:
            ts = int(item[ts_key])
            if ts in seen:
                raise ValueError(f"{dataset}: duplicate timestamp across pages: {ts}")
            seen.add(ts)
            if start_ms <= ts < end_ms:
                rows_by_ts[ts] = item
        pages.append(raw_meta)
        if not timestamps or min(timestamps) <= start_ms or len(raw_rows) < PAGE_LIMIT:
            break
        cursor = min(timestamps)
        if pause:
            time.sleep(pause)
    else:
        raise RuntimeError(f"{dataset}: reached --max-pages={max_pages} before covering start time")
    ordered = [rows_by_ts[k] for k in sorted(rows_by_ts)]
    return ordered, pages


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def hourly_grid_report(rows: list[dict[str, Any]], start_ms: int, end_ms: int) -> dict[str, Any]:
    expected = list(range(start_ms, end_ms, HOUR_MS))
    actual = {int(row["timestamp_ms"]) for row in rows}
    missing = [ts for ts in expected if ts not in actual]
    extra = sorted(actual.difference(expected))
    unconfirmed = [row["timestamp_ms"] for row in rows if "confirm" in row and row["confirm"] != "1"]
    return {
        "expected_rows": len(expected), "actual_rows": len(rows),
        "missing_count": len(missing), "missing_first_20_utc": [iso_utc(x) for x in missing[:20]],
        "extra_count": len(extra), "duplicates": len(actual) != len(rows),
        "unconfirmed_count": len(unconfirmed), "unconfirmed_first_20_utc": [iso_utc(x) for x in unconfirmed[:20]],
        "complete": not missing and not extra and not unconfirmed and len(actual) == len(rows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instrument", default=INSTRUMENT, help="OKX instrument ID (default: BTC-USDT-SWAP)")
    parser.add_argument("--start", help="UTC ISO timestamp, inclusive, exact hour; e.g. 2026-10-01T00:00:00Z")
    parser.add_argument("--end", help="UTC ISO timestamp, exclusive, exact hour; defaults to latest closed H1 boundary")
    parser.add_argument("--days", type=int, default=365, help="lookback days when --start is omitted (default: 365)")
    parser.add_argument("--output", type=Path, default=Path("data/archives/okx/BTC-USDT-SWAP"))
    parser.add_argument("--pause", type=float, default=0.15, help="seconds between pages (default: 0.15)")
    parser.add_argument("--max-pages", type=int, default=2000, help="safety limit per endpoint")
    args = parser.parse_args(argv)

    if args.instrument != INSTRUMENT:
        parser.error("this first pilot is deliberately restricted to BTC-USDT-SWAP")
    if args.days < 1 or args.pause < 0 or args.max_pages < 1:
        parser.error("--days and --max-pages must be positive; --pause cannot be negative")
    end_ms = parse_time(args.end) if args.end else (utc_now_ms() // HOUR_MS) * HOUR_MS
    start_ms = parse_time(args.start) if args.start else end_ms - args.days * 24 * HOUR_MS
    if start_ms >= end_ms:
        parser.error("--start must be earlier than --end")
    root = args.output
    if root.exists() and any(root.iterdir()):
        parser.error(f"output directory is not empty; refusing to overwrite: {root}")
    root.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "schema_version": 1, "exchange": "OKX", "market": "public market data only",
        "instrument": args.instrument, "instrument_type": "SWAP", "bar": BAR,
        "requested_start_ms_inclusive": start_ms, "requested_start_utc": iso_utc(start_ms),
        "requested_end_ms_exclusive": end_ms, "requested_end_utc": iso_utc(end_ms),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": BASE_URL, "credentials_used": False,
        "notes": [
            "Current instrument metadata is a snapshot, not historical effective-time specifications.",
            "Funding rows are preserved as returned; this tool does not infer missing settlement events from a fixed interval.",
            "Mark price candles are valuation/reference data, not executable trade prices.",
            "No strategy, PnL, backtest, order, or account endpoint is called.",
        ],
        "datasets": {},
    }
    try:
        for dataset, endpoint, params in (
            ("candles", ENDPOINTS["candles"], {"instId": args.instrument, "bar": BAR, "limit": PAGE_LIMIT}),
            ("mark_price", ENDPOINTS["mark_price"], {"instId": args.instrument, "bar": BAR, "limit": PAGE_LIMIT}),
            ("funding", ENDPOINTS["funding"], {"instId": args.instrument, "limit": PAGE_LIMIT}),
        ):
            rows, pages = fetch_paged(
                dataset, endpoint, params, start_ms, end_ms, root, request_json, args.pause, args.max_pages
            )
            filename = {"candles": "candles_h1.csv", "mark_price": "mark_price_h1.csv",
                        "funding": "funding_history.csv"}[dataset]
            write_csv(root / filename, rows)
            dataset_report: dict[str, Any] = {
                "rows": len(rows), "pages": pages, "csv_file": filename,
                "csv_sha256": hashlib.sha256((root / filename).read_bytes()).hexdigest(),
            }
            if dataset in ("candles", "mark_price"):
                dataset_report["hourly_grid"] = hourly_grid_report(rows, start_ms, end_ms)
            manifest["datasets"][dataset] = dataset_report

        instrument_url = build_url(ENDPOINTS["instrument"], {"instType": "SWAP", "instId": args.instrument})
        body, payload = request_json(instrument_url)
        instrument_meta = _save_raw(root, "instrument", 1, instrument_url, body, payload)
        instruments = payload.get("data", [])
        if not isinstance(instruments, list) or len(instruments) != 1:
            raise ValueError(f"instrument endpoint returned {len(instruments) if isinstance(instruments, list) else 'invalid'} rows")
        (root / "instrument_current.json").write_bytes(body)
        manifest["datasets"]["instrument_current"] = {
            **instrument_meta, "file": "instrument_current.json",
            "instrument_state": instruments[0].get("state"),
            "contract_type": instruments[0].get("ctType"),
            "contract_value": instruments[0].get("ctVal"),
            "contract_value_currency": instruments[0].get("ctValCcy"),
            "tick_size": instruments[0].get("tickSz"),
            "lot_size": instruments[0].get("lotSz"),
            "minimum_size": instruments[0].get("minSz"),
        }
        manifest["status"] = "COMPLETE" if all(
            manifest["datasets"][name]["hourly_grid"]["complete"]
            for name in ("candles", "mark_price")
        ) else "INCOMPLETE_HOURLY_COVERAGE"
        manifest["funding_rows"] = manifest["datasets"]["funding"]["rows"]
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": manifest["status"], "output": str(root),
            "candles": manifest["datasets"]["candles"]["rows"],
            "mark_price": manifest["datasets"]["mark_price"]["rows"],
            "funding": manifest["datasets"]["funding"]["rows"],
            "candles_grid": manifest["datasets"]["candles"]["hourly_grid"],
            "mark_grid": manifest["datasets"]["mark_price"]["hourly_grid"],
            "manifest": str(manifest_path),
        }, ensure_ascii=False, indent=2))
        return 0 if manifest["status"] == "COMPLETE" else 2
    except Exception as exc:
        manifest["status"] = "FAILED"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"ERROR: {manifest['error']}", file=sys.stderr)
        print(f"Partial raw responses and manifest preserved in: {root}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
