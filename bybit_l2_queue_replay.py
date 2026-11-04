"""Conservative aggregate-L2 passive-order replay primitives.

This is not L3 queue reconstruction: cancellations never reduce queue-ahead,
and trades at/before arrival are never credited to a hypothetical order.
"""
from __future__ import annotations

import csv
import gzip
import json
import zipfile
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator

from bybit_instrument_specs import InstrumentSpec as ExchangeInstrumentSpec

ZERO = Decimal("0")


def strict_int(value: object, field: str) -> int:
    """Parse JSON integer fields without bool/string/float coercion."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def parse_trade_timestamp_ms(value: object) -> int:
    """Convert archive seconds or milliseconds to exact integer milliseconds."""
    try:
        raw = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("invalid public trade timestamp") from exc
    if not raw.is_finite() or raw <= ZERO:
        raise ValueError("public trade timestamp must be finite and positive")
    milliseconds = raw if raw > Decimal("1000000000000") else raw * Decimal("1000")
    if milliseconds != milliseconds.to_integral_value():
        raise ValueError("public trade timestamp has sub-millisecond precision")
    return int(milliseconds)


def parse_exchange_bool(value: object, field: str) -> bool:
    if value is True or (type(value) is int and value == 1) or value in ("1", "True", "true"):
        return True
    if value is False or (type(value) is int and value == 0) or value in ("0", "False", "false"):
        return False
    raise ValueError(f"invalid {field} boolean flag: {value!r}")


def dec(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid decimal: {value!r}") from exc
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
        cts = strict_int(event.get("cts"), "cts")
        seq = strict_int(data.get("seq"), "seq")
        update_id = strict_int(data.get("u"), "u")
        if cts <= 0:
            raise ValueError("cts must be positive")
        if seq <= 0:
            raise ValueError("seq must be positive")
        if update_id <= 0:
            raise ValueError("u must be positive")
        if self.last_u is None and kind != "snapshot":
            raise ValueError("order-book stream must begin with a full snapshot")
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


@dataclass(frozen=True)
class PassiveFill:
    timestamp_ms: int
    side: str
    price: Decimal
    quantity: Decimal


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
    block_trade_excluded_count: int = 0
    first_fill_ts: int | None = None
    fills: list[PassiveFill] = field(default_factory=list)
    processed_trade_ids: set[tuple[str, str]] = field(default_factory=set)

    @property
    def remaining(self) -> Decimal:
        return max(ZERO, self.quantity - self.filled)

    @property
    def complete(self) -> bool:
        return self.remaining == ZERO

    @property
    def filled_notional(self) -> Decimal:
        return sum((fill.price * fill.quantity for fill in self.fills), ZERO)

    @property
    def filled_vwap(self) -> Decimal | None:
        if self.filled == ZERO:
            return None
        return self.filled_notional / self.filled


def per_fill_fee_ledger(
    order: PassiveOrder, maker_fee_rates: list[Decimal | str | int | float],
) -> list[dict]:
    """Calculate quote-currency fees only from explicit per-fill fee rates.

    Rates are supplied per fill so tier changes/rebates are never guessed.
    Negative rates are allowed to represent an explicit maker rebate.
    """
    if len(maker_fee_rates) != len(order.fills):
        raise ValueError("one explicit maker fee rate is required for each fill")
    ledger = []
    for index, (fill, raw_rate) in enumerate(zip(order.fills, maker_fee_rates), 1):
        rate = dec(raw_rate)
        notional = fill.price * fill.quantity
        ledger.append({
            "fill_index": index,
            "timestamp_ms": fill.timestamp_ms,
            "price": fill.price,
            "quantity": fill.quantity,
            "notional": notional,
            "maker_fee_rate": rate,
            "fee": notional * rate,
        })
    return ledger


def place_passive_order(
    book: OrderBook, *, side: str, price: Decimal, quantity: Decimal,
    arrival_ts: int, expiry_ts: int,
    instrument_spec: ExchangeInstrumentSpec | None = None,
    symbol: str | None = None,
) -> PassiveOrder:
    if side not in ("Buy", "Sell"):
        raise ValueError("side must be Buy or Sell")
    arrival_ts = strict_int(arrival_ts, "arrival_ts")
    expiry_ts = strict_int(expiry_ts, "expiry_ts")
    price, quantity = dec(price), dec(quantity)
    if price <= ZERO or quantity <= ZERO or expiry_ts <= arrival_ts:
        raise ValueError("invalid price, quantity or lifetime")
    if book.last_cts is None:
        raise ValueError("passive order requires a timestamped order-book state")
    if book.last_cts >= arrival_ts:
        raise ValueError("order-book state must be strictly earlier than order arrival")
    if instrument_spec is not None:
        if not symbol:
            raise ValueError("symbol is required when validating an instrument spec")
        if instrument_spec.symbol != symbol.strip().upper():
            raise ValueError("instrument spec symbol does not match passive order symbol")
        exchange_qty = instrument_spec.validate_order(quantity, price, order_type="limit")
        if exchange_qty != quantity:
            raise ValueError("order quantity is not exactly aligned to qtyStep")
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
    ts = strict_int(trade.get("timestamp_ms"), "public trade timestamp_ms")
    if ts <= order.arrival_ts or ts >= order.expiry_ts or order.complete:
        return
    side = str(trade["side"])
    if side not in ("Buy", "Sell"):
        raise ValueError(f"unknown trade side: {side!r}")
    price, qty = dec(trade["price"]), dec(trade["size"])
    if price <= ZERO or qty <= ZERO:
        raise ValueError("public trade price and size must be positive")
    # Normalized public-trade events must carry both classification flags.
    # Missing metadata is unknown, not equivalent to a confirmed False value.
    if parse_exchange_bool(trade.get("block_trade"), "block trade"):
        order.block_trade_excluded_count += 1
        return
    if parse_exchange_bool(trade.get("rpi"), "RPI"):
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
            order.fills.append(PassiveFill(
                timestamp_ms=ts, side=order.side, price=order.price, quantity=fill,
            ))
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
                if not isinstance(event, dict):
                    raise ValueError(f"invalid order-book event at row {line_no}")
                data = event.get("data")
                if not isinstance(data, dict):
                    raise ValueError(f"invalid order-book data at row {line_no}")
                if data.get("s") != symbol:
                    raise ValueError(f"unexpected symbol at order-book row {line_no}")
                try:
                    strict_int(event.get("cts"), "cts")
                except ValueError as exc:
                    raise ValueError(f"invalid cts at order-book row {line_no}: {exc}") from exc
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
        required = {"timestamp", "symbol", "side", "size", "price", "trdMatchID"}
        fieldnames = reader.fieldnames or []
        if len(fieldnames) != len(set(fieldnames)):
            raise ValueError("trade archive contains duplicate column names")
        fields = set(fieldnames)
        if not required.issubset(fields):
            raise ValueError("trade archive is missing required columns")
        block_flags = [name for name in ("isBlockTrade", "BT") if name in fields]
        if not block_flags:
            raise ValueError("trade archive is missing block-trade flag; queue replay cannot safely classify prints")
        rpi_flags = [name for name in ("RPI", "isRPITrade") if name in fields]
        if not rpi_flags:
            raise ValueError("trade archive is missing RPI flag; queue replay cannot safely classify prints")
        for row_no, row in enumerate(reader, 2):
            if None in row:
                raise ValueError(f"unexpected extra CSV fields at row {row_no}")
            required_row_fields = required | set(block_flags) | set(rpi_flags)
            if any(row.get(name) is None for name in required_row_fields):
                raise ValueError(f"missing CSV field value at row {row_no}")
            if row.get("symbol") != symbol:
                raise ValueError(f"unexpected trade symbol at CSV row {row_no}")
            timestamp_ms = parse_trade_timestamp_ms(row["timestamp"])
            trade_id = row.get("trdMatchID")
            if not isinstance(trade_id, str) or not trade_id.strip():
                raise ValueError(f"missing public trade ID at CSV row {row_no}")
            if trade_id != trade_id.strip():
                raise ValueError(f"public trade ID has surrounding whitespace at CSV row {row_no}")
            block_values = {
                parse_exchange_bool(row[name], "block trade") for name in block_flags
            }
            rpi_values = {
                parse_exchange_bool(row[name], "RPI") for name in rpi_flags
            }
            if len(block_values) != 1:
                raise ValueError(f"conflicting block-trade flag aliases at CSV row {row_no}")
            if len(rpi_values) != 1:
                raise ValueError(f"conflicting RPI flag aliases at CSV row {row_no}")
            yield {
                "timestamp_ms": timestamp_ms,
                "side": row["side"],
                "price": row["price"],
                "size": row["size"],
                "rpi": next(iter(rpi_values)),
                "block_trade": next(iter(block_values)),
                "trade_id": trade_id,
            }


def replay_public_trades(order: PassiveOrder, archive: Path, symbol: str = "AAVEUSDT") -> PassiveOrder:
    previous_ts = None
    previously_processed_ids = set(order.processed_trade_ids)
    seen_trade_ids: set[tuple[str, str]] = set()
    working_order = replace(
        order, fills=list(order.fills),
        processed_trade_ids=set(previously_processed_ids),
    )
    for trade in iter_public_trades(archive, symbol):
        ts = strict_int(trade.get("timestamp_ms"), "public trade timestamp_ms")
        if previous_ts is not None and ts < previous_ts:
            raise ValueError("non-monotonic public trade timestamps")
        previous_ts = ts
        trade_id = trade.get("trade_id")
        if not isinstance(trade_id, str) or not trade_id or trade_id != trade_id.strip():
            raise ValueError("missing public trade ID or malformed surrounding whitespace")
        trade_key = (symbol.strip().upper(), trade_id)
        if trade_key in seen_trade_ids:
            raise ValueError(f"duplicate public trade ID: {trade_id}")
        seen_trade_ids.add(trade_key)
        # Validate the complete archive's ordering and ID uniqueness, including
        # records outside this order's active window. Do not let an early
        # post-expiry row hide a later out-of-order print that belongs in-window.
        if ts <= order.arrival_ts or ts >= order.expiry_ts:
            continue
        if working_order.complete:
            continue
        if trade_key in previously_processed_ids:
            # Replaying an overlapping archive is idempotent: do not consume
            # queue or count the same public match twice.
            continue
        working_order.processed_trade_ids.add(trade_key)
        apply_public_trade(working_order, trade)
    order.__dict__.update(working_order.__dict__)
    return order
