#!/usr/bin/env python3
"""Descriptive, pre-entry BTC H1 signal diagnostics; never selects a filter."""
import csv, json, math
from collections import defaultdict
from pathlib import Path
from statistics import median

DATA = Path("bybit_btcusdt_initial/trade_h1.csv")
TRADES = Path("stop_sensitivity/trades.csv")
OUT = Path("entry_diagnostics")
BAR_MS = 3_600_000
FEATURES = (
    "atr_pct", "volume_ratio", "ema_spread_pct", "ema200_slope5_pct",
    "breakout_atr", "body_range", "close_location",
    "return_1h_pct", "return_3h_pct", "return_6h_pct",
    "return_12h_pct", "return_24h_pct",
)

def ema(values, period):
    out = [None] * len(values)
    if len(values) < period:
        return out
    alpha = 2.0 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * alpha + prev * (1 - alpha)
        out[i] = prev
    return out

def load_bars():
    with DATA.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    bars = []
    for r in rows:
        bars.append({
            "ts": int(r["start_ms"]), "open": float(r["open"]),
            "high": float(r["high"]), "low": float(r["low"]),
            "close": float(r["close"]), "volume": float(r["volume"]),
        })
    bars.sort(key=lambda x: x["ts"])
    if len({b["ts"] for b in bars}) != len(bars):
        raise SystemExit("Duplicate timestamps in official Bybit archive")
    return bars

def build_features(bars):
    n = len(bars)
    seg = [0] * n
    for i in range(1, n):
        seg[i] = seg[i-1] + (bars[i]["ts"] - bars[i-1]["ts"] != BAR_MS)
    e50 = [None] * n
    e200 = [None] * n
    atr = [None] * n
    vr = [None] * n
    prior_high = [None] * n
    for start in range(n):
        if start and seg[start] == seg[start-1]:
            continue
        end = start + 1
        while end < n and seg[end] == seg[start]:
            end += 1
        closes = [bars[i]["close"] for i in range(start, end)]
        a50, a200 = ema(closes, 50), ema(closes, 200)
        for j in range(end-start):
            e50[start+j], e200[start+j] = a50[j], a200[j]
        for i in range(start+14, end):
            trs = []
            for j in range(i-13, i+1):
                pc = bars[j-1]["close"]
                trs.append(max(bars[j]["high"]-bars[j]["low"],
                               abs(bars[j]["high"]-pc), abs(bars[j]["low"]-pc)))
            atr[i] = sum(trs) / 14
        for i in range(start+48, end):
            base = sum(bars[j]["volume"] for j in range(i-48, i)) / 48
            vr[i] = bars[i]["volume"] / base if base else None
            prior_high[i] = max(bars[j]["high"] for j in range(i-48, i))
    out = {}
    for i, b in enumerate(bars):
        if atr[i] is None or e50[i] is None or e200[i] is None or vr[i] is None:
            continue
        if i < 5 or seg[i-5] != seg[i] or e200[i-5] is None:
            continue
        rng = b["high"] - b["low"]
        vals = {
            "atr_pct": atr[i] / b["close"] * 100,
            "volume_ratio": vr[i],
            "ema_spread_pct": (e50[i] - e200[i]) / b["close"] * 100,
            "ema200_slope5_pct": (e200[i] / e200[i-5] - 1) * 100 if e200[i-5] else None,
            "breakout_atr": (b["close"] - prior_high[i]) / atr[i] if prior_high[i] is not None else None,
            "body_range": abs(b["close"] - b["open"]) / rng if rng else None,
            "close_location": (b["close"] - b["low"]) / rng if rng else None,
        }
        for h in (1, 3, 6, 12, 24):
            prev = i-h
            vals[f"return_{h}h_pct"] = (b["close"] / bars[prev]["close"] - 1) * 100 if prev >= 0 and seg[prev] == seg[i] else None
        out[b["ts"]] = vals
    return out, bars, seg

