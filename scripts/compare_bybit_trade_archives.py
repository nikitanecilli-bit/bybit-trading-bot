#!/usr/bin/env python3
"""Compare one Tardis Bybit trade day with selected CryptoHFTData hours.

This is a source-to-source consistency check, not an assertion that either
provider is ground truth. Raw archives remain temporary; only a report is kept.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
import tempfile
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

DATE = "2026-11-01"
SYMBOL = "BTCUSDT"
HOURS = ("01", "02", "03", "12")
TARDIS_URL = f"https://datasets.tardis.dev/v1/bybit/trades/2026/11/01/{SYMBOL}.csv.gz"
CHD_BASE = "https://api.cryptohftdata.com/download"
MAX_FILE_BYTES = 50 * 1024 * 1024


def download(url: str, path: Path) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "bybit-trade-crosscheck/1.0"})
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as out:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status}")
        expected = response.headers.get("Content-Length")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise RuntimeError(f"file exceeds {MAX_FILE_BYTES} byte safety limit")
            out.write(chunk)
            digest.update(chunk)
    if expected is not None and total != int(expected):
        raise RuntimeError(f"size mismatch expected={expected} actual={total}")
    return {"bytes": total, "sha256": digest.hexdigest()}


def dec(value: str) -> Decimal:
    return Decimal(value)


def multiset_diff(reference: Counter, candidate: Counter) -> dict:
    matched = sum(min(count, candidate.get(key, 0)) for key, count in reference.items())
    missing = sum(max(count - candidate.get(key, 0), 0)
                  for key, count in reference.items())
    extra = sum(max(count - reference.get(key, 0), 0)
                for key, count in candidate.items())
    return {"matched_rows": matched, "missing_from_cryptohftdata": missing,
            "extra_in_cryptohftdata": extra,
            "tardis_rows": sum(reference.values()),
            "cryptohftdata_rows": sum(candidate.values()),
            "match_pct_of_tardis": round(100 * matched / max(1, sum(reference.values())), 4)}


def main() -> int:
    import pyarrow.parquet as pq
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": DATE, "symbol": SYMBOL, "hours_utc": list(HOURS),
        "scope": "exact multiset comparison by millisecond time, aggressor side, price and quantity; no PnL",
        "raw_archives_uploaded": False,
        "tardis": {}, "hours": {},
    }
    failed = False
    with tempfile.TemporaryDirectory(prefix="bybit-trade-crosscheck-") as tmp:
        root = Path(tmp)
        tardis_path = root / "tardis_trades.csv.gz"
        try:
            report["tardis"]["download"] = download(TARDIS_URL, tardis_path)
            tardis_by_hour = {hour: Counter() for hour in HOURS}
            tardis_rows = 0
            tardis_unknown_side = 0
            tardis_timestamp_regressions = 0
            previous_local = None
            expected_header = ["exchange", "symbol", "timestamp", "local_timestamp",
                               "id", "side", "price", "amount"]
            with gzip.open(tardis_path, "rt", encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream, strict=True)
                if reader.fieldnames != expected_header:
                    raise ValueError(f"Tardis header mismatch: {reader.fieldnames!r}")
                for row_no, row in enumerate(reader, 2):
                    if None in row or row["exchange"] != "bybit" or row["symbol"] != SYMBOL:
                        raise ValueError(f"invalid Tardis row {row_no}")
                    ts_us = int(row["timestamp"])
                    local_us = int(row["local_timestamp"])
                    if previous_local is not None and local_us < previous_local:
                        tardis_timestamp_regressions += 1
                    previous_local = local_us
                    side = row["side"].lower()
                    if side not in ("buy", "sell"):
                        tardis_unknown_side += 1
                        continue
                    hour = datetime.fromtimestamp(ts_us // 1_000_000, tz=timezone.utc).strftime("%H")
                    if hour not in tardis_by_hour:
                        continue
                    key = (ts_us // 1000, side, dec(row["price"]), dec(row["amount"]))
                    tardis_by_hour[hour][key] += 1
                    tardis_rows += 1
            report["tardis"].update({
                "rows_in_selected_hours": tardis_rows,
                "capture_time_regressions": tardis_timestamp_regressions,
                "unknown_side_rows_in_selected_hours": tardis_unknown_side,
            })
        except Exception as exc:
            report["tardis"]["error"] = f"{type(exc).__name__}: {exc}"
            failed = True
            tardis_by_hour = {hour: Counter() for hour in HOURS}

        for hour in HOURS:
            item = {}
            try:
                file_path = f"bybit/{DATE}/{hour}/{SYMBOL}_trades.parquet"
                url = CHD_BASE + "?" + urllib.parse.urlencode({"file": file_path})
                parquet_path = root / f"cryptohftdata_trades_{hour}.parquet"
                item["download"] = download(url, parquet_path)
                table = pq.read_table(parquet_path)
                expected = ["received_time", "event_time", "symbol", "trade_id", "price",
                            "quantity", "trade_time", "is_buyer_maker", "order_type"]
                if table.schema.names != expected:
                    raise ValueError(f"CryptoHFTData schema mismatch: {table.schema.names!r}")
                d = table.to_pydict()
                candidate = Counter()
                for i in range(len(d["trade_id"])):
                    if d["symbol"][i] != SYMBOL:
                        raise ValueError(f"unexpected symbol in hour {hour}")
                    side = "sell" if d["is_buyer_maker"][i] else "buy"
                    key = (d["trade_time"][i], side, dec(d["price"][i]),
                           dec(d["quantity"][i]))
                    candidate[key] += 1
                item["parquet_rows"] = table.num_rows
                item["comparison"] = multiset_diff(tardis_by_hour[hour], candidate)
                item["status"] = "COMPARED"
            except Exception as exc:
                item["status"] = "FAILED"
                item["error"] = f"{type(exc).__name__}: {exc}"
                failed = True
            report["hours"][hour] = item

    output = Path(sys.argv[1] if len(sys.argv) > 1 else "bybit_trade_crosscheck.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
