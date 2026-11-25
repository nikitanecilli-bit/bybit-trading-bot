#!/usr/bin/env python3
"""Verify Bybit MT4 H1 archive OHLC against Bybit's official linear trade tape."""
from __future__ import annotations
import csv, gzip, hashlib, json, urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

DATE = "2025-07-01"
SYMBOL = "BTCUSDT"
OUT = Path("bybit_linear_identity_probe")
OUT.mkdir(exist_ok=True)

def download(url: str, path: Path) -> str:
    req = urllib.request.Request(url, headers={"User-Agent":"bybit-market-identity-probe/1.0","Accept":"*/*"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=180) as response, path.open("wb") as out:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        while True:
            block = response.read(1024*1024)
            if not block:
                break
            digest.update(block)
            out.write(block)
    return digest.hexdigest()

trade_url = f"https://public.bybit.com/trading/{SYMBOL}/{SYMBOL}{DATE}.csv.gz"
mt4_url = f"https://public.bybit.com/kline_for_metatrader4/{SYMBOL}/2025/{SYMBOL}_60_{DATE}_2025-07-31.csv.gz"
trade_path = OUT / "linear_trades.csv.gz"
mt4_path = OUT / "mt4_h1.csv.gz"
trade_sha = download(trade_url, trade_path)
mt4_sha = download(mt4_url, mt4_path)

bars = defaultdict(lambda: {"open":None,"high":None,"low":None,"close":None,"volume":Decimal("0"),"n":0})
with gzip.open(trade_path, "rt", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, strict=True)
    required = {"timestamp","symbol","side","size","price","trdMatchID"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise RuntimeError(f"unexpected official linear trade columns: {reader.fieldnames}")
    for row in reader:
        if row["symbol"] != SYMBOL:
            raise RuntimeError(f"symbol mismatch: {row['symbol']}")
        ts_ms = int(Decimal(row["timestamp"]) * 1000)
        hour = ts_ms // 3_600_000 * 3_600_000
        price = Decimal(row["price"])
        size = Decimal(row["size"])
        b = bars[hour]
        if b["open"] is None:
            b["open"] = price
        b["high"] = price if b["high"] is None else max(b["high"], price)
        b["low"] = price if b["low"] is None else min(b["low"], price)
        b["close"] = price
        b["volume"] += size
        b["n"] += 1

mt4 = {}
with gzip.open(mt4_path, "rt", encoding="utf-8", newline="") as f:
    reader = csv.reader(f, strict=True)
    for row in reader:
        if len(row) < 6:
            continue
        dt = datetime.strptime(row[0].strip(), "%Y.%m.%d %H:%M").replace(tzinfo=timezone.utc)
        # MT4 archive labels are UTC+3; normalize to UTC before matching.
        utc_dt = dt - timedelta(hours=3)
        ts = int(utc_dt.replace(tzinfo=timezone.utc).timestamp()*1000)
        if DATE <= utc_dt.strftime("%Y-%m-%d") < "2025-07-02":
            mt4[ts] = tuple(Decimal(x.strip()) for x in row[1:6])

comparisons = []
for ts in sorted(set(bars) & set(mt4)):
    b, m = bars[ts], mt4[ts]
    official = (b["open"],b["high"],b["low"],b["close"])
    mt4_ohlc = m[:4]
    diffs = [abs(a-c) for a,c in zip(official,mt4_ohlc)]
    comparisons.append({
        "timestamp_utc":datetime.fromtimestamp(ts/1000,timezone.utc).isoformat(),
        "linear_trade_count":b["n"],
        "official_ohlc":[str(x) for x in official],
        "mt4_ohlc":[str(x) for x in mt4_ohlc],
        "max_abs_price_diff":str(max(diffs)),
        "exact_ohlc_match":all(d==0 for d in diffs),
        "within_one_tick":max(diffs) <= Decimal("0.10"),
        "official_base_volume":str(b["volume"]),
        "mt4_volume":str(m[4]),
        "volume_diff":str(abs(b["volume"]-m[4])),
    })

result = {
    "date_utc":DATE,"symbol":SYMBOL,
    "official_trade_archive_url":trade_url,"mt4_kline_archive_url":mt4_url,
    "official_trade_archive_sha256":trade_sha,"mt4_archive_sha256":mt4_sha,
    "linear_trade_hours":len(bars),"mt4_hours_on_date":sum(1 for t in mt4 if datetime.fromtimestamp(t/1000,timezone.utc).strftime("%Y-%m-%d")==DATE),
    "overlap_hours":len(comparisons),
    "exact_ohlc_hours":sum(1 for x in comparisons if x["exact_ohlc_match"]),
    "within_one_tick_hours":sum(1 for x in comparisons if x["within_one_tick"]),
    "max_volume_diff":max((Decimal(x["volume_diff"]) for x in comparisons),default=Decimal("0")).__str__(),
    "max_abs_price_diff":max((Decimal(x["max_abs_price_diff"]) for x in comparisons),default=Decimal("0")).__str__(),
    "comparisons":comparisons,
}
(OUT/"identity_probe.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
