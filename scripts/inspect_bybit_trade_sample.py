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
from decimal import Decimal, InvalidOperation
from pathlib import Path

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


def parse_archive_timestamp_ms(value: object) -> int:
    """Parse archive seconds or milliseconds without float rounding."""
    try:
        raw = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("invalid trade archive timestamp") from exc
    if not raw.is_finite() or raw <= 0:
        raise ValueError("trade archive timestamp must be finite and positive")
    milliseconds = raw if raw >= Decimal("1000000000000") else raw * Decimal("1000")
    if milliseconds != milliseconds.to_integral_value():
        raise ValueError("trade archive timestamp has sub-millisecond precision")
    return int(milliseconds)


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
        nonmonotonic = duplicate_ids = rows = 0
        before_book = after_book = within_book = 0
        rpi_counts = Counter()
        seen_ids = set()
        total_size = Decimal("0")
        total_notional = Decimal("0")
        fields = []
        with gzip.open(archive, "rt", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames or [])
            required = {"timestamp", "symbol", "side", "size", "price"}
            missing = sorted(required - set(fields))
            if missing:
                raise ValueError(f"trade CSV missing required columns: {missing}")
            for row in reader:
                if row.get("symbol") != SYMBOL:
                    raise ValueError(f"unexpected trade symbol: {row.get('symbol')!r}")
                ts = parse_archive_timestamp_ms(row["timestamp"])
                side = str(row["side"]).strip()
                if side not in ("Buy", "Sell"):
                    raise ValueError(f"unexpected aggressor side: {side!r}")
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
                trade_id = row.get("trdMatchID")
                if trade_id:
                    if trade_id in seen_ids:
                        duplicate_ids += 1
                    seen_ids.add(trade_id)
                side_counts[side] += 1
                total_size += qty
                total_notional += qty * price
                rows += 1

        block_flags = block_trade_flag_columns(fields)
        report["validation"] = {
            "rows": rows,
            "columns": fields,
            "timestamp_min_ms": ts_min,
            "timestamp_max_ms": ts_max,
            "duration_hours": round((ts_max - ts_min) / 3_600_000, 4),
            "nonmonotonic_timestamp_count": nonmonotonic,
            "duplicate_trade_id_count": duplicate_ids,
            "unique_trade_ids": len(seen_ids),
            "aggressor_side_counts": dict(side_counts),
            "total_contract_size": str(total_size),
            "total_contract_notional_usdt": str(total_notional),
            "has_rpi_flag": "RPI" in fields or "isRPITrade" in fields,
            "rpi_flag_value_counts": dict(rpi_counts),
            "has_block_trade_flag": bool(block_flags),
            "block_trade_flag_columns": block_flags,
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
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
