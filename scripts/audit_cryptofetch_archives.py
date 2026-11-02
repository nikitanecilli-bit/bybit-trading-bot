#!/usr/bin/env python3
"""Compare duplicate CryptoFetch ZIP datasets without selecting or modifying data."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

FILE_RE = re.compile(r"(?i)([a-z0-9]+usdt)_(1h|15m)_.*\.csv$")
STEP_MS = {"1h": 3_600_000, "15m": 900_000}
FIELDS = ("open", "high", "low", "close", "volume")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decimal_text(value: Any, field: str, *, positive: bool = False) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not number.is_finite() or (positive and number <= 0):
        raise ValueError(f"invalid {field}")
    normalized = number.normalize()
    return format(normalized, "f")


def parse_member(raw: Any, symbol: str, timeframe: str) -> dict[int, tuple[str, ...]]:
    text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
    reader = csv.DictReader(text)
    required = {"open_time_ms", *FIELDS}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError(f"missing columns: {sorted(required)}")
    candles: dict[int, tuple[str, ...]] = {}
    step = STEP_MS[timeframe]
    for line, row in enumerate(reader, start=2):
        try:
            ts = int(row["open_time_ms"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid timestamp at CSV line {line}") from exc
        if ts <= 0 or ts % step:
            raise ValueError(f"unaligned timestamp at CSV line {line}")
        o, h, low, close = [decimal_text(row[k], k, positive=True) for k in FIELDS[:4]]
        volume = decimal_text(row["volume"], "volume")
        if Decimal(volume) < 0:
            raise ValueError(f"negative volume at CSV line {line}")
        if Decimal(h) < max(Decimal(o), Decimal(low), Decimal(close)):
            raise ValueError(f"invalid high at CSV line {line}")
        if Decimal(low) > min(Decimal(o), Decimal(h), Decimal(close)):
            raise ValueError(f"invalid low at CSV line {line}")
        if ts in candles:
            raise ValueError(f"duplicate timestamp {ts} within {symbol} {timeframe}")
        candles[ts] = (o, h, low, close, volume)
    return candles


def inspect_archives(archive_dir: Path) -> tuple[list[dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    inventory: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for archive in sorted(archive_dir.glob("*.zip")):
        archive_hash = sha256_file(archive)
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                match = FILE_RE.fullmatch(Path(info.filename).name)
                if not match:
                    continue
                symbol, timeframe = match.group(1).upper(), match.group(2).lower()
                base = {
                    "archive": archive.name, "archive_sha256": archive_hash,
                    "member": info.filename, "symbol": symbol, "timeframe": timeframe,
                }
                try:
                    with zf.open(info) as raw:
                        candles = parse_member(raw, symbol, timeframe)
                    timestamps = sorted(candles)
                    gaps = sum(1 for a, b in zip(timestamps, timestamps[1:])
                               if b - a != STEP_MS[timeframe])
                    item = {
                        **base, "bars": len(candles), "first_ts": timestamps[0] if timestamps else None,
                        "last_ts": timestamps[-1] if timestamps else None, "gap_intervals": gaps, "has_data": bool(candles),
                        "backtest_eligible": len(candles) >= 200, "valid": True, "error": "", "candles": candles,
                    }
                    inventory.append({k: v for k, v in item.items() if k != "candles"})
                    groups[(symbol, timeframe)].append(item)
                except Exception as exc:
                    inventory.append({**base, "bars": 0, "first_ts": None,
                                      "last_ts": None, "gap_intervals": None, "has_data": False, "backtest_eligible": False,
                                      "valid": False, "error": str(exc)})
    return inventory, groups


def compare_groups(groups: dict[tuple[str, str], list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    comparisons = []
    conflicts_total = 0
    non_superset = 0
    duplicate_groups = 0
    for (symbol, timeframe), items in sorted(groups.items()):
        if len(items) < 2:
            continue
        duplicate_groups += 1
        ordered = sorted(items, key=lambda x: (x["bars"], x["archive"]), reverse=True)
        legacy_winner = ordered[0]
        for left_index in range(len(items)):
            for right_index in range(left_index + 1, len(items)):
                left, right = items[left_index], items[right_index]
                left_ts, right_ts = set(left["candles"]), set(right["candles"])
                overlap = left_ts & right_ts
                conflicts = [ts for ts in overlap if left["candles"][ts] != right["candles"][ts]]
                winner_timestamps = set(legacy_winner["candles"])
                winner_is_superset = (
                    winner_timestamps.issuperset(left_ts)
                    and winner_timestamps.issuperset(right_ts)
                )
                if not winner_is_superset:
                    non_superset += 1
                conflicts_total += len(conflicts)
                comparisons.append({
                    "symbol": symbol, "timeframe": timeframe,
                    "left_archive": left["archive"], "right_archive": right["archive"],
                    "left_bars": left["bars"], "right_bars": right["bars"],
                    "overlap_bars": len(overlap),
                    "exact_overlap_bars": len(overlap) - len(conflicts),
                    "conflicting_overlap_bars": len(conflicts),
                    "left_only_bars": len(left_ts - right_ts),
                    "right_only_bars": len(right_ts - left_ts),
                    "legacy_longest_archive": legacy_winner["archive"],
                    "legacy_longest_is_superset_of_pair": winner_is_superset,
                    "first_conflict_ts": min(conflicts) if conflicts else None,
                })
    return comparisons, {
        "duplicate_symbol_timeframe_groups": duplicate_groups,
        "pairwise_comparisons": len(comparisons),
        "conflicting_overlap_bars": conflicts_total,
        "longest_archive_not_superset_pair_count": non_superset,
    }


def write_outputs(output_dir: Path, inventory: list[dict[str, Any]],
                  comparisons: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, rows in (("archive_inventory.csv", inventory),
                           ("pairwise_comparisons.csv", comparisons)):
        fields = list(rows[0]) if rows else []
        with (output_dir / filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            if fields:
                writer.writeheader()
                writer.writerows(rows)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# CryptoFetch archive comparison",
        "",
        f"- Candidate CSV members: {summary['candidate_files']}",
        f"- Structurally valid members: {summary['valid_files']}",
        f"- Members meeting legacy 200-bar minimum: {summary['backtest_eligible_files']}",
        f"- Valid but too short for legacy backtest loader: {summary['too_short_for_backtest_files']}",
        f"- Rejected members: {summary['rejected_files']}",
        f"- Duplicate symbol/timeframe groups: {summary['duplicate_symbol_timeframe_groups']}",
        f"- Pairwise comparisons: {summary['pairwise_comparisons']}",
        f"- Conflicting overlapping candles: {summary['conflicting_overlap_bars']}",
        f"- Longest-file selections that are not pairwise supersets: {summary['longest_archive_not_superset_pair_count']}",
        "",
        "The legacy loader selects the largest row count; this audit does not change that selection.",
        "A non-superset result means the selected file omits timestamps present in another candidate.",
        "A conflicting overlap means two archives disagree on at least one OHLCV candle.",
    ]
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, default=Path("data/archives/cryptofetch"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/audits/cryptofetch_archive_comparison"))
    parser.add_argument("--allow-conflicts", action="store_true")
    args = parser.parse_args()
    inventory, groups = inspect_archives(args.archive_dir)
    comparisons, pair_summary = compare_groups(groups)
    summary = {
        "schema_version": 1,
        "archive_dir": str(args.archive_dir),
        "candidate_files": len(inventory),
        "valid_files": sum(bool(x["valid"]) for x in inventory),
        "backtest_eligible_files": sum(bool(x.get("backtest_eligible")) for x in inventory),
        "too_short_for_backtest_files": sum(bool(x["valid"]) and not bool(x.get("backtest_eligible")) for x in inventory),
        "rejected_files": sum(not bool(x["valid"]) for x in inventory),
        **pair_summary,
    }
    write_outputs(args.output_dir, inventory, comparisons, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if summary["rejected_files"]:
        return 2
    if summary["conflicting_overlap_bars"] and not args.allow_conflicts:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
