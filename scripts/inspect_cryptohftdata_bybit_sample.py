#!/usr/bin/env python3
"""Download and validate one public CryptoHFTData Bybit hour.

Raw Parquet files stay in a temporary directory. Only a compact report and hashes
are retained. This is a data-quality check, not a strategy backtest.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from statistics import median

DATE = "2026-11-01"
HOUR = "12"
SYMBOL = "BTCUSDT"
BASE = "https://api.cryptohftdata.com/download"
MAX_FILE_BYTES = 50 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024

EXPECTED = {
    "trades": ["received_time", "event_time", "symbol", "trade_id", "price",
               "quantity", "trade_time", "is_buyer_maker", "order_type"],
    "orderbook": ["received_time", "event_time", "transaction_time", "symbol",
                  "event_type", "first_update_id", "final_update_id",
                  "prev_final_update_id", "last_update_id", "side", "price",
                  "quantity", "order_count"],
    "mark_price": ["received_time", "event_time", "symbol", "mark_price",
                   "index_price", "estimated_settle_price", "funding_rate",
                   "next_funding_time"],
}


def file_url(dataset: str) -> str:
    name = f"{SYMBOL}_{dataset}.parquet"
    path = f"bybit/{DATE}/{HOUR}/{name}"
    return BASE + "?" + urllib.parse.urlencode({"file": path})


def download(url: str, path: Path) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "bybit-data-inspector/1.0"})
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as out:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status}")
        expected = response.headers.get("Content-Length")
        while True:
            chunk = response.read(CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise RuntimeError(f"file exceeds {MAX_FILE_BYTES} byte safety limit")
            out.write(chunk)
            digest.update(chunk)
    if expected is not None and total != int(expected):
        raise RuntimeError(f"size mismatch expected={expected} actual={total}")
    return {"bytes": total, "sha256": digest.hexdigest()}


def offset_stats(values: list[int]) -> dict:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    def pct(p: int) -> int:
        return ordered[max(0, (len(ordered) * p + 99) // 100 - 1)]
    return {"count": len(values), "min_us": min(values), "max_us": max(values),
            "mean_us": round(sum(values) / len(values), 3),
            "median_us": median(ordered), "p95_us": pct(95), "p99_us": pct(99)}


def monotonic_regressions(values: list[int]) -> int:
    return sum(1 for a, b in zip(values, values[1:]) if b < a)


def positive_decimal(value, name: str, allow_zero: bool = False) -> Decimal:
    if value is None:
        raise ValueError(f"{name} unexpectedly null")
    parsed = Decimal(str(value))
    if not parsed.is_finite() or parsed < 0 or (not allow_zero and parsed == 0):
        raise ValueError(f"{name} out of range: {value!r}")
    return parsed


def load_table(path: Path, dataset: str):
    import pyarrow.parquet as pq
    parquet = pq.ParquetFile(path)
    table = parquet.read()
    names = table.schema.names
    if names != EXPECTED[dataset]:
        raise ValueError(f"{dataset} schema mismatch: {names!r}")
    return parquet, table


def validate_trades(table) -> dict:
    d = table.to_pydict()
    n = len(d["trade_id"])
    if n == 0:
        raise ValueError("empty trades file")
    ids = d["trade_id"]
    nonnull_ids = [str(x) for x in ids if x is not None]
    event = d["event_time"]
    trade_time = d["trade_time"]
    received = d["received_time"]
    offsets_message = []
    offsets_trade = []
    for r, e, t in zip(received, event, trade_time):
        if r is None or e is None or t is None:
            raise ValueError("null trade timestamp")
        offsets_message.append(r // 1000 - e * 1000)
        offsets_trade.append(r // 1000 - t * 1000)
    prices = [positive_decimal(x, "trade price") for x in d["price"]]
    quantities = [positive_decimal(x, "trade quantity") for x in d["quantity"]]
    if any(s not in (True, False) for s in d["is_buyer_maker"]):
        raise ValueError("invalid is_buyer_maker value")
    if any(s != SYMBOL for s in d["symbol"]):
        raise ValueError("unexpected trade symbol")
    return {
        "rows": n,
        "event_time_unit": "milliseconds",
        "received_time_unit": "nanoseconds",
        "trade_time_unit": "milliseconds",
        "event_time_min": min(event), "event_time_max": max(event),
        "trade_time_min": min(trade_time), "trade_time_max": max(trade_time),
        "received_time_min": min(received), "received_time_max": max(received),
        "event_time_regressions": monotonic_regressions(event),
        "trade_time_regressions": monotonic_regressions(trade_time),
        "received_time_regressions": monotonic_regressions(received),
        "unique_trade_ids": len(set(nonnull_ids)),
        "null_trade_ids": len(ids) - len(nonnull_ids),
        "duplicate_trade_ids": len(nonnull_ids) - len(set(nonnull_ids)),
        "buyer_maker_true": sum(1 for x in d["is_buyer_maker"] if x is True),
        "buyer_maker_false": sum(1 for x in d["is_buyer_maker"] if x is False),
        "price_min": str(min(prices)), "price_max": str(max(prices)),
        "quantity_min": str(min(quantities)), "quantity_max": str(max(quantities)),
        "received_minus_event_message": offset_stats(offsets_message),
        "received_minus_trade_time": offset_stats(offsets_trade),
    }


def validate_orderbook(table) -> dict:
    d = table.to_pydict()
    n = len(d["received_time"])
    if n == 0:
        raise ValueError("empty orderbook file")
    if any(s != SYMBOL for s in d["symbol"]):
        raise ValueError("unexpected orderbook symbol")
    received = d["received_time"]
    event = d["event_time"]
    transaction = d["transaction_time"]
    offsets_event = [r // 1000 - e * 1000 for r, e in zip(received, event)]
    offsets_transaction = [
        r // 1000 - t * 1000 for r, t in zip(received, transaction) if t is not None
    ]
    event_types = Counter(d["event_type"])
    if set(event_types) - {"snapshot", "update"}:
        raise ValueError(f"unexpected orderbook event types: {event_types}")
    if not event_types.get("snapshot"):
        raise ValueError("orderbook has no snapshot")
    null_counts = {
        name: sum(1 for x in d[name] if x is None)
        for name in ("first_update_id", "final_update_id", "prev_final_update_id",
                     "last_update_id", "transaction_time", "order_count")
    }

    # Group rows from the same exchange message and rebuild the visible L2 book.
    state_bids: dict[Decimal, Decimal] = {}
    state_asks: dict[Decimal, Decimal] = {}
    best_bid = best_ask = None
    has_snapshot = False
    current_key = None
    group = []
    messages = Counter()
    crossed = empty_sides = pre_snapshot_updates = 0
    first_cross = None
    snapshot_ids = 0
    final_id_gaps = final_id_regressions = prev_id_mismatches = 0
    final_id_jumps = 0
    previous_final_id = None
    previous_last_id = None
    transaction_offsets = []

    def flush_group(key, rows):
        nonlocal best_bid, best_ask, has_snapshot, crossed, empty_sides
        nonlocal first_cross, snapshot_ids, previous_final_id, previous_last_id
        nonlocal final_id_gaps, final_id_regressions, prev_id_mismatches, final_id_jumps
        if key is None:
            return
        event_type = key[1]
        messages[event_type] += 1
        final_id = key[2]
        prev_id = key[3]
        last_id = key[4]
        trans_time = key[5]
        if trans_time is not None and key[0] is not None:
            transaction_offsets.append(key[0] // 1000 - trans_time * 1000)

        if event_type == "snapshot":
            state_bids.clear()
            state_asks.clear()
            best_bid = best_ask = None
            has_snapshot = True
            snapshot_ids += 1
            previous_final_id = final_id
            previous_last_id = last_id
        elif not has_snapshot:
            pre_snapshot_updates += len(rows)
            return
        else:
            if prev_id is not None and previous_final_id is not None and prev_id != previous_final_id:
                prev_id_mismatches += 1
            if final_id is not None and previous_final_id is not None:
                if final_id < previous_final_id and final_id != 1:
                    final_id_regressions += 1
                elif final_id == previous_final_id:
                    final_id_gaps += 1
                elif final_id > previous_final_id + 1:
                    final_id_jumps += 1
            if last_id is not None and previous_last_id is not None and last_id < previous_last_id:
                final_id_regressions += 1
            previous_final_id = final_id if final_id is not None else previous_final_id
            previous_last_id = last_id if last_id is not None else previous_last_id

        for side, price_raw, qty_raw in rows:
            price = positive_decimal(price_raw, "orderbook price")
            qty = positive_decimal(qty_raw, "orderbook quantity", allow_zero=True)
            book = state_bids if side == "bid" else state_asks if side == "ask" else None
            if book is None:
                raise ValueError(f"invalid orderbook side: {side!r}")
            if qty == 0:
                if price in book:
                    del book[price]
                    if side == "bid" and best_bid == price:
                        best_bid = max(book) if book else None
                    elif side == "ask" and best_ask == price:
                        best_ask = min(book) if book else None
            else:
                book[price] = qty
                if side == "bid" and (best_bid is None or price > best_bid):
                    best_bid = price
                elif side == "ask" and (best_ask is None or price < best_ask):
                    best_ask = price
        if has_snapshot:
            if best_bid is None or best_ask is None:
                empty_sides += 1
            elif best_bid >= best_ask:
                crossed += 1
                if first_cross is None:
                    first_cross = {"received_time_ns": key[0], "best_bid": str(best_bid),
                                   "best_ask": str(best_ask)}

    for i in range(n):
        key = (received[i], d["event_type"][i], d["final_update_id"][i],
               d["prev_final_update_id"][i], d["last_update_id"][i],
               transaction[i])
        if current_key is None:
            current_key = key
        elif key != current_key:
            flush_group(current_key, group)
            current_key = key
            group = []
        group.append((d["side"][i], d["price"][i], d["quantity"][i]))
    flush_group(current_key, group)

    if monotonic_regressions(received):
        raise ValueError("orderbook received_time is not monotonic in stored row order")
    return {
        "rows": n,
        "event_time_unit": "milliseconds",
        "transaction_time_unit": "milliseconds; Bybit matching-engine timestamp",
        "received_time_unit": "nanoseconds",
        "event_time_min": min(event), "event_time_max": max(event),
        "transaction_time_min": min(x for x in transaction if x is not None),
        "transaction_time_max": max(x for x in transaction if x is not None),
        "received_time_min": min(received), "received_time_max": max(received),
        "event_time_regressions": monotonic_regressions(event),
        "transaction_time_regressions": monotonic_regressions(
            [x for x in transaction if x is not None]
        ),
        "received_time_regressions": 0,
        "message_counts": dict(messages),
        "snapshot_messages": snapshot_ids,
        "rows_before_first_snapshot": pre_snapshot_updates,
        "null_counts": null_counts,
        "final_update_id_equal_previous_count": final_id_gaps,
        "final_update_id_regressions_or_last_update_id_regressions": final_id_regressions,
        "final_update_id_jumps_over_one": final_id_jumps,
        "prev_final_update_id_mismatches": prev_id_mismatches,
        "book_reconstruction": {
            "method": "apply absolute price-level quantity; zero deletes; clear on each snapshot; check best bid/ask after each message",
            "crossed_message_states": crossed,
            "message_states_with_empty_best_side": empty_sides,
            "first_crossed_state": first_cross,
            "final_bid_levels": len(state_bids),
            "final_ask_levels": len(state_asks),
        },
        "received_minus_event_time": offset_stats(offsets_event),
        "received_minus_transaction_time": offset_stats(transaction_offsets),
    }


def validate_mark_price(table) -> dict:
    d = table.to_pydict()
    n = len(d["received_time"])
    if n == 0:
        raise ValueError("empty mark price file")
    if any(s != SYMBOL for s in d["symbol"]):
        raise ValueError("unexpected mark price symbol")
    event = d["event_time"]
    received = d["received_time"]
    mark = [positive_decimal(x, "mark_price") for x in d["mark_price"] if x is not None]
    index = [positive_decimal(x, "index_price") for x in d["index_price"] if x is not None]
    funding = [Decimal(str(x)) for x in d["funding_rate"] if x is not None]
    next_funding = [x for x in d["next_funding_time"] if x is not None]
    return {
        "rows": n,
        "event_time_min": min(event), "event_time_max": max(event),
        "received_time_min": min(received), "received_time_max": max(received),
        "event_time_regressions": monotonic_regressions(event),
        "received_time_regressions": monotonic_regressions(received),
        "null_counts": {
            name: sum(1 for x in d[name] if x is None)
            for name in ("mark_price", "index_price", "estimated_settle_price",
                         "funding_rate", "next_funding_time")
        },
        "mark_price_min": str(min(mark)) if mark else None,
        "mark_price_max": str(max(mark)) if mark else None,
        "index_price_min": str(min(index)) if index else None,
        "index_price_max": str(max(index)) if index else None,
        "funding_rate_min": str(min(funding)) if funding else None,
        "funding_rate_max": str(max(funding)) if funding else None,
        "next_funding_time_min": min(next_funding) if next_funding else None,
        "next_funding_time_max": max(next_funding) if next_funding else None,
        "received_minus_event_time": offset_stats(
            [r // 1000 - e * 1000 for r, e in zip(received, event)]
        ),
    }


def main() -> int:
    import pyarrow.parquet as pq  # noqa: F401
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "CryptoHFTData",
        "date": DATE,
        "hour_utc": HOUR,
        "symbol": SYMBOL,
        "scope": "one-hour Parquet integrity/schema/chronology/L2 reconstruction; no strategy PnL",
        "raw_archives_uploaded": False,
        "datasets": {},
    }
    validators = {"trades": validate_trades, "orderbook": validate_orderbook,
                  "mark_price": validate_mark_price}
    failed = False
    with tempfile.TemporaryDirectory(prefix="cryptohftdata-bybit-") as tmp:
        for dataset, validator in validators.items():
            item = {"url": file_url(dataset)}
            try:
                path = Path(tmp) / f"{dataset}.parquet"
                item["download"] = download(item["url"], path)
                parquet, table = load_table(path, dataset)
                item["parquet"] = {
                    "rows_from_metadata": parquet.metadata.num_rows,
                    "row_groups": parquet.metadata.num_row_groups,
                    "schema": str(parquet.schema_arrow),
                }
                item["validation"] = validator(table)
                item["status"] = "VALIDATED"
            except Exception as exc:
                item["status"] = "FAILED"
                item["error"] = f"{type(exc).__name__}: {exc}"
                failed = True
            report["datasets"][dataset] = item

    trades = report["datasets"].get("trades", {}).get("validation")
    book = report["datasets"].get("orderbook", {}).get("validation")
    mark = report["datasets"].get("mark_price", {}).get("validation")
    if trades and book:
        report["cross_feed_time_ranges"] = {
            "trade_time_min_ms": trades["trade_time_min"],
            "trade_time_max_ms": trades["trade_time_max"],
            "book_transaction_time_min_ms": book["transaction_time_min"],
            "book_transaction_time_max_ms": book["transaction_time_max"],
            "ranges_overlap": max(trades["trade_time_min"], book["transaction_time_min"])
                              <= min(trades["trade_time_max"], book["transaction_time_max"]),
            "note": "Bybit docs state orderbook cts is matching-engine time correlated with publicTrade T; this range overlap is not an event-by-event identity proof.",
        }
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "cryptohftdata_bybit_sample_inspection.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
