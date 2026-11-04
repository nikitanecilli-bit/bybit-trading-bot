#!/usr/bin/env python3
"""Offline audit of timestamp coverage and collection windows for Bybit snapshots.

This tool never contacts Bybit. It reports observed cadence and gaps without
assuming that any particular cadence is sufficient for historical tradability.
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from instrument_spec_history import InstrumentSpecHistory
from bybit_risk_tiers import RiskTierHistory


def utc_ms(value: Any, field: str) -> int:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    if parsed.microsecond % 1000:
        raise ValueError(f"{field} must have millisecond precision")
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = parsed.astimezone(timezone.utc) - epoch
    return ((delta.days * 86_400 + delta.seconds) * 1000
            + delta.microseconds // 1000)


def inspect_snapshot(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: cannot read snapshot JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: snapshot root must be an object")
    fetched_text = payload.get("fetched_at")
    fetched_ms = utc_ms(fetched_text, "fetched_at")
    started_text = payload.get("collection_started_at")
    started_ms = utc_ms(started_text, "collection_started_at") if started_text is not None else None
    if started_ms is not None and started_ms > fetched_ms:
        raise ValueError(f"{path}: collection_started_at is after fetched_at")
    rows = payload.get("instruments")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: instruments must be a non-empty list")
    count = payload.get("count")
    if type(count) is not int or count != len(rows):
        raise ValueError(f"{path}: count does not match instruments")
    symbols: dict[str, str | None] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{path}: instrument row must be an object")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(f"{path}: instrument row has invalid symbol")
        symbol = symbol.strip().upper()
        if symbol in symbols:
            raise ValueError(f"{path}: duplicate symbol {symbol}")
        status = row.get("status")
        if status is not None and not isinstance(status, str):
            raise ValueError(f"{path}: status for {symbol} must be a string")
        symbols[symbol] = status
    page_observations = payload.get("page_observations")
    page_summary = None
    if page_observations is not None:
        if not isinstance(page_observations, list) or not page_observations:
            raise ValueError(f"{path}: page_observations must be a non-empty list")
        page_counts: dict[str, int] = {}
        page_durations: list[int] = []
        page_symbols: set[str] = set()
        page_symbol_counts: dict[str, int] = {}
        page_has_next: dict[str, list[bool]] = {}
        by_status: dict[str, dict[str, Any]] = {}
        previous_received: int | None = None
        last_status: str | None = None
        completed_statuses: set[str] = set()
        for item in page_observations:
            if not isinstance(item, dict):
                raise ValueError(f"{path}: page observation must be an object")
            status = item.get("status_filter")
            index = item.get("page_index")
            if not isinstance(status, str) or not status or type(index) is not int or index < 1:
                raise ValueError(f"{path}: invalid page observation status or index")
            started = utc_ms(item.get("request_started_at"), "request_started_at")
            received = utc_ms(item.get("request_completed_at"), "request_completed_at")
            if started > received:
                raise ValueError(f"{path}: page request starts after response")
            if previous_received is not None and started < previous_received:
                raise ValueError(f"{path}: page observations are not chronological")
            if started_text is not None and started < started_ms:
                raise ValueError(f"{path}: page request starts before collection_started_at")
            if received > fetched_ms:
                raise ValueError(f"{path}: page response is after fetched_at")
            if status != last_status:
                if status in completed_statuses:
                    raise ValueError(f"{path}: page observations interleave status filter groups")
                if last_status is not None:
                    completed_statuses.add(last_status)
                last_status = status
            expected_index = page_counts.get(status, 0) + 1
            if index != expected_index:
                raise ValueError(f"{path}: page indexes are not sequential for {status}")
            rows_count = item.get("row_count")
            symbols_in_page = item.get("symbols")
            has_next = item.get("has_next_page")
            if (type(rows_count) is not int or rows_count < 0
                    or not isinstance(symbols_in_page, list)
                    or len(symbols_in_page) != rows_count
                    or type(has_next) is not bool):
                raise ValueError(f"{path}: invalid page observation row metadata")
            normalized_symbols = []
            for symbol in symbols_in_page:
                if not isinstance(symbol, str) or not symbol.strip():
                    raise ValueError(f"{path}: invalid page observation symbol")
                normalized_symbols.append(symbol.strip().upper())
            if len(normalized_symbols) != len(set(normalized_symbols)):
                raise ValueError(f"{path}: duplicate page observation symbols")
            page_symbols.update(normalized_symbols)
            for symbol in normalized_symbols:
                page_symbol_counts[symbol] = page_symbol_counts.get(symbol, 0) + 1
            page_counts[status] = expected_index
            page_has_next.setdefault(status, []).append(has_next)
            duration = received - started
            page_durations.append(duration)
            summary = by_status.setdefault(status, {
                "page_count": 0, "first_request_started_at": item["request_started_at"],
                "last_request_completed_at": item["request_completed_at"],
                "row_count": 0,
            })
            summary["page_count"] += 1
            summary["last_request_completed_at"] = item["request_completed_at"]
            summary["row_count"] += rows_count
            previous_received = received
        for status, continuation_flags in page_has_next.items():
            if any(flag is False for flag in continuation_flags[:-1]) or continuation_flags[-1] is not False:
                raise ValueError(f"{path}: page continuation flags are inconsistent for {status}")
        category = payload.get("category")
        if "universe_history" in path.parts:
            expected_filters = ("default", "PreLaunch", "Settling", "Delivering", "Closed")
        else:
            expected_filters = {
                "linear": ("PreLaunch", "Trading", "Settling", "Delivering", "Closed"),
                "inverse": ("PreLaunch", "Trading", "Settling", "Delivering", "Closed"),
                "spot": ("Trading",),
                "option": ("PreLaunch", "Trading", "Delivering", "Closed"),
            }.get(category)
        if expected_filters is not None and tuple(page_has_next) != expected_filters:
            raise ValueError(f"{path}: page observations do not cover expected status filters in order")
        if page_symbols != set(symbols):
            raise ValueError(f"{path}: page observation symbols do not match snapshot instruments")
        page_summary = {
            "page_count": len(page_observations),
            "request_duration_ms": _distribution(page_durations),
            "status_filters": by_status,
            "duplicate_symbol_observations": [
                {"symbol": symbol, "occurrences": count}
                for symbol, count in sorted(page_symbol_counts.items()) if count > 1
            ],
        }
    return {
        "path": str(path),
        "fetched_at": fetched_text,
        "fetched_at_ms": fetched_ms,
        "collection_started_at": started_text,
        "collection_started_at_ms": started_ms,
        "collection_duration_ms": (
            fetched_ms - started_ms if started_ms is not None else None
        ),
        "count": len(rows),
        "symbols": symbols,
        "page_observations": page_summary,
    }


def _distribution(values: list[int]) -> dict[str, int | float | None]:
    if not values:
        return {"min": None, "median": None, "max": None}
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def audit_directory(directory: Path) -> dict[str, Any]:
    files = sorted(directory.glob("*.json")) if directory.is_dir() else []
    snapshots = [inspect_snapshot(path) for path in files]
    snapshots.sort(key=lambda item: item["fetched_at_ms"])
    times = [item["fetched_at_ms"] for item in snapshots]
    if len(times) != len(set(times)):
        raise ValueError(f"{directory}: duplicate fetched_at timestamps")
    intervals = []
    for previous, current in zip(snapshots, snapshots[1:]):
        start = current["collection_started_at_ms"]
        gap = (start - previous["fetched_at_ms"]
               if start is not None else
               current["fetched_at_ms"] - previous["fetched_at_ms"])
        previous_end = previous["fetched_at_ms"]
        intervals.append({
            "previous_fetched_at": previous["fetched_at"],
            "current_collection_started_at": current["collection_started_at"],
            "current_fetched_at": current["fetched_at"],
            "gap_from_previous_completion_ms": gap,
            "gap_basis": "completion_to_start" if start is not None else "completion_to_completion",
            "collection_windows_overlap": start is not None and start < previous_end,
            "symbols_added": len(set(current["symbols"]) - set(previous["symbols"])),
            "symbols_removed": len(set(previous["symbols"]) - set(current["symbols"])),
            "status_changes": sum(
                previous["symbols"][symbol] != current["symbols"][symbol]
                for symbol in set(previous["symbols"]) & set(current["symbols"])
                if previous["symbols"][symbol] is not None
                and current["symbols"][symbol] is not None
            ),
        })
    durations = [
        item["collection_duration_ms"] for item in snapshots
        if item["collection_duration_ms"] is not None
    ]
    gaps = [item["gap_from_previous_completion_ms"] for item in intervals]
    return {
        "directory": str(directory),
        "snapshot_count": len(snapshots),
        "snapshots": [{
            "path": item["path"], "fetched_at": item["fetched_at"],
            "page_observations": item["page_observations"],
        } for item in snapshots],
        "snapshots_with_page_observations": sum(
            item["page_observations"] is not None for item in snapshots
        ),
        "first_fetched_at": snapshots[0]["fetched_at"] if snapshots else None,
        "last_fetched_at": snapshots[-1]["fetched_at"] if snapshots else None,
        "collection_duration_ms": _distribution(durations),
        "collection_durations_ms": durations,
        "inter_snapshot_gap_ms": _distribution(gaps),
        "overlapping_collection_windows": sum(
            item["collection_windows_overlap"] for item in intervals
        ),
        "snapshots_missing_collection_started_at": sum(
            item["collection_started_at"] is None for item in snapshots
        ),
        "intervals": intervals,
    }



def audit_joint_market_state(
    instrument_directory: Path, risk_directory: Path,
) -> dict[str, Any]:
    """Audit every distinct as-of pair selected by the joined runtime histories."""
    instrument_files = sorted(instrument_directory.glob("*.json")) if instrument_directory.is_dir() else []
    risk_files = sorted(risk_directory.glob("*.json")) if risk_directory.is_dir() else []
    if not instrument_files or not risk_files:
        return {
            "status": "INCOMPLETE",
            "instrument_snapshot_count": len(instrument_files),
            "risk_tier_snapshot_count": len(risk_files),
            "reason": "both dated linear instrument and risk-tier archives are required",
            "skew_budget_recommendation_ms": None,
        }

    instrument_history = InstrumentSpecHistory.from_directory(instrument_directory, "linear")
    risk_history = RiskTierHistory.from_directory(risk_directory, "linear")
    boundaries = sorted({
        item.fetched_at_ms for item in instrument_history.snapshots
    } | {
        item.fetched_at_ms for item in risk_history.snapshots
    })
    seen_pairs: set[tuple[int, int]] = set()
    observations: list[dict[str, Any]] = []
    for as_of_ts in boundaries:
        eligible_instruments = [
            item for item in instrument_history.snapshots
            if item.fetched_at_ms <= as_of_ts
        ]
        eligible_risks = [
            item for item in risk_history.snapshots
            if item.fetched_at_ms <= as_of_ts
        ]
        if not eligible_instruments or not eligible_risks:
            continue
        instrument_snapshot = eligible_instruments[-1]
        risk_snapshot = eligible_risks[-1]
        pair = (instrument_snapshot.fetched_at_ms, risk_snapshot.fetched_at_ms)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        trading_symbols = {
            symbol for symbol, spec in instrument_snapshot.specs.items()
            if spec.status == "Trading"
        }
        risk_symbols = set(risk_snapshot.tiers_by_symbol)
        missing = sorted(trading_symbols - risk_symbols)
        extra = sorted(risk_symbols - trading_symbols)
        covered = len(trading_symbols & risk_symbols)
        coverage = covered / len(trading_symbols) if trading_symbols else 0.0
        tier_counts = [
            len(risk_snapshot.tiers_by_symbol[symbol])
            for symbol in sorted(trading_symbols & risk_symbols)
        ]
        observations.append({
            "as_of_boundary_ms": as_of_ts,
            "instrument_fetched_at_ms": instrument_snapshot.fetched_at_ms,
            "risk_tiers_fetched_at_ms": risk_snapshot.fetched_at_ms,
            "snapshot_skew_ms": abs(
                instrument_snapshot.fetched_at_ms - risk_snapshot.fetched_at_ms
            ),
            "instrument_age_at_boundary_ms": as_of_ts - instrument_snapshot.fetched_at_ms,
            "risk_tiers_age_at_boundary_ms": as_of_ts - risk_snapshot.fetched_at_ms,
            "trading_instrument_count": len(trading_symbols),
            "risk_tier_symbol_count": len(risk_symbols),
            "trading_symbols_with_risk_tiers": covered,
            "trading_symbol_risk_coverage": coverage,
            "trading_symbols_missing_risk_tiers": missing,
            "risk_only_symbols": extra,
            "risk_tier_count_per_covered_symbol": _distribution(tier_counts),
        })

    skews = [item["snapshot_skew_ms"] for item in observations]
    coverages = [item["trading_symbol_risk_coverage"] for item in observations]
    return {
        "status": "DATA_FOUND",
        "instrument_snapshot_count": len(instrument_history.snapshots),
        "risk_tier_snapshot_count": len(risk_history.snapshots),
        "distinct_as_of_pairs": len(observations),
        "snapshot_skew_ms": _distribution(skews),
        "snapshot_skew_observations_ms": skews,
        "trading_symbol_risk_coverage": _distribution(coverages),
        "pairs_with_missing_trading_symbol_risk_tiers": sum(
            bool(item["trading_symbols_missing_risk_tiers"]) for item in observations
        ),
        "pairs_with_zero_missing_trading_symbols": sum(
            not item["trading_symbols_missing_risk_tiers"] for item in observations
        ),
        "observations": observations,
        "skew_budget_recommendation_ms": None,
        "skew_budget_note": (
            "Observed skew is descriptive only. It does not establish safe freshness, "
            "exchange-side atomicity, or acceptable strategy risk; no budget is inferred."
        ),
    }



def build_report(root: Path) -> dict[str, Any]:
    targets = {
        "linear_universe": root / "data" / "universe_history" / "linear",
        "linear_instrument_specs": root / "data" / "instrument_specs" / "linear",
        "linear_risk_tiers": root / "data" / "instrument_specs" / "risk_limits" / "linear",
    }
    sections = {name: audit_directory(path) for name, path in targets.items()
                if name != "linear_risk_tiers"}
    joint = audit_joint_market_state(
        targets["linear_instrument_specs"], targets["linear_risk_tiers"]
    )
    any_data = any(
        len(list(path.glob("*.json"))) if path.is_dir() else 0
        for path in targets.values()
    )
    return {
        "schema_version": 2,
        "audit": "bybit_instrument_snapshot_temporal_coverage",
        "mode": "offline_only",
        "root": str(root),
        "status": "NO_DATA" if not any_data else (
            "DATA_FOUND" if joint["status"] == "DATA_FOUND" else "INCOMPLETE"
        ),
        "sections": sections,
        "joint_linear_market_state": joint,
        "interpretation": (
            "Observed snapshot spacing is not proof of continuous tradability. "
            "Collection intervals are non-atomic; missing transition events between "
            "observations remain unknown. No sufficiency threshold is assumed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--max-gap-hours", type=float, default=None,
                        help="Optional user-chosen maximum gap; no default is assumed.")
    parser.add_argument("--max-collection-minutes", type=float, default=None,
                        help="Optional user-chosen maximum collection duration.")
    parser.add_argument("--require-data", action="store_true",
                        help="Return non-zero when no snapshots are present.")
    args = parser.parse_args()
    if args.max_gap_hours is not None and args.max_gap_hours < 0:
        parser.error("--max-gap-hours cannot be negative")
    if args.max_collection_minutes is not None and args.max_collection_minutes < 0:
        parser.error("--max-collection-minutes cannot be negative")
    report = build_report(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.require_data and report["status"] == "NO_DATA":
        return 2
    gap_limit = args.max_gap_hours * 3_600_000 if args.max_gap_hours is not None else None
    duration_limit = (
        args.max_collection_minutes * 60_000
        if args.max_collection_minutes is not None else None
    )
    for section in report["sections"].values():
        if section["overlapping_collection_windows"]:
            return 1
        if gap_limit is not None and any(
            item["gap_from_previous_completion_ms"] > gap_limit
            for item in section["intervals"]
        ):
            return 1
        if duration_limit is not None and any(
            duration > duration_limit
            for duration in section["collection_durations_ms"]
        ):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
