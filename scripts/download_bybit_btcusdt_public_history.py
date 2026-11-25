#!/usr/bin/env python3
"""Bounded, public-only Bybit BTCUSDT H1/Mark/funding history downloader.

Raw API page responses are retained as gzip JSONL alongside normalized CSVs.
No credentials, private endpoints, account data, or trading actions.
"""
from __future__ import annotations
import csv, gzip, hashlib, json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Official Bybit mainnet hosts; US-based runners may be restricted.
BASE_CANDIDATES = ["https://api.bybit.com", "https://api.bytick.com", "https://api.bybit.eu"]
BASE = None
CATEGORY = "linear"
SYMBOL = "BTCUSDT"
INTERVAL = "60"
START_MS = int(datetime.fromisoformat(os.getenv("START_UTC", "2020-01-01").replace("Z","+00:00")).replace(tzinfo=timezone.utc).timestamp()*1000)
END_MS = int(datetime.now(timezone.utc).timestamp()*1000)
OUT = Path(os.getenv("OUT_DIR", "bybit_btcusdt_initial"))
OUT.mkdir(parents=True, exist_ok=True)

def request(path, params):
    global BASE
    hosts = [BASE] if BASE else BASE_CANDIDATES
    last = None
    for host in hosts:
        url = host + path + "?" + urllib.parse.urlencode(params)
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent":"bybit-btcusdt-research/1.0"})
                with urllib.request.urlopen(req, timeout=35) as r:
                    payload = json.loads(r.read())
                if payload.get("retCode") != 0:
                    raise RuntimeError(f"Bybit retCode={payload.get('retCode')} retMsg={payload.get('retMsg')}")
                BASE = host
                return payload
            except Exception as e:
                last = e
                if isinstance(e, urllib.error.HTTPError) and e.code == 403:
                    break
                time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"Request failed on official Bybit hosts {hosts}: {last}")

def collect(path, name, params, row_key, timestamp_index, limit=1000, time_keys=("startTime","endTime")):
    cursor = END_MS
    pages = 0
    rows = {}
    raw_path = OUT / f"{name}.raw.jsonl.gz"
    with gzip.open(raw_path, "wt", encoding="utf-8") as raw:
        while cursor >= START_MS:
            p = dict(params)
            p[time_keys[0]] = START_MS
            p[time_keys[1]] = cursor
            p["limit"] = limit
            payload = request(path, p)
            raw.write(json.dumps(payload, separators=(",",":")) + "\n")
            batch = payload.get("result", {}).get(row_key, [])
            if not batch:
                break
            oldest = min(int(x[timestamp_index]) for x in batch)
            for x in batch:
                ts = int(x[timestamp_index])
                if START_MS <= ts <= END_MS:
                    rows[ts] = x
            pages += 1
            if oldest <= START_MS or oldest >= cursor:
                break
            cursor = oldest - 1
            time.sleep(0.12)
    ordered = [rows[k] for k in sorted(rows)]
    csv_path = OUT / f"{name}.csv"
    if name in ("trade_h1", "mark_h1"):
        headers = ["start_ms","open","high","low","close","volume","turnover","confirm"]
    else:
        headers = ["symbol","funding_rate","funding_time_ms"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(headers); w.writerows(ordered)
    return {"name":name,"pages":pages,"rows":len(ordered),"first_ts":min(rows) if rows else None,
            "last_ts":max(rows) if rows else None,"csv":csv_path.name,"raw":raw_path.name}

results=[]
results.append(collect("/v5/market/kline","trade_h1",
    {"category":CATEGORY,"symbol":SYMBOL,"interval":INTERVAL},"list",0,1000,("start","end")))
results.append(collect("/v5/market/mark-price-kline","mark_h1",
    {"category":CATEGORY,"symbol":SYMBOL,"interval":INTERVAL},"list",0,1000,("start","end")))
results.append(collect("/v5/market/funding/history","funding",
    {"category":CATEGORY,"symbol":SYMBOL},"list",2,200))

# Capture current contract metadata for context only; not treated as historical specs.
for name,path,params in [
    ("instrument_info","/v5/market/instruments-info",{"category":CATEGORY,"symbol":SYMBOL}),
    ("risk_limit_current","/v5/market/risk-limit",{"category":CATEGORY,"symbol":SYMBOL}),
]:
    payload=request(path,params)
    (OUT/f"{name}.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
    results.append({"name":name,"retCode":payload.get("retCode")})

manifest={"source":"Bybit public V5 REST API","category":CATEGORY,"symbol":SYMBOL,
          "start_ms":START_MS,"end_ms":END_MS,"start_utc":datetime.fromtimestamp(START_MS/1000,timezone.utc).isoformat(),
          "end_utc":datetime.fromtimestamp(END_MS/1000,timezone.utc).isoformat(),"results":results}
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name!="manifest.json":
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        manifest.setdefault("sha256",{})[p.name]=h
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print(json.dumps(manifest,indent=2))
