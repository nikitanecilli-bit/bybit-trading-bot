"""Provenance manifest helpers for Bybit funding archive collection.

This records what the collector requested and what the API returned. It does
not claim that an API response itself contains every exchange settlement;
that requires an independently evidenced dated settlement schedule.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone


SCHEMA_VERSION = 1


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_data_row_count(path: str | Path) -> int:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in csv.DictReader(handle)))


def verify_existing_funding_manifest(
    csv_path: str | Path,
    manifest_path: str | Path,
    *,
    symbol: str,
) -> bool:
    """Refuse to extend an archive whose previously attested bytes have changed."""
    csv_path, manifest_path = Path(csv_path), Path(manifest_path)
    if not manifest_path.is_file():
        return False
    if not csv_path.is_file():
        raise ValueError("funding manifest exists but its CSV archive is missing")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("existing funding manifest is unreadable; refusing to overwrite provenance") from exc
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("symbol") != symbol.upper():
        raise ValueError("existing funding manifest schema/symbol mismatch")
    if payload.get("csv_sha256") != sha256_file(csv_path):
        raise ValueError("existing funding CSV hash differs from its manifest; refusing to extend archive")
    if payload.get("csv_data_rows") != csv_data_row_count(csv_path):
        raise ValueError("existing funding CSV row count differs from its manifest; refusing to extend archive")
    return True


def record_funding_collection(
    csv_path: str | Path,
    manifest_path: str | Path,
    *,
    symbol: str,
    category: str,
    api_base: str,
    requested_start_ms: int,
    requested_end_ms: int,
    pages: list[dict],
    collected_at_ms: int,
) -> dict:
    csv_path, manifest_path = Path(csv_path), Path(manifest_path)
    previous = None
    if manifest_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid existing funding manifest: {manifest_path}") from exc
        if previous.get("schema_version") != SCHEMA_VERSION or previous.get("symbol") != symbol.upper():
            raise ValueError("existing funding manifest schema/symbol mismatch")
    runs = list(previous.get("runs", [])) if previous else []
    runs.append({
        "requested_start_ms": int(requested_start_ms),
        "requested_end_ms": int(requested_end_ms),
        "pages": pages,
        "collected_at_ms": int(collected_at_ms),
    })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "symbol": symbol.upper(),
        "category": category,
        "endpoint": "/v5/market/funding/history",
        "api_base": api_base.rstrip("/"),
        "csv_file": csv_path.name,
        "csv_sha256": sha256_file(csv_path),
        "csv_data_rows": csv_data_row_count(csv_path),
        "runs": runs,
        "settlement_schedule_evidence": None,
        "note": "Query provenance only; a dated authoritative settlement schedule with source snapshot hashes is still required to prove event completeness.",
        "updated_at_utc": datetime.fromtimestamp(collected_at_ms / 1000, tz=timezone.utc).isoformat(),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, manifest_path)
    return payload


def validate_funding_manifest(
    csv_path: str | Path,
    manifest_path: str | Path,
    *,
    symbol: str,
    required_start_ms: int,
    required_end_ms: int,
) -> dict:
    csv_path, manifest_path = Path(csv_path), Path(manifest_path)
    if not csv_path.is_file() or not manifest_path.is_file():
        return {"ok": False, "status": "missing_csv_or_manifest"}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"ok": False, "status": "invalid_manifest"}
    errors = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported_schema")
    if payload.get("symbol") != symbol.upper():
        errors.append("symbol_mismatch")
    if payload.get("csv_sha256") != sha256_file(csv_path):
        errors.append("csv_hash_mismatch")
    if payload.get("csv_data_rows") != csv_data_row_count(csv_path):
        errors.append("csv_row_count_mismatch")
    intervals = []
    for run in payload.get("runs", []):
        start, end = run.get("requested_start_ms"), run.get("requested_end_ms")
        pages = run.get("pages")
        if not isinstance(start, int) or not isinstance(end, int) or end < start or not isinstance(pages, list):
            errors.append("invalid_run_metadata")
            continue
        page_intervals = []
        for page in pages:
            if not isinstance(page, dict):
                errors.append("invalid_page_metadata")
                continue
            if page.get("complete") is not True:
                # A saturated API page is only a partial response; its window
                # must be covered by recursive sub-queries or later pages.
                continue
            lo, hi = page.get("request_start_ms"), page.get("request_end_ms")
            rows = page.get("response_rows")
            if (not isinstance(lo, int) or not isinstance(hi, int) or hi < lo
                    or not isinstance(rows, int) or rows < 0):
                errors.append("invalid_page_metadata")
                continue
            first_ts, last_ts = page.get("first_ts"), page.get("last_ts")
            if rows == 0:
                if first_ts is not None or last_ts is not None:
                    errors.append("invalid_empty_page_metadata")
                    continue
            else:
                if (not isinstance(first_ts, int) or not isinstance(last_ts, int)
                        or first_ts > last_ts or first_ts < lo or last_ts > hi):
                    errors.append("invalid_page_timestamp_bounds")
                    continue
            if page.get("out_of_window_rows", 0) != 0:
                errors.append("page_contains_out_of_window_rows")
                continue
            page_intervals.append((lo, hi))
        page_intervals.sort()
        cursor = start
        for lo, hi in page_intervals:
            if hi < cursor:
                continue
            if lo > cursor:
                break
            cursor = max(cursor, hi + 1)
        if cursor <= end:
            errors.append("query_window_not_fully_covered")
        else:
            intervals.append((start, end))
    intervals.sort()
    cursor = int(required_start_ms)
    for lo, hi in intervals:
        if hi < cursor:
            continue
        if lo > cursor:
            break
        cursor = max(cursor, hi + 1)
    query_coverage_ok = cursor > int(required_end_ms)
    if not query_coverage_ok:
        errors.append("required_query_interval_not_covered")
    schedule_evidence = payload.get("settlement_schedule_evidence")
    schedule_verified = False
    expected_events = set()
    if not isinstance(schedule_evidence, dict):
        errors.append("dated_settlement_schedule_evidence_missing")
    else:
        raw_schedule_path = schedule_evidence.get("path")
        expected_schedule_hash = schedule_evidence.get("sha256")
        if not isinstance(raw_schedule_path, str) or not raw_schedule_path:
            errors.append("invalid_schedule_evidence_path")
        else:
            schedule_path = Path(raw_schedule_path)
            if not schedule_path.is_absolute():
                schedule_path = manifest_path.parent / schedule_path
            if not schedule_path.is_file():
                errors.append("schedule_evidence_file_missing")
            elif not isinstance(expected_schedule_hash, str) or sha256_file(schedule_path) != expected_schedule_hash:
                errors.append("schedule_evidence_hash_mismatch")
            else:
                try:
                    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    schedule = None
                    errors.append("invalid_schedule_evidence_json")
                if isinstance(schedule, dict):
                    if (schedule.get("schema_version") != 1
                            or schedule.get("source") != "bybit_dated_instrument_snapshots"
                            or str(schedule.get("symbol", "")).upper() != symbol.upper()
                            or schedule.get("category") != payload.get("category")):
                        errors.append("schedule_evidence_identity_mismatch")
                    try:
                        schedule_start = int(schedule["coverage_start_ms"])
                        schedule_end = int(schedule["coverage_end_ms"])
                    except (KeyError, TypeError, ValueError):
                        schedule_start, schedule_end = 0, -1
                        errors.append("invalid_schedule_evidence_coverage")
                    if schedule_start > int(required_start_ms) or schedule_end < int(required_end_ms):
                        errors.append("schedule_evidence_does_not_cover_required_interval")
                    source_snapshots = schedule.get("source_snapshots")
                    if not isinstance(source_snapshots, list) or not source_snapshots:
                        errors.append("schedule_source_snapshots_missing")
                    else:
                        snapshot_times = []
                        snapshot_intervals = []
                        for snapshot in source_snapshots:
                            if not isinstance(snapshot, dict):
                                errors.append("invalid_schedule_source_snapshot")
                                continue
                            source_path_raw = snapshot.get("path")
                            source_hash = snapshot.get("sha256")
                            try:
                                fetched_at_ms = int(snapshot["fetched_at_ms"])
                                interval_minutes = int(snapshot["funding_interval_minutes"])
                            except (KeyError, TypeError, ValueError):
                                errors.append("invalid_schedule_source_snapshot_metadata")
                                continue
                            source_path = Path(str(source_path_raw or ""))
                            if not source_path.is_absolute():
                                source_path = schedule_path.parent / source_path
                            if (not source_path.is_file() or not isinstance(source_hash, str)
                                    or sha256_file(source_path) != source_hash):
                                errors.append("schedule_source_snapshot_hash_mismatch")
                            else:
                                try:
                                    source_payload = json.loads(source_path.read_text(encoding="utf-8"))
                                    source_fetched_at = datetime.fromisoformat(
                                        str(source_payload["fetched_at"]).replace("Z", "+00:00")
                                    )
                                    source_fetched_ms = int(source_fetched_at.timestamp() * 1000)
                                    source_rows = source_payload.get("instruments")
                                    matches = [
                                        row for row in source_rows or []
                                        if str(row.get("symbol", "")).upper() == symbol.upper()
                                    ]
                                    source_interval = int(matches[0]["fundingInterval"]) if len(matches) == 1 else 0
                                    if (source_payload.get("schema_version") != 1
                                            or source_payload.get("source") != "Bybit V5 GET /v5/market/instruments-info"
                                            or source_payload.get("category") != payload.get("category")
                                            or source_fetched_at.tzinfo is None
                                            or source_fetched_ms != fetched_at_ms
                                            or source_interval != interval_minutes):
                                        errors.append("schedule_source_snapshot_metadata_mismatch")
                                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                                    errors.append("invalid_schedule_source_snapshot")
                            if interval_minutes not in {60, 120, 240, 480}:
                                errors.append("invalid_funding_interval_minutes")
                            snapshot_times.append(fetched_at_ms)
                            snapshot_intervals.append((fetched_at_ms, interval_minutes))
                        if snapshot_times != sorted(set(snapshot_times)):
                            errors.append("schedule_source_snapshots_not_strictly_ordered")
                        elif snapshot_times and (
                            snapshot_times[0] > int(required_start_ms)
                            or snapshot_times[-1] < int(required_end_ms)
                        ):
                            errors.append("schedule_source_snapshots_do_not_bracket_interval")
                    # Do not trust the schedule's expected-timestamp list as
                    # its own proof. Reconstruct the UTC settlement grid from
                    # the dated instrument snapshots when the interval is
                    # unchanged throughout the required window. If it changed,
                    # snapshot timestamps alone do not establish the exact
                    # effective boundary, so fail closed.
                    distinct_intervals = {interval for _, interval in snapshot_intervals}
                    if len(distinct_intervals) == 1 and snapshot_times:
                        stable_interval_ms = next(iter(distinct_intervals)) * 60_000
                        first_expected = (
                            (int(required_start_ms) + stable_interval_ms - 1)
                            // stable_interval_ms
                        ) * stable_interval_ms
                        reconstructed_grid = set(range(
                            first_expected, int(required_end_ms) + 1, stable_interval_ms
                        ))
                    else:
                        reconstructed_grid = None
                        if len(distinct_intervals) > 1:
                            errors.append("funding_interval_changed_without_effective_boundary_evidence")
                    raw_expected = schedule.get("expected_settlement_timestamps_ms")
                    if not isinstance(raw_expected, list):
                        errors.append("expected_settlement_timestamps_missing")
                    else:
                        try:
                            values = [int(value) for value in raw_expected]
                            if values != sorted(set(values)):
                                raise ValueError
                            expected_events = set(values)
                            if reconstructed_grid is not None and expected_events != reconstructed_grid:
                                errors.append("expected_settlement_schedule_not_reconstructed_from_interval")
                        except (TypeError, ValueError):
                            errors.append("invalid_expected_settlement_timestamps")
                    if not errors or all(
                        error not in errors for error in (
                            "schedule_evidence_identity_mismatch",
                            "invalid_schedule_evidence_coverage",
                            "schedule_evidence_does_not_cover_required_interval",
                            "schedule_source_snapshots_missing",
                            "invalid_schedule_source_snapshot",
                            "invalid_schedule_source_snapshot_metadata",
                            "schedule_source_snapshot_hash_mismatch",
                            "schedule_source_snapshots_not_strictly_ordered",
                            "schedule_source_snapshots_do_not_bracket_interval",
                            "schedule_source_snapshot_metadata_mismatch",
                            "invalid_funding_interval_minutes",
                            "expected_settlement_timestamps_missing",
                            "invalid_expected_settlement_timestamps",
                            "funding_interval_changed_without_effective_boundary_evidence",
                            "expected_settlement_schedule_not_reconstructed_from_interval",
                        )
                    ):
                        funding_timestamps = set()
                        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                            reader = csv.DictReader(handle)
                            timestamp_column = (
                                "funding_timestamp_ms" if reader.fieldnames and "funding_timestamp_ms" in reader.fieldnames
                                else "timestamp" if reader.fieldnames and "timestamp" in reader.fieldnames
                                else None
                            )
                            if timestamp_column is None:
                                errors.append("funding_timestamp_column_missing")
                            else:
                                for row in reader:
                                    try:
                                        funding_timestamps.add(int(row[timestamp_column]))
                                    except (TypeError, ValueError, KeyError):
                                        errors.append("invalid_funding_timestamp_in_csv")
                                        break
                        expected_in_interval = {
                            ts for ts in expected_events
                            if int(required_start_ms) <= ts <= int(required_end_ms)
                        }
                        actual_in_interval = {
                            ts for ts in funding_timestamps
                            if int(required_start_ms) <= ts <= int(required_end_ms)
                        }
                        if expected_in_interval != actual_in_interval:
                            errors.append("funding_events_do_not_match_dated_schedule")
                        for event_ts in expected_in_interval:
                            applicable = [
                                interval for snapshot_ts, interval in snapshot_intervals
                                if snapshot_ts <= event_ts
                            ]
                            if not applicable:
                                errors.append("funding_event_has_no_preceding_interval_snapshot")
                                continue
                            interval_ms = applicable[-1] * 60_000
                            if event_ts % interval_ms != 0:
                                errors.append("funding_event_not_aligned_to_dated_interval")
                        if not any(error in errors for error in (
                            "funding_events_do_not_match_dated_schedule",
                            "funding_event_has_no_preceding_interval_snapshot",
                            "funding_event_not_aligned_to_dated_interval",
                        )):
                            schedule_verified = True
    return {
        "ok": not errors,
        "status": "ok" if not errors else "incomplete",
        "errors": errors,
        "query_coverage_ok": query_coverage_ok,
        "settlement_schedule_verified": schedule_verified,
        "csv_sha256": payload.get("csv_sha256"),
        "runs": len(payload.get("runs", [])),
    }
