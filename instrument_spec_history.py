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


_INSTRUMENT_STATUS_FILTERS = {
    "linear": ("PreLaunch", "Trading", "Settling", "Delivering", "Closed"),
    "inverse": ("PreLaunch", "Trading", "Settling", "Delivering", "Closed"),
    "spot": ("Trading",),
    "option": ("PreLaunch", "Trading", "Delivering", "Closed"),
}


def _validate_page_observations(
    payload: dict[str, Any], path: Path, fetched_at_ms: int,
    collection_started_at_ms: int | None, expected_symbols: set[str],
    category: str,
) -> None:
    observations = payload.get("page_observations")
    if observations is None:
        return
    if not isinstance(observations, list) or not observations:
        raise ValueError(f"{path}: page_observations must be a non-empty list")
    if collection_started_at_ms is None:
        raise ValueError(f"{path}: page_observations require collection_started_at")
    expected_filters = _INSTRUMENT_STATUS_FILTERS.get(category)
    if expected_filters is None:
        raise ValueError(f"{path}: no page status-filter contract for {category}")
    seen_symbols: set[str] = set()
    page_counts: dict[str, int] = {}
    continuation: dict[str, list[bool]] = {}
    completed_filters: set[str] = set()
    previous_completed: int | None = None
    last_filter: str | None = None
    for item in observations:
        if not isinstance(item, dict) or set(item) != {
            "status_filter", "page_index", "request_started_at",
            "request_completed_at", "row_count", "symbols", "has_next_page",
        }:
            raise ValueError(f"{path}: invalid instrument page observation schema")
        status = item["status_filter"]
        index = item["page_index"]
        if not isinstance(status, str) or status not in expected_filters:
            raise ValueError(f"{path}: unexpected instrument status filter")
        if type(index) is not int or index < 1:
            raise ValueError(f"{path}: invalid instrument page index")
        if status != last_filter:
            if status in completed_filters:
                raise ValueError(f"{path}: instrument page status groups are interleaved")
            if expected_filters.index(status) != len(completed_filters):
                raise ValueError(f"{path}: instrument page status groups are out of order")
            if last_filter is not None:
                completed_filters.add(last_filter)
            last_filter = status
        if index != page_counts.get(status, 0) + 1:
            raise ValueError(f"{path}: instrument page indexes are not sequential for {status}")
        started_text, completed_text = item["request_started_at"], item["request_completed_at"]
        if not isinstance(started_text, str) or not isinstance(completed_text, str):
            raise ValueError(f"{path}: instrument page timestamps must be strings")
        started, completed = _utc_ms(started_text), _utc_ms(completed_text)
        if started > completed or started < collection_started_at_ms or completed > fetched_at_ms:
            raise ValueError(f"{path}: instrument page request is outside collection bounds")
        if previous_completed is not None and started < previous_completed:
            raise ValueError(f"{path}: instrument page observations are not chronological")
        rows_count, symbols, has_next = item["row_count"], item["symbols"], item["has_next_page"]
        if type(rows_count) is not int or rows_count < 0 or not isinstance(symbols, list):
            raise ValueError(f"{path}: invalid instrument page row metadata")
        if len(symbols) != rows_count or type(has_next) is not bool:
            raise ValueError(f"{path}: instrument page row count or continuation metadata mismatch")
        normalized = []
        for symbol in symbols:
            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError(f"{path}: invalid instrument page symbol")
            normalized.append(symbol.strip().upper())
        if len(normalized) != len(set(normalized)):
            raise ValueError(f"{path}: duplicate symbol within instrument page")
        seen_symbols.update(normalized)
        page_counts[status] = index
        continuation.setdefault(status, []).append(has_next)
        previous_completed = completed

    actual_filters = tuple(status for status in expected_filters if status in page_counts)
    if actual_filters != expected_filters:
        raise ValueError(f"{path}: instrument page status-filter coverage is incomplete")
    for status, flags in continuation.items():
        if any(flag is False for flag in flags[:-1]) or flags[-1] is not False:
            raise ValueError(f"{path}: instrument page continuation is inconsistent for {status}")
    if seen_symbols != expected_symbols:
        raise ValueError(f"{path}: instrument page symbols do not match snapshot instruments")


@dataclass(frozen=True)
class InstrumentIdentity:
    contract_type: str
    base_coin: str
    quote_coin: str
    settle_coin: str


