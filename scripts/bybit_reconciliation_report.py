#!/usr/bin/env python3
"""Build a fail-closed, report-only comparison of local backup and Bybit snapshot.

This module reads local JSON only. It never calls an exchange endpoint and never
creates, amends, cancels, or closes orders or positions. It intentionally cannot
return a reconciliation PASS because the local state has no exact exchange qty,
positionIdx, order IDs, or execution ledger.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import urllib.parse
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exchange_execution_identity import (
    ExchangeExecutionIdentity,
    ExecutionIdentityError,
    ExchangeOrderIdentity,
    ExchangePositionIdentity,
)

from bybit_reconciliation import (
    SnapshotValidationError,
    deduplicate_executions,
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


def _validate_page_provenance(pages: list[dict[str, Any]], field: str,
                              endpoint: str, *, interval_scoped: bool = False) -> None:
    """Verify schema-v2 page provenance against the stored canonical responses."""
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for index, page in enumerate(pages):
        key = (page.get("interval_start_ms"), page.get("interval_end_ms")) if interval_scoped else ()
        groups.setdefault(key, []).append(page)
    for group_key, group in groups.items():
        previous_completed = None
        previous_next_cursor_hash = None
        for page_index, page in enumerate(group):
            provenance = page.get("page_provenance")
            response = page.get("response")
            cursor = page.get("requested_cursor")
            if not isinstance(provenance, dict) or not isinstance(response, dict) or not isinstance(cursor, str):
                raise ReportError(f"snapshot raw.{field} page provenance is missing or malformed")
            expected_keys = {
                "endpoint", "page_index", "request_started_at_ms", "request_completed_at_ms",
                "query_params", "query_params_sha256", "requested_cursor_sha256",
                "next_cursor_sha256", "response_canonical_sha256", "ret_code", "row_count",
                "has_next_page",
            }
            if set(provenance) != expected_keys:
                raise ReportError(f"snapshot raw.{field} page provenance fields mismatch")
            if provenance["endpoint"] != endpoint or provenance["page_index"] != page_index:
                raise ReportError(f"snapshot raw.{field} page provenance endpoint/index mismatch")
            started, completed = provenance["request_started_at_ms"], provenance["request_completed_at_ms"]
            for name, value in (("request_started_at_ms", started), ("request_completed_at_ms", completed),
                                ("page_index", provenance["page_index"]), ("row_count", provenance["row_count"])):
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ReportError(f"snapshot raw.{field} provenance {name} is invalid")
            if started <= 0 or completed < started:
                raise ReportError(f"snapshot raw.{field} provenance request time bounds are invalid")
            if previous_completed is not None and started < previous_completed:
                raise ReportError(f"snapshot raw.{field} page requests overlap or are out of order")
            params = provenance["query_params"]
            if not isinstance(params, dict) or params.get("cursor", "") != cursor:
                raise ReportError(f"snapshot raw.{field} provenance query params mismatch cursor")
            hashes = {
                "query_params_sha256": hashlib.sha256(_canonical_json_bytes(params)).hexdigest(),
                "requested_cursor_sha256": hashlib.sha256(cursor.encode("utf-8")).hexdigest(),
                "response_canonical_sha256": hashlib.sha256(_canonical_json_bytes(response)).hexdigest(),
            }
            for name, expected in hashes.items():
                if provenance.get(name) != expected:
                    raise ReportError(f"snapshot raw.{field} provenance {name} mismatch")
            result = response.get("result")
            if not isinstance(result, dict) or not isinstance(result.get("list"), list):
                raise ReportError(f"snapshot raw.{field} response list is malformed")
            next_cursor = result.get("nextPageCursor", "")
            if not isinstance(next_cursor, str):
                raise ReportError(f"snapshot raw.{field} next cursor is malformed")
            next_hash = hashlib.sha256(next_cursor.encode("utf-8")).hexdigest()
            if provenance.get("next_cursor_sha256") != next_hash:
                raise ReportError(f"snapshot raw.{field} provenance next cursor hash mismatch")
            if provenance.get("ret_code") != response.get("retCode") or response.get("retCode") != 0:
                raise ReportError(f"snapshot raw.{field} provenance retCode mismatch")
            if provenance.get("row_count") != len(result["list"]):
                raise ReportError(f"snapshot raw.{field} provenance row count mismatch")
            has_next = bool(next_cursor)
            if provenance.get("has_next_page") is not has_next:
                raise ReportError(f"snapshot raw.{field} provenance continuation mismatch")
            if previous_next_cursor_hash is not None and previous_next_cursor_hash != hashes["requested_cursor_sha256"]:
                raise ReportError(f"snapshot raw.{field} provenance cursor chain mismatch")
            if page_index < len(group) - 1 and not has_next:
                raise ReportError(f"snapshot raw.{field} provenance terminates before final page")
            if page_index == len(group) - 1 and has_next:
                raise ReportError(f"snapshot raw.{field} provenance has no terminal page")
            previous_completed = completed
            previous_next_cursor_hash = next_hash


def _parse_exchange_snapshot(snapshot: dict[str, Any], saved_at_ms: int) -> tuple[tuple, tuple, tuple]:
    if not isinstance(snapshot, dict):
        raise ReportError("exchange snapshot root must be an object")
    schema_version = snapshot.get("schema_version")
    if schema_version not in (1, 2, 3):
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
    if schema_version == 3:
        base_url = snapshot.get("base_url")
        allowed_hosts = {
            "api.bybit.com", "api.bytick.com", "api.bybit.kz", "api.bybit.tr",
            "api.bybitgeorgia.ge", "api.bybit.ae", "api.bybit.eu", "api.bybit.id",
        }
        try:
            parsed_base_url = urllib.parse.urlsplit(base_url) if isinstance(base_url, str) else None
            valid_base_url = (
                parsed_base_url is not None
                and parsed_base_url.scheme == "https"
                and parsed_base_url.hostname in allowed_hosts
                and parsed_base_url.username is None
                and parsed_base_url.password is None
                and parsed_base_url.port in (None, 443)
                and parsed_base_url.path in ("", "/")
                and not parsed_base_url.query
                and not parsed_base_url.fragment
            )
        except ValueError:
            valid_base_url = False
        if not valid_base_url:
            raise ReportError("snapshot base_url is not an official HTTPS Bybit API host")
        fingerprint = snapshot.get("api_key_fingerprint_sha256")
        if (not isinstance(fingerprint, str) or len(fingerprint) != 64
                or any(char not in "0123456789abcdef" for char in fingerprint)):
            raise ReportError("snapshot API-key fingerprint is missing or malformed")
    if schema_version in (2, 3):
        _validate_page_provenance(raw["positions"], "positions", "/v5/position/list")
        _validate_page_provenance(raw["active_orders"], "active_orders", "/v5/order/realtime")
        _validate_page_provenance(history_pages, "order_history", "/v5/order/history", interval_scoped=True)
        _validate_page_provenance(execution_pages, "executions", "/v5/execution/list", interval_scoped=True)

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
        parsed_execution_rows = []
        for interval in sorted(grouped):
            parsed_execution_rows.extend(parse_execution_pages(grouped[interval]))
        executions = deduplicate_executions(parsed_execution_rows)
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


def compare_execution_snapshots(initial: dict[str, Any], refreshed: dict[str, Any]) -> dict[str, Any]:
    """Compare two read-only captures and surface executions discovered later.

    Both captures must cover the same saved-backup lifecycle start. New execIds
    whose event timestamp is at/before the first capture's server-time bound
    are late discoveries, not proof that the first response was complete.
    """
    if not isinstance(initial, dict) or not isinstance(refreshed, dict):
        raise ReportError("both execution snapshots must be objects")
    if initial.get("saved_at_utc") != refreshed.get("saved_at_utc"):
        raise ReportError("execution snapshots must share the same saved_at_utc")
    if initial.get("schema_version") != 3 or refreshed.get("schema_version") != 3:
        raise ReportError("execution snapshot comparison requires schema_version 3")
    if initial.get("base_url") != refreshed.get("base_url"):
        raise ReportError("execution snapshots must use the same Bybit base_url")
    initial_fingerprint = initial.get("api_key_fingerprint_sha256")
    refreshed_fingerprint = refreshed.get("api_key_fingerprint_sha256")
    if (not isinstance(initial_fingerprint, str) or len(initial_fingerprint) != 64
            or any(char not in "0123456789abcdef" for char in initial_fingerprint)
            or initial_fingerprint != refreshed_fingerprint):
        raise ReportError("execution snapshots must have the same valid API-key fingerprint")
    saved_dt = _utc_timestamp(initial.get("saved_at_utc"), "snapshot saved_at_utc")
    saved_at_ms = int(saved_dt.timestamp() * 1000)
    _, _, _, initial_execs = _parse_exchange_snapshot(initial, saved_at_ms)
    _, _, _, refreshed_execs = _parse_exchange_snapshot(refreshed, saved_at_ms)
    initial_by_id = {item.exec_id: item for item in initial_execs}
    refreshed_by_id = {item.exec_id: item for item in refreshed_execs}
    conflicts = sorted(
        exec_id for exec_id in initial_by_id.keys() & refreshed_by_id.keys()
        if initial_by_id[exec_id] != refreshed_by_id[exec_id]
    )
    if conflicts:
        raise ReportError(f"execution identity changed between snapshots: {conflicts}")
    new_ids = sorted(refreshed_by_id.keys() - initial_by_id.keys())
    first_bound = initial.get("bybit_server_time_before_ms")
    later_bound = refreshed.get("bybit_server_time_before_ms")
    if (isinstance(first_bound, bool) or not isinstance(first_bound, int)
            or isinstance(later_bound, bool) or not isinstance(later_bound, int)
            or later_bound <= first_bound):
        raise ReportError("refreshed snapshot must have a strictly later server-time bound")
    late_ids = sorted(exec_id for exec_id in new_ids
                      if refreshed_by_id[exec_id].exec_time_ms <= first_bound)
    subsequent_ids = sorted(set(new_ids) - set(late_ids))
    return {
        "status": "LATE_EXECUTIONS_DISCOVERED" if late_ids else (
            "NEW_EXECUTIONS_DISCOVERED" if new_ids else "NO_NEW_EXECUTIONS_OBSERVED"
        ),
        "initial_server_time_bound_ms": first_bound,
        "refreshed_server_time_bound_ms": later_bound,
        "new_execution_count": len(new_ids),
        "new_exec_ids": new_ids,
        "late_execution_count": len(late_ids),
        "late_exec_ids": late_ids,
        "subsequent_execution_count": len(subsequent_ids),
        "subsequent_exec_ids": subsequent_ids,
        "execution_history_complete": False,
        "reconciliation_pass": False,
        "live_resume_allowed": False,
    }



def build_execution_merge_plan(local_backup: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build a strictly read-only, all-or-nothing execution-ledger merge proposal.

    The returned records are candidates only. This function never mutates the
    supplied backup, writes files, or marks exchange history complete.
    """
    if not isinstance(local_backup, dict):
        raise ReportError("local backup root must be an object")
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 3:
        raise ReportError("execution merge planning requires schema_version 3")
    if local_backup.get("saved_at_utc") != snapshot.get("saved_at_utc"):
        raise ReportError("snapshot saved_at_utc does not match local backup")
    saved_dt = _utc_timestamp(local_backup.get("saved_at_utc"), "local backup saved_at_utc")
    saved_at_ms = int(saved_dt.timestamp() * 1000)
    _, _, _, parsed = _parse_exchange_snapshot(snapshot, saved_at_ms)

    positions = local_backup.get("open_positions")
    if not isinstance(positions, dict):
        raise ReportError("local backup open_positions must be an object")
    by_symbol: dict[str, dict[str, Any]] = {}
    for key, state in positions.items():
        if not isinstance(key, str) or not isinstance(state, dict):
            raise ReportError("local open position entries must be objects keyed by symbol")
        symbol = state.get("symbol", key)
        if symbol != key or symbol in by_symbol:
            raise ReportError("local open position symbol identity is ambiguous")
        by_symbol[symbol] = state

    known_orders: dict[str, dict[str, ExchangeOrderIdentity]] = {}
    known_execs: dict[str, dict[str, ExchangeExecutionIdentity]] = {}
    position_identities: dict[str, ExchangePositionIdentity] = {}
    for symbol, state in by_symbol.items():
        try:
            raw_position = state.get("exchange_position_identity")
            if not isinstance(raw_position, dict):
                raise ReportError(f"local position {symbol} lacks exchange position identity")
            position_identity = ExchangePositionIdentity.from_dict(raw_position)
            if position_identity.symbol != symbol:
                raise ReportError(f"local position {symbol} exchange identity symbol mismatch")
            position_identities[symbol] = position_identity
            orders_raw = state.get("exchange_orders", [])
            executions_raw = state.get("exchange_executions", [])
            if not isinstance(orders_raw, list) or not isinstance(executions_raw, list):
                raise ReportError(f"local position {symbol} exchange ledgers must be lists")
            order_map: dict[str, ExchangeOrderIdentity] = {}
            for raw in orders_raw:
                order = ExchangeOrderIdentity.from_dict(raw)
                if order.symbol != symbol or order.order_id in order_map:
                    raise ReportError(f"local position {symbol} has invalid/duplicate exchange order")
                order_map[order.order_id] = order
            exec_map: dict[str, ExchangeExecutionIdentity] = {}
            for raw in executions_raw:
                execution = ExchangeExecutionIdentity.from_dict(raw)
                if execution.symbol != symbol or execution.exec_id in exec_map:
                    raise ReportError(f"local position {symbol} has invalid/duplicate execution ledger")
                exec_map[execution.exec_id] = execution
            known_orders[symbol] = order_map
            known_execs[symbol] = exec_map
        except (ValueError, TypeError, ExecutionIdentityError) as exc:
            if isinstance(exc, ReportError):
                raise
            raise ReportError(f"local exchange ledger for {symbol} is invalid: {exc}") from exc

    planned: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in by_symbol}
    duplicates: list[str] = []
    for row in parsed:
        symbol = row.symbol
        if symbol not in by_symbol:
            raise ReportError(f"execution {row.exec_id} has no local open-position ledger for {symbol}")
        position = position_identities[symbol]
        orders = known_orders[symbol]
        order = orders.get(row.order_id)
        if order is None and row.order_id != position.entry_order_id:
            raise ReportError(f"execution {row.exec_id} references unknown local order {row.order_id}")
        expected_side = order.side if order is not None else position.side
        expected_link = order.order_link_id if order is not None else position.entry_order_link_id
        if row.side != expected_side:
            raise ReportError(f"execution {row.exec_id} side conflicts with local order/position")
        if expected_link and row.order_link_id != expected_link:
            raise ReportError(f"execution {row.exec_id} orderLinkId conflicts with local order/position")
        candidate = ExchangeExecutionIdentity(
            exec_id=row.exec_id, order_id=row.order_id, order_link_id=row.order_link_id,
            symbol=row.symbol, side=row.side, exec_qty=str(row.exec_qty),
            exec_price=str(row.exec_price), exec_time_ms=row.exec_time_ms,
            exec_fee=None if row.exec_fee is None else str(row.exec_fee),
        )
        existing = known_execs[symbol].get(candidate.exec_id)
        if existing is not None:
            if existing != candidate:
                raise ReportError(f"conflicting local execution identity: {candidate.exec_id}")
            duplicates.append(candidate.exec_id)
            continue
        planned[symbol].append(candidate.to_dict())

    proposed = {symbol: rows for symbol, rows in planned.items() if rows}
    plan = {
        "plan_schema_version": 1,
        "status": "DRY_RUN_MERGE_PLAN",
        "mode": "READ_ONLY_NO_MUTATION",
        "base_backup_sha256": hashlib.sha256(_canonical_json_bytes(local_backup)).hexdigest(),
        "planned_insert_count": sum(len(rows) for rows in proposed.values()),
        "exact_duplicate_count": len(duplicates),
        "planned_insertions": proposed,
        "exact_duplicate_exec_ids": sorted(duplicates),
        "execution_history_complete": False,
        "reconciliation_pass": False,
        "live_resume_allowed": False,
    }
    plan["plan_sha256"] = hashlib.sha256(_canonical_json_bytes(plan)).hexdigest()
    return plan


