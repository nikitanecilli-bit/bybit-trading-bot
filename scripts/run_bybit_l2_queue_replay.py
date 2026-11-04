#!/usr/bin/env python3
"""Run a small, non-strategy queue-replay probe on one matched Bybit data day."""
from __future__ import annotations

import hashlib
import json
import tempfile
import urllib.request
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bybit_l2_queue_replay import (
    OrderBook, iter_book_events, place_passive_order, replay_public_trades,
    signed_markout_bps,
)

BOOK_URL = "https://quote-saver.bycsi.com/orderbook/linear/AAVEUSDT/2025-09-02_AAVEUSDT_ob200.data.zip"
TRADES_URL = "https://public.bybit.com/trading/AAVEUSDT/AAVEUSDT2025-09-02.csv.gz"
SYMBOL = "AAVEUSDT"
HOUR_MS = 3_600_000
ORDER_LIFETIME_MS = 60 * 60_000
ORDER_QTY = Decimal("1")


def download(url: str, path: Path) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "bybit-l2-queue-replay/1.0"})
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as out:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status}")
        expected = response.headers.get("Content-Length")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
            total += len(chunk)
    if expected is not None and total != int(expected):
        raise RuntimeError(f"download size mismatch: expected={expected}, actual={total}")
    return {"bytes": total, "sha256": digest.hexdigest()}


def capture_scenarios(book_archive: Path) -> tuple[list[dict], dict]:
    offsets = [2, 8, 14, 20]
    book = OrderBook()
    snapshots = []
    next_index = 0
    first_cts = last_cts = None
    events = 0

    def capture(arrival: int) -> None:
        if book.last_cts is None:
            raise ValueError("no initialized order book at scheduled arrival")
        snapshots.append({
            "arrival_ts": arrival,
            "book_cts": book.last_cts,
            "bids": dict(book.bids),
            "asks": dict(book.asks),
        })

    # One pass through the complete L2 archive. A scheduled order is placed
    # using the latest book state at/before its timestamp, never a future delta.
    for event in iter_book_events(book_archive, SYMBOL):
        cts = int(event["cts"])
        if first_cts is None:
            first_cts = cts
        if last_cts is not None and cts < last_cts:
            raise ValueError("non-monotonic cts in full order-book archive")
        # Capture before applying cts == arrival events: their sequence
        # relative to the hypothetical order is unknown.
        while next_index < len(offsets) and first_cts + offsets[next_index] * HOUR_MS <= cts:
            arrival = first_cts + offsets[next_index] * HOUR_MS
            capture(arrival)
            next_index += 1
        book.apply(event)
        events += 1
        last_cts = cts

    while next_index < len(offsets):
        arrival = first_cts + offsets[next_index] * HOUR_MS
        if arrival > last_cts:
            raise ValueError("archive does not cover all scheduled arrival times")
        capture(arrival)
        next_index += 1
    return snapshots, {
        "events_scanned": events,
        "cts_min_ms": first_cts,
        "cts_max_ms": last_cts,
        "duration_hours": round((last_cts - first_cts) / HOUR_MS, 4),
    }


def capture_book_states_at(book_archive: Path, targets: list[int]) -> dict[int, dict]:
    ordered = sorted(set(targets))
    states = {}
    next_index = 0
    book = OrderBook()

    def capture(target: int) -> None:
        if book.last_cts is None:
            return
        states[target] = {
            "book_cts": book.last_cts,
            "bids": dict(book.bids),
            "asks": dict(book.asks),
        }

    for event in iter_book_events(book_archive, SYMBOL):
        cts = int(event["cts"])
        # Exclude same-millisecond book events; no order sequence exists to
        # establish whether they preceded or followed hypothetical arrival.
        while next_index < len(ordered) and ordered[next_index] <= cts:
            capture(ordered[next_index])
            next_index += 1
        book.apply(event)
        while next_index < len(ordered) and ordered[next_index] == cts:
            capture(ordered[next_index])
            next_index += 1
    while next_index < len(ordered):
        if book.last_cts is not None and ordered[next_index] <= book.last_cts:
            capture(ordered[next_index])
        next_index += 1
    return states


