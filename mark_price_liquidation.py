"""Isolated USDT-linear liquidation price model based on Bybit's published formula.

This module is deliberately position-level. It does NOT model cross/portfolio
margin, account balance sharing, auto-margin replenishment, hedging offsets,
ADL, partial liquidation, bankruptcy execution, or exchange matching.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

from bybit_risk_tiers import RiskTier


def _d(value, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite {field}")
    return result


@dataclass(frozen=True)
class IsolatedLiquidationEstimate:
    direction: str
    liquidation_price: Decimal
    liquidation_position_value: Decimal
    tier_id: int
    maintenance_margin_rate: Decimal
    mm_deduction: Decimal
    leverage: Decimal
    extra_margin: Decimal


def _tier_band_contains(tiers: tuple[RiskTier, ...], index: int, value: Decimal) -> bool:
    lower = tiers[index - 1].risk_limit_value if index else Decimal("0")
    return lower < value <= tiers[index].risk_limit_value


def calculate_isolated_usdt_liquidation_price(
    *,
    symbol: str,
    direction: str,
    entry_price,
    quantity,
    leverage,
    tiers: Iterable[RiskTier],
    taker_fee_rate="0.00055",
    extra_margin="0",
) -> IsolatedLiquidationEstimate:
    """Solve the isolated USDT-linear LP using Bybit's tiered published formula.

    The risk tier is selected at the *candidate liquidation notional*, rather
    than blindly reusing the entry tier. The returned estimate assumes constant
    quantity, fixed isolated leverage and no funding/partial close before LP.
    """
    side = str(direction).strip().lower()
    if side not in {"long", "short"}:
        raise ValueError("direction must be 'long' or 'short'")
    entry = _d(entry_price, "entry_price")
    qty = _d(quantity, "quantity")
    lev = _d(leverage, "leverage")
    fee = _d(taker_fee_rate, "taker_fee_rate")
    margin = _d(extra_margin, "extra_margin")
    if min(entry, qty, lev) <= 0 or fee < 0 or fee >= 1 or margin < 0:
        raise ValueError("prices, quantity and leverage must be positive; fee in [0,1); margin non-negative")

    ordered = tuple(sorted(tiers, key=lambda item: item.risk_limit_value))
    if not ordered:
        raise ValueError("at least one dated risk tier is required")
    if any(tier.symbol.strip().upper() != symbol.strip().upper() for tier in ordered):
        raise ValueError("all risk tiers must belong to the requested symbol")
    if len({tier.risk_limit_value for tier in ordered}) != len(ordered):
        raise ValueError("risk-tier limits must be unique")
    for tier in ordered:
        if (tier.risk_limit_value <= 0 or tier.maintenance_margin_rate < 0
                or tier.maintenance_margin_rate >= 1 or tier.mm_deduction < 0
                or tier.max_leverage <= 0):
            raise ValueError("risk-tier values are outside supported linear isolated ranges")

    entry_value = entry * qty
    entry_tier = next((tier for tier in ordered if entry_value <= tier.risk_limit_value), None)
    if entry_tier is None:
        raise ValueError(f"{symbol} entry notional exceeds highest riskLimitValue")
    if lev > entry_tier.max_leverage:
        raise ValueError(f"{symbol} leverage exceeds entry tier maxLeverage")

    candidates = []
    for index, tier in enumerate(ordered):
        mmr = tier.maintenance_margin_rate
        deduction = tier.mm_deduction
        if lev > tier.max_leverage:
            continue
        if side == "long":
            denominator = qty * (Decimal("1") - mmr)
            numerator = entry_value * (Decimal("1") - Decimal("1") / lev)
            numerator -= margin / (Decimal("1") - fee)
            numerator -= deduction
        else:
            denominator = qty * (Decimal("1") + mmr)
            numerator = entry_value * (Decimal("1") + Decimal("1") / lev)
            numerator += margin / (Decimal("1") + fee)
            numerator += deduction
        if denominator <= 0:
            continue
        price = numerator / denominator
        if price <= 0:
            continue
        liquidation_value = price * qty
        if _tier_band_contains(ordered, index, liquidation_value):
            candidates.append((price, tier, liquidation_value))

    if len(candidates) != 1:
        raise ValueError(
            f"{symbol} could not resolve a unique liquidation tier "
            f"from candidate notional (matches={len(candidates)})"
        )
    price, tier, value = candidates[0]
    return IsolatedLiquidationEstimate(
        direction=side,
        liquidation_price=price,
        liquidation_position_value=value,
        tier_id=tier.tier_id,
        maintenance_margin_rate=tier.maintenance_margin_rate,
        mm_deduction=tier.mm_deduction,
        leverage=lev,
        extra_margin=margin,
    )
