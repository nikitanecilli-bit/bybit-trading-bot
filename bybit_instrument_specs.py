"""Versioned Bybit linear instrument constraints for research execution models.

This module parses public V5 instruments-info snapshots. It does not place orders
and does not silently substitute defaults for missing exchange constraints.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
from typing import Any, Mapping


SCHEMA_VERSION = 1


def _decimal(value: Any, field: str, *, optional: bool = False) -> Decimal | None:
    if value is None or value == "":
        if optional:
            return None
        raise ValueError(f"missing instrument field: {field}")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid decimal for {field}: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite decimal for {field}: {value!r}")
    return result


def _positive(value: Any, field: str, *, optional: bool = False) -> Decimal | None:
    result = _decimal(value, field, optional=optional)
    if result is not None and result <= 0:
        raise ValueError(f"{field} must be > 0")
    return result


def _floor_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def _ceil_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_CEILING) * step


@dataclass(frozen=True)
class InstrumentSpec:
    schema_version: int
    symbol: str
    category: str
    status: str
    fetched_at: str | None
    tick_size: Decimal
    qty_step: Decimal
    min_order_qty: Decimal
    min_notional_value: Decimal
    max_order_qty: Decimal | None = None
    min_leverage: Decimal | None = None
    max_leverage: Decimal | None = None
    leverage_step: Decimal | None = None

    @classmethod
    def from_snapshot(cls, payload: Mapping[str, Any]) -> "InstrumentSpec":
        if not isinstance(payload, Mapping):
            raise ValueError("instrument snapshot must be a mapping")
        instrument = payload.get("instrument", payload)
        if not isinstance(instrument, Mapping):
            raise ValueError("snapshot 'instrument' must be a mapping")
        price_filter = instrument.get("priceFilter") or {}
        lot_filter = instrument.get("lotSizeFilter") or {}
        leverage_filter = instrument.get("leverageFilter") or {}
        symbol = str(instrument.get("symbol") or "").strip()
        category = str(instrument.get("category") or "linear").strip()
        if not symbol:
            raise ValueError("instrument symbol is required")
        tick_size = _positive(price_filter.get("tickSize"), "priceFilter.tickSize")
        qty_step = _positive(lot_filter.get("qtyStep"), "lotSizeFilter.qtyStep")
        min_qty = _positive(lot_filter.get("minOrderQty"), "lotSizeFilter.minOrderQty")
        min_notional = _positive(
            lot_filter.get("minNotionalValue"), "lotSizeFilter.minNotionalValue"
        )
        max_qty = _positive(lot_filter.get("maxOrderQty"), "lotSizeFilter.maxOrderQty", optional=True)
        min_lev = _positive(leverage_filter.get("minLeverage"), "leverageFilter.minLeverage", optional=True)
        max_lev = _positive(leverage_filter.get("maxLeverage"), "leverageFilter.maxLeverage", optional=True)
        lev_step = _positive(leverage_filter.get("leverageStep"), "leverageFilter.leverageStep", optional=True)
        if max_qty is not None and max_qty < min_qty:
            raise ValueError("maxOrderQty cannot be below minOrderQty")
        if min_lev is not None and max_lev is not None and max_lev < min_lev:
            raise ValueError("maxLeverage cannot be below minLeverage")
        return cls(
            schema_version=SCHEMA_VERSION,
            symbol=symbol,
            category=category,
            status=str(instrument.get("status") or "unknown"),
            fetched_at=str(payload.get("fetched_at")) if payload.get("fetched_at") else None,
            tick_size=tick_size,
            qty_step=qty_step,
            min_order_qty=min_qty,
            min_notional_value=min_notional,
            max_order_qty=max_qty,
            min_leverage=min_lev,
            max_leverage=max_lev,
            leverage_step=lev_step,
        )

    def round_price(self, price: Any, *, side: str) -> Decimal:
        """Round a buy limit down and a sell limit up, never making it more aggressive."""
        value = _positive(price, "price")
        if side == "buy":
            return _floor_step(value, self.tick_size)
        if side == "sell":
            return _ceil_step(value, self.tick_size)
        raise ValueError("side must be 'buy' or 'sell'")

    def round_qty(self, qty: Any) -> Decimal:
        """Round quantity down to qtyStep; never round risk upward."""
        value = _positive(qty, "qty")
        return _floor_step(value, self.qty_step)

    def validate_order(self, qty: Any, price: Any) -> Decimal:
        """Return rounded quantity or reject exchange minimum/maximum constraints."""
        rounded_qty = self.round_qty(qty)
        px = _positive(price, "price")
        if rounded_qty < self.min_order_qty:
            raise ValueError("quantity is below minOrderQty after qtyStep rounding")
        if self.max_order_qty is not None and rounded_qty > self.max_order_qty:
            raise ValueError("quantity exceeds maxOrderQty")
        if rounded_qty * px < self.min_notional_value:
            raise ValueError("order notional is below minNotionalValue")
        return rounded_qty
