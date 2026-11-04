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
                raw_ts = float(row["timestamp"])
                ts = int(round(raw_ts if raw_ts > 1_000_000_000_000 else raw_ts * 1000))
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
                trade_id = row.get("trdMatchID")
                if trade_id:
                    if trade_id in seen_ids:
                        duplicate_ids += 1
                    seen_ids.add(trade_id)
                side_counts[side] += 1
                total_size += qty
                total_notional += qty * price
                rows += 1

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
            "has_rpi_flag": "isRPITrade" in fields,
            "has_block_trade_flag": "isBlockTrade" in fields,
            "matching_engine_cts_min_ms": cts_min,
            "matching_engine_cts_max_ms": cts_max,
            "trade_timestamps_within_book_cts_range": (
                None if cts_min is None else ts_min >= cts_min and ts_max <= cts_max
            ),
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
