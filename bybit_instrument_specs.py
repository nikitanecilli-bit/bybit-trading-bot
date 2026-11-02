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
    min_price: Decimal
    max_price: Decimal
    qty_step: Decimal
    min_order_qty: Decimal
    min_notional_value: Decimal
    max_order_qty: Decimal | None = None
    max_market_order_qty: Decimal | None = None
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
        category = str(instrument.get("category") or "linear").strip().lower()
        if category != "linear":
            raise ValueError("InstrumentSpec only supports linear contracts")
        if not symbol:
            raise ValueError("instrument symbol is required")
        tick_size = _positive(price_filter.get("tickSize"), "priceFilter.tickSize")
        min_price = _positive(price_filter.get("minPrice"), "priceFilter.minPrice")
        max_price = _positive(price_filter.get("maxPrice"), "priceFilter.maxPrice")
        if max_price < min_price:
            raise ValueError("priceFilter.maxPrice cannot be below minPrice")
        qty_step = _positive(lot_filter.get("qtyStep"), "lotSizeFilter.qtyStep")
        min_qty = _positive(lot_filter.get("minOrderQty"), "lotSizeFilter.minOrderQty")
        min_notional = _positive(
            lot_filter.get("minNotionalValue"), "lotSizeFilter.minNotionalValue"
        )
        max_qty = _positive(lot_filter.get("maxOrderQty"), "lotSizeFilter.maxOrderQty")
        max_market_qty = _positive(
            lot_filter.get("maxMktOrderQty"), "lotSizeFilter.maxMktOrderQty"
        )
        min_lev = _positive(leverage_filter.get("minLeverage"), "leverageFilter.minLeverage", optional=True)
        max_lev = _positive(leverage_filter.get("maxLeverage"), "leverageFilter.maxLeverage", optional=True)
        lev_step = _positive(leverage_filter.get("leverageStep"), "leverageFilter.leverageStep", optional=True)
        if max_qty is not None and max_qty < min_qty:
            raise ValueError("maxOrderQty cannot be below minOrderQty")
        if max_market_qty is not None and max_market_qty < min_qty:
            raise ValueError("maxMktOrderQty cannot be below minOrderQty")
        if min_lev is not None and max_lev is not None and max_lev < min_lev:
            raise ValueError("maxLeverage cannot be below minLeverage")
        return cls(
            schema_version=SCHEMA_VERSION,
            symbol=symbol,
            category=category,
            status=str(instrument.get("status") or "unknown"),
            fetched_at=str(payload.get("fetched_at")) if payload.get("fetched_at") else None,
            tick_size=tick_size,
            min_price=min_price,
            max_price=max_price,
            qty_step=qty_step,
            min_order_qty=min_qty,
            min_notional_value=min_notional,
            max_order_qty=max_qty,
            max_market_order_qty=max_market_qty,
            min_leverage=min_lev,
            max_leverage=max_lev,
            leverage_step=lev_step,
        )

    def round_price(self, price: Any, *, side: str) -> Decimal:
        """Round a buy limit down and a sell limit up, never making it more aggressive."""
        value = _positive(price, "price")
        if side == "buy":
            rounded = _floor_step(value, self.tick_size)
        elif side == "sell":
            rounded = _ceil_step(value, self.tick_size)
        else:
            raise ValueError("side must be 'buy' or 'sell'")
        if rounded <= 0:
            raise ValueError("price rounds to zero at tickSize")
        if rounded < self.min_price or rounded > self.max_price:
            raise ValueError("rounded limit price is outside minPrice/maxPrice")
        return rounded

    def round_qty(self, qty: Any) -> Decimal:
        """Round quantity down to qtyStep; never round risk upward."""
        value = _positive(qty, "qty")
        return _floor_step(value, self.qty_step)

    def validate_order(self, qty: Any, price: Any, *, order_type: str = "limit") -> Decimal:
        """Return rounded quantity or reject exchange minimum/maximum constraints."""
        if order_type not in {"limit", "market"}:
            raise ValueError("order_type must be 'limit' or 'market'")
        if self.status != "Trading":
            raise ValueError(f"instrument status {self.status!r} is not tradable")
        rounded_qty = self.round_qty(qty)
        px = _positive(price, "price")
        if order_type == "limit" and not (self.min_price <= px <= self.max_price):
            raise ValueError("limit price is outside minPrice/maxPrice")
        if order_type == "limit" and px % self.tick_size != 0:
            raise ValueError("limit price must be aligned to tickSize; call round_price first")
        if rounded_qty < self.min_order_qty:
            raise ValueError("quantity is below minOrderQty after qtyStep rounding")
        maximum = self.max_order_qty if order_type == "limit" else self.max_market_order_qty
        maximum_name = "maxOrderQty" if order_type == "limit" else "maxMktOrderQty"
        if maximum is not None and rounded_qty > maximum:
            raise ValueError(f"quantity exceeds {maximum_name}")
        if rounded_qty * px < self.min_notional_value:
            raise ValueError("order notional is below minNotionalValue")
        return rounded_qty
