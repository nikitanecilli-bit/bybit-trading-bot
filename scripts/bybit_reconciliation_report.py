#!/usr/bin/env python3
"""Build a fail-closed, report-only comparison of local backup and Bybit snapshot.

This module reads local JSON only. It never calls an exchange endpoint and never
creates, amends, cancels, or closes orders or positions. It intentionally cannot
return a reconciliation PASS because the local state has no exact exchange qty,
positionIdx, order IDs, or execution ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bybit_reconciliation import (
    SnapshotValidationError,
    parse_active_order_pages,
    parse_execution_pages,
    parse_position_pages,
)


class ReportError(ValueError):
    """Input backup or snapshot is malformed or cannot be trusted."""


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReportError("snapshot raw payload is not canonical JSON") from exc


def _utc_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ReportError(f"{field} must be a non-empty ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReportError(f"{field} is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReportError(f"{field} must include a UTC offset")
    if parsed.utcoffset().total_seconds() != 0:
        raise ReportError(f"{field} must be expressed in UTC")
    return parsed


def _page_tuples(pages: Any, field: str) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(pages, list) or not pages:
        raise ReportError(f"snapshot raw.{field} must be a non-empty page list")
    result = []
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise ReportError(f"snapshot raw.{field}[{index}] must be an object")
        cursor = page.get("requested_cursor")
        response = page.get("response")
        if not isinstance(cursor, str) or not isinstance(response, dict):
            raise ReportError(f"snapshot raw.{field}[{index}] has invalid page envelope")
        result.append((cursor, response))
    return result


def _parse_exchange_snapshot(snapshot: dict[str, Any], saved_at_ms: int) -> tuple[tuple, tuple, tuple]:
    if not isinstance(snapshot, dict):
        raise ReportError("exchange snapshot root must be an object")
    if snapshot.get("schema_version") != 1:
        raise ReportError("unsupported exchange snapshot schema_version")
    if snapshot.get("category") != "linear" or snapshot.get("settle_coin") != "USDT":
        raise ReportError("snapshot is not scoped to Bybit linear/USDT")
    if snapshot.get("status") != "CAPTURED_READ_ONLY_NOT_RECONCILED":
        raise ReportError("snapshot status is not CAPTURED_READ_ONLY_NOT_RECONCILED")
    raw = snapshot.get("raw")
    if not isinstance(raw, dict) or set(raw) != {"positions", "active_orders", "order_history", "executions"}:
        raise ReportError("snapshot raw sections are missing or unexpected")
    digest = hashlib.sha256(_canonical_json_bytes(raw)).hexdigest()
    if snapshot.get("raw_sha256") != digest:
        raise ReportError("snapshot raw_sha256 mismatch")

    position_pages = _page_tuples(raw["positions"], "positions")
    order_pages = _page_tuples(raw["active_orders"], "active_orders")
    history_pages = raw["order_history"]
    if not isinstance(history_pages, list) or not history_pages:
        raise ReportError("snapshot raw.order_history must be a non-empty page list")
    execution_pages = raw["executions"]
    if not isinstance(execution_pages, list) or not execution_pages:
        raise ReportError("snapshot raw.executions must be a non-empty page list")

    try:
        positions = parse_position_pages(position_pages)
        orders = parse_active_order_pages(order_pages)
        history_grouped: dict[tuple[int, int], list[tuple[str, dict[str, Any]]]] = {}
        for index, page in enumerate(history_pages):
            if not isinstance(page, dict):
                raise ReportError(f"snapshot raw.order_history[{index}] must be an object")
            start = page.get("interval_start_ms")
            end = page.get("interval_end_ms")
            if (isinstance(start, bool) or not isinstance(start, int)
                    or isinstance(end, bool) or not isinstance(end, int)
                    or start <= 0 or end <= start):
                raise ReportError(f"snapshot raw.order_history[{index}] has invalid interval")
            cursor = page.get("requested_cursor")
            response = page.get("response")
            if not isinstance(cursor, str) or not isinstance(response, dict):
                raise ReportError(f"snapshot raw.order_history[{index}] has invalid page envelope")
            history_grouped.setdefault((start, end), []).append((cursor, response))
        history_by_id = {}
        for interval in sorted(history_grouped):
            for item in parse_active_order_pages(history_grouped[interval]):
                previous = history_by_id.get(item.order_id)
                if previous is None or item.updated_time_ms > previous.updated_time_ms:
                    history_by_id[item.order_id] = item
                elif item.updated_time_ms == previous.updated_time_ms and item != previous:
                    raise ReportError(f"historical order {item.order_id} has conflicting records")
        historical_orders = tuple(history_by_id[key] for key in sorted(history_by_id))

        grouped: dict[tuple[int, int], list[tuple[str, dict[str, Any]]]] = {}
        for index, page in enumerate(execution_pages):
            if not isinstance(page, dict):
                raise ReportError(f"snapshot raw.executions[{index}] must be an object")
            start = page.get("interval_start_ms")
            end = page.get("interval_end_ms")
            if (isinstance(start, bool) or not isinstance(start, int)
                    or isinstance(end, bool) or not isinstance(end, int)
                    or start <= 0 or end <= start):
                raise ReportError(f"snapshot raw.executions[{index}] has invalid interval")
            cursor = page.get("requested_cursor")
            response = page.get("response")
            if not isinstance(cursor, str) or not isinstance(response, dict):
                raise ReportError(f"snapshot raw.executions[{index}] has invalid page envelope")
            grouped.setdefault((start, end), []).append((cursor, response))
        executions_by_id = {}
        for interval in sorted(grouped):
            for execution in parse_execution_pages(grouped[interval]):
                executions_by_id[execution.exec_id] = execution
        executions = tuple(executions_by_id[key] for key in sorted(executions_by_id))
    except SnapshotValidationError as exc:
        raise ReportError(f"exchange snapshot parser rejected input: {exc}") from exc

    counts = snapshot.get("counts")
    expected_counts = {
        "positions": len(positions),
        "active_orders": len(orders),
        "historical_orders": len(historical_orders),
        "executions": len(executions),
        "position_pages": len(position_pages),
        "active_order_pages": len(order_pages),
        "order_history_pages": len(history_pages),
        "execution_pages": len(execution_pages),
    }
    if not isinstance(counts, dict):
        raise ReportError("snapshot counts must be an object")
    for key, expected in expected_counts.items():
        value = counts.get(key)
        if isinstance(value, bool) or value != expected:
            raise ReportError(f"snapshot counts.{key} does not match validated raw data")

    before = snapshot.get("bybit_server_time_before_ms")
    after = snapshot.get("bybit_server_time_after_ms")
    capture_now = snapshot.get("capture_now_ms")
    for field, value in (("bybit_server_time_before_ms", before),
                         ("bybit_server_time_after_ms", after),
                         ("capture_now_ms", capture_now)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ReportError(f"snapshot {field} is invalid")
    if before <= saved_at_ms or before > after or after - before > 120_000 or capture_now != before:
        raise ReportError("snapshot server-time bounds are inconsistent with backup time")
    interval_keys = sorted(grouped)
    history_interval_keys = sorted(history_grouped)
    if history_interval_keys != interval_keys:
        raise ReportError("order-history and execution interval coverage differs")
    coverage = snapshot.get("order_history_coverage")
    if not isinstance(coverage, dict) or coverage.get("status") != "QUERYABLE_WINDOW_ONLY_NOT_COMPLETE":
        raise ReportError("order-history coverage limitation metadata is missing")
    if (coverage.get("start_ms") != saved_at_ms or coverage.get("end_ms") != capture_now
            or coverage.get("duration_ms") != capture_now - saved_at_ms):
        raise ReportError("order-history coverage metadata does not match capture window")
    expected_start = saved_at_ms
    for start, end in interval_keys:
        if start != expected_start or end - start > 7 * 24 * 60 * 60 * 1000:
            raise ReportError("execution intervals are not contiguous or exceed seven days")
        expected_start = end
    if expected_start != capture_now:
        raise ReportError("execution intervals do not reach the capture boundary")
    return positions, orders, historical_orders, executions


def build_report(local_backup: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ReportError("exchange snapshot root must be an object")
    if not isinstance(local_backup, dict):
        raise ReportError("local backup root must be an object")
    required = {
        "saved_at_utc", "bot_version", "risk", "open_positions",
        "pending_orders", "trade_seq",
    }
    missing = required.difference(local_backup)
    if missing:
        raise ReportError(f"local backup missing required fields: {sorted(missing)}")
    saved_dt = _utc_timestamp(local_backup["saved_at_utc"], "local backup saved_at_utc")
    saved_at_ms = int(saved_dt.timestamp() * 1000)
    if snapshot.get("saved_at_utc") != local_backup["saved_at_utc"]:
        raise ReportError("snapshot saved_at_utc does not match local backup")
    if not isinstance(local_backup["open_positions"], dict):
        raise ReportError("local backup open_positions must be an object")
    if not isinstance(local_backup["pending_orders"], dict):
        raise ReportError("local backup pending_orders must be an object")
    if not isinstance(local_backup["risk"], dict):
        raise ReportError("local backup risk must be an object")
    if not isinstance(local_backup["bot_version"], str) or not local_backup["bot_version"]:
        raise ReportError("local backup bot_version must be a non-empty string")
    seq = local_backup["trade_seq"]
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise ReportError("local backup trade_seq must be a non-negative integer")

    positions, orders, historical_orders, executions = _parse_exchange_snapshot(snapshot, saved_at_ms)
    local_positions = local_backup["open_positions"]
    pending = local_backup["pending_orders"]

    local_position_rows = []
    for key, value in sorted(local_positions.items()):
        if not isinstance(key, str) or not key or not isinstance(value, dict):
            raise ReportError("each local open position must be an object keyed by symbol")
        symbol = value.get("symbol")
        direction = value.get("direction")
        if symbol != key or direction not in ("long", "short"):
            raise ReportError(f"local position {key} has inconsistent symbol/direction")
        local_position_rows.append({"symbol": key, "direction": direction})

    exchange_position_rows = [
        {
            "symbol": item.symbol,
            "position_idx": item.position_idx,
            "side": item.side,
            "qty": str(item.size),
            "avg_price": str(item.avg_price),
            "take_profit": str(item.take_profit) if item.take_profit is not None else None,
            "stop_loss": str(item.stop_loss) if item.stop_loss is not None else None,
            "trailing_stop": str(item.trailing_stop) if item.trailing_stop is not None else None,
            "tpsl_mode": item.tpsl_mode,
            "protection_status": (
                "UNKNOWN_FIELDS_MISSING"
                if item.stop_loss is None or item.trailing_stop is None
                else "NO_EXCHANGE_STOP"
                if item.stop_loss == 0 and item.trailing_stop == 0
                else "EXCHANGE_STOP_CONFIGURED"
            ),
        }
        for item in positions
    ]
    def order_row(item):
        return {
            "order_id": item.order_id,
            "order_link_id": item.order_link_id,
            "parent_order_link_id": item.parent_order_link_id,
            "symbol": item.symbol,
            "side": item.side,
            "position_idx": item.position_idx,
            "qty": str(item.qty),
            "leaves_qty": str(item.leaves_qty),
            "cum_exec_qty": str(item.cum_exec_qty),
            "order_status": item.order_status,
            "order_type": item.order_type,
            "stop_order_type": item.stop_order_type,
            "trigger_price": str(item.trigger_price) if item.trigger_price is not None else None,
            "take_profit": str(item.take_profit) if item.take_profit is not None else None,
            "stop_loss": str(item.stop_loss) if item.stop_loss is not None else None,
            "tpsl_mode": item.tpsl_mode,
            "tp_trigger_by": item.tp_trigger_by,
            "sl_trigger_by": item.sl_trigger_by,
            "reduce_only": item.reduce_only,
            "close_on_trigger": item.close_on_trigger,
            "created_time_ms": item.created_time_ms,
            "updated_time_ms": item.updated_time_ms,
        }

    active_order_rows = [order_row(item) for item in orders]
    historical_order_rows = [order_row(item) for item in historical_orders]
    conditional_order_rows = [
        order_row(item)
        for item in list(orders) + list(historical_orders)
        if (item.stop_order_type not in (None, "", "UNKNOWN")
            or (item.trigger_price is not None and item.trigger_price > 0)
            or (item.take_profit is not None and item.take_profit > 0)
            or (item.stop_loss is not None and item.stop_loss > 0))
    ]

    exchange_by_symbol = {}
    for item in positions:
        exchange_by_symbol.setdefault(item.symbol, []).append(item)
    local_by_symbol = {row["symbol"]: row for row in local_position_rows}

    direction_conflicts = []
    for symbol, local in local_by_symbol.items():
        exchange_rows = exchange_by_symbol.get(symbol, [])
        if exchange_rows and all(
            ("long" if row.side == "Buy" else "short") != local["direction"]
            for row in exchange_rows
        ):
            direction_conflicts.append(symbol)

    reasons = [
        "Local OpenPositionState has no exact exchange contract qty or positionIdx.",
        "Local backup has no Bybit orderId/orderLinkId mapping for active orders.",
        "Local backup has no complete execution ledger to prove fills since saved_at_utc.",
        "pending_orders are next-bar signal intents, not proof of exchange active orders.",
    ]
    if local_position_rows or exchange_position_rows:
        reasons.append("Open positions exist on at least one side; exact position reconciliation is unsupported.")
    if any(row["protection_status"] == "UNKNOWN_FIELDS_MISSING" for row in exchange_position_rows):
        reasons.append("Bybit position response omitted stopLoss/trailingStop fields; exchange protection state is unknown.")
    if any(row["protection_status"] == "NO_EXCHANGE_STOP" for row in exchange_position_rows):
        reasons.append("At least one exchange position has neither stopLoss nor trailingStop configured.")
    if orders:
        reasons.append("Exchange active orders exist but cannot be mapped to local exchange order identities.")
    if historical_orders:
        reasons.append("Historical exchange orders exist but cannot be mapped to a local order/event ledger.")
    if conditional_order_rows:
        reasons.append("Conditional/TP/SL order records exist; local conditional-order identity and trigger-health model is absent.")
    reasons.append("Bybit order-history API has retention/status limits and may be delayed; this capture is explicitly not a complete order journal.")
    if executions:
        reasons.append("Exchange executions exist but cannot be compared with a local execution ledger.")
    if direction_conflicts:
        reasons.append("Local and exchange position directions conflict for: " + ", ".join(direction_conflicts))
    if not local_position_rows and not exchange_position_rows and not orders and not executions:
        reasons.append("Both snapshots show no open positions/orders, but absence of a local execution ledger prevents a safe resume verdict.")

    return {
        "schema_version": 1,
        "status": "BLOCKED_UNSUPPORTED_LOCAL_MODEL",
        "reconciliation_pass": False,
        "live_resume_allowed": False,
        "local": {
            "saved_at_utc": local_backup["saved_at_utc"],
            "bot_version": local_backup["bot_version"],
            "open_position_count": len(local_position_rows),
            "pending_signal_count": len(pending),
            "trade_seq": seq,
        },
        "exchange": {
            "snapshot_status": snapshot["status"],
            "raw_sha256": snapshot["raw_sha256"],
            "position_count": len(positions),
            "active_order_count": len(orders),
            "historical_order_count": len(historical_orders),
            "order_history_coverage": snapshot["order_history_coverage"],
            "execution_count_since_backup": len(executions),
            "positions": exchange_position_rows,
            "active_order_ids": [item.order_id for item in orders],
            "active_orders": active_order_rows,
            "historical_orders": historical_order_rows,
            "conditional_orders": conditional_order_rows,
            "historical_order_ids": [item.order_id for item in historical_orders],
            "historical_order_statuses": {item.order_id: item.order_status for item in historical_orders},
            "execution_ids": [item.exec_id for item in executions],
        },
        "diagnostics": {
            "local_symbols": sorted(local_by_symbol),
            "exchange_symbols": sorted(exchange_by_symbol),
            "direction_conflicts": direction_conflicts,
            "local_symbols_missing_on_exchange": sorted(set(local_by_symbol) - set(exchange_by_symbol)),
            "exchange_symbols_missing_locally": sorted(set(exchange_by_symbol) - set(local_by_symbol)),
        },
        "block_reasons": reasons,
        "note": "Report-only diagnostic. No order or position mutation is possible from this tool.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", required=True, help="Local bot_state_backup.json")
    parser.add_argument("--snapshot", required=True, help="Read-only Bybit snapshot JSON")
    parser.add_argument("--output", required=True, help="Output report JSON")
    args = parser.parse_args()
    try:
        local_backup = json.loads(Path(args.backup).read_text(encoding="utf-8"))
        snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        report = build_report(local_backup, snapshot)
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, ReportError, ValueError) as exc:
        print(f"BLOCKED: {exc}")
        return 1
    print(f"Report saved: {args.output}; status={report['status']}; live_resume_allowed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
