"""Typed, fail-closed exchange execution identity records.

Pure data contracts only: no HTTP, credentials, order placement, or qty inference.
All quantities/prices are decimal strings to preserve exchange precision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


class ExecutionIdentityError(ValueError):
    """Exchange execution identity is incomplete, invalid, or ambiguous."""


def _text(value: Any, field: str, *, optional: bool = False) -> str:
    if optional and value == "":
        return ""
    if not isinstance(value, str) or not value.strip():
        raise ExecutionIdentityError(f"{field} must be a non-empty string")
    return value


def _decimal_text(value: Any, field: str, *, positive: bool = False,
                  nonnegative: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionIdentityError(f"{field} must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ExecutionIdentityError(f"{field} must be a decimal string") from exc
    if not parsed.is_finite():
        raise ExecutionIdentityError(f"{field} must be finite")
    if positive and parsed <= 0:
        raise ExecutionIdentityError(f"{field} must be > 0")
    if nonnegative and parsed < 0:
        raise ExecutionIdentityError(f"{field} must be >= 0")
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ExecutionIdentityError(f"{field} must be an integer >= {minimum}")
    return value


@dataclass(frozen=True)
class ExchangePositionIdentity:
    category: str
    settle_coin: str
    symbol: str
    position_idx: int
    position_mode: str
    side: str
    qty: str
    avg_price: str
    entry_order_id: str
    entry_order_link_id: str = ""

    def __post_init__(self) -> None:
        if self.category != "linear":
            raise ExecutionIdentityError("category must be linear")
        _text(self.settle_coin, "settle_coin")
        _text(self.symbol, "symbol")
        _integer(self.position_idx, "position_idx")
        if self.position_idx not in (0, 1, 2):
            raise ExecutionIdentityError("position_idx must be 0, 1, or 2")
        if self.position_mode not in ("one_way", "hedge"):
            raise ExecutionIdentityError("position_mode must be one_way or hedge")
        if (self.position_mode == "one_way") != (self.position_idx == 0):
            raise ExecutionIdentityError("position_mode conflicts with position_idx")
        if self.side not in ("Buy", "Sell"):
            raise ExecutionIdentityError("side must be Buy or Sell")
        _decimal_text(self.qty, "qty", positive=True)
        _decimal_text(self.avg_price, "avg_price", positive=True)
        _text(self.entry_order_id, "entry_order_id")
        _text(self.entry_order_link_id, "entry_order_link_id", optional=True)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExchangePositionIdentity":
        if not isinstance(value, Mapping):
            raise ExecutionIdentityError("position identity must be an object")
        expected = set(cls.__dataclass_fields__)
        if set(value) != expected:
            raise ExecutionIdentityError(
                f"position identity fields mismatch: missing={sorted(expected-set(value))}, "
                f"unknown={sorted(set(value)-expected)}"
            )
        return cls(**dict(value))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExchangeExecutionIdentity:
    exec_id: str
    order_id: str
    order_link_id: str
    symbol: str
    side: str
    exec_qty: str
    exec_price: str
    exec_time_ms: int
    exec_fee: str | None = None

    def __post_init__(self) -> None:
        for field in ("exec_id", "order_id", "symbol"):
            _text(getattr(self, field), field)
        _text(self.order_link_id, "order_link_id", optional=True)
        if self.side not in ("Buy", "Sell"):
            raise ExecutionIdentityError("side must be Buy or Sell")
        _decimal_text(self.exec_qty, "exec_qty", positive=True)
        _decimal_text(self.exec_price, "exec_price", positive=True)
        _integer(self.exec_time_ms, "exec_time_ms", minimum=1)
        if self.exec_fee is not None:
            _decimal_text(self.exec_fee, "exec_fee")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExchangeExecutionIdentity":
        if not isinstance(value, Mapping):
            raise ExecutionIdentityError("execution identity must be an object")
        expected = set(cls.__dataclass_fields__)
        if set(value) != expected:
            raise ExecutionIdentityError(
                f"execution identity fields mismatch: missing={sorted(expected-set(value))}, "
                f"unknown={sorted(set(value)-expected)}"
            )
        return cls(**dict(value))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExchangeExecutionCoverage:
    """Caller-attested, half-open execution-history query window [start, end)."""
    coverage_id: str
    symbol: str
    window_start_ms: int
    window_end_ms: int
    page_count: int
    pagination_complete: bool
    terminal_page_seen: bool

    def __post_init__(self) -> None:
        _text(self.coverage_id, "coverage_id")
        _text(self.symbol, "symbol")
        _integer(self.window_start_ms, "window_start_ms", minimum=1)
        _integer(self.window_end_ms, "window_end_ms", minimum=1)
        if self.window_end_ms <= self.window_start_ms:
            raise ExecutionIdentityError("coverage window_end_ms must exceed window_start_ms")
        _integer(self.page_count, "page_count", minimum=1)
        if not isinstance(self.pagination_complete, bool) or not isinstance(self.terminal_page_seen, bool):
            raise ExecutionIdentityError("coverage pagination flags must be booleans")
        if self.pagination_complete and not self.terminal_page_seen:
            raise ExecutionIdentityError("complete pagination requires terminal page observation")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExchangeExecutionCoverage":
        if not isinstance(value, Mapping):
            raise ExecutionIdentityError("execution coverage must be an object")
        expected = set(cls.__dataclass_fields__)
        if set(value) != expected:
            raise ExecutionIdentityError(
                f"execution coverage fields mismatch: missing={sorted(expected-set(value))}, "
                f"unknown={sorted(set(value)-expected)}"
            )
        return cls(**dict(value))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExchangeOrderIdentity:
    order_id: str
    order_link_id: str
    symbol: str
    side: str
    position_idx: int
    qty: str
    leaves_qty: str
    cum_exec_qty: str
    order_status: str
    reduce_only: bool
    close_on_trigger: bool
    trigger_price: str | None = None

    def __post_init__(self) -> None:
        for field in ("order_id", "symbol", "order_status"):
            _text(getattr(self, field), field)
        _text(self.order_link_id, "order_link_id", optional=True)
        if self.side not in ("Buy", "Sell"):
            raise ExecutionIdentityError("side must be Buy or Sell")
        _integer(self.position_idx, "position_idx")
        if self.position_idx not in (0, 1, 2):
            raise ExecutionIdentityError("position_idx must be 0, 1, or 2")
        qty = Decimal(_decimal_text(self.qty, "qty", positive=True))
        leaves = Decimal(_decimal_text(self.leaves_qty, "leaves_qty", nonnegative=True))
        cumulative = Decimal(_decimal_text(self.cum_exec_qty, "cum_exec_qty", nonnegative=True))
        if leaves > qty or cumulative > qty or leaves + cumulative > qty:
            raise ExecutionIdentityError("order quantities are inconsistent")
        if not isinstance(self.reduce_only, bool) or not isinstance(self.close_on_trigger, bool):
            raise ExecutionIdentityError("reduce_only and close_on_trigger must be booleans")
        if self.trigger_price is not None:
            _decimal_text(self.trigger_price, "trigger_price", positive=True)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExchangeOrderIdentity":
        if not isinstance(value, Mapping):
            raise ExecutionIdentityError("order identity must be an object")
        expected = set(cls.__dataclass_fields__)
        if set(value) != expected:
            raise ExecutionIdentityError(
                f"order identity fields mismatch: missing={sorted(expected-set(value))}, "
                f"unknown={sorted(set(value)-expected)}"
            )
        return cls(**dict(value))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
