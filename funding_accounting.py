"""Pure, cumulative funding cashflow calculation for a single open position.

The returned amount is positive when paid and negative when received. The
supplied mark is an exact-timestamp mark-candle open proxy, not necessarily
the exchange's final settlement mark. MTM and final close share this helper.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping


CENT = Decimal("0.01")


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
) -> Decimal:
    """Return cumulative funding paid/received in [entry_ts, as_of_ts].

    Funding settlement at entry timestamp is excluded; settlement at the
    as-of timestamp is included. A settlement at or before the conservative
    TP1 candle-close boundary uses full initial quantity; later settlements
    use the remaining position fraction.
    """
    entry_ts = int(position.entry_ts)
    as_of_ts = int(as_of_ts)
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

    tp1_ts = getattr(position, "tp1_ts_ms", None)
    if bool(getattr(position, "tp1_hit", False)) and tp1_ts is None:
        raise ValueError("tp1_ts_ms is required when tp1_hit is true")
    if tp1_ts is not None:
        tp1_ts = int(tp1_ts)
        if tp1_ts < entry_ts:
            raise ValueError("tp1_ts_ms cannot precede entry")

    sign = Decimal("1") if direction == "long" else Decimal("-1")
    quantity = size_usdt / entry_price
    total = Decimal("0")
    seen: set[int] = set()

    for event in events:
        try:
            ts = int(event["ts"])
            rate = _d(event["rate"], "funding rate")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid funding event: {event!r}") from exc
        if ts in seen:
            raise ValueError(f"duplicate funding settlement timestamp: {ts}")
        seen.add(ts)
        if not (entry_ts < ts <= as_of_ts):
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
        if tp1_ts is not None and ts > tp1_ts:
            fraction = remaining_fraction
        total += sign * quantity * mark * fraction * rate

    return total.quantize(CENT, rounding=ROUND_HALF_UP)
