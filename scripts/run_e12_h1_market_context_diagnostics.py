#!/usr/bin/env python3
"""Causal broad-market context snapshot for the E11 shared-capital trade timestamps.

No strategy simulation or threshold optimization. All context uses completed H1 bars
at the signal timestamp across the fixed 47-symbol fold-eligible universe.
"""
from __future__ import annotations
import csv, os, sys, statistics
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Bybit_Trading_Engine_v14_research as em
from run_uploaded_dataset_backtests import read_zip_datasets

FOLDS = [
    (1, "2026-04-27T12:00:00Z", "2026-06-21T05:00:00Z"),
    (2, "2026-06-21T06:00:00Z", "2026-08-14T23:00:00Z"),
    (3, "2026-08-15T00:00:00Z", "2026-10-27T00:00:00Z"),
]

def ts_ms(value):
    return int(datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()*1000)

def iso(ts):
    return datetime.fromtimestamp(ts/1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    all_data = read_zip_datasets()
    selected = {sym: item for (sym, tf), item in all_data.items()
                if tf == "1h" and len(item[2]) >= 500}
    fold_bounds = [(ts_ms(a), ts_ms(b)) for _, a, b in FOLDS]
    eligible = {}
    manifest = []
    for sym, (count, archive, candles) in sorted(selected.items()):
        stamps = [c.ts for c in candles]
        counts = [sum(lo <= t <= hi for t in stamps) for lo, hi in fold_bounds]
        include = all(n >= 100 for n in counts)
        manifest.append({
            "symbol": sym, "bars": count, "start_utc": iso(stamps[0]),
            "end_utc": iso(stamps[-1]), "source_archive": os.path.basename(archive),
            "fold1_bars": counts[0], "fold2_bars": counts[1], "fold3_bars": counts[2],
            "included": int(include),
        })
        if include:
            eligible[sym] = candles
    symbols = sorted(eligible)
    if len(symbols) < 10:
        raise SystemExit(f"Insufficient fold-eligible universe: {len(symbols)}")
    common = None
    for sym in symbols:
        st = {c.ts for c in eligible[sym]}
        common = st if common is None else common.intersection(st)
    stamps = sorted(common or [])
    if len(stamps) < 3000:
        raise SystemExit(f"Insufficient common H1 timestamps: {len(stamps)}")
    data = {}
    for sym in symbols:
        index = {c.ts: c for c in eligible[sym]}
        data[sym] = [index[t] for t in stamps]
    em.check_alignment(data)
    print(f"Context universe={len(symbols)} common bars={len(stamps)} window={iso(stamps[0])}..{iso(stamps[-1])}")

    out = []
    for i, ts in enumerate(stamps):
        if i < 72:
            continue
        r24, r72, e24, atrp = [], [], [], []
        per_symbol = {}
        for sym in symbols:
            candles = data[sym]
            close = candles[i].close
            ret24 = (close / candles[i-24].close - 1.0) * 100.0
            ret72 = (close / candles[i-72].close - 1.0) * 100.0
            path24 = sum(abs(candles[k].close-candles[k-1].close) for k in range(i-23, i+1))
            eff24 = abs(close-candles[i-24].close) / path24 if path24 else 0.0
            atr = em.QuantStrategyCore.compute_atr(candles[:i], 14)
            atr_pct = atr / close * 100.0 if close else 0.0
            r24.append(ret24); r72.append(ret72); e24.append(eff24); atrp.append(atr_pct)
            if sym in ("BTCUSDT", "ETHUSDT"):
                per_symbol[sym.lower().replace("usdt","")] = {
                    "ret24": ret24, "ret72": ret72, "eff24": eff24, "atr_pct": atr_pct
                }
        fold = next((n for n, (lo, hi) in zip((1,2,3), fold_bounds) if lo <= ts <= hi), "")
        btc = per_symbol.get("btc", {})
        eth = per_symbol.get("eth", {})
        out.append({
            "signal_ts": ts, "time_utc": iso(ts), "fold": fold,
            "universe_symbols": len(symbols),
            "broad_positive_24h_share": sum(x > 0 for x in r24)/len(r24),
            "broad_positive_72h_share": sum(x > 0 for x in r72)/len(r72),
            "broad_median_ret_24h_pct": statistics.median(r24),
            "broad_median_ret_72h_pct": statistics.median(r72),
            "broad_median_efficiency_24h": statistics.median(e24),
            "broad_median_atr_pct": statistics.median(atrp),
            "broad_iqr_ret_24h_pct": sorted(r24)[int(0.75*(len(r24)-1))] - sorted(r24)[int(0.25*(len(r24)-1))],
            "broad_iqr_ret_72h_pct": sorted(r72)[int(0.75*(len(r72)-1))] - sorted(r72)[int(0.25*(len(r72)-1))],
            "broad_p10_ret_72h_pct": sorted(r72)[int(0.10*(len(r72)-1))],
            "broad_p90_ret_72h_pct": sorted(r72)[int(0.90*(len(r72)-1))],
            "broad_std_ret_72h_pct": statistics.pstdev(r72),
            "btc_ret_24h_pct": btc.get("ret24", ""),
            "btc_ret_72h_pct": btc.get("ret72", ""),
            "btc_efficiency_24h": btc.get("eff24", ""),
            "btc_atr_pct": btc.get("atr_pct", ""),
            "eth_ret_24h_pct": eth.get("ret24", ""),
            "eth_ret_72h_pct": eth.get("ret72", ""),
            "eth_efficiency_24h": eth.get("eff24", ""),
            "eth_atr_pct": eth.get("atr_pct", ""),
        })
    with open("e12_h1_market_context_by_hour.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    with open("e12_h1_market_context_universe_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader(); w.writerows(manifest)
    print(f"Wrote context rows={len(out)}; fold counts=" +
          str({n:sum(1 for x in out if x["fold"]==n) for n in (1,2,3)}))
    print("CAVEAT: completed-bar Binance OHLCV proxy; fixed universe excludes 3 short-history symbols; descriptive context only, no strategy changes.")

if __name__ == "__main__":
    main()