def rank_values(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg
        i = j
    return ranks

def spearman(xs, ys):
    if len(xs) < 3:
        return None
    rx, ry = rank_values(xs), rank_values(ys)
    mx, my = sum(rx)/len(rx), sum(ry)/len(ry)
    cov = sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    vx = sum((a-mx)**2 for a in rx)
    vy = sum((b-my)**2 for b in ry)
    return cov / (vx*vy)**0.5 if vx and vy else None

def main():
    bars = load_bars()
    features, bars, seg = build_features(bars)
    index = {b["ts"]: i for i, b in enumerate(bars)}
    with TRADES.open(newline="", encoding="utf-8-sig") as f:
        trades = [r for r in csv.DictReader(f)
                  if r["symbol"] == "BTCUSDT" and float(r["cost_multiplier"]) == 1.0]
    detailed = []
    for t in trades:
        entry_ts = int(t["entry_ts"])
        signal_ts = entry_ts - BAR_MS
        f = features.get(signal_ts)
        if f is None:
            continue
        i = index.get(entry_ts)
        row = {**t, "signal_ts": signal_ts, **f}
        for h in (1, 3, 6, 12, 24, 32):
            j = i + h - 1 if i is not None else len(bars)
            value = None
            if i is not None and j < len(bars) and seg[j] == seg[i]:
                value = (bars[j]["close"] / float(t["entry"]) - 1) * 100
            row[f"forward_{h}h_pct"] = value
        detailed.append(row)
    OUT.mkdir(exist_ok=True)
    if not detailed:
        raise SystemExit("No trades could be joined to Bybit signal candles")
    fields = list(detailed[0])
    with (OUT / "trade_features.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(detailed)

    groups = defaultdict(list)
    for r in detailed:
        groups[(r["stop_atr"], r["fold"], "win" if float(r["net_pnl"]) > 0 else "loss")].append(r)
    summary = []
    for (stop, fold, outcome), rows in sorted(groups.items(), key=lambda x: (float(x[0][0]), int(x[0][1]), x[0][2])):
        item = {"stop_atr": float(stop), "fold": int(fold), "outcome": outcome, "trades": len(rows)}
        for col in FEATURES + tuple(f"forward_{h}h_pct" for h in (1,3,6,12,24,32)):
            values = [float(r[col]) for r in rows if r.get(col) not in ("", None)]
            item[col + "_median"] = round(median(values), 5) if values else None
        summary.append(item)
    with (OUT / "group_medians.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)

    # Spearman rank correlations: exploratory only, never used to select a filter.
    correlations = []
    for fold in (1, 2, 3, "ALL"):
        rows = [r for r in detailed if float(r["stop_atr"]) == 3.5 and
                (fold == "ALL" or int(r["fold"]) == fold)]
        for feature in FEATURES:
            pairs = [(float(r[feature]), float(r["net_pnl"])) for r in rows
                     if r.get(feature) not in ("", None)]
            rho = spearman([x for x,_ in pairs], [y for _,y in pairs])
            correlations.append({"fold": fold, "feature": feature,
                                 "trades": len(pairs),
                                 "spearman_rho": round(rho, 4) if rho is not None else None})
    with (OUT / "spearman_correlations.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(correlations[0])); w.writeheader(); w.writerows(correlations)

    # A compact fold comparison for the 3.5 ATR candidate; descriptive only.
    lines = [
        "# BTC H1 Entry-Quality Diagnostics (descriptive, no filter selected)",
        "",
        "Source: official Bybit BTCUSDT H1 trade-kline archive and the stop-sensitivity trade ledger.",
        "Features are sampled on the signal candle close, before entry at the next candle open.",
        "Forward returns are descriptive outcomes, not input features and were not used to select any rule.",
        "",
        "## Fold comparison — 3.5 ATR, 1x modeled costs",
        "",
        "| Fold | Trades | Win rate | Median ATR% | Median volume ratio | Median EMA spread% | Median 6h momentum% | Median 24h momentum% | Median 6h forward return% | Median 32h forward return% |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for fold in (1,2,3):
        rows = [r for r in detailed if float(r["stop_atr"]) == 3.5 and int(r["fold"]) == fold]
        def med(k):
            v=[float(r[k]) for r in rows if r.get(k) not in ("",None)]
            return median(v) if v else float("nan")
        wr=100*sum(float(r["net_pnl"])>0 for r in rows)/len(rows) if rows else 0
        lines.append(f"| {fold} | {len(rows)} | {wr:.1f}% | {med('atr_pct'):.3f} | {med('volume_ratio'):.3f} | {med('ema_spread_pct'):.3f} | {med('return_6h_pct'):.3f} | {med('return_24h_pct'):.3f} | {med('forward_6h_pct'):.3f} | {med('forward_32h_pct'):.3f} |")
    lines += [
        "",
        "## Interpretation guardrails",
        "",
        "- These are medians and small-to-moderate samples, not statistically validated predictors.",
        "- The third fold has lower median pre-entry volume expansion and 6h/24h momentum than folds 1–2 in this sample; this describes the historical period and is not a proposed filter.",
        "- Inspect spearman_correlations.csv: feature/PnL associations are exploratory, unstable across folds, and must not be interpreted as predictive rules.",
        "- Forward returns are calculated from entry open to future close independently of the strategy's actual exit. They must not be used to construct a live filter.",
        "- Do not add thresholds from this report. Any candidate feature must be preregistered and tested on a separate untouched period.",
        "- OHLCV-only: funding, mark price, liquidation, historical instrument/risk specs, spread and execution effects remain excluded.",
        "",
        "The script intentionally emits diagnostics only and never changes strategy parameters or trading permissions.",
    ]
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "methodology.json").write_text(json.dumps({
        "data_source": "Official Bybit BTCUSDT H1 public trade-kline archive",
        "signal_time": "signal candle close; entry on next candle open",
        "features": list(FEATURES),
        "forward_horizons_hours": [1,3,6,12,24,32],
        "cost_filter": "cost_multiplier=1.0; trade PnL labels only",
        "purpose": "descriptive entry-quality diagnostics; no feature selection",
        "rows": len(detailed),\n        "correlation_method": "Spearman rank correlation of each pre-entry feature with net trade PnL, separately by fold and pooled; exploratory only",
        "limitations": ["OHLCV only", "no funding", "no mark price", "no liquidation model",
                        "no dated instrument/risk specs", "no spread or execution model"]
    }, indent=2), encoding="utf-8")
    print(f"ENTRY_DIAGNOSTICS rows={len(detailed)}; groups={len(summary)}; output={OUT}")

if __name__ == "__main__":
    main()
