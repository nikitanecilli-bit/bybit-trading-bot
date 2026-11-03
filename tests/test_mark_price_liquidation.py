"""Deterministic tests for Bybit isolated USDT-linear liquidation estimates."""
from decimal import Decimal

import pytest

from bybit_risk_tiers import RiskTier
from mark_price_liquidation import calculate_isolated_usdt_liquidation_price


def tier(tier_id, limit, mmr, max_lev, deduction="0"):
    return RiskTier(
        symbol="BTCUSDT", tier_id=tier_id,
        risk_limit_value=Decimal(limit),
        maintenance_margin_rate=Decimal(mmr),
        initial_margin_rate=Decimal("0.01"),
        max_leverage=Decimal(max_lev),
        mm_deduction=Decimal(deduction),
        is_lowest_risk=(tier_id == 1),
    )


def test_bybit_published_isolated_long_example():
    result = calculate_isolated_usdt_liquidation_price(
        symbol="BTCUSDT", direction="long", entry_price="40000",
        quantity="1", leverage="50",
        tiers=[tier(1, "1000000", "0.005", "100")],
        taker_fee_rate="0.00055", extra_margin="3000",
    )
    assert result.liquidation_price.quantize(Decimal("0.01")) == Decimal("36380.25")


def test_long_and_short_prices_are_on_adverse_sides_of_entry():
    tiers = [tier(1, "1000000", "0.005", "100")]
    long = calculate_isolated_usdt_liquidation_price(
        symbol="BTCUSDT", direction="long", entry_price="40000",
        quantity="1", leverage="10", tiers=tiers,
    )
    short = calculate_isolated_usdt_liquidation_price(
        symbol="BTCUSDT", direction="short", entry_price="40000",
        quantity="1", leverage="10", tiers=tiers,
    )
    assert long.liquidation_price < Decimal("40000")
    assert short.liquidation_price > Decimal("40000")


def test_candidate_liquidation_notional_selects_its_own_tier():
    tiers = [
        tier(1, "100000", "0.005", "100"),
        tier(2, "500000", "0.01", "50", "500"),
    ]
    result = calculate_isolated_usdt_liquidation_price(
        symbol="BTCUSDT", direction="long", entry_price="120000",
        quantity="1", leverage="10", tiers=tiers,
    )
    assert result.tier_id == 2
    assert Decimal("100000") < result.liquidation_position_value <= Decimal("500000")


def test_rejects_entry_over_highest_risk_limit():
    with pytest.raises(ValueError, match="entry notional exceeds"):
        calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="long", entry_price="600000",
            quantity="1", leverage="10",
            tiers=[tier(1, "500000", "0.005", "100")],
        )


def test_rejects_leverage_above_entry_tier_limit():
    with pytest.raises(ValueError, match="entry tier maxLeverage"):
        calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="long", entry_price="120000",
            quantity="1", leverage="60",
            tiers=[
                tier(1, "100000", "0.005", "100"),
                tier(2, "500000", "0.01", "50", "500"),
            ],
        )


def test_rejects_invalid_inputs_and_unresolved_tier():
    tiers = [tier(1, "1000000", "0.005", "100")]
    with pytest.raises(ValueError, match="direction"):
        calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="flat", entry_price="100",
            quantity="1", leverage="10", tiers=tiers,
        )
    with pytest.raises(ValueError, match="fee"):
        calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="long", entry_price="100",
            quantity="1", leverage="10", tiers=tiers, taker_fee_rate="1",
        )
    with pytest.raises(ValueError, match="unique"):
        calculate_isolated_usdt_liquidation_price(
            symbol="BTCUSDT", direction="long", entry_price="100",
            quantity="1", leverage="10",
            tiers=[tier(1, "1000", "0.005", "100"), tier(2, "1000", "0.01", "50")],
        )
