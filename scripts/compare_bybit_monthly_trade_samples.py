#!/usr/bin/env python3
"""Cross-check four sampled Bybit BTCUSDT trade days across two providers.

CryptoHFTData historical objects may be outer Zstandard-wrapped Parquet, while
newer objects may be raw Parquet. The loader detects both formats. Hourly
requests are paced below the anonymous 60-files/minute limit.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import zstandard

from compare_bybit_trade_archives import dec, multiset_diff

DATES = ("2025-07-01", "2025-07-03", "2025-08-01", "2025-08-15", "2026-11-01")
HOURS = tuple(f"{hour:02d}" for hour in range(24))
SYMBOL = "BTCUSDT"
CHD_BASE = "https://api.cryptohftdata.com/v1/download"
TARDIS_BASE = "https://datasets.tardis.dev/v1/bybit/trades"
MAX_TARDIS_BYTES = 250 * 1024 * 1024
MAX_CHD_BYTES = 200 * 1024 * 1024


def file_url(base: str, file_path: str) -> str:
    return base + "?" + urllib.parse.urlencode({"file": file_path})


def download(url: str, path: Path, max_bytes: int) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "bybit-monthly-crosscheck/1.0"})
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as out:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status}")
        expected = response.headers.get("Content-Length")
        content_type = response.headers.get("Content-Type")
        final_url = response.geturl()
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise RuntimeError(f"file exceeds safety limit {max_bytes} bytes")
            out.write(chunk)
            digest.update(chunk)
    if expected is not None and total != int(expected):
        raise RuntimeError(f"size mismatch expected={expected} actual={total}")
    return {"bytes": total, "sha256": digest.hexdigest(),
            "content_type": content_type, "final_url": final_url}


def normalize_parquet(path: Path) -> tuple[Path, str]:
    with path.open("rb") as stream:
        magic = stream.read(4)
    if magic == b"PAR1":
        return path, "raw_parquet"
    if magic == b"\x28\xb5\x2f\xfd":
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




def tardis_url(date: str) -> str:
    year, month, day = date.split("-")
    return f"{TARDIS_BASE}/{year}/{month}/{day}/{SYMBOL}.csv.gz"


def chd_url(date: str, hour: str) -> str:
    file_path = f"bybit/{date}/{hour}/{SYMBOL}_trades.parquet"
    return file_url(CHD_BASE, file_path)


def load_tardis_day(path: Path) -> tuple[dict[str, Counter], int, dict]:
    by_hour = {hour: Counter() for hour in HOURS}
    unknown_sides = 0
    ids = []
    total_rows = 0
    expected = ["exchange", "symbol", "timestamp", "local_timestamp",
                "id", "side", "price", "amount"]
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != expected:
            raise ValueError(f"Tardis header mismatch: {reader.fieldnames!r}")
        for row_no, row in enumerate(reader, 2):
            total_rows += 1
            if None in row or row["exchange"] != "bybit" or row["symbol"] != SYMBOL:
                raise ValueError(f"invalid Tardis row {row_no}")
            ts_us = int(row["timestamp"])
            if row["id"]:
                ids.append(row["id"])
            hour = datetime.fromtimestamp(ts_us // 1_000_000, tz=timezone.utc).strftime("%H")
            side = row["side"].lower()
            if side not in ("buy", "sell"):
                unknown_sides += 1
                continue
            by_hour[hour][(ts_us // 1000, side, dec(row["price"]), dec(row["amount"]))] += 1
    id_diagnostics = {
        "rows_with_nonempty_id": len(ids),
        "empty_id_rows": total_rows - len(ids),
        "unique_ids": len(set(ids)),
        "duplicate_id_rows": len(ids) - len(set(ids)),
    }
    return by_hour, unknown_sides, id_diagnostics


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider_a": "Tardis.dev",
        "provider_b": "CryptoHFTData",
        "symbol": SYMBOL,
        "dates": list(DATES),
        "event_hours_utc": list(HOURS),
        "receive_partitions": "target date 00-23 plus next day 00; grouped by trade_time UTC",
        "scope": "all 24 hours per monthly sample day; exact trade multiset comparison; no PnL",
        "raw_archives_uploaded": False,
        "days": {},
    }
    total = {"tardis_rows": 0, "cryptohftdata_rows": 0, "matched_rows": 0,
             "missing_from_cryptohftdata": 0, "extra_in_cryptohftdata": 0,
             "missing_hour_files": 0}
    failed = False
    request_count = 0

    with tempfile.TemporaryDirectory(prefix="bybit-monthly-crosscheck-") as tmp:
        root = Path(tmp)
        for date in DATES:
            day_report = {"hours": {}}
            tardis_path = root / f"tardis_{date}.csv.gz"
            try:
                day_report["tardis_download"] = download(
                    tardis_url(date), tardis_path, MAX_TARDIS_BYTES
                )
                tardis_by_hour, unknown_sides, tardis_id_diagnostics = load_tardis_day(tardis_path)
                day_report["tardis_unknown_side_rows"] = unknown_sides
                day_report["tardis_id_integrity"] = tardis_id_diagnostics
                day_report["tardis_rows"] = sum(sum(c.values()) for c in tardis_by_hour.values())
            except Exception as exc:
                day_report["status"] = "TARDIS_SAMPLE_FAILED"
                day_report["error"] = f"{type(exc).__name__}: {exc}"
                report["days"][date] = day_report
                failed = True
                continue


            candidate_by_event_hour = {hour: Counter() for hour in HOURS}
            candidate_received_by_event_hour = {hour: {} for hour in HOURS}
            file_diagnostics = {}
            receive_partitions = [(date, hour) for hour in HOURS]
            next_day = (datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        + timedelta(days=1)).strftime("%Y-%m-%d")
            receive_partitions.append((next_day, "00"))

            for receive_date, receive_hour in receive_partitions:
                partition_key = f"{receive_date}T{receive_hour}"
                try:
                    if request_count:
                        time.sleep(1.05)
                    request_count += 1
                    parquet_path = root / f"chd_{receive_date}_{receive_hour}.parquet"
                    download_meta = download(chd_url(receive_date, receive_hour), parquet_path, MAX_CHD_BYTES)
                    normalized_path, container = normalize_parquet(parquet_path)
                    table = pq.read_table(normalized_path)
                    expected = ["received_time", "event_time", "symbol", "trade_id", "price", "quantity", "trade_time", "is_buyer_maker", "order_type"]
                    if table.schema.names != expected:
                        raise ValueError(f"CryptoHFTData schema mismatch: {table.schema.names!r}")
                    d = table.to_pydict()
                    ids = [str(x) for x in d["trade_id"] if x is not None]
                    order_types = Counter()
                    id_to_keys = {}
                    event_rows_in_target_day = 0
                    lag_ms = []
                    for i in range(len(d["trade_id"])):
                        if d["symbol"][i] != SYMBOL:
                            raise ValueError(f"unexpected symbol in {partition_key}")
                        trade_ts = int(d["trade_time"][i])
                        trade_dt = datetime.fromtimestamp(trade_ts / 1000, tz=timezone.utc)
                        if trade_dt.strftime("%Y-%m-%d") != date:
                            continue
                        event_hour = trade_dt.strftime("%H")
                        side = "sell" if d["is_buyer_maker"][i] else "buy"
                        key = (trade_ts, side, dec(d["price"][i]), dec(d["quantity"][i]))
                        candidate_by_event_hour[event_hour][key] += 1
                        received_ts = int(d["received_time"][i])
                        candidate_received_by_event_hour[event_hour].setdefault(key, []).append(received_ts)
                        event_rows_in_target_day += 1
                        order_types[str(d["order_type"][i])] += 1
                        trade_id = d["trade_id"][i]
                        if trade_id is not None:
                            id_to_keys.setdefault(str(trade_id), set()).add(key)
                        lag_ms.append(received_ts // 1_000_000 - trade_ts)
                    sorted_lag = sorted(lag_ms)
                    file_diagnostics[partition_key] = {
                        "status": "DOWNLOADED",
                        "download": download_meta,
                        "container": container,
                        "parquet_rows": table.num_rows,
                        "target_day_event_rows": event_rows_in_target_day,
                        "trade_id_integrity": {
                            "null_ids": len(d["trade_id"]) - len(ids),
                            "unique_ids": len(set(ids)),
                            "duplicate_rows": len(ids) - len(set(ids)),
                            "zero_id_rows": sum(1 for x in ids if x == "0"),
                            "conflicting_ids_with_multiple_trade_payloads": sum(1 for payloads in id_to_keys.values() if len(payloads) > 1),
                        },
                        "order_type_counts": dict(order_types),
                        "receive_minus_trade_ms": {
                            "min": min(lag_ms) if lag_ms else None,
                            "median": sorted_lag[len(sorted_lag)//2] if sorted_lag else None,
                            "max": max(lag_ms) if lag_ms else None,
                            "negative_rows": sum(1 for x in lag_ms if x < 0),
                        },
                    }
                except urllib.error.HTTPError as exc:
                    file_diagnostics[partition_key] = {"status": "HTTP_ERROR", "http_status": exc.code, "error": f"HTTP {exc.code}: {exc.reason}"}
                except Exception as exc:
                    file_diagnostics[partition_key] = {"status": "DOWNLOAD_OR_DECODE_FAILED", "error": f"{type(exc).__name__}: {exc}"}

            day_hour_comparisons = {}
            for event_hour in HOURS:
                reference = tardis_by_hour[event_hour]
                candidate = candidate_by_event_hour[event_hour]
                comparison = multiset_diff(reference, candidate)
                multiplicity = Counter()
                samples = []
                for key in set(reference) | set(candidate):
                    ref_n = reference[key]
                    chd_n = candidate[key]
                    if ref_n == 0:
                        category = "candidate_only"
                    elif chd_n == ref_n:
                        category = "exact_count"
                    elif chd_n == 3 * ref_n:
                        category = "exactly_3x"
                    elif chd_n > ref_n:
                        category = "more_than_reference"
                    else:
                        category = "less_than_reference"
                    multiplicity[category] += 1
                    if category == "exactly_3x" and len(samples) < 5:
                        receive_values = candidate_received_by_event_hour[event_hour].get(key, [])
                        samples.append({
                            "trade_key": [key[0], key[1], str(key[2]), str(key[3])],
                            "tardis_multiplicity": ref_n,
                            "cryptohftdata_multiplicity": chd_n,
                            "receive_times_ns": receive_values[:6],
                            "distinct_receive_times": len(set(receive_values)),
                        })
                comparison["payload_multiplicity_diagnostics"] = {
                    "unique_payload_keys_by_relation": dict(multiplicity),
                    "examples_exactly_3x": samples,
                }
                day_hour_comparisons[event_hour] = comparison
                for key in ("tardis_rows", "cryptohftdata_rows", "matched_rows", "missing_from_cryptohftdata", "extra_in_cryptohftdata"):
                    total[key] += comparison[key]
            day_report["receive_partitions"] = file_diagnostics
            day_report["event_hour_comparisons"] = day_hour_comparisons
            day_report["cryptohftdata_event_rows"] = sum(sum(x.values()) for x in candidate_by_event_hour.values())
            day_report["status"] = (
                "OPERATIONAL_GAPS" if any(v["status"] != "DOWNLOADED" for v in file_diagnostics.values())
                else "MISMATCH_REVIEW_REQUIRED" if any(v["missing_from_cryptohftdata"] or v["extra_in_cryptohftdata"] for v in day_hour_comparisons.values())
                else "EXACT_MATCH"
            )
            report["days"][date] = day_report


    report["totals"] = total
    report["comparison_status"] = (
        "OPERATIONAL_GAPS" if any(
            day.get("status") == "OPERATIONAL_GAPS" for day in report["days"].values()
        )
        else "MISMATCH_REVIEW_REQUIRED"
        if total["missing_from_cryptohftdata"] or total["extra_in_cryptohftdata"]
        else "EXACT_MATCH"
    )
    report["crypto_files_requested"] = request_count
    report["rate_limit_policy"] = "1.05 second delay between CryptoHFTData file requests"
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "bybit_monthly_trade_crosscheck.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failed or any(day.get('status') == 'OPERATIONAL_GAPS' for day in report['days'].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
