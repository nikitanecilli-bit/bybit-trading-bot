"""Point-in-time Bybit linear risk-tier selection; no live or account-margin assumptions."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def _d(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"invalid {field}")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite {field}")
    return result


def _timestamp_ms(value: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid risk-tier fetched_at: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("risk-tier fetched_at must include timezone")
    if parsed.microsecond % 1000:
        raise ValueError("risk-tier fetched_at must have millisecond precision")
    normalized = parsed.astimezone(timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = normalized - epoch
    return ((delta.days * 86_400 + delta.seconds) * 1000
            + delta.microseconds // 1000)


def _as_of_ms(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("as_of_ts must be an integer millisecond timestamp")
    return value


@dataclass(frozen=True)
class RiskTier:
    symbol: str
    tier_id: int
    risk_limit_value: Decimal
    maintenance_margin_rate: Decimal
    initial_margin_rate: Decimal
    max_leverage: Decimal
    mm_deduction: Decimal
    is_lowest_risk: bool


@dataclass(frozen=True)
class RiskMarginRequirement:
    position_value: Decimal
    leverage: Decimal
    max_leverage: Decimal
    initial_margin: Decimal
    maintenance_margin: Decimal
    tier_id: int
    risk_limit_value: Decimal
    maintenance_margin_rate: Decimal
    mm_deduction: Decimal


@dataclass(frozen=True)
class RiskTierSnapshot:
    fetched_at: str
    fetched_at_ms: int
    category: str
    tiers_by_symbol: dict[str, tuple[RiskTier, ...]]


def calculate_margin_requirements_from_tiers(
    symbol: str, position_value: Decimal | str | float,
    *, leverage: Decimal | str | float, tiers: tuple[RiskTier, ...],
) -> RiskMarginRequirement:
    """Calculate IM/MM from a risk-tier ladder already selected by a joined as-of state."""
    value = _d(position_value, "position_value")
    lev = _d(leverage, "leverage")
    if value <= 0 or lev <= 0:
        raise ValueError("position_value and leverage must be > 0")
    if not tiers:
        raise ValueError(f"{symbol} has no joined risk tiers")
    tier = next((item for item in tiers if value <= item.risk_limit_value), None)
    if tier is None:
        raise ValueError(f"{symbol} position value exceeds highest riskLimitValue")
    if lev > tier.max_leverage:
        raise ValueError(
            f"{symbol} leverage {lev} exceeds tier {tier.tier_id} maxLeverage {tier.max_leverage}"
        )
    initial_margin = value / lev
    maintenance_margin = value * tier.maintenance_margin_rate - tier.mm_deduction
    if initial_margin <= 0 or maintenance_margin < 0:
        raise ValueError(f"{symbol} tier {tier.tier_id} produced invalid IM/MM requirement")
    return RiskMarginRequirement(
        position_value=value, leverage=lev, max_leverage=tier.max_leverage,
        initial_margin=initial_margin, maintenance_margin=maintenance_margin,
        tier_id=tier.tier_id, risk_limit_value=tier.risk_limit_value,
        maintenance_margin_rate=tier.maintenance_margin_rate,
        mm_deduction=tier.mm_deduction,
    )


class RiskTierHistory:
    """Loads archived Bybit V5 risk-limit pages and performs as-of tier selection."""

    def __init__(self, snapshots: list[RiskTierSnapshot]):
        if not snapshots:
            raise ValueError("no risk-tier snapshots loaded")
        ordered = sorted(snapshots, key=lambda item: item.fetched_at_ms)
        stamps = [item.fetched_at_ms for item in ordered]
        if len(stamps) != len(set(stamps)):
            raise ValueError("duplicate risk-tier snapshot timestamps")
        if any(item.category != "linear" for item in ordered):
            raise ValueError("RiskTierHistory only supports linear contracts")
        if len({item.category for item in ordered}) != 1:
            raise ValueError("risk-tier snapshot categories cannot be mixed")
        self.snapshots = ordered
        self.category = ordered[0].category

    @classmethod
    def from_directory(cls, directory: str | Path, category: str = "linear"):
        root = Path(directory)
        if not root.is_dir():
            raise ValueError(f"risk-tier directory does not exist: {root}")
        snapshots = []
        for path in sorted(root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"{path}: cannot read risk-tier snapshot") from exc
            if (not isinstance(payload, dict)
                    or isinstance(payload.get("schema_version"), bool)
                    or not isinstance(payload.get("schema_version"), int)
                    or payload.get("schema_version") != 1):
                raise ValueError(f"{path}: unsupported risk-tier schema")
            if payload.get("source") != "Bybit V5 GET /v5/market/risk-limit":
                raise ValueError(f"{path}: invalid or missing Bybit risk-limit source")
            if payload.get("category") != category:
                raise ValueError(f"{path}: expected {category} category")
            fetched_at = str(payload.get("fetched_at") or "")
            fetched_at_ms = _timestamp_ms(fetched_at)
            rows = payload.get("tiers")
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"{path}: tiers must be a non-empty list")
            if (isinstance(payload.get("tier_count"), bool)
                    or not isinstance(payload.get("tier_count"), int)
                    or payload.get("tier_count") != len(rows)):
                raise ValueError(f"{path}: tier_count does not match rows")
            grouped: dict[str, list[RiskTier]] = {}
            seen: set[tuple[str, int]] = set()
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"{path}: tier row must be an object")
                symbol = str(row.get("symbol") or "").strip().upper()
                tier_id = row.get("id")
                if not symbol or isinstance(tier_id, bool) or not isinstance(tier_id, int) or tier_id <= 0:
                    raise ValueError(f"{path}: invalid symbol or tier id")
                key = (symbol, tier_id)
                if key in seen:
                    raise ValueError(f"{path}: duplicate tier {key}")
                seen.add(key)
                lowest = row.get("isLowestRisk")
                if isinstance(lowest, bool) or not isinstance(lowest, int) or lowest not in (0, 1):
                    raise ValueError(f"{path}: isLowestRisk must be integer 0 or 1")
                deduction_raw = row.get("mmDeduction")
                if deduction_raw in (None, "") and lowest != 1:
                    raise ValueError(f"{path}: missing mmDeduction for non-lowest tier {symbol}")
                risk_limit = _d(row.get("riskLimitValue"), "riskLimitValue")
                mmr = _d(row.get("maintenanceMargin"), "maintenanceMargin")
                imr = _d(row.get("initialMargin"), "initialMargin")
                max_lev = _d(row.get("maxLeverage"), "maxLeverage")
                deduction = _d("0" if deduction_raw in (None, "") else deduction_raw, "mmDeduction")
                if min(risk_limit, mmr, imr, max_lev) <= 0 or deduction < 0:
                    raise ValueError(f"{path}: risk tier values outside valid range")
                grouped.setdefault(symbol, []).append(RiskTier(
                    symbol, tier_id, risk_limit, mmr, imr, max_lev, deduction, bool(lowest)
                ))
            final: dict[str, tuple[RiskTier, ...]] = {}
            for symbol, tiers in grouped.items():
                tiers.sort(key=lambda item: item.risk_limit_value)
                if len({item.risk_limit_value for item in tiers}) != len(tiers):
                    raise ValueError(f"{path}: duplicate risk limit for {symbol}")
                if sum(1 for item in tiers if item.is_lowest_risk) != 1 or not tiers[0].is_lowest_risk:
                    raise ValueError(f"{path}: exactly the lowest tier must have isLowestRisk=1 for {symbol}")
                for i, tier in enumerate(tiers):
                    if i == 0:
                        continue
                    prev = tiers[i - 1]
                    if tier.risk_limit_value <= prev.risk_limit_value:
                        raise ValueError(f"{path}: risk limits not increasing for {symbol}")
                    if tier.maintenance_margin_rate < prev.maintenance_margin_rate:
                        raise ValueError(f"{path}: MMR decreases for {symbol}")
                    if tier.initial_margin_rate < prev.initial_margin_rate:
                        raise ValueError(f"{path}: IMR decreases for {symbol}")
                    if tier.max_leverage > prev.max_leverage:
                        raise ValueError(f"{path}: max leverage increases for {symbol}")
                    expected = prev.risk_limit_value * (tier.maintenance_margin_rate - prev.maintenance_margin_rate) + prev.mm_deduction
                    if abs(tier.mm_deduction - expected) > Decimal("0.00000001"):
                        raise ValueError(f"{path}: mmDeduction recurrence mismatch for {symbol} tier {tier.tier_id}")
                final[symbol] = tuple(tiers)
            snapshots.append(RiskTierSnapshot(fetched_at, fetched_at_ms, category, final))
        return cls(snapshots)

    def get_tiers(self, symbol: str, as_of_ts: int, *, max_age_ms: int | None = None) -> tuple[RiskTier, ...]:
        """Return the symbol's complete point-in-time tier ladder.

        Unlike get_tier(), this does not apply a leverage constraint: existing
        positions must continue to be evaluated for maintenance-margin shortfall
        if Mark Price moves them into a tier whose maxLeverage is below their
        historical entry leverage.
        """
        timestamp = _as_of_ms(as_of_ts)
        eligible = [item for item in self.snapshots if item.fetched_at_ms <= timestamp]
        if not eligible:
            raise ValueError(f"no {self.category} risk-tier snapshot at or before {timestamp}")
        selected = eligible[-1]
        age = timestamp - selected.fetched_at_ms
        if max_age_ms is not None:
            if max_age_ms < 0:
                raise ValueError("max_age_ms cannot be negative")
            if age > max_age_ms:
                raise ValueError(f"risk-tier snapshot is stale: age_ms={age}, max_age_ms={max_age_ms}")
        tiers = selected.tiers_by_symbol.get(symbol.strip().upper())
        if not tiers:
            raise ValueError(f"{symbol} absent from dated risk-tier snapshot")
        return tiers

    def get_tier(self, symbol: str, as_of_ts: int, position_value: Decimal | str | float,
                 *, leverage: Decimal | str | float, max_age_ms: int | None = None) -> RiskTier:
        timestamp = _as_of_ms(as_of_ts)
        value = _d(position_value, "position_value")
        lev = _d(leverage, "leverage")
        if value <= 0 or lev <= 0:
            raise ValueError("position_value and leverage must be > 0")
        eligible = [item for item in self.snapshots if item.fetched_at_ms <= timestamp]
        if not eligible:
            raise ValueError(f"no {self.category} risk-tier snapshot at or before {timestamp}")
        selected = eligible[-1]
        age = timestamp - selected.fetched_at_ms
        if max_age_ms is not None:
            if max_age_ms < 0:
                raise ValueError("max_age_ms cannot be negative")
            if age > max_age_ms:
                raise ValueError(f"risk-tier snapshot is stale: age_ms={age}, max_age_ms={max_age_ms}")
        tiers = selected.tiers_by_symbol.get(symbol.strip().upper())
        if not tiers:
            raise ValueError(f"{symbol} absent from dated risk-tier snapshot")
        tier = next((item for item in tiers if value <= item.risk_limit_value), None)
        if tier is None:
            raise ValueError(f"{symbol} position value exceeds highest riskLimitValue")
        if lev > tier.max_leverage:
            raise ValueError(
                f"{symbol} leverage {lev} exceeds tier {tier.tier_id} maxLeverage {tier.max_leverage}"
            )
        return tier

    def calculate_margin_requirements(
        self, symbol: str, as_of_ts: int, position_value: Decimal | str | float,
        *, leverage: Decimal | str | float, max_age_ms: int | None = None,
    ) -> RiskMarginRequirement:
        """Calculate position-level USDT IM/MM from the selected dated risk tier.

        IM is position value / configured leverage. MM follows Bybit's published
        linear formula: position value * MMR - mmDeduction. This is not an
        account-level solvency or liquidation-price calculation.
        """
        value = _d(position_value, "position_value")
        lev = _d(leverage, "leverage")
        tier = self.get_tier(
            symbol, as_of_ts, value, leverage=lev, max_age_ms=max_age_ms
        )
        initial_margin = value / lev
        maintenance_margin = value * tier.maintenance_margin_rate - tier.mm_deduction
        if initial_margin <= 0 or maintenance_margin < 0:
            raise ValueError(
                f"{symbol} tier {tier.tier_id} produced invalid IM/MM requirement"
            )
        return RiskMarginRequirement(
            position_value=value,
            leverage=lev,
            max_leverage=tier.max_leverage,
            initial_margin=initial_margin,
            maintenance_margin=maintenance_margin,
            tier_id=tier.tier_id,
            risk_limit_value=tier.risk_limit_value,
            maintenance_margin_rate=tier.maintenance_margin_rate,
            mm_deduction=tier.mm_deduction,
        )
