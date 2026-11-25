#!/usr/bin/env python3
"""Validate public Bybit BTCUSDT historical order-book archives."""
from __future__ import annotations
import hashlib, json, os, time, urllib.error, urllib.request, zipfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SYMBOL = "BTCUSDT"
DATES = [date.fromisoformat(x.strip()) for x in os.getenv(
    "ORDERBOOK_DATES", "2024-04-11,2025-11-02"
).split(",") if x.strip()]
OUT = Path(os.getenv("OUT_DIR", "orderbook_archive_validation"))
RAW = OUT / "raw"
RAW.mkdir(parents=True, exist_ok=True)

def expected_depth(day: date) -> int:
    # Bybit changed historical futures orderbook downloads from 500 to 200
    # levels on 2025-08-21. Sample dates are away from the transition boundary.
    return 500 if day < date(2025, 8, 21) else 200

def download(day: date, depth: int):
    filename = f"{day.isoformat()}_{SYMBOL}_ob{depth}.data.zip"
    url = f"https://quote-saver.bycsi.com/orderbook/linear/{SYMBOL}/{filename}"
    path = RAW / filename
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "bybit-public-archive-validation/1.0"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=600) as response, path.open("wb") as f:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                break
            except urllib.error.HTTPError as exc:
                if path.exists():
                    path.unlink()
                if exc.code == 404:
                    raise RuntimeError(f"Bybit archive file not found: {url}") from exc
                if exc.code not in (429, 500, 502, 503, 504):
                    raise
                time.sleep(2 ** attempt)
            except Exception:
                if path.exists():
                    path.unlink()
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return url, path, digest

def inspect(day: date):
    depth = expected_depth(day)
    url, path, digest = download(day, depth)
    counts = Counter()
    first_ts = last_ts = first_cts = last_cts = None
    first_type = last_type = None
    min_u = max_u = prev_u = None
    min_seq = max_seq = prev_seq = None
    u_non_increasing = seq_non_increasing = 0
    topic_mismatch = symbol_mismatch = malformed = outside_day = 0
    max_bid_depth = max_ask_depth = 0
    snapshot_levels = []
    zip_names = []

    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC failure: {bad}")
        zip_names = zf.namelist()
        data_files = [n for n in zip_names if n.endswith(".data")]
        if len(data_files) != 1:
            raise RuntimeError(f"Expected one .data file, got {zip_names}")
        with zf.open(data_files[0], "r") as stream:
            for raw in stream:
                if not raw.strip():
                    continue
                try:
                    obj = json.loads(raw)
                    typ = obj["type"]
                    ts = int(obj["ts"])
                    data = obj["data"]
                    u = int(data["u"]) if data.get("u") is not None else None
                    seq = int(data["seq"]) if data.get("seq") is not None else None
                except Exception:
                    malformed += 1
                    continue
                counts[typ] += 1
                if first_type is None:
                    first_type = typ
                last_type = typ
                first_ts = ts if first_ts is None else min(first_ts, ts)
                last_ts = ts if last_ts is None else max(last_ts, ts)
                if not (int(datetime.combine(day, datetime.min.time(), timezone.utc).timestamp()*1000)
                        <= ts < int(datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp()*1000)):
                    outside_day += 1
                topic = obj.get("topic", "")
                if topic != f"orderbook.{depth}.{SYMBOL}":
                    topic_mismatch += 1
                if data.get("s") != SYMBOL:
                    symbol_mismatch += 1
                if data.get("cts") is not None:
                    cts = int(data["cts"])
                    first_cts = cts if first_cts is None else min(first_cts, cts)
                    last_cts = cts if last_cts is None else max(last_cts, cts)
                bids = data.get("b", [])
                asks = data.get("a", [])
                if typ == "snapshot":
                    max_bid_depth = max(max_bid_depth, len(bids))
                    max_ask_depth = max(max_ask_depth, len(asks))
                    snapshot_levels.append((len(bids), len(asks)))
                    prev_u = u
                    prev_seq = seq
                elif typ == "delta":
                    if u is not None:
                        min_u = u if min_u is None else min(min_u, u)
                        max_u = u if max_u is None else max(max_u, u)
                        if prev_u is not None and u <= prev_u:
                            u_non_increasing += 1
                        prev_u = u
                    if seq is not None:
                        min_seq = seq if min_seq is None else min(min_seq, seq)
                        max_seq = seq if max_seq is None else max(max_seq, seq)
                        if prev_seq is not None and seq <= prev_seq:
                            seq_non_increasing += 1
                        prev_seq = seq

    total = sum(counts.values())
    if total == 0 or counts["snapshot"] == 0:
        raise RuntimeError(f"No usable orderbook snapshot/delta records in {path}")
    if malformed or topic_mismatch or symbol_mismatch or outside_day:
        raise RuntimeError(
            f"Integrity checks failed: malformed={malformed}, topic_mismatch={topic_mismatch}, "
            f"symbol_mismatch={symbol_mismatch}, outside_day={outside_day}"
        )
    return {
        "date": day.isoformat(), "symbol": SYMBOL, "depth": depth, "url": url,
        "zip_bytes": path.stat().st_size, "sha256": digest, "zip_members": zip_names,
        "records": total, "record_types": dict(counts),
        "first_record_type": first_type, "last_record_type": last_type,
        "first_ts_utc": datetime.fromtimestamp(first_ts/1000, timezone.utc).isoformat(),
        "last_ts_utc": datetime.fromtimestamp(last_ts/1000, timezone.utc).isoformat(),
        "first_cts_utc": datetime.fromtimestamp(first_cts/1000, timezone.utc).isoformat() if first_cts else None,
        "last_cts_utc": datetime.fromtimestamp(last_cts/1000, timezone.utc).isoformat() if last_cts else None,
        "max_snapshot_bid_levels": max_bid_depth, "max_snapshot_ask_levels": max_ask_depth,
        "snapshot_count": len(snapshot_levels),
        "delta_u_non_increasing_count": u_non_increasing,
        "delta_seq_non_increasing_count": seq_non_increasing,
        "delta_u_min": min_u, "delta_u_max": max_u,
        "delta_seq_min": min_seq, "delta_seq_max": max_seq,
        "malformed": malformed, "topic_mismatch": topic_mismatch,
        "symbol_mismatch": symbol_mismatch, "outside_day_timestamps": outside_day,
        "interpretation": "Raw Bybit snapshot/delta archive validated; update continuity and replay semantics still require a dedicated full-book reconstruction test."
    }

def main():
    results = [inspect(day) for day in DATES]
    report = {
        "source": "Bybit Historical Data OrderBook product; public linear BTCUSDT archive",
        "dates": [d.isoformat() for d in DATES],
        "results": results,
        "depth_change_note": "500 levels before 2025-08-21; 200 levels from 2025-08-21 per Bybit historical data notice."
    }
    (OUT / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
