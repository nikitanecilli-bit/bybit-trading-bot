#!/usr/bin/env python3
"""Cross-check four monthly Bybit BTCUSDT trade days across two providers.

Tardis offers first-of-month sample days. CryptoHFTData hourly downloads are
paced below its anonymous 60-files/minute limit. Raw files stay temporary.
"""
from __future__ import annotations

import csv
import gzip
import json
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from compare_bybit_trade_archives import dec, download, multiset_diff

DATES = ("2025-07-01", "2025-12-01", "2026-04-01", "2026-11-01")
HOURS = tuple(f"{hour:02d}" for hour in range(24))
SYMBOL = "BTCUSDT"
CHD_BASE = "https://api.cryptohftdata.com/download"
TARDIS_BASE = "https://datasets.tardis.dev/v1/bybit/trades"


def tardis_url(date: str) -> str:
    year, month, day = date.split("-")
    return f"{TARDIS_BASE}/{year}/{month}/{day}/{SYMBOL}.csv.gz"


def chd_url(date: str, hour: str) -> str:
    file_path = f"bybit/{date}/{hour}/{SYMBOL}_trades.parquet"
    return CHD_BASE + "?" + urllib.parse.urlencode({"file": file_path})


def load_tardis_day(path: Path) -> tuple[dict[str, Counter], int]:
    by_hour = {hour: Counter() for hour in HOURS}
    unknown_sides = 0
    expected = ["exchange", "symbol", "timestamp", "local_timestamp",
                "id", "side", "price", "amount"]
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != expected:
            raise ValueError(f"Tardis header mismatch: {reader.fieldnames!r}")
        for row_no, row in enumerate(reader, 2):
            if None in row or row["exchange"] != "bybit" or row["symbol"] != SYMBOL:
                raise ValueError(f"invalid Tardis row {row_no}")
            ts_us = int(row["timestamp"])
            hour = datetime.fromtimestamp(ts_us // 1_000_000, tz=timezone.utc).strftime("%H")
            side = row["side"].lower()
            if side not in ("buy", "sell"):
                unknown_sides += 1
                continue
            by_hour[hour][(ts_us // 1000, side, dec(row["price"]), dec(row["amount"]))] += 1
    return by_hour, unknown_sides


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider_a": "Tardis.dev",
        "provider_b": "CryptoHFTData",
        "symbol": SYMBOL,
        "dates": list(DATES),
        "hours_utc": list(HOURS),
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
                day_report["tardis_download"] = download(tardis_url(date), tardis_path)
                tardis_by_hour, unknown_sides = load_tardis_day(tardis_path)
                day_report["tardis_unknown_side_rows"] = unknown_sides
                day_report["tardis_rows"] = sum(sum(c.values()) for c in tardis_by_hour.values())
            except Exception as exc:
                day_report["status"] = "TARDIS_SAMPLE_FAILED"
                day_report["error"] = f"{type(exc).__name__}: {exc}"
                report["days"][date] = day_report
                failed = True
                continue

            for hour in HOURS:
                item = {}
                try:
                    if request_count:
                        time.sleep(1.05)
                    request_count += 1
                    url = chd_url(date, hour)
                    parquet_path = root / f"chd_{date}_{hour}.parquet"
                    item["download"] = download(url, parquet_path)
                    table = pq.read_table(parquet_path)
                    expected = ["received_time", "event_time", "symbol", "trade_id",
                                "price", "quantity", "trade_time", "is_buyer_maker",
                                "order_type"]
                    if table.schema.names != expected:
                        raise ValueError(f"CryptoHFTData schema mismatch: {table.schema.names!r}")
                    d = table.to_pydict()
                    candidate = Counter()
                    ids = [str(x) for x in d["trade_id"] if x is not None]
                    for i in range(len(d["trade_id"])):
                        if d["symbol"][i] != SYMBOL:
                            raise ValueError(f"unexpected symbol in {date} {hour}")
                        side = "sell" if d["is_buyer_maker"][i] else "buy"
                        key = (d["trade_time"][i], side, dec(d["price"][i]),
                               dec(d["quantity"][i]))
                        candidate[key] += 1
                    item["crypto_rows"] = table.num_rows
                    item["trade_id_duplicates"] = len(ids) - len(set(ids))
                    item["comparison"] = multiset_diff(tardis_by_hour[hour], candidate)
                    item["status"] = "COMPARED"
                    for key in ("tardis_rows", "cryptohftdata_rows", "matched_rows",
                                "missing_from_cryptohftdata", "extra_in_cryptohftdata"):
                        pass
                    total["tardis_rows"] += item["comparison"]["tardis_rows"]
                    total["cryptohftdata_rows"] += item["comparison"]["cryptohftdata_rows"]
                    total["matched_rows"] += item["comparison"]["matched_rows"]
                    total["missing_from_cryptohftdata"] += item["comparison"]["missing_from_cryptohftdata"]
                    total["extra_in_cryptohftdata"] += item["comparison"]["extra_in_cryptohftdata"]
                except Exception as exc:
                    item["status"] = "MISSING_OR_FAILED"
                    item["error"] = f"{type(exc).__name__}: {exc}"
                    total["missing_hour_files"] += 1
                day_report["hours"][hour] = item
            day_report["status"] = (
                "COMPARED_WITH_GAPS" if any(v["status"] != "COMPARED"
                                             for v in day_report["hours"].values())
                else "COMPARED"
            )
            report["days"][date] = day_report

    report["totals"] = total
    report["crypto_files_requested"] = request_count
    report["rate_limit_policy"] = "1.05 second delay between CryptoHFTData file requests"
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "bybit_monthly_trade_crosscheck.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
