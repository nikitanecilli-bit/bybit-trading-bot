"""Strict, read-only parsers for Bybit V5 reconciliation snapshots.

This module performs no network calls and has no trading side effects.
It parses complete, caller-supplied paginated response captures only.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence


class SnapshotValidationError(ValueError):
    """Raised when an exchange snapshot is invalid, incomplete, or ambiguous."""


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    position_idx: int
    side: str
    size: Decimal
    avg_price: Decimal
    updated_time_ms: int
    position_status: str


@dataclass(frozen=True)
class ActiveOrderSnapshot:
    order_id: str
    order_link_id: str
    symbol: str
    side: str
    qty: Decimal
    leaves_qty: Decimal
    cum_exec_qty: Decimal
    order_status: str
    created_time_ms: int
    updated_time_ms: int
    position_idx: int | None


@dataclass(frozen=True)
class ExecutionSnapshot:
    exec_id: str
    order_id: str
    order_link_id: str
    symbol: str
    exec_type: str
    exec_time_ms: int
    side: str | None
    exec_qty: Decimal | None
    exec_price: Decimal | None
    exec_fee: Decimal | None


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotValidationError(f"{field} must be a non-empty string")
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise SnapshotValidationError(f"{field} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SnapshotValidationError(f"{field} must be an integer") from exc
    if isinstance(value, float) and not value.is_integer():
        raise SnapshotValidationError(f"{field} must be an integer")
    if isinstance(value, str) and str(parsed) != value.strip():
        raise SnapshotValidationError(f"{field} must be an integer string")
    if parsed < minimum:
        raise SnapshotValidationError(f"{field} must be >= {minimum}")
    return parsed


def _decimal(value: Any, field: str, *, minimum: Decimal | None = None,
             allow_empty: bool = False) -> Decimal | None:
    if allow_empty and value in (None, ""):
        return None
    if isinstance(value, bool):
        raise SnapshotValidationError(f"{field} must be a decimal")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SnapshotValidationError(f"{field} must be a decimal") from exc
    if not parsed.is_finite():
        raise SnapshotValidationError(f"{field} must be finite")
    if minimum is not None and parsed < minimum:
        raise SnapshotValidationError(f"{field} must be >= {minimum}")
    return parsed


def _response_page(payload: Mapping[str, Any], requested_cursor: str,
                   expected_cursor: str) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(payload, Mapping):
        raise SnapshotValidationError("response page must be an object")
    if requested_cursor != expected_cursor:
        raise SnapshotValidationError("pagination cursor chain is discontinuous")
    ret_code = payload.get("retCode")
    if isinstance(ret_code, bool) or not isinstance(ret_code, int) or ret_code != 0:
        raise SnapshotValidationError(f"Bybit retCode is not integer zero: {ret_code!r}")
    result = payload.get("result")
    if not isinstance(result, Mapping):
        raise SnapshotValidationError("response result must be an object")
    rows = result.get("list")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise SnapshotValidationError("response result.list must be a list of objects")
    cursor = result.get("nextPageCursor", "")
    if not isinstance(cursor, str):
        raise SnapshotValidationError("nextPageCursor must be a string")
    return [dict(row) for row in rows], cursor


def _collect_complete_pages(pages: Iterable[tuple[str, Mapping[str, Any]]]) -> list[dict[str, Any]]:
    page_list = list(pages)
    if not page_list:
        raise SnapshotValidationError("snapshot has no response pages")
    expected_cursor = ""
    seen_cursors: set[str] = set()
    all_rows: list[dict[str, Any]] = []
    for index, (requested_cursor, payload) in enumerate(page_list):
        rows, next_cursor = _response_page(payload, requested_cursor, expected_cursor)
        all_rows.extend(rows)
        if next_cursor:
            if next_cursor in seen_cursors:
                raise SnapshotValidationError("pagination cursor repeated; refusing ambiguous snapshot")
            seen_cursors.add(next_cursor)
            if index == len(page_list) - 1:
                raise SnapshotValidationError("snapshot pagination is incomplete")
        elif index != len(page_list) - 1:
            raise SnapshotValidationError("unexpected page after pagination completed")
        expected_cursor = next_cursor
    if expected_cursor:
        raise SnapshotValidationError("snapshot pagination is incomplete")
    return all_rows


def parse_position_pages(
    pages: Iterable[tuple[str, Mapping[str, Any]]],
) -> tuple[PositionSnapshot, ...]:
    rows = _collect_complete_pages(pages)
    parsed: list[PositionSnapshot] = []
    seen: set[tuple[str, int]] = set()
    for row in rows:
        symbol = _nonempty_string(row.get("symbol"), "position.symbol").upper()
        idx = _integer(row.get("positionIdx"), "position.positionIdx")
        if idx not in (0, 1, 2):
            raise SnapshotValidationError("position.positionIdx must be 0, 1, or 2")
        size = _decimal(row.get("size"), "position.size", minimum=Decimal("0"))
        if size == 0:
            # Bybit may return an empty row when querying a specific symbol.
            continue
        side = _nonempty_string(row.get("side"), "position.side")
        if side not in ("Buy", "Sell"):
            raise SnapshotValidationError("open position side must be Buy or Sell")
        avg_price = _decimal(row.get("avgPrice"), "position.avgPrice", minimum=Decimal("0"))
        if avg_price == 0:
            raise SnapshotValidationError("open position avgPrice must be > 0")
        updated = _integer(row.get("updatedTime"), "position.updatedTime", minimum=1)
        status = _nonempty_string(row.get("positionStatus"), "position.positionStatus")
        key = (symbol, idx)
        if key in seen:
            raise SnapshotValidationError(f"duplicate position identity: {key}")
        seen.add(key)
        parsed.append(PositionSnapshot(symbol, idx, side, size, avg_price, updated, status))
    return tuple(sorted(parsed, key=lambda item: (item.symbol, item.position_idx)))


def parse_active_order_pages(
    pages: Iterable[tuple[str, Mapping[str, Any]]],
) -> tuple[ActiveOrderSnapshot, ...]:
    rows = _collect_complete_pages(pages)
    parsed: list[ActiveOrderSnapshot] = []
    seen: set[str] = set()
    for row in rows:
        order_id = _nonempty_string(row.get("orderId"), "order.orderId")
        if order_id in seen:
            raise SnapshotValidationError(f"duplicate orderId: {order_id}")
        seen.add(order_id)
        symbol = _nonempty_string(row.get("symbol"), "order.symbol").upper()
        side = _nonempty_string(row.get("side"), "order.side")
        if side not in ("Buy", "Sell"):
            raise SnapshotValidationError("order.side must be Buy or Sell")
        qty = _decimal(row.get("qty"), "order.qty", minimum=Decimal("0"))
        leaves = _decimal(row.get("leavesQty"), "order.leavesQty", minimum=Decimal("0"))
        cumulative = _decimal(row.get("cumExecQty"), "order.cumExecQty", minimum=Decimal("0"))
        if qty == 0 or leaves > qty or cumulative > qty or leaves + cumulative > qty:
            raise SnapshotValidationError("order quantities are inconsistent")
        status = _nonempty_string(row.get("orderStatus"), "order.orderStatus")
        created = _integer(row.get("createdTime"), "order.createdTime", minimum=1)
        updated = _integer(row.get("updatedTime"), "order.updatedTime", minimum=1)
        raw_idx = row.get("positionIdx")
        idx = None if raw_idx in (None, "") else _integer(raw_idx, "order.positionIdx")
        if idx is not None and idx not in (0, 1, 2):
            raise SnapshotValidationError("order.positionIdx must be 0, 1, or 2")
        link_id = row.get("orderLinkId", "")
        if not isinstance(link_id, str):
            raise SnapshotValidationError("order.orderLinkId must be a string")
        parsed.append(ActiveOrderSnapshot(
            order_id, link_id, symbol, side, qty, leaves, cumulative,
            status, created, updated, idx,
        ))
    return tuple(sorted(parsed, key=lambda item: item.order_id))


def parse_execution_pages(
    pages: Iterable[tuple[str, Mapping[str, Any]]],
) -> tuple[ExecutionSnapshot, ...]:
    rows = _collect_complete_pages(pages)
    parsed: list[ExecutionSnapshot] = []
    seen: set[str] = set()
    for row in rows:
        exec_id = _nonempty_string(row.get("execId"), "execution.execId")
        if exec_id in seen:
            raise SnapshotValidationError(f"duplicate execId: {exec_id}")
        seen.add(exec_id)
        order_id = row.get("orderId", "")
        link_id = row.get("orderLinkId", "")
        if not isinstance(order_id, str) or not isinstance(link_id, str):
            raise SnapshotValidationError("execution order identifiers must be strings")
        symbol = _nonempty_string(row.get("symbol"), "execution.symbol").upper()
        exec_type = _nonempty_string(row.get("execType"), "execution.execType")
        exec_time = _integer(row.get("execTime"), "execution.execTime", minimum=1)
        side_raw = row.get("side", "")
        if side_raw not in ("", "Buy", "Sell"):
            raise SnapshotValidationError("execution.side must be Buy, Sell, or empty")
        qty = _decimal(row.get("execQty"), "execution.execQty",
                       minimum=Decimal("0"), allow_empty=True)
        price = _decimal(row.get("execPrice"), "execution.execPrice",
                         minimum=Decimal("0"), allow_empty=True)
        fee = _decimal(row.get("execFee"), "execution.execFee",
                       allow_empty=True)
        if exec_type == "Trade":
            if side_raw not in ("Buy", "Sell") or qty is None or qty <= 0 or price is None or price <= 0:
                raise SnapshotValidationError("Trade execution requires side, positive qty, and positive price")
            if not order_id:
                raise SnapshotValidationError("Trade execution requires orderId")
        parsed.append(ExecutionSnapshot(
            exec_id, order_id, link_id, symbol, exec_type, exec_time,
            side_raw or None, qty, price, fee,
        ))
    return tuple(sorted(parsed, key=lambda item: (item.exec_time_ms, item.exec_id)))
