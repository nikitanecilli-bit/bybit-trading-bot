#!/usr/bin/env python3
"""Validate Bybit public BTCUSDT linear trade archives against official H1 candles."""
from __future__ import annotations
import csv, gzip, hashlib, io, json, os, time, urllib.error, urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from statistics import median

SYMBOL = os.getenv("SYMBOL", "BTCUSDT").upper()
START = date.fromisoformat(os.getenv("START_DATE", "2024-04-11"))
END = date.fromisoformat(os.getenv("END_DATE", "2024-04-13"))
KLINE = Path(os.getenv("KLINE_PATH", "bybit_btcusdt_initial/trade_h1.csv"))
OUT = Path(os.getenv("OUT_DIR", "trade_flow_validation"))
OUT.mkdir(parents=True, exist_ok=True)
HOUR_MS = 3_600_000

def days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def fetch_day(day: date):
    name = f"{SYMBOL}{day.isoformat()}.csv.gz"
    url = f"https://public.bybit.com/trading/{SYMBOL}/{name}"
    req = urllib.request.Request(url, headers={"User-Agent": "bybit-market-research/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                raw = response.read()
            payload = gzip.decompress(raw)
            return url, raw, payload
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return url, None, None
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2 ** attempt)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Could not download {url}")

def main():
    if not KLINE.exists():
        raise SystemExit(f"Missing official H1 archive: {KLINE}")
    candles = {}
    with KLINE.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ts = int(r["start_ms"])
            candles[ts] = float(r["volume"])

    agg = defaultdict(lambda: {"buy": 0.0, "sell": 0.0, "count": 0,
                               "buy_count": 0, "sell_count": 0,
                               "max_trade_size": 0.0, "notional": 0.0})
    manifest_days, missing = [], []
    total_rows = 0
    total_bytes = 0
    for day in days(START, END):
        url, raw, payload = fetch_day(day)
        if payload is None:
            missing.append(day.isoformat())
            continue
        digest = hashlib.sha256(raw).hexdigest()
        text = payload.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        required = {"timestamp", "symbol", "side", "size", "price", "trdMatchID"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise SystemExit(f"Unexpected columns in {url}: {reader.fieldnames}")
        rows = 0
        for r in reader:
            if r.get("symbol") != SYMBOL:
                continue
            side = r.get("side")
            if side not in ("Buy", "Sell"):
                raise SystemExit(f"Unexpected taker side {side!r} in {url}")
            ts_ms = int(float(r["timestamp"]) * 1000)
            hour = (ts_ms // HOUR_MS) * HOUR_MS
            size = float(r["size"])
            price = float(r["price"])
            x = agg[hour]
            x["buy" if side == "Buy" else "sell"] += size
            x["buy_count" if side == "Buy" else "sell_count"] += 1
            x["count"] += 1
            x["max_trade_size"] = max(x["max_trade_size"], size)
            x["notional"] += size * price
            rows += 1
        total_rows += rows
        total_bytes += len(raw)
        manifest_days.append({"date": day.isoformat(), "url": url, "rows": rows,
                              "compressed_bytes": len(raw), "sha256": digest,
                              "columns": reader.fieldnames})
        time.sleep(0.15)

    out_rows = []
    diffs = []
    for hour in sorted(agg):
        x = agg[hour]
        total = x["buy"] + x["sell"]
        candle_volume = candles.get(hour)
        diff_pct = ((total / candle_volume) - 1.0) * 100 if candle_volume else None
        if diff_pct is not None:
            diffs.append(abs(diff_pct))
        out_rows.append({
            "hour_utc": datetime.fromtimestamp(hour/1000, timezone.utc).isoformat(),
            "buy_taker_volume": round(x["buy"], 10),
            "sell_taker_volume": round(x["sell"], 10),
            "delta": round(x["buy"] - x["sell"], 10),
            "total_trade_volume": round(total, 10),
            "buy_count": x["buy_count"], "sell_count": x["sell_count"],
            "trade_count": x["count"],
            "max_trade_size": round(x["max_trade_size"], 10),
            "trade_notional_usdt": round(x["notional"], 4),
            "official_h1_volume": candle_volume,
            "volume_difference_pct": round(diff_pct, 6) if diff_pct is not None else None,
        })
    if out_rows:
        with (OUT / "hourly_trade_flow.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
            w.writeheader(); w.writerows(out_rows)
    report = {
        "source": "Bybit official public linear trade archive: public.bybit.com/trading",
        "symbol": SYMBOL, "start_date": START.isoformat(), "end_date": END.isoformat(),
        "daily_files_found": len(manifest_days), "daily_files_missing": missing,
        "trade_rows": total_rows, "compressed_bytes": total_bytes,
        "hourly_buckets": len(out_rows),
        "hours_matched_to_official_h1": len(diffs),
        "absolute_volume_difference_pct_median": round(median(diffs), 6) if diffs else None,
        "absolute_volume_difference_pct_p95": round(sorted(diffs)[int(0.95*(len(diffs)-1))], 6) if diffs else None,
        "days": manifest_days,
        "interpretation": "Trade side is aggressor/taker side. Historical trades do not reconstruct resting limit orders or historical order-book depth."
    }
    (OUT / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if missing:
        raise SystemExit(f"Missing trade archive dates: {missing}")
    if not diffs:
        raise SystemExit("No hourly trade buckets matched the official H1 archive")

if __name__ == "__main__":
    main()
