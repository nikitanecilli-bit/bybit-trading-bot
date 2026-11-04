"""As-of lookup for timestamped, full-universe Bybit instrument snapshots."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bybit_instrument_specs import InstrumentSpec


def _utc_ms(value: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid snapshot fetched_at timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("snapshot fetched_at must include timezone")
    if parsed.microsecond % 1000:
        raise ValueError("snapshot fetched_at must have millisecond precision")
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = parsed.astimezone(timezone.utc) - epoch
    return ((delta.days * 86_400 + delta.seconds) * 1000
            + delta.microseconds // 1000)


@dataclass(frozen=True)
class InstrumentSnapshot:
    fetched_at: str
    fetched_at_ms: int
    category: str
    specs: dict[str, InstrumentSpec]


class InstrumentSpecHistory:
    """Selects only the newest complete snapshot not later than the requested time."""

    def __init__(self, snapshots: list[InstrumentSnapshot]):
        if not snapshots:
            raise ValueError("no instrument snapshots loaded")
        ordered = sorted(snapshots, key=lambda item: item.fetched_at_ms)
        times = [item.fetched_at_ms for item in ordered]
        if len(times) != len(set(times)):
            raise ValueError("duplicate instrument snapshot timestamps")
        categories = {item.category for item in ordered}
        if len(categories) != 1:
            raise ValueError("instrument snapshot categories cannot be mixed")
        self.snapshots = ordered
        self.category = ordered[0].category

    @classmethod
    def from_directory(cls, directory: str | Path,
                       category: str = "linear") -> "InstrumentSpecHistory":
        root = Path(directory)
        if not root.is_dir():
            raise ValueError(f"instrument snapshot directory does not exist: {root}")
        snapshots: list[InstrumentSnapshot] = []
        for path in sorted(root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"{path}: cannot read instrument snapshot JSON") from exc
            if (not isinstance(payload, dict)
                    or isinstance(payload.get("schema_version"), bool)
                    or not isinstance(payload.get("schema_version"), int)
                    or payload.get("schema_version") != 1):
                raise ValueError(f"{path}: unsupported instrument snapshot schema")
            snapshot_category = str(payload.get("category") or "")
            if payload.get("source") != "Bybit V5 GET /v5/market/instruments-info":
                raise ValueError(f"{path}: invalid or missing Bybit instruments-info source")
            if snapshot_category != category:
                raise ValueError(f"{path}: expected category {category}, got {snapshot_category!r}")
            fetched_at = str(payload.get("fetched_at") or "")
            fetched_at_ms = _utc_ms(fetched_at)
            rows = payload.get("instruments")
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"{path}: instruments must be a non-empty list")
            if (isinstance(payload.get("count"), bool)
                    or not isinstance(payload.get("count"), int)
                    or payload.get("count") != len(rows)):
                raise ValueError(
                    f"{path}: snapshot count {payload.get('count')!r} does not match {len(rows)} rows"
                )
            specs: dict[str, InstrumentSpec] = {};
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"{path}: instrument rows must be objects")
                # Bybit returns category on result, not on each result.list row.
                # Preserve a row-level category when present so mismatches fail closed.
                instrument = dict(row)
                instrument.setdefault("category", snapshot_category)
                spec = InstrumentSpec.from_snapshot({
                    "fetched_at": fetched_at,
                    "instrument": instrument,
                })
                if spec.category != category:
                    raise ValueError(f"{path}: instrument {spec.symbol} has wrong category")
                if spec.symbol in specs:
                    raise ValueError(f"{path}: duplicate instrument symbol {spec.symbol}")
                specs[spec.symbol] = spec
            snapshots.append(InstrumentSnapshot(
                fetched_at=fetched_at,
                fetched_at_ms=fetched_at_ms,
                category=snapshot_category,
                specs=specs,
            ))
        return cls(snapshots)

    def get_spec(self, symbol: str, as_of_ts: int, *,
                 max_age_ms: int | None = None,
                 require_trading: bool = True) -> InstrumentSpec:
        if isinstance(as_of_ts, bool) or not isinstance(as_of_ts, int):
            raise ValueError("as_of_ts must be an integer millisecond timestamp")
        eligible = [snapshot for snapshot in self.snapshots
                    if snapshot.fetched_at_ms <= as_of_ts]
        if not eligible:
            raise ValueError(
                f"no {self.category} instrument snapshot exists at or before {as_of_ts}"
            )
        selected = eligible[-1]
        age = as_of_ts - selected.fetched_at_ms
        if max_age_ms is not None:
            if max_age_ms < 0:
                raise ValueError("max_age_ms cannot be negative")
            if age > max_age_ms:
                raise ValueError(
                    f"instrument snapshot is stale for {symbol}: age_ms={age}, max_age_ms={max_age_ms}"
                )
        key = symbol.strip().upper()
        spec = selected.specs.get(key)
        if spec is None:
            raise ValueError(
                f"{key} is absent from latest full-universe snapshot at {selected.fetched_at}"
            )
        if require_trading and spec.status != "Trading":
            raise ValueError(f"{key} status at {selected.fetched_at} is {spec.status!r}, not Trading")
        return spec
