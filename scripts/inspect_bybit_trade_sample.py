#!/usr/bin/env python3
"""Download and fully scan one Bybit public linear trade archive."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import tempfile
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bybit_l2_queue_replay import parse_exchange_bool, parse_trade_timestamp_ms
from report_io import write_json_report

URL = "https://public.bybit.com/trading/AAVEUSDT/AAVEUSDT2025-09-02.csv.gz"
SYMBOL = "AAVEUSDT"
ORDERBOOK_REPORT = Path("bybit_orderbook_sample_inspection.json")
CHUNK = 1024 * 1024


def download(url: str, path: Path) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "bybit-trade-sample-inspector/1.0"})
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=90) as response, path.open("wb") as out:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status}")
        expected = response.headers.get("Content-Length")
        while True:
            chunk = response.read(CHUNK)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
            total += len(chunk)
    if expected is not None and total != int(expected):
        raise RuntimeError(f"download size mismatch: expected={expected}, actual={total}")
    return total, digest.hexdigest()


def block_trade_flag_columns(fields: list[str]) -> list[str]:
    """Return supported Bybit block-trade flag columns in stable order."""
    return [name for name in ("isBlockTrade", "BT") if name in fields]

def validate_trade_csv_header(fields: list[str]) -> None:
    """Reject ambiguous headers using the queue replay CSV contract."""
    if len(fields) != len(set(fields)):
        raise ValueError("trade CSV contains duplicate column names")
    required = {"timestamp", "symbol", "side", "size", "price"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"trade CSV missing required columns: {missing}")


def validate_trade_csv_row(row: dict, row_no: int) -> None:
    """Reject malformed CSV row widths and missing core values."""
    if None in row:
        raise ValueError(f"unexpected extra CSV fields at row {row_no}")
    required = {"timestamp", "symbol", "side", "size", "price"}
    missing = sorted(name for name in required if row.get(name) is None)
    if missing:
        raise ValueError(f"missing CSV field value at row {row_no}: {missing}")




def validated_trade_csv_reader(stream):
    """Build a strict CSV reader and validate every row's width."""
    reader = csv.DictReader(stream, strict=True)
    fields = list(reader.fieldnames or [])
    validate_trade_csv_header(fields)

    def rows():
        for row_no, row in enumerate(reader, 2):
            validate_trade_csv_row(row, row_no)
            yield row_no, row

    return fields, rows()


def trade_timestamp_order_status(nonmonotonic_count: int) -> str:
    """Classify whether archive trade timestamps are replay-order compatible."""
    if isinstance(nonmonotonic_count, bool) or not isinstance(nonmonotonic_count, int):
        raise ValueError("nonmonotonic timestamp count must be an integer")
    if nonmonotonic_count < 0:
        raise ValueError("nonmonotonic timestamp count must be non-negative")
    return "valid" if nonmonotonic_count == 0 else "invalid"



def trade_archive_replay_compatibility_status(
    timestamp_status: str,
    trade_id_status: str,
    rpi_status: str,
    block_trade_status: str,
) -> str:
    """Summarize whether the scanned archive meets queue-replay input requirements."""
    required_statuses = (
        timestamp_status,
        trade_id_status,
        rpi_status,
        block_trade_status,
    )
    return (
        "valid"
        if all(status == "valid" for status in required_statuses)
        else "invalid_or_incomplete"
    )


def validate_trade_side(value: object) -> str:
    """Validate the exact public-trade aggressor-side token; do not trim/coerce."""
    if value not in ("Buy", "Sell"):
        raise ValueError(f"unexpected aggressor side: {value!r}")
    return value


def classify_trade_id(value: object, seen_ids: set[str]) -> str:
    """Classify a CSV trade ID using the queue replay strict identity rules."""
    if not isinstance(value, str) or not value.strip():
        return "missing"
    if value != value.strip():
        return "malformed"
    if value in seen_ids:
        return "duplicate"
    seen_ids.add(value)
    return "unique"


