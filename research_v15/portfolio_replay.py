"""Chronological portfolio replay over isolated symbol backtest candidates.

Research diagnostic only: trade signals and exits come from per-symbol runs.
This overlays shared equity and risk admission; it does not regenerate signals
after rejected entries and does not model portfolio mark-to-market or funding.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from research_v15.backtest import position_size
from research_v15.portfolio import portfolio_risk_capacity


def replay_portfolio(
    symbol_results: Sequence[Mapping[str, Any]],
    starting_equity: float = 10_000.0,
    risk_pct: float = 0.01,
    max_portfolio_risk_pct: float = 0.03,
) -> dict[str, Any]:
    """Replay candidate trades chronologically using shared equity and risk cap."""
    if not math.isfinite(starting_equity) or starting_equity <= 0:
        raise ValueError("starting_equity must be finite and positive")
    if not math.isfinite(risk_pct) or not 0 < risk_pct <= 0.05:
        raise ValueError("risk_pct must be in (0, 0.05]")
    if not math.isfinite(max_portfolio_risk_pct) or not 0 < max_portfolio_risk_pct <= 1:
        raise ValueError("max_portfolio_risk_pct must be in (0, 1]")

    candidates: list[dict[str, Any]] = []
    for result in symbol_results:
        symbol = str(result.get("symbol", "UNKNOWN"))
        for trade in result.get("trades", []):
            required = ("side", "entry_ts", "exit_ts", "entry_price", "qty", "initial_risk_usdt", "net_pnl")
            if any(key not in trade for key in required):
                raise ValueError(f"trade for {symbol} is missing required fields")
            side = trade["side"]
            entry_price = float(trade["entry_price"])
            qty = float(trade["qty"])
            initial_risk = float(trade["initial_risk_usdt"])
            net_pnl = float(trade["net_pnl"])
            if side not in ("long", "short") or entry_price <= 0 or qty <= 0 or initial_risk <= 0:
                raise ValueError(f"invalid trade sizing or side for {symbol}")
            if not all(math.isfinite(x) for x in (entry_price, qty, initial_risk, net_pnl)):
                raise ValueError(f"non-finite trade value for {symbol}")
            if int(trade["exit_ts"]) < int(trade["entry_ts"]):
                raise ValueError(f"exit precedes entry for {symbol}")
            candidates.append({**trade, "symbol": symbol})

    # Stable tie-break makes simultaneous signals reproducible.
    candidates.sort(key=lambda t: (int(t["entry_ts"]), t["symbol"], int(t["exit_ts"])))
    equity = float(starting_equity)
    peak_equity = equity
    max_drawdown = 0.0
    open_positions: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    realized_pnl = 0.0

    def realize_positions(cutoff_ts: int, inclusive: bool) -> None:
        nonlocal equity, peak_equity, max_drawdown, realized_pnl
        exiting = [
            p for p in open_positions
            if int(p["exit_ts"]) <= cutoff_ts if inclusive
        ] if inclusive else [
            p for p in open_positions if int(p["exit_ts"]) < cutoff_ts
        ]
        for position in sorted(exiting, key=lambda p: (int(p["exit_ts"]), p["symbol"])):
            equity += position["net_pnl"]
            realized_pnl += position["net_pnl"]
            peak_equity = max(peak_equity, equity)
            if peak_equity > 0:
                max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity)
            open_positions.remove(position)

    # Group entries by timestamp. Exits earlier than this timestamp are realized
    # before sizing; exits at the same timestamp are released only after entries.
    cursor = 0
    while cursor < len(candidates):
        entry_ts = int(candidates[cursor]["entry_ts"])
        realize_positions(entry_ts, inclusive=False)
        group_end = cursor
        while group_end < len(candidates) and int(candidates[group_end]["entry_ts"]) == entry_ts:
            group_end += 1

        for trade in candidates[cursor:group_end]:
            open_risks = [p["risk_usdt"] for p in open_positions]
            stop_distance = float(trade["initial_risk_usdt"]) / float(trade["qty"])
            sizing = position_size(equity, risk_pct, float(trade["entry_price"]), stop_distance, trade["side"])
            proposed_risk = float(sizing["total_estimated_stop_loss"])
            capacity = portfolio_risk_capacity(equity, max_portfolio_risk_pct, open_risks, proposed_risk)
            if not capacity["approved"] or sizing["qty"] <= 0:
                rejected.append({
                    "symbol": trade["symbol"], "entry_ts": int(trade["entry_ts"]),
                    "proposed_risk_usdt": round(proposed_risk, 8),
                    "available_risk_usdt": round(float(capacity["available_risk"]), 8),
                    "reason": "portfolio_risk_limit",
                })
                continue

            scale = float(sizing["qty"]) / float(trade["qty"])
            accepted.append({
                "symbol": trade["symbol"], "side": trade["side"],
                "entry_ts": int(trade["entry_ts"]), "exit_ts": int(trade["exit_ts"]),
                "qty": float(sizing["qty"]), "scale_factor": scale,
                "risk_usdt": proposed_risk,
                "net_pnl": float(trade["net_pnl"]) * scale,
                "exit_reason": trade.get("exit_reason", "unknown"),
            })
            open_positions.append(accepted[-1])

        realize_positions(entry_ts, inclusive=True)
        cursor = group_end

    # Realize all remaining positions by exit time.
    if open_positions:
        realize_positions(max(int(p["exit_ts"]) for p in open_positions), inclusive=True)

    total_candidates = len(candidates)
    by_symbol = {}
    for trade in candidates:
        symbol = trade["symbol"]
        stats = by_symbol.setdefault(symbol, {
            "candidate_trades": 0, "accepted_trades": 0, "rejected_trades": 0,
            "candidate_net_pnl": 0.0, "accepted_net_pnl": 0.0,
        })
        stats["candidate_trades"] += 1
        stats["candidate_net_pnl"] += float(trade["net_pnl"])
    for trade in accepted:
        stats = by_symbol[trade["symbol"]]
        stats["accepted_trades"] += 1
        stats["accepted_net_pnl"] += float(trade["net_pnl"])
    for trade in rejected:
        by_symbol[trade["symbol"]]["rejected_trades"] += 1
    symbol_summary = []
    for symbol, stats in sorted(by_symbol.items()):
        stats["candidate_net_pnl"] = round(stats["candidate_net_pnl"], 4)
        stats["accepted_net_pnl"] = round(stats["accepted_net_pnl"], 4)
        stats["acceptance_rate_pct"] = round(100 * stats["accepted_trades"] / stats["candidate_trades"], 4)
        symbol_summary.append({"symbol": symbol, **stats})
    return {
        "starting_equity": round(starting_equity, 8),
        "ending_equity": round(equity, 8),
        "net_pnl": round(equity - starting_equity, 8),
        "realized_pnl_sum": round(realized_pnl, 8),
        "reconciliation_error": round((equity - starting_equity) - realized_pnl, 10),
        "candidate_trades": total_candidates,
        "accepted_trades": len(accepted),
        "rejected_trades": len(rejected),
        "acceptance_rate_pct": round(100 * len(accepted) / total_candidates, 4) if total_candidates else 0.0,
        "max_realized_drawdown_pct": round(max_drawdown * 100, 4),
        "max_portfolio_risk_pct": max_portfolio_risk_pct * 100,
        "risk_pct_per_position": risk_pct * 100,
        "by_symbol": symbol_summary,
        "accepted": accepted,
        "rejected": rejected,
        "assumptions": {
            "candidate_signals_from_independent_symbol_backtests": True,
            "shared_equity_for_resizing": True,
            "rejected_entries_do_not_regenerate_signals": True,
            "portfolio_mark_to_market_drawdown": False,
            "funding_included": False,
            "correlation_or_gap_risk_included": False,
            "same_timestamp_exits_release_risk_after_entries": True,
        },
    }
