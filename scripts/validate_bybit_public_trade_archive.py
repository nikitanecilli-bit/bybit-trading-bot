#!/usr/bin/env python3
"""Validate Bybit public BTCUSDT linear trade archives against official H1 candles and detect timestamp offset."""
from __future__ import annotations
import csv, gzip, hashlib, io, json, os, time, urllib.error, urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import median

SYMBOL = os.getenv("SYMBOL", "BTCUSDT").upper()
START = date.fromisoformat(os.getenv("START_DATE", "2024-04-11"))
END = date.fromisoformat(os.getenv("END_DATE", "2024-04-13"))
DATES_RAW = os.getenv("TRADE_DATES", "").strip()
TRADE_DATES = [date.fromisoformat(x.strip()) for x in DATES_RAW.split(",") if x.strip()] if DATES_RAW else None
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
            candles[int(r["start_ms"])] = float(r["volume"])

    agg = defaultdict(lambda: {"buy": 0.0, "sell": 0.0, "count": 0,
                               "buy_count": 0, "sell_count": 0,
                               "rpi_buy": 0.0, "rpi_sell": 0.0,
                               "rpi_count": 0, "rpi_volume": 0.0,
                               "rpi_unknown_count": 0,
                               "max_trade_size": 0.0, "notional": 0.0})
    manifest_days, missing = [], []
    total_rows = total_bytes = 0
    selected_days = sorted(set(TRADE_DATES or list(days(START, END))))
    for day in selected_days:
        url, raw, payload = fetch_day(day)
        if payload is None:
            missing.append(day.isoformat())
            continue
        digest = hashlib.sha256(raw).hexdigest()
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig", errors="replace")))
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
            # Decimal avoids binary-float truncation around millisecond boundaries.
            ts_ms = int(Decimal(r["timestamp"]) * Decimal(1000))
            hour = (ts_ms // HOUR_MS) * HOUR_MS
            size, price = float(r["size"]), float(r["price"])
            x = agg[hour]
            x["buy" if side == "Buy" else "sell"] += size
            x["buy_count" if side == "Buy" else "sell_count"] += 1
            x["count"] += 1
            rpi_raw = str(r.get("RPI", "")).strip().lower()
            if rpi_raw in ("1", "true", "yes", "y"):
                x["rpi_buy" if side == "Buy" else "rpi_sell"] += size
                x["rpi_count"] += 1
                x["rpi_volume"] += size
            elif rpi_raw not in ("", "0", "false", "no", "n"):
                x["rpi_unknown_count"] += 1
            x["max_trade_size"] = max(x["max_trade_size"], size)
            x["notional"] += size * price
            rows += 1
        total_rows += rows
        total_bytes += len(raw)
        manifest_days.append({"date": day.isoformat(), "url": url, "rows": rows,
                              "compressed_bytes": len(raw), "sha256": digest,
                              "columns": reader.fieldnames})
        time.sleep(0.15)

    if missing:
        raise SystemExit(f"Missing trade archive dates: {missing}")
    if not agg:
        raise SystemExit("No public trade rows downloaded")

    # Detect the constant shift by comparing each trade-hour volume with candle volumes
    # at candidate offsets. Positive offset means candle timestamp is later than trade UTC.
    alignment = []
    for offset in range(-6, 7):
        diffs = []
        for hour, x in agg.items():
            candle_volume = candles.get(hour + offset * HOUR_MS)
            total = x["buy"] + x["sell"]
            if candle_volume is not None and candle_volume > 0:
                diffs.append(abs(total / candle_volume - 1.0) * 100)
        if diffs:
            ordered = sorted(diffs)
            alignment.append({
                "candle_timestamp_offset_hours": offset,
                "matched_hours": len(diffs),
                "median_abs_volume_difference_pct": round(median(diffs), 8),
                "p95_abs_volume_difference_pct": round(ordered[int(0.95*(len(ordered)-1))], 8),
                "max_abs_volume_difference_pct": round(max(diffs), 8),
            })
    best = min(alignment, key=lambda x: (x["median_abs_volume_difference_pct"],
                                         x["p95_abs_volume_difference_pct"]))
    best_offset = best["candle_timestamp_offset_hours"]

    # Diagnose alignment separately for each UTC trade date, so a seasonal
    # server-clock change cannot be hidden by a pooled result.
    per_day_alignment = []
    for day in selected_days:
        day_hours = [(h, x) for h, x in agg.items()
                     if datetime.fromtimestamp(h/1000, timezone.utc).date() == day]
        candidates = []
        for offset in range(-6, 7):
            diffs = []
            for hour, x in day_hours:
                cv = candles.get(hour + offset * HOUR_MS)
                tv = x["buy"] + x["sell"]
                if cv is not None and cv > 0:
                    diffs.append(abs(tv / cv - 1.0) * 100)
            if diffs:
                ordered = sorted(diffs)
                candidates.append({"offset_hours": offset, "matched_hours": len(diffs),
                                   "median_abs_diff_pct": round(median(diffs), 8),
                                   "p95_abs_diff_pct": round(ordered[int(0.95*(len(ordered)-1))], 8)})
        if candidates:
            day_best = min(candidates, key=lambda x: (x["median_abs_diff_pct"], x["p95_abs_diff_pct"]))
            per_day_alignment.append({"trade_date": day.isoformat(), "best": day_best})

    out_rows = []
    for hour in sorted(agg):
        x = agg[hour]
        total = x["buy"] + x["sell"]
        candle_ts = hour + best_offset * HOUR_MS
        candle_volume = candles.get(candle_ts)
        diff_pct = ((total / candle_volume) - 1.0) * 100 if candle_volume else None
        out_rows.append({
            "trade_hour_utc": datetime.fromtimestamp(hour/1000, timezone.utc).isoformat(),
            "matched_candle_timestamp": datetime.fromtimestamp(candle_ts/1000, timezone.utc).isoformat(),
            "buy_taker_volume": round(x["buy"], 10),
            "sell_taker_volume": round(x["sell"], 10),
            "delta": round(x["buy"] - x["sell"], 10),
            "total_trade_volume": round(total, 10),
            "buy_count": x["buy_count"], "sell_count": x["sell_count"],
            "trade_count": x["count"],
            "max_trade_size": round(x["max_trade_size"], 10),
            "trade_notional_usdt": round(x["notional"], 4),
            "rpi_trade_count": x["rpi_count"],
            "rpi_trade_volume": round(x["rpi_volume"], 10),
            "rpi_volume_share_pct": round(x["rpi_volume"] / total * 100, 6) if total else 0.0,
            "non_rpi_delta": round((x["buy"] - x["rpi_buy"]) - (x["sell"] - x["rpi_sell"]), 10),
            "rpi_unknown_count": x["rpi_unknown_count"],
            "official_h1_volume": candle_volume,
            "volume_difference_pct": round(diff_pct, 8) if diff_pct is not None else None,
        })
    if out_rows:
        with (OUT / "hourly_trade_flow.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
            w.writeheader(); w.writerows(out_rows)
    report = {
        "source": "Bybit official public linear trade archive: public.bybit.com/trading",
        "symbol": SYMBOL,
        "trade_dates": [d.isoformat() for d in selected_days],
        "daily_files_found": len(manifest_days), "daily_files_missing": missing,
        "trade_rows": total_rows, "compressed_bytes": total_bytes,
        "hourly_buckets": len(out_rows),
        "best_alignment": best,
        "alignment_candidates": alignment,
        "per_day_best_alignment": per_day_alignment,
        "rpi_columns_present_dates": [d["date"] for d in manifest_days if "RPI" in d["columns"]],
        "rpi_note": "RPI trades are tracked separately because RPI liquidity is not visible in the public orderbook API; never silently mix RPI flow with visible-book pressure.",
        "interpretation": (
            "Positive offset means official H1 candle timestamps are later than trade UTC. "
            "If +3h remains exact across years, normalize H1 timestamps by subtracting 3h. "
            "Trade side is taker/aggressor side; trade archives do not reconstruct resting limit orders."
        ),
        "days": manifest_days,
    }
    (OUT / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
