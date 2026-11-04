"""Conservative aggregate-L2 passive-order replay primitives.

This is not L3 queue reconstruction: cancellations never reduce queue-ahead,
and trades at/before arrival are never credited to a hypothetical order.
"""
from __future__ import annotations

import csv
import gzip
import json
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterator

ZERO = Decimal("0")


def dec(value: object) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError(f"non-finite decimal: {value!r}")
    return result


class OrderBook:
    def __init__(self) -> None:
        self.bids: dict[Decimal, Decimal] = {}
        self.asks: dict[Decimal, Decimal] = {}
        self.last_cts: int | None = None
        self.last_seq: int | None = None
        self.last_u: int | None = None

    def apply(self, event: dict) -> None:
        kind = event.get("type")
        data = event.get("data")
        if kind not in ("snapshot", "delta") or not isinstance(data, dict):
            raise ValueError("invalid order-book event")
        cts = int(event["cts"])
        seq = int(data["seq"])
        raw_u = data.get("u")
        if isinstance(raw_u, bool) or raw_u is None:
            raise ValueError("missing or invalid order-book update ID")
        try:
            update_id = int(raw_u)
        except (TypeError, ValueError) as exc:
            raise ValueError("missing or invalid order-book update ID") from exc
        if update_id <= 0:
            raise ValueError("order-book update ID must be positive")
        reset_snapshot = update_id == 1
        if reset_snapshot and kind != "snapshot":
            raise ValueError("u=1 restart marker requires a full snapshot for this archive format")
        if self.last_cts is not None and cts < self.last_cts:
            raise ValueError("non-monotonic matching-engine timestamp")
        # u=1 resets the book contents, but seq remains a separate cross-sequence
        # ordering signal; do not infer that its ordering epoch also reset.
        if self.last_seq is not None and seq < self.last_seq:
            raise ValueError("non-monotonic cross sequence")
        # Build and validate the candidate state before mutating the live book.
        # A malformed delta/snapshot must not leave a partially applied book.
        next_bids = {} if kind == "snapshot" else dict(self.bids)
        next_asks = {} if kind == "snapshot" else dict(self.asks)
        for key, book_side in (("b", next_bids), ("a", next_asks)):
            levels = data.get(key)
            if not isinstance(levels, list):
                raise ValueError(f"missing {key} levels")
            for level in levels:
                if not isinstance(level, list) or len(level) != 2:
                    raise ValueError("invalid price/quantity level")
                price, qty = dec(level[0]), dec(level[1])
                if price <= ZERO or qty < ZERO:
                    raise ValueError("price must be positive and quantity non-negative")
                if qty == ZERO:
                    book_side.pop(price, None)
                else:
                    book_side[price] = qty
        if next_bids and next_asks and max(next_bids) >= min(next_asks):
            raise ValueError("crossed reconstructed order book")
        self.bids, self.asks = next_bids, next_asks
        self.last_cts, self.last_seq, self.last_u = cts, seq, update_id

    def best_bid(self) -> tuple[Decimal, Decimal]:
        if not self.bids:
            raise ValueError("no bid levels")
        price = max(self.bids)
        return price, self.bids[price]

    def best_ask(self) -> tuple[Decimal, Decimal]:
        if not self.asks:
            raise ValueError("no ask levels")
        price = min(self.asks)
        return price, self.asks[price]

    def quantity_at(self, side: str, price: Decimal) -> Decimal:
        levels = self.bids if side == "Buy" else self.asks
        return levels.get(price, ZERO)

    def copy_levels(self) -> tuple[dict[Decimal, Decimal], dict[Decimal, Decimal]]:
        return dict(self.bids), dict(self.asks)


@dataclass
class PassiveOrder:
    side: str
    price: Decimal
    quantity: Decimal
    arrival_ts: int
    expiry_ts: int
    queue_ahead_initial: Decimal
    queue_ahead_remaining: Decimal
    filled: Decimal = ZERO
    fill_count: int = 0
    eligible_trade_count: int = 0
    rpi_excluded_count: int = 0
    first_fill_ts: int | None = None

    @property
    def remaining(self) -> Decimal:
        return max(ZERO, self.quantity - self.filled)

    @property
    def complete(self) -> bool:
        return self.remaining == ZERO


def place_passive_order(
    book: OrderBook, *, side: str, price: Decimal, quantity: Decimal,
    arrival_ts: int, expiry_ts: int,
) -> PassiveOrder:
    if side not in ("Buy", "Sell"):
        raise ValueError("side must be Buy or Sell")
    price, quantity = dec(price), dec(quantity)
    if price <= ZERO or quantity <= ZERO or expiry_ts <= arrival_ts:
        raise ValueError("invalid price, quantity or lifetime")
    best_bid, _ = book.best_bid()
    best_ask, _ = book.best_ask()
    if (side == "Buy" and price >= best_ask) or (side == "Sell" and price <= best_bid):
        raise ValueError("marketable order is not a passive maker order")
    queue = book.quantity_at(side, price)
    return PassiveOrder(
        side=side, price=price, quantity=quantity, arrival_ts=arrival_ts,
        expiry_ts=expiry_ts, queue_ahead_initial=queue, queue_ahead_remaining=queue,
    )


