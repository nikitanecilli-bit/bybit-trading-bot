#!/usr/bin/env python3
"""Download and validate one public Tardis Bybit sample day.

The raw archives are processed in a temporary directory and are not uploaded.
Only a compact report with hashes and validation metrics is retained.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
import tempfile
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median

DATE = "2026-11-01"
SYMBOL = "BTCUSDT"
BASE = "https://datasets.tardis.dev/v1/bybit"
MAX_FILE_BYTES = 100 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


def source_url(dataset: str) -> str:
    year, month, day = DATE.split("-")
    return f"{BASE}/{dataset}/{year}/{month}/{day}/{SYMBOL}.csv.gz"


def download(url: str, path: Path) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": "bybit-tardis-sample-inspector/1.0"}
    )
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as out:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status}")
        expected = response.headers.get("Content-Length")
        while True:
            chunk = response.read(CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise RuntimeError(
                    f"archive exceeds {MAX_FILE_BYTES} byte safety limit"
                )
            out.write(chunk)
            digest.update(chunk)
    if expected is not None and total != int(expected):
        raise RuntimeError(f"download size mismatch: expected={expected}, actual={total}")
    return {"bytes": total, "sha256": digest.hexdigest()}


def strict_positive_int(value: str, field: str, row_no: int) -> int:
    if not value or not value.isdigit():
        raise ValueError(f"invalid {field} at row {row_no}: {value!r}")
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"non-positive {field} at row {row_no}")
    return parsed


def strict_decimal(value: str, field: str, row_no: int, allow_zero: bool) -> Decimal:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"invalid {field} at row {row_no}: {value!r}") from exc
    if not parsed.is_finite() or parsed < 0 or (not allow_zero and parsed == 0):
        raise ValueError(f"out-of-range {field} at row {row_no}: {value!r}")
    return parsed


def offset_summary(offsets: list[int], total: int, minimum: int | None,
                   maximum: int | None, sum_value: int) -> dict:
    if total == 0:
        return {"count": 0, "min_us": None, "max_us": None, "mean_us": None,
                "sample_count": 0, "sample_median_us": None,
                "sample_p95_us": None, "sample_p99_us": None}
    ordered = sorted(offsets)
    def percentile(p: int) -> int:
        idx = max(0, (len(ordered) * p + 99) // 100 - 1)
        return ordered[idx]
    return {
        "count": total,
        "min_us": minimum,
        "max_us": maximum,
        "mean_us": round(sum_value / total, 3),
        "sample_count": len(ordered),
        "sample_median_us": median(ordered) if ordered else None,
        "sample_p95_us": percentile(95) if ordered else None,
        "sample_p99_us": percentile(99) if ordered else None,
        "quantiles_are_deterministic_stride_sample": True,
    }


def scan_dataset(path: Path, dataset: str) -> dict:
    if dataset == "trades":
        required = {"exchange", "symbol", "timestamp", "local_timestamp",
                    "id", "side", "price", "amount"}
    elif dataset == "incremental_book_L2":
        required = {"exchange", "symbol", "timestamp", "local_timestamp",
                    "is_snapshot", "side", "price", "amount"}
    else:
        raise ValueError(f"unsupported dataset: {dataset}")

    rows = 0
    ts_min = ts_max = local_min = local_max = None
    previous_ts = previous_local = None
    event_time_regressions = local_time_regressions = 0
    offset_sum = offset_min = offset_max = None
    offset_sample: list[int] = []
    side_counts = Counter()
    snapshot_rows = delta_rows = deltas_before_snapshot = 0
    snapshot_local_times: set[int] = set()
    seen_trade_ids: set[str] = set()
    missing_trade_ids = duplicate_trade_ids = 0
    first_snapshot_seen = False

    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        fields = set(reader.fieldnames or [])
        if fields != required:
            missing = sorted(required - fields)
            extra = sorted(fields - required)
            raise ValueError(f"{dataset} CSV header mismatch; missing={missing}, extra={extra}")
        for row_no, row in enumerate(reader, 2):
            if None in row:
                raise ValueError(f"extra CSV fields at row {row_no}")
            if row.get("exchange") != "bybit" or row.get("symbol") != SYMBOL:
                raise ValueError(f"unexpected exchange/symbol at row {row_no}")
            ts = strict_positive_int(row.get("timestamp", ""), "timestamp", row_no)
            local_ts = strict_positive_int(row.get("local_timestamp", ""),
                                           "local_timestamp", row_no)
            price = strict_decimal(row.get("price", ""), "price", row_no, False)
            amount = strict_decimal(row.get("amount", ""), "amount", row_no,
                                    dataset == "incremental_book_L2")
            if ts_min is None or ts < ts_min:
                ts_min = ts
            if ts_max is None or ts > ts_max:
                ts_max = ts
            if local_min is None or local_ts < local_min:
                local_min = local_ts
            if local_max is None or local_ts > local_max:
                local_max = local_ts
            if previous_ts is not None and ts < previous_ts:
                event_time_regressions += 1
            if previous_local is not None and local_ts < previous_local:
                local_time_regressions += 1
            previous_ts, previous_local = ts, local_ts

            offset = local_ts - ts
            offset_sum = (offset_sum or 0) + offset
            offset_min = offset if offset_min is None else min(offset_min, offset)
            offset_max = offset if offset_max is None else max(offset_max, offset)
            if rows % 100 == 0:
                offset_sample.append(offset)

            side = row.get("side", "")
            if dataset == "trades":
                if side not in ("buy", "sell", "unknown"):
                    raise ValueError(f"unexpected trade side at row {row_no}: {side!r}")
                trade_id = row.get("id", "")
                if not trade_id:
                    missing_trade_ids += 1
                elif trade_id in seen_trade_ids:
                    duplicate_trade_ids += 1
                else:
                    seen_trade_ids.add(trade_id)
            else:
                if side not in ("bid", "ask"):
                    raise ValueError(f"unexpected book side at row {row_no}: {side!r}")
                snapshot = row.get("is_snapshot", "")
                if snapshot == "true":
                    snapshot_rows += 1
                    first_snapshot_seen = True
                    snapshot_local_times.add(local_ts)
                elif snapshot == "false":
                    delta_rows += 1
                    if not first_snapshot_seen:
                        deltas_before_snapshot += 1
                else:
                    raise ValueError(f"invalid is_snapshot at row {row_no}: {snapshot!r}")
            side_counts[side] += 1
            rows += 1

    if rows == 0:
        raise ValueError(f"{dataset} archive contains no rows")
    if local_time_regressions:
        raise ValueError(
            f"{dataset} local_timestamp order regressed {local_time_regressions} times"
        )
    if dataset == "incremental_book_L2" and not first_snapshot_seen:
        raise ValueError("L2 archive contains no initial snapshot")

    report = {
        "rows": rows,
        "exchange": "bybit",
        "symbol": SYMBOL,
        "timestamp_unit": "microseconds since Unix epoch",
        "event_timestamp_min": ts_min,
        "event_timestamp_max": ts_max,
        "local_timestamp_min": local_min,
        "local_timestamp_max": local_max,
        "event_timestamp_regressions_in_capture_order": event_time_regressions,
        "local_timestamp_regressions": local_time_regressions,
        "local_minus_event_offset": offset_summary(
            offset_sample, rows, offset_min, offset_max, offset_sum or 0
        ),
        "side_counts": dict(side_counts),
    }
    if dataset == "trades":
        report.update({
            "unique_nonempty_trade_ids": len(seen_trade_ids),
            "missing_trade_ids": missing_trade_ids,
            "duplicate_trade_ids": duplicate_trade_ids,
        })
    else:
        report.update({
            "snapshot_rows": snapshot_rows,
            "delta_rows": delta_rows,
            "distinct_snapshot_local_timestamps": len(snapshot_local_times),
            "deltas_before_first_snapshot": deltas_before_snapshot,
        })
    return report


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Tardis.dev",
        "date": DATE,
        "symbol": SYMBOL,
        "scope": "one-day source integrity and schema validation; no PnL/backtest",
        "raw_archives_uploaded": False,
        "datasets": {},
    }
    failed = False
    with tempfile.TemporaryDirectory(prefix="tardis-bybit-sample-") as tmp:
        for dataset in ("trades", "incremental_book_L2"):
            item = {"url": source_url(dataset)}
            try:
                archive = Path(tmp) / f"{dataset}.csv.gz"
                item["download"] = download(item["url"], archive)
                item["validation"] = scan_dataset(archive, dataset)
                item["status"] = "VALIDATED"
            except Exception as exc:
                item["status"] = "FAILED"
                item["error"] = f"{type(exc).__name__}: {exc}"
                failed = True
            report["datasets"][dataset] = item

    trades = report["datasets"].get("trades", {}).get("validation")
    book = report["datasets"].get("incremental_book_L2", {}).get("validation")
    if trades and book:
        report["cross_feed_coverage"] = {
            "event_time_overlap_start_us": max(
                trades["event_timestamp_min"], book["event_timestamp_min"]
            ),
            "event_time_overlap_end_us": min(
                trades["event_timestamp_max"], book["event_timestamp_max"]
            ),
            "capture_time_overlap_start_us": max(
                trades["local_timestamp_min"], book["local_timestamp_min"]
            ),
            "capture_time_overlap_end_us": min(
                trades["local_timestamp_max"], book["local_timestamp_max"]
            ),
            "interpretation": (
                "Range overlap only; it does not prove event-level clock alignment "
                "or same-event timestamp equivalence."
            ),
        }
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "tardis_bybit_sample_inspection.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
