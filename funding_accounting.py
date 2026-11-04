"""Pure, cumulative funding cashflow calculation for a single open position.

The returned amount is positive when paid and negative when received. The
supplied mark is an exact-timestamp mark-candle open proxy, not necessarily
the exchange's final settlement mark. MTM and final close share this helper.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping


CENT = Decimal("0.01")


def _timestamp_ms(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer millisecond timestamp")
    return value


def _d(value: Any, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name}: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite {name}: {value!r}")
    return result


def accrued_funding_cost(
    position: Any,
    events: Iterable[Mapping[str, Any]],
    mark_prices: Mapping[int, Any],
    as_of_ts: int,
    closed_ts_ms: int | None = None,
    defer_boundary_receipts: bool = False,
) -> Decimal:
    """Return cumulative funding paid/received in [entry_ts, as_of_ts].

    Settlement at the entry timestamp is treated conservatively: a possible
    payment is charged, while a possible receipt is excluded because Bybit does
    not guarantee inclusion for executions within five seconds of settlement.
    The as-of timestamp is included. mark_prices contains timestamp-aligned
    mark-candle open proxies. At an ambiguous final-close boundary, payments
    use full initial quantity and receipts use zero quantity. At an ambiguous
    TP1-only boundary, payments use full quantity and receipts use the
    remaining fraction; later settlements use the remaining fraction. For
    pre-exit MTM, defer receipts at the current as-of boundary until a later mark.
    """
    entry_ts = _timestamp_ms(position.entry_ts, "entry_ts")
    as_of_ts = _timestamp_ms(as_of_ts, "as_of_ts")
    if as_of_ts < entry_ts:
        raise ValueError("as_of_ts cannot precede position entry")
    direction = str(position.direction).lower()
    if direction not in {"long", "short"}:
        raise ValueError("position direction must be long or short")

    entry_price = _d(position.entry_price, "entry_price")
    size_usdt = _d(position.size_usdt, "size_usdt")
    remaining_fraction = _d(position.remaining_fraction, "remaining_fraction")
    if entry_price <= 0 or size_usdt <= 0:
        raise ValueError("entry_price and size_usdt must be > 0")
    if remaining_fraction < 0 or remaining_fraction > 1:
        raise ValueError("remaining_fraction must be within [0, 1]")

    tp1_hit = getattr(position, "tp1_hit", False)
    if not isinstance(tp1_hit, bool):
        raise ValueError("tp1_hit must be bool")
    tp1_ts = getattr(position, "tp1_ts_ms", None)
    if tp1_hit and tp1_ts is None:
        raise ValueError("tp1_ts_ms is required when tp1_hit is true")
    if not tp1_hit and tp1_ts is not None:
        raise ValueError("tp1_ts_ms cannot be set when tp1_hit is false")
    if tp1_ts is not None:
        tp1_ts = _timestamp_ms(tp1_ts, "tp1_ts_ms")
        if tp1_ts < entry_ts:
            raise ValueError("tp1_ts_ms cannot precede entry")
    if closed_ts_ms is not None:
        closed_ts_ms = _timestamp_ms(closed_ts_ms, "closed_ts_ms")
        if closed_ts_ms < entry_ts:
            raise ValueError("closed_ts_ms cannot precede position entry")

    sign = Decimal("1") if direction == "long" else Decimal("-1")
    exact_initial = getattr(position, "contract_qty", None)
    exact_remaining = getattr(position, "remaining_contract_qty", None)
    quantity = _d(exact_initial, "contract_qty") if exact_initial is not None else size_usdt / entry_price
    remaining_quantity = (
        _d(exact_remaining, "remaining_contract_qty")
        if exact_remaining is not None else quantity * remaining_fraction
    )
    if quantity <= 0 or remaining_quantity < 0 or remaining_quantity > quantity:
        raise ValueError("contract quantities must satisfy 0 <= remaining <= initial")
    if tp1_hit and remaining_quantity >= quantity:
        raise ValueError("tp1_hit requires a reduced remaining contract quantity")
    if not tp1_hit and remaining_quantity != quantity:
        raise ValueError("remaining contract quantity cannot be partial when tp1_hit is false")
    remaining_ratio = remaining_quantity / quantity
    total = Decimal("0")
    seen: set[int] = set()

    for event in events:
        try:
            ts = _timestamp_ms(event["ts"], "funding event timestamp")
            rate = _d(event["rate"], "funding rate")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid funding event: {event!r}") from exc
        if ts in seen:
            raise ValueError(f"duplicate funding settlement timestamp: {ts}")
        seen.add(ts)
        if not (entry_ts <= ts <= as_of_ts):
            continue
        mark_raw = mark_prices.get(ts)
        if mark_raw is None:
            raise RuntimeError(
                f"Missing exact candle-boundary mark proxy for funding timestamp {ts}"
            )
        mark = _d(mark_raw, "funding mark price")
        if mark <= 0:
            raise ValueError(f"funding mark price must be > 0 at {ts}")
        fraction = Decimal("1")
        full_position_cost = sign * quantity * mark * rate
        if ts == entry_ts and full_position_cost < 0:
            # Entry and funding settlement boundary ordering is unknown.
            # Charge a possible payment, but never assume a receipt.
            fraction = Decimal("0")
        elif closed_ts_ms is not None and ts == closed_ts_ms:
            # A full exit and settlement share an OHLC candle-close boundary.
            # With unknown event order, charge a payment on full size but never
            # credit a receipt on a position that may already have been closed.
            if full_position_cost < 0:
                fraction = Decimal("0")
        elif defer_boundary_receipts and ts == as_of_ts and full_position_cost < 0:
            # MTM runs before candle exit resolution. Defer same-boundary receipts
            # so they cannot mask an adverse stop/kill-switch mark. If still open,
            # the receipt is included at the next mark (ts < as_of_ts).
            fraction = Decimal("0")
        elif tp1_ts is not None and ts > tp1_ts:
            fraction = remaining_ratio
        elif tp1_ts is not None and ts == tp1_ts:
            # TP1 and funding share a candle-close boundary, but position remains
            # open: use full size for payments and remaining size for receipts.
            if full_position_cost < 0:
                fraction = remaining_ratio
        total += sign * quantity * mark * fraction * rate

    return total.quantize(CENT, rounding=ROUND_HALF_UP)


def accrued_funding_cost_for_remaining_margin(
    position: Any,
    events: Iterable[Mapping[str, Any]],
    mark_prices: Mapping[int, Any],
    as_of_ts: int,
    defer_boundary_receipts: bool = False,
) -> Decimal:
    """Funding cashflows allocated to the currently open isolated position.

    If TP1 partially closed the original position, Bybit's partial-close PnL
    accounting prorates accumulated funding across the closed and remaining
    quantities. Therefore every funding cashflow accrued over the original
    position lifecycle is allocated to the current remaining quantity ratio,
    including settlements before TP1. This helper returns only the remaining
    position's share; accrued_funding_cost() continues to return the full
    position-lifecycle cashflow for final trade PnL.
    """
    entry_ts = _timestamp_ms(position.entry_ts, "entry_ts")
    as_of_ts = _timestamp_ms(as_of_ts, "as_of_ts")
    direction = str(position.direction).lower()
    if direction not in {"long", "short"} or as_of_ts < entry_ts:
        raise ValueError("valid direction and as_of_ts >= entry_ts are required")
    entry_price = _d(position.entry_price, "entry_price")
    size_usdt = _d(position.size_usdt, "size_usdt")
    if entry_price <= 0 or size_usdt <= 0:
        raise ValueError("entry_price and size_usdt must be > 0")
    exact_initial = getattr(position, "contract_qty", None)
    exact_remaining = getattr(position, "remaining_contract_qty", None)
    quantity = _d(exact_initial, "contract_qty") if exact_initial is not None else size_usdt / entry_price
    remaining_fraction = _d(position.remaining_fraction, "remaining_fraction")
    if remaining_fraction < 0 or remaining_fraction > 1:
        raise ValueError("remaining_fraction must be within [0, 1]")
    remaining = _d(exact_remaining, "remaining_contract_qty") if exact_remaining is not None else quantity * remaining_fraction
    if quantity <= 0 or remaining < 0 or remaining > quantity:
        raise ValueError("invalid initial or remaining contract quantity")
    ratio = remaining / quantity
    tp1_hit = getattr(position, "tp1_hit", False)
    if not isinstance(tp1_hit, bool):
        raise ValueError("tp1_hit must be bool")
    tp1_ts = getattr(position, "tp1_ts_ms", None)
    if tp1_hit and tp1_ts is None:
        raise ValueError("tp1_ts_ms is required when tp1_hit is true")
    if not tp1_hit and tp1_ts is not None:
        raise ValueError("tp1_ts_ms cannot be set when tp1_hit is false")
    if tp1_ts is not None:
        tp1_ts = _timestamp_ms(tp1_ts, "tp1_ts_ms")
        if tp1_ts < entry_ts:
            raise ValueError("tp1_ts_ms cannot precede position entry")
    if tp1_hit and remaining >= quantity:
        raise ValueError("tp1_hit requires a reduced remaining contract quantity")
    if not tp1_hit and remaining != quantity:
        raise ValueError("remaining contract quantity cannot be partial when tp1_hit is false")
    sign = Decimal("1") if direction == "long" else Decimal("-1")
    total = Decimal("0")
    seen: set[int] = set()
    for event in events:
        try:
            ts = _timestamp_ms(event["ts"], "funding event timestamp")
            rate = _d(event["rate"], "funding rate")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid funding event: {event!r}") from exc
        if ts in seen:
            raise ValueError(f"duplicate funding settlement timestamp: {ts}")
        seen.add(ts)
        if not (entry_ts <= ts <= as_of_ts):
            continue
        mark_raw = mark_prices.get(ts)
        if mark_raw is None:
            raise RuntimeError(f"Missing exact candle-boundary mark proxy for funding timestamp {ts}")
        mark = _d(mark_raw, "funding mark price")
        if mark <= 0:
            raise ValueError(f"funding mark price must be > 0 at {ts}")
        full_cost = sign * quantity * mark * rate
        # Once TP1 has partially closed the position, only the
        # remaining share of all accumulated funding belongs to the open leg.
        # This includes settlements that happened before the TP1 timestamp.
        tp1_effective_as_of = tp1_ts is not None and tp1_ts <= as_of_ts
        fraction = ratio if tp1_effective_as_of else Decimal("1")
        if ts == entry_ts and full_cost < 0:
            # Do not book a potentially unavailable receipt at the entry instant.
            fraction = Decimal("0")
        if defer_boundary_receipts and ts == as_of_ts and full_cost < 0:
            # The current-boundary receipt is deferred until the next mark,
            # because MTM is evaluated before same-candle exit resolution.
            fraction = Decimal("0")
        total += full_cost * fraction
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