def apply_execution_merge_plan(
    local_backup: dict[str, Any], plan: dict[str, Any],
) -> dict[str, Any]:
    """Apply a dry-run proposal to a detached backup copy, never to disk or engine state.

    The complete backup hash prevents applying a plan after any intervening
    state change. A canonical plan hash detects accidental plan alteration.
    All candidate rows are validated before a replacement copy is returned.
    """
    if not isinstance(local_backup, dict) or not isinstance(plan, dict):
        raise ReportError("backup and merge plan must be objects")
    if plan.get("plan_schema_version") != 1 or plan.get("status") != "DRY_RUN_MERGE_PLAN":
        raise ReportError("unsupported execution merge plan")
    if plan.get("mode") != "READ_ONLY_NO_MUTATION":
        raise ReportError("execution merge plan mode is not read-only")
    if (plan.get("execution_history_complete") is not False
            or plan.get("reconciliation_pass") is not False
            or plan.get("live_resume_allowed") is not False):
        raise ReportError("execution merge plan contains forbidden state escalation")
    supplied_digest = plan.get("plan_sha256")
    unsigned_plan = {key: value for key, value in plan.items() if key != "plan_sha256"}
    expected_digest = hashlib.sha256(_canonical_json_bytes(unsigned_plan)).hexdigest()
    if not isinstance(supplied_digest, str) or supplied_digest != expected_digest:
        raise ReportError("execution merge plan integrity check failed")
    current_backup_digest = hashlib.sha256(_canonical_json_bytes(local_backup)).hexdigest()
    if plan.get("base_backup_sha256") != current_backup_digest:
        raise ReportError("stale execution merge plan: local backup changed after planning")

    insertions = plan.get("planned_insertions")
    if not isinstance(insertions, dict):
        raise ReportError("planned insertions must be an object")
    expected_count = plan.get("planned_insert_count")
    if isinstance(expected_count, bool) or not isinstance(expected_count, int) or expected_count < 0:
        raise ReportError("planned insert count is invalid")
    if sum(len(rows) for rows in insertions.values() if isinstance(rows, list)) != expected_count:
        raise ReportError("planned insert count does not match insertion payload")

    candidate = copy.deepcopy(local_backup)
    positions = candidate.get("open_positions")
    if not isinstance(positions, dict):
        raise ReportError("local backup open_positions must be an object")
    inserted = 0
    for symbol, rows in insertions.items():
        if not isinstance(symbol, str) or not isinstance(rows, list) or symbol not in positions:
            raise ReportError("planned insertion references an unknown position")
        state = positions[symbol]
        if not isinstance(state, dict) or state.get("symbol", symbol) != symbol:
            raise ReportError("local position identity is invalid")
        try:
            raw_position = state.get("exchange_position_identity")
            if not isinstance(raw_position, dict):
                raise ReportError(f"local position {symbol} lacks exchange position identity")
            position = ExchangePositionIdentity.from_dict(raw_position)
            if position.symbol != symbol:
                raise ReportError(f"local position {symbol} exchange identity mismatch")
            orders_raw = state.get("exchange_orders", [])
            executions_raw = state.get("exchange_executions", [])
            if not isinstance(orders_raw, list) or not isinstance(executions_raw, list):
                raise ReportError(f"local position {symbol} ledgers must be lists")
            orders = [ExchangeOrderIdentity.from_dict(item) for item in orders_raw]
            executions = [ExchangeExecutionIdentity.from_dict(item) for item in executions_raw]
            if any(item.symbol != symbol for item in orders + executions):
                raise ReportError(f"local position {symbol} ledger symbol mismatch")
            order_map = {item.order_id: item for item in orders}
            exec_map = {item.exec_id: item for item in executions}
            if len(order_map) != len(orders) or len(exec_map) != len(executions):
                raise ReportError(f"local position {symbol} ledger contains duplicate identities")
            new_rows = []
            for raw in rows:
                execution = ExchangeExecutionIdentity.from_dict(raw)
                if execution.symbol != symbol or execution.exec_id in exec_map:
                    raise ReportError(f"planned execution {execution.exec_id} is duplicate or mismatched")
                order = order_map.get(execution.order_id)
                if order is None and execution.order_id != position.entry_order_id:
                    raise ReportError(f"planned execution {execution.exec_id} references unknown order")
                expected_side = order.side if order is not None else position.side
                expected_link = order.order_link_id if order is not None else position.entry_order_link_id
                if execution.side != expected_side or (
                    expected_link and execution.order_link_id != expected_link
                ):
                    raise ReportError(f"planned execution {execution.exec_id} conflicts with order identity")
                exec_map[execution.exec_id] = execution
                new_rows.append(execution.to_dict())
            for order_id, order in order_map.items():
                filled = sum(
                    (Decimal(item.exec_qty) for item in exec_map.values() if item.order_id == order_id),
                    start=Decimal("0"),
                )
                if filled > Decimal(order.cum_exec_qty):
                    raise ReportError(f"planned executions exceed cumulative fill for order {order_id}")
            state["exchange_executions"] = sorted(
                [item.to_dict() for item in exec_map.values()],
                key=lambda item: (item["exec_time_ms"], item["exec_id"]),
            )
            inserted += len(new_rows)
        except (ValueError, TypeError, ExecutionIdentityError) as exc:
            if isinstance(exc, ReportError):
                raise
            raise ReportError(f"execution merge validation failed for {symbol}: {exc}") from exc

    if inserted != expected_count:
        raise ReportError("applied execution count does not match plan")
    return {
        "status": "DETACHED_BACKUP_CANDIDATE",
        "mode": "NO_DISK_OR_ENGINE_MUTATION",
        "backup": candidate,
        "inserted": inserted,
        "execution_history_complete": False,
        "reconciliation_pass": False,
        "live_resume_allowed": False,
    }