@dataclass(frozen=True)
class InstrumentSnapshot:
    fetched_at: str
    fetched_at_ms: int
    collection_started_at_ms: int | None
    category: str
    specs: dict[str, InstrumentSpec]
    identities: dict[str, InstrumentIdentity]


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
        last_identity_by_symbol: dict[str, InstrumentIdentity] = {}
        for snapshot in ordered:
            for symbol, identity in snapshot.identities.items():
                previous_identity = last_identity_by_symbol.get(symbol)
                if previous_identity is not None and previous_identity != identity:
                    raise ValueError(
                        f"instrument identity changed while symbol was reused: {symbol}"
                    )
                last_identity_by_symbol[symbol] = identity
        self.snapshots = ordered
        self.category = ordered[0].category
        self.possible_renames = self._find_possible_renames(ordered)

    @staticmethod
    def _find_possible_renames(
        snapshots: list[InstrumentSnapshot],
    ) -> list[dict[str, str]]:
        candidates: list[dict[str, str]] = []
        last_symbol_by_identity: dict[InstrumentIdentity, tuple[str, str]] = {}
        for snapshot in snapshots:
            current_by_identity = {
                identity: symbol for symbol, identity in snapshot.identities.items()
            }
            for identity, new_symbol in current_by_identity.items():
                previous = last_symbol_by_identity.get(identity)
                if previous is not None:
                    old_symbol, previous_fetched_at = previous
                    if old_symbol != new_symbol:
                        candidates.append({
                            "previous_symbol": old_symbol,
                            "current_symbol": new_symbol,
                            "previous_fetched_at": previous_fetched_at,
                            "current_fetched_at": snapshot.fetched_at,
                            "classification": "possible_rename_not_proven",
                        })
                last_symbol_by_identity[identity] = (new_symbol, snapshot.fetched_at)
        return candidates

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
            raw_fetched_at = payload.get("fetched_at")
            if not isinstance(raw_fetched_at, str) or not raw_fetched_at:
                raise ValueError(f"{path}: fetched_at must be a non-empty ISO-8601 string")
            fetched_at = raw_fetched_at
            fetched_at_ms = _utc_ms(fetched_at)
            raw_started_at = payload.get("collection_started_at")
            if raw_started_at is not None and (
                    not isinstance(raw_started_at, str) or not raw_started_at):
                raise ValueError(f"{path}: collection_started_at must be an ISO-8601 string")
            started_at_ms = _utc_ms(raw_started_at) if raw_started_at is not None else None
            if started_at_ms is not None and started_at_ms > fetched_at_ms:
                raise ValueError(f"{path}: collection_started_at cannot be after fetched_at")
            rows = payload.get("instruments")
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"{path}: instruments must be a non-empty list")
            if (isinstance(payload.get("count"), bool)
                    or not isinstance(payload.get("count"), int)
                    or payload.get("count") != len(rows)):
                raise ValueError(
                    f"{path}: snapshot count {payload.get('count')!r} does not match {len(rows)} rows"
                )
            specs: dict[str, InstrumentSpec] = {}
            identities: dict[str, InstrumentIdentity] = {}
            identity_owners: dict[InstrumentIdentity, str] = {}
            _validate_page_observations(
                payload, path, fetched_at_ms, started_at_ms, set(
                    str(row.get("symbol", "")).strip().upper()
                    for row in rows if isinstance(row, dict)
                ), category,
            )
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
                identity_values = {}
                for field in ("contractType", "baseCoin", "quoteCoin", "settleCoin"):
                    value = instrument.get(field)
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(
                            f"{path}: instrument {spec.symbol} has missing or invalid identity field {field}"
                        )
                    identity_values[field] = value.strip()
                identity = InstrumentIdentity(
                    contract_type=identity_values["contractType"],
                    base_coin=identity_values["baseCoin"],
                    quote_coin=identity_values["quoteCoin"],
                    settle_coin=identity_values["settleCoin"],
                )
                other_symbol = identity_owners.get(identity)
                if other_symbol is not None and other_symbol != spec.symbol:
                    raise ValueError(
                        f"{path}: ambiguous duplicate contract identity for {other_symbol} and {spec.symbol}"
                    )
                identity_owners[identity] = spec.symbol
                specs[spec.symbol] = spec
                identities[spec.symbol] = identity
            snapshots.append(InstrumentSnapshot(
                fetched_at=fetched_at,
                fetched_at_ms=fetched_at_ms,
                collection_started_at_ms=started_at_ms,
                category=snapshot_category,
                specs=specs,
                identities=identities,
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
