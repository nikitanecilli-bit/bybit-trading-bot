#!/usr/bin/env python3
"""Download and fully validate one Bybit L2 archive; retain only a compact report."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import tempfile
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

URL = "https://quote-saver.bycsi.com/orderbook/linear/AAVEUSDT/2025-09-02_AAVEUSDT_ob200.data.zip"
TRADES_URL = "https://public.bybit.com/trading/AAVEUSDT/AAVEUSDT2025-09-02.csv.gz"
SYMBOL = "AAVEUSDT"
CHUNK = 1024 * 1024


def download(url: str, path: Path) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "bybit-orderbook-sample-inspector/1.0"})
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


def validate_level(level: object) -> None:
    if not isinstance(level, list) or len(level) != 2:
        raise ValueError("book level must be [price, quantity]")
    price, qty = Decimal(str(level[0])), Decimal(str(level[1]))
    if not price.is_finite() or price <= 0 or not qty.is_finite() or qty < 0:
        raise ValueError("book level contains invalid price or quantity")


def inspect_member(zf: zipfile.ZipFile, member: str) -> dict:
    event_types = Counter()
    ts_min = ts_max = cts_min = cts_max = None
    previous_ts = previous_seq = None
    nonmonotonic_ts = nonmonotonic_seq = duplicate_ts = 0
    cts_missing = u_reset_count = 0
    first_events, last_events = [], []
    max_bid_levels = max_ask_levels = 0
    first_snapshot = None
    rows = 0

    with zf.open(member, "r") as stream:
        for raw in stream:
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except Exception as exc:
                raise ValueError(f"invalid JSON at row {rows + 1}: {exc}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"event {rows + 1} is not an object")
            kind = event.get("type")
            if kind not in ("snapshot", "delta"):
                raise ValueError(f"unsupported event type at row {rows + 1}: {kind!r}")
            data = event.get("data")
            if not isinstance(data, dict) or data.get("s") != SYMBOL:
                raise ValueError(f"wrong/missing symbol at row {rows + 1}")
            ts = int(event["ts"])
            cts = int(event["cts"]) if event.get("cts") is not None else None
            seq = int(data["seq"])
            update_id = int(data["u"])
            if ts_min is None or ts < ts_min:
                ts_min = ts
            if ts_max is None or ts > ts_max:
                ts_max = ts
            if cts is not None:
                if cts_min is None or cts < cts_min:
                    cts_min = cts
                if cts_max is None or cts > cts_max:
                    cts_max = cts
            if previous_ts is not None:
                if ts < previous_ts:
                    nonmonotonic_ts += 1
                if ts == previous_ts:
                    duplicate_ts += 1
            if previous_seq is not None and seq < previous_seq:
                nonmonotonic_seq += 1
            if update_id == 1:
                u_reset_count += 1
            if "cts" not in event:
                cts_missing += 1

            bids, asks = data.get("b"), data.get("a")
            if kind == "snapshot":
                if not isinstance(bids, list) or not isinstance(asks, list):
                    raise ValueError(f"snapshot missing full bid/ask arrays at row {rows + 1}")
                for level in bids:
                    validate_level(level)
                for level in asks:
                    validate_level(level)
                max_bid_levels = max(max_bid_levels, len(bids))
                max_ask_levels = max(max_ask_levels, len(asks))
                if first_snapshot is None:
                    first_snapshot = {
                        "ts": ts, "seq": seq, "u": update_id,
                        "bid_levels": len(bids), "ask_levels": len(asks),
                        "best_bid": bids[0] if bids else None,
                        "best_ask": asks[0] if asks else None,
                    }
            else:
                if not isinstance(bids, list) or not isinstance(asks, list):
                    raise ValueError(f"delta missing bid/ask change arrays at row {rows + 1}")
                for level in bids + asks:
                    validate_level(level)

            item = {"type": kind, "ts": ts, "seq": seq, "u": update_id}
            if len(first_events) < 5:
                first_events.append(item)
            last_events.append(item)
            if len(last_events) > 5:
                last_events.pop(0)
            event_types[kind] += 1
            rows += 1
            previous_ts, previous_seq = ts, seq

    if rows == 0 or first_snapshot is None:
        raise ValueError("archive has no usable snapshot/events")
    return {
        "rows": rows,
        "event_types": dict(event_types),
        "timestamp_min_ms": ts_min,
        "timestamp_max_ms": ts_max,
        "matching_engine_cts_min_ms": cts_min,
        "matching_engine_cts_max_ms": cts_max,
        "duration_hours": round((ts_max - ts_min) / 3_600_000, 4),
        "nonmonotonic_timestamp_count": nonmonotonic_ts,
        "duplicate_adjacent_timestamp_count": duplicate_ts,
        "nonmonotonic_cross_sequence_count": nonmonotonic_seq,
        "update_id_reset_count": u_reset_count,
        "missing_cts_count": cts_missing,
        "max_snapshot_bid_levels": max_bid_levels,
        "max_snapshot_ask_levels": max_ask_levels,
        "first_snapshot": first_snapshot,
        "first_events": first_events,
        "last_events": last_events,
    }


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_url": URL,
        "symbol": SYMBOL,
        "scope": "one full archive download; full JSONL scan; zip CRC checked by streaming to EOF",
        "status": "started",
    }
    with tempfile.TemporaryDirectory(prefix="bybit-ob-inspect-") as tmp:
        archive = Path(tmp) / "sample.data.zip"
        size, sha256 = download(URL, archive)
        report["download"] = {"bytes": size, "sha256": sha256}
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            data_members = [name for name in names if name.endswith(".data")]
            if len(data_members) != 1:
                raise ValueError(f"expected exactly one .data member, found {data_members!r}")
            report["zip_members"] = names
            report["stream_validation"] = inspect_member(zf, data_members[0])
        report["status"] = "success"
    output = Path("bybit_orderbook_sample_inspection.json")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, InvalidOperation) as exc:
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        raise
