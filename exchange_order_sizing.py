"""Convert notional-based risk sizing into exchange-valid linear contract quantity."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from bybit_instrument_specs import InstrumentSpec


@dataclass(frozen=True)
class ExchangeSizedOrder:
    symbol: str
    order_type: Literal["market", "limit"]
    side: Literal["buy", "sell"]
    qty: Decimal
    price: Decimal
    notional_usdt: Decimal
    risk_usdt: Decimal


def size_to_exchange_constraints(
    spec: InstrumentSpec,
    target_notional_usdt: Decimal | str | float,
    reference_price: Decimal | str | float,
    risk_budget_usdt: Decimal | str | float,
    *,
    order_type: Literal["market", "limit"],
    side: Literal["buy", "sell"],
    price_is_execution: bool = False,
    position_qty_cap: Decimal | str | float | None = None,
) -> ExchangeSizedOrder:
    """Floor quantity to qtyStep and reject all min/max exchange constraints.

    For limit orders, price is rounded away from aggressiveness (buy down,
    sell up), then quantity is recalculated at that rounded price so the
    notional/risk budget is not increased by tick rounding. Market reference
    prices are not tick-rounded.
    """
    target = Decimal(str(target_notional_usdt))
    ref = Decimal(str(reference_price))
    risk = Decimal(str(risk_budget_usdt))
    if not target.is_finite() or target <= 0:
        raise ValueError("target_notional_usdt must be finite and > 0")
    if not ref.is_finite() or ref <= 0:
        raise ValueError("reference_price must be finite and > 0")
    if not risk.is_finite() or risk <= 0:
        raise ValueError("risk_budget_usdt must be finite and > 0")
    if order_type not in {"market", "limit"}:
        raise ValueError("order_type must be market or limit")
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")

    # A simulated/observed fill price is already the execution price; do not
    # round it to a different quote. validate_order still enforces tick alignment
    # for limit fills and the correct order-type quantity cap.
    price = (
        ref if price_is_execution
        else spec.round_price(ref, side=side) if order_type == "limit"
        else ref
    )
    raw_qty = target / price
    if position_qty_cap is not None:
        cap = Decimal(str(position_qty_cap))
        if not cap.is_finite() or cap <= 0:
            raise ValueError("position_qty_cap must be finite and > 0")
        raw_qty = min(raw_qty, cap)
    qty = spec.validate_order(raw_qty, price, order_type=order_type)
    notional = qty * price
    adjusted_risk = risk * notional / target
    if adjusted_risk > risk:
        raise ArithmeticError("exchange rounding unexpectedly increased risk budget")
    return ExchangeSizedOrder(
        symbol=spec.symbol,
        order_type=order_type,
        side=side,
        qty=qty,
        price=price,
        notional_usdt=notional,
        risk_usdt=adjusted_risk,
    )
