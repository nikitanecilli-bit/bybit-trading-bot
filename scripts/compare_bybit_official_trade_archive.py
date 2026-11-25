#!/usr/bin/env python3
"""Compare CryptoHFTData Bybit trades with Bybit's own daily public trade archive.

This is a bounded data-integrity check only. It does not run a strategy or PnL.
The official archive exposes trdMatchID UUIDs; CryptoHFTData documents trade_id
as a stable 64-bit hash of that UUID. We verify both event payloads and IDs.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import zstandard

DATES = ("2025-07-01", "2026-11-01")
SYMBOL = "BTCUSDT"
CHD_BASE = "https://api.cryptohftdata.com/v1/download"
OFFICIAL_BASE = "https://public.bybit.com/trading"
MAX_BYTES = 500 * 1024 * 1024
FNV_OFFSET_BASIS_64 = 0xCBF29CE484222325
# This non-standard multiplier is exactly the one documented by CryptoHFTData.
FNV_MULTIPLIER = 0x1000001B3
MASK_64 = (1 << 64) - 1
SIGN_BIT_64 = (1 << 63) - 1


def dec(value: object) -> Decimal:
    return Decimal(str(value))


def fnv1a_bybit_id(uuid: str) -> int:
    value = FNV_OFFSET_BASIS_64
    for byte in uuid.encode("utf-8"):
        value ^= byte
        value = (value * FNV_MULTIPLIER) & MASK_64
    return value & SIGN_BIT_64


def download(url: str, path: Path) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": "bybit-official-archive-crosscheck/1.0", "Accept": "*/*"}
    )
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as out:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status}")
        expected = response.headers.get("Content-Length")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BYTES:
                raise RuntimeError(f"file exceeds safety limit {MAX_BYTES} bytes")
            out.write(chunk)
            digest.update(chunk)
    if expected is not None and total != int(expected):
        raise RuntimeError(f"size mismatch expected={expected} actual={total}")
    return {"bytes": total, "sha256": digest.hexdigest()}


def chd_url(date: str, hour: str) -> str:
    file_path = f"bybit/{date}/{hour}/{SYMBOL}_trades.parquet"
    return CHD_BASE + "?" + urllib.parse.urlencode({"file": file_path})


def normalize_parquet(path: Path) -> tuple[Path, str]:
    with path.open("rb") as stream:
        magic = stream.read(4)
    if magic == b"PAR1":
        return path, "raw_parquet"
    if magic == b"\\x28\\xb5\\x2f\\xfd":
        decoded = path.with_name(path.stem + ".decoded.parquet")
        with path.open("rb") as source, decoded.open("wb") as target:
            zstandard.ZstdDecompressor().copy_stream(source, target)
        with decoded.open("rb") as stream:
            prefix = stream.read(4)
            stream.seek(-4, 2)
            suffix = stream.read(4)
        if prefix != b"PAR1" or suffix != b"PAR1":
            raise ValueError("Zstandard payload is not a complete Parquet file")
        return decoded, "zstd_wrapped_parquet"
    raise ValueError(f"unknown Parquet container magic: {magic.hex()}")


def official_archive_url(date: str) -> str:
    return f"{OFFICIAL_BASE}/{SYMBOL}/{SYMBOL}{date}.csv.gz"


def load_official(path: Path, date: str) -> tuple[Counter, dict, dict]:
    payloads: Counter = Counter()
    ids_by_payload: dict[tuple, Counter] = defaultdict(Counter)
    ids = []
    rows = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        expected = ["timestamp", "symbol", "side", "size", "price", "tickDirection",
                    "trdMatchID", "grossValue", "homeNotional", "foreignNotional"]
        if reader.fieldnames is None or reader.fieldnames[:len(expected)] != expected:
            raise ValueError(f"official archive header mismatch: {reader.fieldnames!r}")
        for row_no, row in enumerate(reader, 2):
            rows += 1
            if row["symbol"] != SYMBOL:
                raise ValueError(f"unexpected symbol on row {row_no}")
            timestamp_ms = int(dec(row["timestamp"]) * 1000)
            event_date = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            if event_date != date:
                continue
            side = row["side"].strip().lower()
            if side not in ("buy", "sell"):
                raise ValueError(f"invalid side on row {row_no}: {row['side']!r}")
            trade_uuid = row["trdMatchID"].strip()
            if not trade_uuid:
                raise ValueError(f"empty trdMatchID on row {row_no}")
            key = (timestamp_ms, side, dec(row["price"]), dec(row["size"]))
            payloads[key] += 1
            ids_by_payload[key][fnv1a_bybit_id(trade_uuid)] += 1
            ids.append(trade_uuid)
    diagnostics = {
        "rows_in_gzip": rows,
        "target_date_rows": sum(payloads.values()),
        "unique_trdMatchID": len(set(ids)),
        "duplicate_trdMatchID_rows": len(ids) - len(set(ids)),
        "empty_trdMatchID_rows": 0,
    }
    return payloads, ids_by_payload, diagnostics


def load_chd_day(root: Path, date: str, request_state: dict) -> tuple[Counter, dict, dict]:
    payloads: Counter = Counter()
    ids_by_payload: dict[tuple, Counter] = defaultdict(Counter)
    partition_report = {}
    next_day = (datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                + timedelta(days=1)).strftime("%Y-%m-%d")
    partitions = [(date, f"{hour:02d}") for hour in range(24)] + [(next_day, "00")]
    for receive_date, hour in partitions:
        if request_state["count"]:
            time.sleep(1.05)
        request_state["count"] += 1
        partition = f"{receive_date}T{hour}"
        archive = root / f"chd_{receive_date}_{hour}.parquet"
        meta = download(chd_url(receive_date, hour), archive)
        normalized, container = normalize_parquet(archive)
        table = pq.read_table(normalized)
        expected = ["received_time", "event_time", "symbol", "trade_id", "price",
                    "quantity", "trade_time", "is_buyer_maker", "order_type"]
        if table.schema.names != expected:
            raise ValueError(f"CryptoHFTData schema mismatch in {partition}: {table.schema.names!r}")
        data = table.to_pydict()
        ids = [int(value) for value in data["trade_id"] if value is not None]
        rows_for_day = 0
        for i in range(table.num_rows):
            if data["symbol"][i] != SYMBOL:
                raise ValueError(f"unexpected symbol in {partition}")
            timestamp_ms = int(data["trade_time"][i])
            event_date = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            if event_date != date:
                continue
            side = "sell" if data["is_buyer_maker"][i] else "buy"
            key = (timestamp_ms, side, dec(data["price"][i]), dec(data["quantity"][i]))
            payloads[key] += 1
            if data["trade_id"][i] is not None:
                ids_by_payload[key][int(data["trade_id"][i])] += 1
            rows_for_day += 1
        partition_report[partition] = {
            "container": container,
            "download": meta,
            "parquet_rows": table.num_rows,
            "target_date_event_rows": rows_for_day,
            "trade_id_type": str(table.schema.field("trade_id").type),
            "trade_id_zero_rows": sum(1 for value in ids if value == 0),
            "trade_id_nonzero_unique": len({value for value in ids if value != 0}),
            "trade_id_unique_all": len(set(ids)),
        }
    return payloads, ids_by_payload, partition_report


def compare_ids(reference: dict, candidate: dict) -> dict:
    shared_payloads = set(reference) & set(candidate)
    matched_id_rows = 0
    id_mismatch_rows = 0
    zero_id_rows = 0
    comparable_rows = 0
    for key in shared_payloads:
        ref_ids = reference[key]
        chd_ids = candidate[key]
        comparable_rows += min(sum(ref_ids.values()), sum(chd_ids.values()))
        zero_id_rows += chd_ids.get(0, 0)
        common = ref_ids & chd_ids
        matched_id_rows += sum(common.values())
        id_mismatch_rows += max(0, min(sum(ref_ids.values()), sum(chd_ids.values())) - sum(common.values()))
    return {
        "shared_payload_keys": len(shared_payloads),
        "comparable_rows": comparable_rows,
        "matching_hashed_id_rows": matched_id_rows,
        "id_mismatch_rows": id_mismatch_rows,
        "zero_id_rows_on_shared_payloads": zero_id_rows,
    }


def main() -> int:
    if fnv1a_bybit_id("caa63c3c-3c80-540f-8364-ea18a6824a70") != 2580710057459900140:
        raise RuntimeError("CryptoHFTData documented FNV-1a example does not match")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL,
        "official_source": "Bybit public.bybit.com/trading",
        "candidate_source": "CryptoHFTData Bybit linear trades",
        "dates": {},
        "scope": "daily public trade archive vs event-time grouped hourly Parquet; payload and documented trade_id hash; no PnL",
        "raw_archives_uploaded": False,
    }
    request_state = {"count": 0}
    with tempfile.TemporaryDirectory(prefix="bybit-official-trade-crosscheck-") as tmp:
        root = Path(tmp)
        for date in DATES:
            day = {}
            try:
                official_path = root / f"official_{date}.csv.gz"
                day["official_download"] = download(official_archive_url(date), official_path)
                official_payloads, official_ids, official_diag = load_official(official_path, date)
                day["official"] = official_diag
                chd_payloads, chd_ids, partitions = load_chd_day(root, date, request_state)
                day["cryptohftdata"] = {
                    "event_rows": sum(chd_payloads.values()),
                    "partitions": partitions,
                }
                missing = official_payloads - chd_payloads
                extra = chd_payloads - official_payloads
                day["payload_comparison"] = {
                    "official_rows": sum(official_payloads.values()),
                    "cryptohftdata_rows": sum(chd_payloads.values()),
                    "matched_rows": sum(official_payloads.values()) - sum(missing.values()),
                    "missing_from_cryptohftdata": sum(missing.values()),
                    "extra_in_cryptohftdata": sum(extra.values()),
                    "missing_payload_keys": len(missing),
                    "extra_payload_keys": len(extra),
                }
                day["trade_id_comparison"] = compare_ids(official_ids, chd_ids)
                day["status"] = (
                    "EXACT_PAYLOAD_AND_ID_MATCH"
                    if not missing and not extra and day["trade_id_comparison"]["id_mismatch_rows"] == 0
                    else "MISMATCH_REVIEW_REQUIRED"
                )
            except Exception as exc:
                day["status"] = "SAMPLE_FAILED"
                day["error"] = f"{type(exc).__name__}: {exc}"
            report["dates"][date] = day
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/bybit_official_trade_crosscheck.json")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if any(day["status"] != "EXACT_PAYLOAD_AND_ID_MATCH" for day in report["dates"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
