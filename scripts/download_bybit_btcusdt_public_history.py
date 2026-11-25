#!/usr/bin/env python3
"""Download Bybit's own public BTCUSDT H1 archive (CSV.GZ), no credentials."""
from __future__ import annotations
import csv, gzip, hashlib, io, json, os, time, urllib.error, urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

SYMBOL = "BTCUSDT"
START = date.fromisoformat(os.getenv("START_DATE", "2020-01-01"))
END = datetime.now(timezone.utc).date()
OUT = Path(os.getenv("OUT_DIR", "bybit_btcusdt_initial"))
OUT.mkdir(parents=True, exist_ok=True)

def months_between(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1

def month_end(y, m):
    if m == 12:
        return date(y, 12, 31)
    return date(y, m + 1, 1).fromordinal(date(y, m + 1, 1).toordinal() - 1)

def fetch_month(y, m):
    start = date(y, m, 1)
    end = month_end(y, m)
    url = (f"https://public.bybit.com/kline_for_metatrader4/{SYMBOL}/{y}/"
           f"{SYMBOL}_60_{start.isoformat()}_{end.isoformat()}.csv.gz")
    req = urllib.request.Request(url, headers={"User-Agent":"bybit-btcusdt-research/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                raw = response.read()
            payload = gzip.decompress(raw) if raw[:2] == bytes([31,139]) else raw
            return url, payload
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return url, None
            if e.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2 ** attempt)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Unable to download {url}")

rows = {}
months_ok, months_missing, raw_files = [], [], []
for y, m in months_between(START, END):
    label = f"{y:04d}-{m:02d}"
    url, payload = fetch_month(y, m)
    if payload is None:
        months_missing.append(label)
        continue
    raw_path = OUT / f"{SYMBOL}_H1_{label}.csv"
    raw_path.write_bytes(payload)
    raw_files.append(raw_path)
    count = 0
    for line in payload.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        parts = next(csv.reader([line]))
        if len(parts) < 6:
            continue
        try:
            dt = datetime.strptime(parts[0].strip(), "%Y.%m.%d %H:%M").replace(tzinfo=timezone.utc)
            ts = int(dt.timestamp() * 1000)
            if ts < int(datetime.combine(START, datetime.min.time(), tzinfo=timezone.utc).timestamp()*1000):
                continue
            if ts > int(datetime.combine(END, datetime.min.time(), tzinfo=timezone.utc).timestamp()*1000):
                continue
            rows[ts] = [ts, *[p.strip() for p in parts[1:6]]]
            count += 1
        except (ValueError, IndexError):
            continue
    months_ok.append({"month":label,"rows_in_file":count,"bytes":len(payload),"url":url})
    time.sleep(0.1)

ordered = [rows[k] for k in sorted(rows)]
csv_path = OUT / "trade_h1.csv"
with csv_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["start_ms","open","high","low","close","volume"])
    w.writerows(ordered)

manifest = {
    "source":"Bybit official public archive: public.bybit.com/kline_for_metatrader4",
    "category":"linear","symbol":SYMBOL,"interval":"60",
    "requested_start":START.isoformat(),"requested_end":END.isoformat(),
    "rows":len(ordered),
    "first_utc":datetime.fromtimestamp(ordered[0][0]/1000,timezone.utc).isoformat() if ordered else None,
    "last_utc":datetime.fromtimestamp(ordered[-1][0]/1000,timezone.utc).isoformat() if ordered else None,
    "months_downloaded":months_ok,"months_missing":months_missing,
    "csv":csv_path.name
}
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name != "manifest.json":
        manifest.setdefault("sha256",{})[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print(json.dumps(manifest,indent=2))