def persist_execution_merge_plan(
    local_backup: dict[str, Any], plan: dict[str, Any], *,
    persistence: Any, risk_mgr: Any,
) -> dict[str, Any]:
    """Apply a verified plan and persist it with retry-safe commit classification.

    This is an explicit local Plan B operation. It never talks to Bybit, mutates
    a live engine instance, or promotes any reconciliation/live-resume gate.
    """
    result = apply_execution_merge_plan(local_backup, plan)
    candidate = result["backup"]
    candidate_digest = hashlib.sha256(_canonical_json_bytes(candidate)).hexdigest()
    base_digest = plan.get("base_backup_sha256")
    if not isinstance(base_digest, str):
        raise ReportError("execution merge plan lacks base backup digest")
    if candidate_digest == base_digest:
        return {
            "status": "NO_NEW_EXECUTIONS",
            "persisted_backup_sha256": base_digest,
            "inserted": 0,
            "execution_history_complete": False,
            "reconciliation_pass": False,
            "live_resume_allowed": False,
        }

    try:
        observed = persistence.inspect_reconciliation_persistence(
            expected_backup_sha256=base_digest,
            candidate_sha256=candidate_digest,
        )
    except Exception as exc:
        raise ReportError(f"cannot classify Plan B reconciliation state: {exc}") from exc

    if observed == "CANDIDATE_INSTALLED_DURABLE":
        status = "ALREADY_APPLIED_DURABLE"
        persisted_digest = candidate_digest
    elif observed == "BASE_UNCHANGED":
        try:
            persisted_digest = persistence.save_reconciliation_candidate(
                candidate, expected_backup_sha256=base_digest, risk_mgr=risk_mgr,
            )
        except Exception as save_error:
            # os.replace may have succeeded even if directory fsync or the
            # acknowledgement failed. Inspect and re-fsync before deciding.
            try:
                after_error = persistence.inspect_reconciliation_persistence(
                    expected_backup_sha256=base_digest,
                    candidate_sha256=candidate_digest,
                )
            except Exception as inspect_error:
                raise ReportError(
                    f"Plan B save outcome is uncertain; save={save_error}; "
                    f"inspection={inspect_error}"
                ) from save_error
            if after_error == "CANDIDATE_INSTALLED_DURABLE":
                status = "PERSISTED_RECOVERED_AFTER_ACK_ERROR"
                persisted_digest = candidate_digest
            elif after_error == "BASE_UNCHANGED":
                raise ReportError(f"Plan B candidate was not installed: {save_error}") from save_error
            else:
                raise ReportError(
                    f"Plan B changed during interrupted save; observed={after_error}"
                ) from save_error
        else:
            if persisted_digest != candidate_digest:
                raise ReportError("Plan B persistence returned an unexpected candidate digest")
            status = "PERSISTED"
    elif observed == "BACKUP_MISSING":
        raise ReportError("Plan B backup disappeared before reconciliation persistence")
    else:
        raise ReportError(
            f"stale reconciliation plan: current Plan B state is {observed}"
        )

    return {
        "status": status,
        "persisted_backup_sha256": persisted_digest,
        "inserted": result["inserted"],
        "execution_history_complete": False,
        "reconciliation_pass": False,
        "live_resume_allowed": False,
    }


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
    conditional_by_id = {}
    for item in list(orders) + list(historical_orders):
        previous = conditional_by_id.get(item.order_id)
        if previous is None or item.updated_time_ms > previous.updated_time_ms:
            conditional_by_id[item.order_id] = item
    conditional_order_rows = [
        order_row(item)
        for item in conditional_by_id.values()
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
