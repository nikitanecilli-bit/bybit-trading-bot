#!/usr/bin/env python3
"""Verify Bybit MT4 H1 archive OHLC against Bybit official linear trade tape.

The MT4 archive timestamps are UTC+3. Trade archive timestamps are Unix UTC.
We normalize MT4 timestamps by -3 hours before matching. This is a bounded
identity check, not a market PnL backtest.
"""
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
    req = urllib.request.Request(url, headers={"User-Agent":"bybit-market-identity-probe/1.1","Accept":"*/*"})
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
        price, size = Decimal(row["price"]), Decimal(row["size"])
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
        local_dt = datetime.strptime(row[0].strip(), "%Y.%m.%d %H:%M")
        utc_dt = (local_dt - timedelta(hours=3)).replace(tzinfo=timezone.utc)
        ts = int(utc_dt.timestamp()*1000)
        mt4[ts] = tuple(Decimal(x.strip()) for x in row[1:6])

comparisons = []
for ts in sorted(set(bars) & set(mt4)):
    b, m = bars[ts], mt4[ts]
    official = (b["open"],b["high"],b["low"],b["close"])
    archived = m[:4]
    diffs = [abs(a-c) for a,c in zip(official,archived)]
    comparisons.append({
        "timestamp_utc":datetime.fromtimestamp(ts/1000,timezone.utc).isoformat(),
        "linear_trade_count":b["n"],
        "official_ohlc":[str(x) for x in official],
        "mt4_ohlc":[str(x) for x in archived],
        "ohlc_abs_diff":[str(x) for x in diffs],
        "high_low_close_exact":all(d==0 for d in diffs[1:]),
        "open_within_one_tick":diffs[0] <= Decimal("0.10"),
        "official_base_volume":str(b["volume"]),
        "mt4_volume":str(m[4]),
        "volume_exact":b["volume"] == m[4],
    })

if len(comparisons) != 24:
    raise RuntimeError(f"expected 24 overlapping hours after UTC normalization, got {len(comparisons)}")
result = {
    "date_utc":DATE,"symbol":SYMBOL,
    "mt4_timezone_normalization":"UTC+3 local timestamps shifted by -3 hours",
    "official_trade_archive_url":trade_url,"mt4_kline_archive_url":mt4_url,
    "official_trade_archive_sha256":trade_sha,"mt4_archive_sha256":mt4_sha,
    "linear_trade_hours":len(bars),"mt4_rows":len(mt4),
    "overlap_hours":len(comparisons),
    "exact_high_low_close_hours":sum(x["high_low_close_exact"] for x in comparisons),
    "open_within_one_tick_hours":sum(x["open_within_one_tick"] for x in comparisons),
    "exact_volume_hours":sum(x["volume_exact"] for x in comparisons),
    "max_abs_price_diff":str(max(Decimal(d) for x in comparisons for d in x["ohlc_abs_diff"])),
    "comparisons":comparisons,
}
(OUT/"identity_probe.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
