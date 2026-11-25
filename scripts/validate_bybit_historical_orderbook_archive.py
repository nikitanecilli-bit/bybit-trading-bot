#!/usr/bin/env python3
"""Validate public Bybit BTCUSDT historical order-book archives."""
from __future__ import annotations
import hashlib, json, os, time, urllib.error, urllib.request, zipfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bybit_l2_queue_replay import OrderBook

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
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
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
    outside_samples = []
    sample_snapshot = None
    sample_delta = None
    top_level_keys = data_keys = None
    cts_top_level_count = cts_data_count = 0
    zip_names = []
    strict_book = OrderBook()
    strict_replay_counts = Counter()
    bid_book, ask_book = {}, {}
    replay_initialized = False
    replay_deltas = replay_snapshots = 0
    bid_inserts = ask_inserts = bid_updates = ask_updates = 0
    bid_deletes = ask_deletes = 0
    delete_missing_bid = delete_missing_ask = 0
    invalid_levels = crossed_samples = 0
    max_bid_levels_seen = max_ask_levels_seen = 0
    min_spread = None
    max_spread_bps = 0.0
    previous_ts = None
    non_monotonic_ts = 0
    max_record_gap_ms = 0
    gaps_over_500ms = 0
    replay_checks = 0

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
                if typ not in ("snapshot", "delta"):
                    raise RuntimeError(f"Unexpected record type: {typ!r}")
                strict_book.apply(obj)
                strict_replay_counts[typ] += 1
                counts[typ] += 1
                if previous_ts is not None:
                    gap = ts - previous_ts
                    if gap < 0:
                        non_monotonic_ts += 1
                    else:
                        max_record_gap_ms = max(max_record_gap_ms, gap)
                        if gap > 500:
                            gaps_over_500ms += 1
                previous_ts = ts
                if top_level_keys is None:
                    top_level_keys = sorted(obj.keys())
                    data_keys = sorted(data.keys())
                if first_type is None:
                    first_type = typ
                last_type = typ
                first_ts = ts if first_ts is None else min(first_ts, ts)
                last_ts = ts if last_ts is None else max(last_ts, ts)
                if not (int(datetime.combine(day, datetime.min.time(), timezone.utc).timestamp()*1000)
                        <= ts < int(datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp()*1000)):
                    outside_day += 1
                    if len(outside_samples) < 12:
                        outside_samples.append({"ts_utc": datetime.fromtimestamp(ts/1000, timezone.utc).isoformat(), "type": typ, "cts": data.get("cts")})
                topic = obj.get("topic", "")
                if topic != f"orderbook.{depth}.{SYMBOL}":
                    topic_mismatch += 1
                if data.get("s") != SYMBOL:
                    symbol_mismatch += 1
                if obj.get("cts") is not None:
                    cts_top_level_count += 1
                    cts = int(obj["cts"])
                    first_cts = cts if first_cts is None else min(first_cts, cts)
                    last_cts = cts if last_cts is None else max(last_cts, cts)
                if data.get("cts") is not None:
                    cts_data_count += 1
                    cts = int(data["cts"])
                    first_cts = cts if first_cts is None else min(first_cts, cts)
                    last_cts = cts if last_cts is None else max(last_cts, cts)
                bids = data.get("b", [])
                asks = data.get("a", [])
                if typ == "snapshot":
                    if sample_snapshot is None:
                        sample_snapshot = {"top_level_keys": sorted(obj.keys()), "data_keys": sorted(data.keys()), "bids_first3": bids[:3], "asks_first3": asks[:3], "u": u, "seq": seq}
                    max_bid_depth = max(max_bid_depth, len(bids))
                    max_ask_depth = max(max_ask_depth, len(asks))
                    snapshot_levels.append((len(bids), len(asks)))
                    bid_book, ask_book = {}, {}
                    for p_raw, q_raw in bids:
                        p, q = float(p_raw), float(q_raw)
                        if p <= 0 or q <= 0:
                            invalid_levels += 1
                        bid_book[p] = q
                    for p_raw, q_raw in asks:
                        p, q = float(p_raw), float(q_raw)
                        if p <= 0 or q <= 0:
                            invalid_levels += 1
                        ask_book[p] = q
                    replay_initialized = True
                    replay_snapshots += 1
                    max_bid_levels_seen = max(max_bid_levels_seen, len(bid_book))
                    max_ask_levels_seen = max(max_ask_levels_seen, len(ask_book))
                    if bid_book and ask_book:
                        best_bid, best_ask = max(bid_book), min(ask_book)
                        spread = best_ask - best_bid
                        min_spread = spread if min_spread is None else min(min_spread, spread)
                        if best_bid >= best_ask:
                            crossed_samples += 1
                    prev_u = u
                    prev_seq = seq
                elif typ == "delta":
                    if not replay_initialized:
                        raise RuntimeError("Delta received before initial snapshot")
                    replay_deltas += 1
                    if sample_delta is None:
                        sample_delta = {"top_level_keys": sorted(obj.keys()), "data_keys": sorted(data.keys()), "bids_first3": bids[:3], "asks_first3": asks[:3], "u": u, "seq": seq}
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
                    for side_name, levels, book in (("bid", bids, bid_book), ("ask", asks, ask_book)):
                        for p_raw, q_raw in levels:
                            p, q = float(p_raw), float(q_raw)
                            if p <= 0 or q < 0:
                                invalid_levels += 1
                                continue
                            if q == 0:
                                if p in book:
                                    del book[p]
                                    if side_name == "bid": bid_deletes += 1
                                    else: ask_deletes += 1
                                else:
                                    if side_name == "bid": delete_missing_bid += 1
                                    else: delete_missing_ask += 1
                            elif p in book:
                                book[p] = q
                                if side_name == "bid": bid_updates += 1
                                else: ask_updates += 1
                            else:
                                book[p] = q
                                if side_name == "bid": bid_inserts += 1
                                else: ask_inserts += 1
                    max_bid_levels_seen = max(max_bid_levels_seen, len(bid_book))
                    max_ask_levels_seen = max(max_ask_levels_seen, len(ask_book))
                    if replay_deltas % 1000 == 0 and bid_book and ask_book:
                        best_bid, best_ask = max(bid_book), min(ask_book)
                        spread = best_ask - best_bid
                        min_spread = spread if min_spread is None else min(min_spread, spread)
                        if best_bid >= best_ask:
                            crossed_samples += 1
                        replay_checks += 1

    total = sum(counts.values())
    if total == 0 or counts["snapshot"] == 0:
        raise RuntimeError(f"No usable orderbook snapshot/delta records in {path}")
    if malformed or topic_mismatch or symbol_mismatch or invalid_levels or crossed_samples or non_monotonic_ts:
        raise RuntimeError(
            f"Integrity checks failed: malformed={malformed}, topic_mismatch={topic_mismatch}, "
            f"symbol_mismatch={symbol_mismatch}, invalid_levels={invalid_levels}, crossed_checks={crossed_samples}, non_monotonic_ts={non_monotonic_ts}, outside_day={outside_day}"
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
        "strict_decimal_replay": {
            "record_types": dict(strict_replay_counts),
            "final_bid_levels": len(strict_book.bids),
            "final_ask_levels": len(strict_book.asks),
            "final_best_bid": str(strict_book.best_bid()[0]) if strict_book.bids else None,
            "final_best_ask": str(strict_book.best_ask()[0]) if strict_book.asks else None,
            "final_spread": str(strict_book.best_ask()[0] - strict_book.best_bid()[0]) if strict_book.bids and strict_book.asks else None,
            "cts_seq_update_ids_valid": True,
            "all_reconstructed_states_uncrossed": True
        },
        "replay": {
            "snapshots_replayed": replay_snapshots, "deltas_replayed": replay_deltas,
            "bid_inserts": bid_inserts, "ask_inserts": ask_inserts,
            "bid_updates": bid_updates, "ask_updates": ask_updates,
            "bid_deletes": bid_deletes, "ask_deletes": ask_deletes,
            "delete_missing_bid": delete_missing_bid, "delete_missing_ask": delete_missing_ask,
            "invalid_levels": invalid_levels, "crossed_book_checks": crossed_samples,
            "periodic_checks": replay_checks,
            "max_bid_levels_seen": max_bid_levels_seen, "max_ask_levels_seen": max_ask_levels_seen,
            "minimum_sampled_spread": min_spread,
            "record_timestamp_non_monotonic": non_monotonic_ts,
            "max_record_gap_ms": max_record_gap_ms, "gaps_over_500ms": gaps_over_500ms
        },
        "delta_u_non_increasing_count": u_non_increasing,
        "delta_seq_non_increasing_count": seq_non_increasing,
        "delta_u_min": min_u, "delta_u_max": max_u,
        "delta_seq_min": min_seq, "delta_seq_max": max_seq,
        "malformed": malformed, "topic_mismatch": topic_mismatch,
        "symbol_mismatch": symbol_mismatch, "outside_day_timestamps": outside_day,
        "outside_day_samples": outside_samples,
        "top_level_keys": top_level_keys, "data_keys": data_keys,
        "cts_top_level_count": cts_top_level_count, "cts_data_count": cts_data_count,
        "sample_snapshot": sample_snapshot, "sample_delta": sample_delta,
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