def add_post_fill_markouts(book_archive: Path, results: list[dict]) -> None:
    horizons = (1_000, 5_000, 30_000, 60_000)
    target_keys = {}
    for result in results:
        fills = result.get("fills", [])
        for fill in fills:
            fill_ts = int(fill["timestamp_ms"])
            fill["post_fill_markout"] = []
            for horizon in horizons:
                target = fill_ts + horizon
                target_keys.setdefault(target, []).append((fill, horizon))

    states = capture_book_states_at(book_archive, list(target_keys))
    for target, keys in target_keys.items():
        state = states.get(target)
        for fill, horizon in keys:
            if state is None or not state["bids"] or not state["asks"]:
                fill["post_fill_markout"].append({
                    "horizon_ms": horizon, "status": "no_book_state",
                })
                continue
            best_bid = max(state["bids"])
            best_ask = min(state["asks"])
            if best_bid > best_ask:
                raise ValueError("crossed book in post-fill markout snapshot")
            signed = signed_markout_bps(
                fill["side"], Decimal(fill["price"]), best_bid, best_ask,
            )
            fill["post_fill_markout"].append({
                "horizon_ms": horizon,
                "book_state_cts_ms": state["book_cts"],
                "book_state_age_ms": target - state["book_cts"],
                "best_bid": str(best_bid),
                "best_ask": str(best_ask),
                "mid_price": str((best_bid + best_ask) / Decimal("2")),
                "signed_mid_markout_bps": str(signed),
            })


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL,
        "method": "aggregate L2 queue-ahead; trades only; no cancellation credit; no same-ms fills",
        "warning": "Four deterministic hypothetical orders only. This is not strategy PnL, a fill-rate estimate, L3 replay, or exchange-confirmed execution.",
        "order_spec_validation": "not_performed_no_verified_historical_snapshot",
        "fee_accounting": "not_calculated_requires_account_fee_tier_per_fill",
        "status": "started",
    }
    with tempfile.TemporaryDirectory(prefix="bybit-l2-queue-replay-") as tmp:
        book_path = Path(tmp) / "book.zip"
        trades_path = Path(tmp) / "trades.csv.gz"
        report["book_download"] = download(BOOK_URL, book_path)
        report["trades_download"] = download(TRADES_URL, trades_path)

        snapshots, coverage = capture_scenarios(book_path)
        report["book_coverage"] = coverage
        results = []
        for index, snapshot in enumerate(snapshots):
            book = OrderBook()
            book.bids = snapshot["bids"]
            book.asks = snapshot["asks"]
            book.last_cts = snapshot["book_cts"]
            side = "Buy" if index % 2 == 0 else "Sell"
            price, displayed = book.best_bid() if side == "Buy" else book.best_ask()
            arrival = snapshot["arrival_ts"]
            order = place_passive_order(
                book, side=side, price=price, quantity=ORDER_QTY,
                arrival_ts=arrival, expiry_ts=arrival + ORDER_LIFETIME_MS,
            )
            replay_public_trades(order, trades_path, SYMBOL)
            results.append({
                "scenario": index + 1,
                "side": side,
                "arrival_ts_ms": arrival,
                "book_state_cts_ms": snapshot["book_cts"],
                "book_state_age_ms": arrival - snapshot["book_cts"],
                "limit_price": str(price),
                "displayed_size_at_limit": str(displayed),
                "queue_ahead_initial": str(order.queue_ahead_initial),
                "order_quantity": str(order.quantity),
                "filled_quantity": str(order.filled),
                "remaining_quantity": str(order.remaining),
                "fill_fraction": str(order.filled / order.quantity),
                "fill_count": order.fill_count,
                "filled_notional": str(order.filled_notional),
                "filled_vwap": None if order.filled_vwap is None else str(order.filled_vwap),
                "fee_ledger": None,
                "fee_ledger_status": "not_calculated_requires_explicit_historical_fee_rate_per_fill",
                "fills": [
                    {
                        "timestamp_ms": fill.timestamp_ms,
                        "side": fill.side,
                        "price": str(fill.price),
                        "quantity": str(fill.quantity),
                    }
                    for fill in order.fills
                ],
                "eligible_opposing_trades_at_price": order.eligible_trade_count,
                "rpi_trades_excluded": order.rpi_excluded_count,
                "first_fill_ts_ms": order.first_fill_ts,
                "time_to_first_fill_ms": (
                    None if order.first_fill_ts is None
                    else order.first_fill_ts - arrival
                ),
                "status": "filled" if order.complete else (
                    "partial" if order.filled > 0 else "not_filled"
                ),
                "expiry_ts_ms": order.expiry_ts,
            })
        add_post_fill_markouts(book_path, results)
        report["scenarios"] = results
        report["status"] = "success"

    output = Path("bybit_l2_queue_replay_report.json")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
