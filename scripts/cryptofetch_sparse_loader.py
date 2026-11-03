"""Load audited CryptoFetch H1 archives for dynamic-universe research replay.

This is a local archive reader only: no network access, exchange API, or orders.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.audit_cryptofetch_archives import inspect_archives, compare_groups
import Bybit_Trading_Engine_v14_research as em

H1_MS = 3_600_000
MIN_HA_BARS = 73


def load_cryptofetch_h1_sparse(archive_dir: str | Path, *, min_bars: int = MIN_HA_BARS):
    root = Path(archive_dir)
    if not root.is_dir():
        raise ValueError(f"CryptoFetch archive directory does not exist: {root}")
    inventory, groups = inspect_archives(root)
    comparisons, summary = compare_groups(groups)
    if summary["conflicting_overlap_bars"]:
        raise ValueError(
            f"Conflicting duplicate OHLCV bars: {summary['conflicting_overlap_bars']}"
        )
    if summary["longest_archive_not_superset_pair_count"]:
        raise ValueError(
            "Longest-file selection is not a timestamp superset for every duplicate pair"
        )
    rejected = [row for row in inventory if not row["valid"]]
    if rejected:
        raise ValueError(f"Rejected archive members: {rejected[:5]}")

    selected: dict[str, dict[str, Any]] = {}
    for (symbol, timeframe), options in groups.items():
        if timeframe != "1h":
            continue
        nonempty = [item for item in options if item["bars"] >= min_bars]
        if not nonempty:
            continue
        winner = max(nonempty, key=lambda item: (item["bars"], item["archive"], item["member"]))
        winner_ts = set(winner["candles"])
        for other in options:
            if not winner_ts.issuperset(other["candles"]):
                raise ValueError(
                    f"{symbol}: selected archive does not cover {other['archive']}/{other['member']}"
                )
        selected[symbol] = winner

    if not selected:
        raise ValueError("No H1 CryptoFetch symbols meet minimum history length")

    common_end = min(item["last_ts"] for item in selected.values())
    data: dict[str, list[em.Candle]] = {}
    manifest = []
    for symbol, item in sorted(selected.items()):
        first_ts, last_ts = item["first_ts"], item["last_ts"]
        included = first_ts <= common_end <= last_ts
        reason = "" if included else "starts_after_common_terminal_timestamp"
        manifest.append({
            "symbol": symbol,
            "archive": item["archive"],
            "archive_sha256": item["archive_sha256"],
            "member": item["member"],
            "bars_in_source": item["bars"],
            "first_ts": first_ts,
            "last_ts": last_ts,
            "common_end_ts": common_end,
            "included": included,
            "exclusion_reason": reason,
        })
        if not included:
            continue
        rows = item["candles"]
        trimmed = [(ts, values) for ts, values in sorted(rows.items()) if ts <= common_end]
        if len(trimmed) < min_bars or trimmed[-1][0] != common_end:
            manifest[-1]["included"] = False
            manifest[-1]["exclusion_reason"] = "insufficient_history_or_no_common_end_bar"
            continue
        timestamps = [ts for ts, _ in trimmed]
        if any(b - a != H1_MS for a, b in zip(timestamps, timestamps[1:])):
            raise ValueError(f"{symbol}: H1 history is not continuous")
        data[symbol] = [
            em.Candle(ts, *(float(value) for value in values))
            for ts, values in trimmed
        ]

    if len(data) < 5:
        raise ValueError(f"Only {len(data)} symbols survive sparse terminal coverage; need at least 5")
    if any(rows[-1].ts != common_end for rows in data.values()):
        raise AssertionError("loader invariant failed: selected symbols must share terminal timestamp")
    return data, manifest, {
        **summary,
        "valid_h1_symbols_before_terminal_filter": len(selected),
        "included_h1_symbols": len(data),
        "common_end_ts": common_end,
        "minimum_h1_bars": min_bars,
    }
