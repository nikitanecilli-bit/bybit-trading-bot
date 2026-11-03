"""Position-level Bybit USDT-linear isolated liquidation and mark-MM estimates.

This is not an account-level cross/portfolio margin or liquidation-engine model.
The liquidation price uses the position's tier at entry. Current maintenance
margin uses the tier selected at current Mark Price for this single position.
Bybit may aggregate positions/orders when determining account risk tiers; that
aggregation is outside this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
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


def _ordered_tiers(symbol: str, tiers: Iterable[RiskTier]) -> tuple[RiskTier, ...]:
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
    return ordered


def _select_tier(ordered: tuple[RiskTier, ...], position_value: Decimal) -> RiskTier:
    tier = next((item for item in ordered if position_value <= item.risk_limit_value), None)
    if tier is None:
        raise ValueError("position value exceeds highest riskLimitValue")
    return tier


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


@dataclass(frozen=True)
class MarkPriceMaintenanceMargin:
    mark_price: Decimal
    position_value: Decimal
    maintenance_margin: Decimal
    estimated_close_fee: Decimal
    tier_id: int
    maintenance_margin_rate: Decimal
    mm_deduction: Decimal


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
    """Calculate the published isolated LP using the entry-selected risk tier.

    Bybit's published formula treats LP as fixed for an unchanged position.
    Tier selection here is therefore based on entry notional, not candidate LP
    notional. Dynamic Mark-Price maintenance-margin tiering is separate.
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

    ordered = _ordered_tiers(symbol, tiers)
    entry_value = entry * qty
    tier = _select_tier(ordered, entry_value)
    if lev > tier.max_leverage:
        raise ValueError(f"{symbol} leverage exceeds entry tier maxLeverage")

    mmr = tier.maintenance_margin_rate
    deduction = tier.mm_deduction
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
        raise ValueError("selected risk tier produces a non-positive liquidation denominator")
    price = numerator / denominator
    if price <= 0:
        raise ValueError("selected risk tier produces a non-positive liquidation price")

    return IsolatedLiquidationEstimate(
        direction=side,
        liquidation_price=price,
        liquidation_position_value=price * qty,
        tier_id=tier.tier_id,
        maintenance_margin_rate=mmr,
        mm_deduction=deduction,
        leverage=lev,
        extra_margin=margin,
    )


def calculate_mark_price_maintenance_margin(
    *,
    symbol: str,
    direction: str,
    entry_price,
    mark_price,
    quantity,
    leverage,
    tiers: Iterable[RiskTier],
    taker_fee_rate="0.00055",
) -> MarkPriceMaintenanceMargin:
    """Calculate single-position MM using the tier selected at current Mark Price.

    Uses Bybit's current USDT-linear isolated MM components:
    mark notional * MMR - mmDeduction + estimated close fee. The estimated
    close fee is based on entry price and leverage. This function does not
    aggregate other positions or active orders into the risk tier, and does not
    compare MM with position margin balance to decide whether liquidation fires.
    """
    side = str(direction).strip().lower()
    if side not in {"long", "short"}:
        raise ValueError("direction must be 'long' or 'short'")
    entry = _d(entry_price, "entry_price")
    mark = _d(mark_price, "mark_price")
    qty = _d(quantity, "quantity")
    lev = _d(leverage, "leverage")
    fee = _d(taker_fee_rate, "taker_fee_rate")
    if min(entry, mark, qty, lev) <= 0 or fee < 0 or fee >= 1:
        raise ValueError("prices, quantity and leverage must be positive; fee in [0,1)")

    ordered = _ordered_tiers(symbol, tiers)
    position_value = mark * qty
    tier = _select_tier(ordered, position_value)
    if lev > tier.max_leverage:
        raise ValueError(f"{symbol} leverage exceeds Mark-Price tier maxLeverage")

    fee_factor = Decimal("1") - Decimal("1") / lev if side == "long" else Decimal("1") + Decimal("1") / lev
    close_fee = qty * entry * fee_factor * fee
    maintenance = position_value * tier.maintenance_margin_rate - tier.mm_deduction + close_fee
    if maintenance < 0:
        raise ValueError("selected tier produces negative maintenance margin")
    return MarkPriceMaintenanceMargin(
        mark_price=mark,
        position_value=position_value,
        maintenance_margin=maintenance,
        estimated_close_fee=close_fee,
        tier_id=tier.tier_id,
        maintenance_margin_rate=tier.maintenance_margin_rate,
        mm_deduction=tier.mm_deduction,
    )



@dataclass(frozen=True)
class IsolatedMarginHealth:
    position_margin_balance: Decimal
    maintenance_margin: Decimal
    margin_surplus: Decimal
    liquidation_triggered: bool
    unrealized_pnl: Decimal
    funding_net_cost: Decimal
    tier_id: int