def apply_public_trade(order: PassiveOrder, trade: dict) -> None:
    ts = int(trade["timestamp_ms"])
    if ts <= order.arrival_ts or ts >= order.expiry_ts or order.complete:
        return
    side = str(trade["side"])
    if side not in ("Buy", "Sell"):
        raise ValueError(f"unknown trade side: {side!r}")
    price, qty = dec(trade["price"]), dec(trade["size"])
    if price <= ZERO or qty <= ZERO:
        raise ValueError("public trade price and size must be positive")
    rpi_flag = str(trade.get("rpi", "0")).strip()
    if rpi_flag not in ("", "0", "1", "False", "false", "True", "true"):
        raise ValueError(f"unknown RPI flag: {rpi_flag!r}")
    if rpi_flag in ("1", "True", "true"):
        order.rpi_excluded_count += 1
        return
    if price != order.price:
        return
    if side == "Buy" and order.side != "Sell":
        return
    if side == "Sell" and order.side != "Buy":
        return
    order.eligible_trade_count += 1
    consumed_ahead = min(order.queue_ahead_remaining, qty)
    order.queue_ahead_remaining -= consumed_ahead
    executable = qty - consumed_ahead
    if executable > ZERO:
        fill = min(order.remaining, executable)
        if fill > ZERO:
            order.filled += fill
            order.fill_count += 1
            if order.first_fill_ts is None:
                order.first_fill_ts = ts


def signed_markout_bps(
    side: str, fill_price: Decimal, best_bid: Decimal, best_ask: Decimal,
) -> Decimal:
    """Signed mid-price markout in bps: positive means favorable to the maker."""
    if side not in ("Buy", "Sell"):
        raise ValueError("side must be Buy or Sell")
    fill_price, best_bid, best_ask = dec(fill_price), dec(best_bid), dec(best_ask)
    if fill_price <= ZERO or best_bid <= ZERO or best_ask <= ZERO or best_bid > best_ask:
        raise ValueError("invalid fill price or BBO")
    mid = (best_bid + best_ask) / Decimal("2")
    sign = Decimal("1") if side == "Buy" else Decimal("-1")
    return (mid - fill_price) / fill_price * sign * Decimal("10000")


def iter_book_events(archive: Path, symbol: str = "AAVEUSDT") -> Iterator[dict]:
    with zipfile.ZipFile(archive) as zf:
        members = [name for name in zf.namelist() if name.endswith(".data")]
        if len(members) != 1:
            raise ValueError(f"expected one .data member, found {members!r}")
        with zf.open(members[0], "r") as stream:
            for line_no, raw in enumerate(stream, 1):
                if not raw.strip():
                    continue
                event = json.loads(raw)
                if event.get("data", {}).get("s") != symbol:
                    raise ValueError(f"unexpected symbol at order-book row {line_no}")
                if event.get("cts") is None:
                    raise ValueError(f"missing cts at order-book row {line_no}")
                yield event


def capture_book_at(
    archive: Path, arrival_ts: int, symbol: str = "AAVEUSDT",
) -> tuple[OrderBook, int]:
    book = OrderBook()
    for event in iter_book_events(archive, symbol):
        # Same-millisecond event ordering relative to our hypothetical order is
        # unknowable without an exchange sequence for the order; exclude it.
        if int(event["cts"]) >= arrival_ts:
            break
        book.apply(event)
    if book.last_cts is None:
        raise ValueError("no order-book snapshot at or before arrival")
    return book, book.last_cts


def iter_public_trades(archive: Path, symbol: str = "AAVEUSDT") -> Iterator[dict]:
    with gzip.open(archive, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"timestamp", "symbol", "side", "size", "price"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("trade archive is missing required columns")
        for row_no, row in enumerate(reader, 2):
            if row.get("symbol") != symbol:
                raise ValueError(f"unexpected trade symbol at CSV row {row_no}")
            raw_ts = float(row["timestamp"])
            timestamp_ms = int(round(raw_ts if raw_ts > 1_000_000_000_000 else raw_ts * 1000))
            yield {
                "timestamp_ms": timestamp_ms,
                "side": row["side"],
                "price": row["price"],
                "size": row["size"],
                "rpi": row.get("RPI", row.get("isRPITrade", "0")),
                "trade_id": row.get("trdMatchID"),
            }


def replay_public_trades(order: PassiveOrder, archive: Path, symbol: str = "AAVEUSDT") -> PassiveOrder:
    previous_ts = None
    for trade in iter_public_trades(archive, symbol):
        ts = trade["timestamp_ms"]
        if previous_ts is not None and ts < previous_ts:
            raise ValueError("non-monotonic public trade timestamps")
        previous_ts = ts
        if ts >= order.expiry_ts:
            break
        apply_public_trade(order, trade)
        if order.complete:
            break
    return order