def classify_boolean_flag_aliases(row: dict, columns: list[str], field: str) -> str:
    """Validate all supported flag aliases using the replay parser's bool contract."""
    if not columns:
        return "missing"
    values = set()
    for name in columns:
        raw = row.get(name)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return "missing"
        try:
            values.add(parse_exchange_bool(raw, field))
        except ValueError:
            return "malformed"
    if len(values) != 1:
        return "conflict"
    return "true" if next(iter(values)) else "false"


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_url": URL,
        "symbol": SYMBOL,
        "scope": "full gzip CSV scan to EOF; gzip CRC validated by streaming",
    }
    book_report = json.loads(ORDERBOOK_REPORT.read_text(encoding="utf-8"))
    book = book_report["stream_validation"]
    cts_min = book.get("matching_engine_cts_min_ms")
    cts_max = book.get("matching_engine_cts_max_ms")

    with tempfile.TemporaryDirectory(prefix="bybit-trades-inspect-") as tmp:
        archive = Path(tmp) / "trades.csv.gz"
        size, sha256 = download(URL, archive)
        report["download"] = {"bytes": size, "sha256": sha256}

        side_counts = Counter()
        ts_min = ts_max = previous_ts = None
        nonmonotonic = duplicate_ids = missing_trade_ids = malformed_trade_ids = rows = 0
        before_book = after_book = within_book = 0
        rpi_counts = Counter()
        block_flag_status_counts = Counter()
        rpi_flag_status_counts = Counter()
        seen_ids = set()
        total_size = Decimal("0")
        total_notional = Decimal("0")
        fields = []
        with gzip.open(archive, "rt", encoding="utf-8", newline="") as stream:
            fields, rows_iter = validated_trade_csv_reader(stream)
            block_flags = block_trade_flag_columns(fields)
            rpi_flags = [name for name in ("RPI", "isRPITrade") if name in fields]
            for row_no, row in rows_iter:
                if row.get("symbol") != SYMBOL:
                    raise ValueError(f"unexpected trade symbol: {row.get('symbol')!r}")
                ts = parse_trade_timestamp_ms(row["timestamp"])
                side = validate_trade_side(row["side"])
                qty = Decimal(row["size"])
                price = Decimal(row["price"])
                if not qty.is_finite() or qty <= 0 or not price.is_finite() or price <= 0:
                    raise ValueError("trade contains invalid price or size")
                ts_min = ts if ts_min is None else min(ts_min, ts)
                ts_max = ts if ts_max is None else max(ts_max, ts)
                if previous_ts is not None and ts < previous_ts:
                    nonmonotonic += 1
                previous_ts = ts
                if cts_min is not None and ts < cts_min:
                    before_book += 1
                elif cts_max is not None and ts > cts_max:
                    after_book += 1
                else:
                    within_book += 1
                rpi_value = row.get("RPI", row.get("isRPITrade"))
                if rpi_value is not None:
                    rpi_counts[str(rpi_value)] += 1
                block_flag_status_counts[classify_boolean_flag_aliases(
                    row, block_flags, "block trade",
                )] += 1
                rpi_flag_status_counts[classify_boolean_flag_aliases(
                    row, rpi_flags, "RPI",
                )] += 1
                trade_id_status = classify_trade_id(row.get("trdMatchID"), seen_ids)
                if trade_id_status == "duplicate":
                    duplicate_ids += 1
                elif trade_id_status == "missing":
                    missing_trade_ids += 1
                elif trade_id_status == "malformed":
                    malformed_trade_ids += 1
                side_counts[side] += 1
                total_size += qty
                total_notional += qty * price
                rows += 1

        def flags_valid(columns: list[str], counts: Counter) -> bool:
            return bool(columns) and not any(
                counts.get(status, 0) for status in ("missing", "malformed", "conflict")
            )

        timestamp_status = trade_timestamp_order_status(nonmonotonic)
        trade_id_status = (
            "valid" if "trdMatchID" in fields and not (
                duplicate_ids or missing_trade_ids or malformed_trade_ids
            ) else "invalid_or_incomplete"
        )
        rpi_status = "valid" if flags_valid(rpi_flags, rpi_flag_status_counts) else "invalid_or_incomplete"
        block_trade_status = (
            "valid" if flags_valid(block_flags, block_flag_status_counts) else "invalid_or_incomplete"
        )
        replay_compatibility_status = trade_archive_replay_compatibility_status(
            timestamp_status, trade_id_status, rpi_status, block_trade_status,
        )
        report["validation"] = {
            "rows": rows,
            "columns": fields,
            "timestamp_min_ms": ts_min,
            "timestamp_max_ms": ts_max,
            "duration_hours": round((ts_max - ts_min) / 3_600_000, 4),
            "nonmonotonic_timestamp_count": nonmonotonic,
            "timestamp_order_validation_status": timestamp_status,
            "duplicate_trade_id_count": duplicate_ids,
            "missing_trade_id_count": missing_trade_ids,
            "malformed_trade_id_count": malformed_trade_ids,
            "has_trade_id_column": "trdMatchID" in fields,
            "trade_id_validation_status": trade_id_status,
            "unique_trade_ids": len(seen_ids),
            "aggressor_side_counts": dict(side_counts),
            "total_contract_size": str(total_size),
            "total_contract_notional_usdt": str(total_notional),
            "has_rpi_flag": bool(rpi_flags),
            "rpi_flag_value_counts": dict(rpi_counts),
            "rpi_flag_status_counts": dict(rpi_flag_status_counts),
            "rpi_flag_validation_status": rpi_status,
            "has_block_trade_flag": bool(block_flags),
            "block_trade_flag_columns": block_flags,
            "block_trade_flag_status_counts": dict(block_flag_status_counts),
            "block_trade_flag_validation_status": block_trade_status,
            "queue_replay_compatibility_status": replay_compatibility_status,
            "matching_engine_cts_min_ms": cts_min,
            "matching_engine_cts_max_ms": cts_max,
            "trades_before_book_cts_start": before_book,
            "trades_within_book_cts_range": within_book,
            "trades_after_book_cts_end": after_book,
            "trade_start_offset_from_book_cts_ms": None if cts_min is None else ts_min - cts_min,
            "trade_end_offset_from_book_cts_ms": None if cts_max is None else ts_max - cts_max,
        }
    report["status"] = "success"
    output = Path("bybit_trade_sample_inspection.json")
    write_json_report(output, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