def evaluate_isolated_margin_health(
    *,
    symbol: str,
    direction: str,
    entry_price,
    mark_price,
    quantity,
    leverage,
    tiers: Iterable[RiskTier],
    taker_fee_rate="0.00055",
    extra_margin="0",
    funding_net_cost="0",
) -> IsolatedMarginHealth:
    """Evaluate one isolated USDT-linear position against current Mark-Price MM.

    Funding net cost is positive when paid/debited from position margin and
    negative when received/credited. Extra margin is the amount currently
    allocated to the remaining position (caller must update it after partial
    closes or manual margin changes). Realized PnL from partial closes is not
    implicitly transferred into remaining position margin.

    Position margin balance = entry-based initial margin (including estimated
    close fee) + allocated extra margin + unrealized PnL - net funding cost.
    Liquidation trigger is margin balance <= Mark-Price maintenance margin.
    This is position-level isolated approximation; account/order tier
    aggregation, actual funding transfer timestamps, AMR and exchange rounding
    are not modeled.
    """
    side = str(direction).strip().lower()
    if side not in {"long", "short"}:
        raise ValueError("direction must be 'long' or 'short'")
    entry = _d(entry_price, "entry_price")
    mark = _d(mark_price, "mark_price")
    qty = _d(quantity, "quantity")
    lev = _d(leverage, "leverage")
    fee = _d(taker_fee_rate, "taker_fee_rate")
    extra = _d(extra_margin, "extra_margin")
    funding = _d(funding_net_cost, "funding_net_cost")
    if min(entry, mark, qty, lev) <= 0 or fee < 0 or fee >= 1 or extra < 0:
        raise ValueError("prices, quantity and leverage must be positive; fee in [0,1); extra margin non-negative")

    margin_req = calculate_mark_price_maintenance_margin(
        symbol=symbol, direction=side, entry_price=entry, mark_price=mark,
        quantity=qty, leverage=lev, tiers=tiers, taker_fee_rate=fee,
    )
    entry_notional = entry * qty
    close_fee = margin_req.estimated_close_fee
    initial_margin = entry_notional / lev + close_fee
    unrealized = (mark - entry) * qty if side == "long" else (entry - mark) * qty
    balance = initial_margin + extra + unrealized - funding
    surplus = balance - margin_req.maintenance_margin
    return IsolatedMarginHealth(
        position_margin_balance=balance,
        maintenance_margin=margin_req.maintenance_margin,
        margin_surplus=surplus,
        liquidation_triggered=surplus <= 0,
        unrealized_pnl=unrealized,
        funding_net_cost=funding,
        tier_id=margin_req.tier_id,
    )

def mark_candle_crosses_liquidation(
    *, direction: str, liquidation_price, mark_low, mark_high
) -> bool:
    """Return whether a Mark-Price candle crossed the fixed isolated LP.

    This detects only a crossing of the fixed LP. A dynamic Mark-Price tier
    upgrade may raise MM and cause liquidation before this LP is touched; that
    separate margin-balance condition is not evaluated here. It also does not
    infer intrabar ordering against a trade-price stop or model settlement.
    """
    side = str(direction).strip().lower()
    if side not in {"long", "short"}:
        raise ValueError("direction must be 'long' or 'short'")
    lp = _d(liquidation_price, "liquidation_price")
    low = _d(mark_low, "mark_low")
    high = _d(mark_high, "mark_high")
    if min(lp, low, high) <= 0 or high < low:
        raise ValueError("liquidation price and Mark-Price OHLC bounds must be positive and ordered")
    return low <= lp if side == "long" else high >= lp


def calculate_isolated_usdt_bankruptcy_price(
    *, direction: str, entry_price, leverage, tick_size=None
) -> Decimal:
    """Calculate isolated USDT bankruptcy price (no extra-margin adjustment).

    Bybit documents long bankruptcy price as entry*(1 - 1/leverage) and short
    as entry*(1 + 1/leverage). When tick_size is supplied, long rounds up and
    short rounds down to the exchange tick. This helper assumes no extra margin
    was manually added and does not model fees/funding altering effective IM.
    """
    side = str(direction).strip().lower()
    if side not in {"long", "short"}:
        raise ValueError("direction must be 'long' or 'short'")
    entry = _d(entry_price, "entry_price")
    lev = _d(leverage, "leverage")
    if entry <= 0 or lev <= 0:
        raise ValueError("entry_price and leverage must be positive")
    price = entry * (Decimal("1") - Decimal("1") / lev if side == "long"
                     else Decimal("1") + Decimal("1") / lev)
    if price <= 0:
        raise ValueError("bankruptcy price must be positive")
    if tick_size is not None:
        tick = _d(tick_size, "tick_size")
        if tick <= 0:
            raise ValueError("tick_size must be positive")
        rounding = ROUND_CEILING if side == "long" else ROUND_FLOOR
        price = (price / tick).to_integral_value(rounding=rounding) * tick
    return price
