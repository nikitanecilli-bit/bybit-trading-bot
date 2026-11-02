#!/usr/bin/env python3
"""Offline inventory of committed CryptoFetch ZIP archives; no network/API calls."""
from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "archives" / "cryptofetch"
TS_FIELDS = ("open_time_ms", "timestamp_ms", "funding_timestamp_ms", "timestamp", "time")
NAME_RE = re.compile(r"(?i)([a-z0-9]+usdt)_(1h|15m)_")


def inspect_csv(zf: zipfile.ZipFile, name: str) -> dict:
    with zf.open(name) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
        fields = reader.fieldnames or []
        ts_field = next((field for field in TS_FIELDS if field in fields), None)
        count, first_ts, last_ts = 0, None, None
        for row in reader:
            count += 1
            if ts_field:
                value = row.get(ts_field)
                if value not in (None, ""):
                    try:
                        ts = int(float(value))
                        first_ts = ts if first_ts is None else min(first_ts, ts)
                        last_ts = ts if last_ts is None else max(last_ts, ts)
                    except (TypeError, ValueError):
                        pass
        base = name.rsplit("/", 1)[-1]
        kind = "other"
        low = (name + " " + ",".join(fields)).lower()
        if "funding_timestamp_ms" in fields or "funding_rate" in fields or "funding" in low:
            kind = "funding"
        elif "mark" in name.lower():
            kind = "mark_or_price"
        elif NAME_RE.search(base) and {"open_time_ms", "open", "high", "low", "close", "volume"}.issubset(fields):
            kind = "ohlcv"
        return {"name": name, "kind": kind, "rows": count, "fields": fields,
                "timestamp_field": ts_field, "first_timestamp": first_ts,
                "last_timestamp": last_ts}


def main() -> None:
    archives = sorted(ROOT.glob("*.zip"))
    if not archives:
        raise SystemExit(f"No ZIP archives found under {ROOT}")
    totals = {"ohlcv": 0, "funding": 0, "mark_or_price": 0, "other": 0}
    print(f"ARCHIVE_ROOT={ROOT}")
    print(f"ARCHIVES={len(archives)}")
    for archive in archives:
        print(f"\\n=== ARCHIVE {archive.name} bytes={archive.stat().st_size} ===")
        with zipfile.ZipFile(archive) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            print(f"ENTRIES={len(names)}")
            for name in names:
                if not name.lower().endswith(".csv"):
                    print(f"NON_CSV {name}")
                    continue
                try:
                    item = inspect_csv(zf, name)
                except Exception as exc:
                    print(f"REJECT {name}: {type(exc).__name__}: {exc}")
                    continue
                totals[item["kind"]] += 1
                print("DATASET " + repr(item))
    print(f"\\nTOTALS={totals}")


if __name__ == "__main__":
    main()
