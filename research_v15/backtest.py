"""Conservative, isolated v15 H1 backtest simulator.

Research-only. Assumptions are deliberately explicit; no live orders are sent.
Intrabar ambiguity is resolved against the strategy (stop before target).
Funding is not modelled and must be added before interpreting results as net-realistic.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Sequence

from research_v15.donchian_signal import donchian_breakout, ema

MAKER_FEE = 0.0002
TAKER_FEE = 0.00055
TAKER_SLIPPAGE = 0.000225


@dataclass(frozen=True)
class Bar:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Trade:
    side: str
    entry_ts: int
    exit_ts: int
    entry_price: float
    exit_price: float
    qty: float
    initial_risk_usdt: float
    gross_pnl: float
    fees: float
    slippage: float
    net_pnl: float
    r_multiple: float
    exit_reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def true_ranges(bars: Sequence[Bar]) -> list[float]:
    out = []
    previous_close = None
    for bar in bars:
        if previous_close is None:
            out.append(bar.high - bar.low)
        else:
            out.append(max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close)))
        previous_close = bar.close
    return out


def rolling_atr(bars: Sequence[Bar], period: int = 14) -> list[float]:
    if period < 1:
        raise ValueError("ATR period must be >= 1")
    tr = true_ranges(bars)
    out = []
    for i in range(len(tr)):
        start = max(0, i - period + 1)
        out.append(sum(tr[start:i + 1]) / (i - start + 1))
    return out



def limit_order_fill(bar: Bar, side: str, limit_price: float) -> float | None:
    """Return a conservative limit fill price for a bar, or None if not touched.

    A gap through the limit is filled at the opening price when that is better
    for the order; an intrabar touch is filled at the limit. This is still an
    OHLC approximation and does not model queue priority or partial fills.
    """
    if side not in ("long", "short"):
        raise ValueError("side must be 'long' or 'short'")
    if limit_price <= 0:
        raise ValueError("limit_price must be positive")
    if side == "long":
        if bar.low > limit_price:
            return None
        return min(limit_price, bar.open)
    if bar.high < limit_price:
        return None
    return max(limit_price, bar.open)



def stop_order_fill(bar: Bar, side: str, stop_price: float) -> float | None:
    """Return stop-market fill price, including adverse opening gaps.

    This OHLC approximation assumes a stop triggers when the bar crosses the
    stop. If the bar opens beyond it, the open is used instead of the stop.
    """
    if side not in ("long", "short"):
        raise ValueError("side must be 'long' or 'short'")
    if stop_price <= 0:
        raise ValueError("stop_price must be positive")
    if side == "long":
        if bar.low > stop_price:
            return None
        return min(bar.open, stop_price)
    if bar.high < stop_price:
        return None
    return max(bar.open, stop_price)


def resolve_stop_target(
    bar: Bar,
    side: str,
    stop_price: float,
    target_price: float,
    target_allowed: bool = True,
) -> tuple[float, str, bool] | None:
    """Resolve stop/target touches conservatively; stop wins if both are hit.

    Returns (raw_fill_price, reason, maker_exit), or None if neither is hit.
    """
    stop_fill = stop_order_fill(bar, side, stop_price)
    if stop_fill is not None:
        return stop_fill, "stop_or_gap", False
    if target_allowed:
        if side == "long" and bar.high >= target_price:
            return target_price, "target", True
        if side == "short" and bar.low <= target_price:
            return target_price, "target", True
    return None



def breakeven_action(
    bar: Bar,
    side: str,
    entry_price: float,
    risk_distance: float,
    trigger_r: float,
    already_moved: bool,
    entry_bar: bool = False,
) -> str | None:
    """Return 'exit', 'move', or None for conservative breakeven handling.

    If the trigger and return to entry occur in the same OHLC bar, return
    'exit' because the intrabar sequence is unknowable. Fees still apply to
    that exit, so breakeven does not imply zero net PnL.
    """
    if side not in ("long", "short"):
        raise ValueError("side must be 'long' or 'short'")
    if entry_price <= 0 or risk_distance <= 0 or trigger_r <= 0:
        raise ValueError("entry price, risk distance, and trigger must be positive")
    if already_moved or entry_bar:
        return None
    favorable = bar.high - entry_price if side == "long" else entry_price - bar.low
    if favorable < trigger_r * risk_distance:
        return None
    returned_to_entry = bar.low <= entry_price if side == "long" else bar.high >= entry_price
    return "exit" if returned_to_entry else "move"


def limit_order_expired(age_bars: int, valid_bars: int) -> bool:
    """Orders are valid for ages 1..valid_bars after the signal candle."""
    if age_bars < 0 or valid_bars < 1:
        raise ValueError("invalid order age or lifetime")
    return age_bars > valid_bars


def trade_economics(
    side: str,
    entry_price: float,
    raw_exit_price: float,
    qty: float,
    maker_entry: bool = True,
    maker_exit: bool = False,
) -> dict[str, float]:
    """Calculate gross PnL and explicit fees/slippage for a completed trade.

    Gross PnL is measured at the raw execution reference prices. Slippage is
    then deducted separately, while exit fees use the actual slipped price.
    """
    if side not in ("long", "short"):
        raise ValueError("side must be 'long' or 'short'")
    if min(entry_price, raw_exit_price, qty) <= 0:
        raise ValueError("prices and quantity must be positive")
    sign = 1.0 if side == "long" else -1.0
    exit_price = raw_exit_price if maker_exit else raw_exit_price * (1.0 - sign * TAKER_SLIPPAGE)
    entry_fee = entry_price * qty * (MAKER_FEE if maker_entry else TAKER_FEE)
    exit_fee = exit_price * qty * (MAKER_FEE if maker_exit else TAKER_FEE)
    gross = (raw_exit_price - entry_price) * qty * sign
    slippage = 0.0 if maker_exit else abs(raw_exit_price - exit_price) * qty
    fees = entry_fee + exit_fee
    net = gross - fees - slippage
    return {
        "exit_price": exit_price,
        "gross_pnl": gross,
        "fees": fees,
        "slippage": slippage,
        "net_pnl": net,
    }



def position_size(
    equity: float,
    risk_pct: float,
    entry_price: float,
    stop_distance: float,
    side: str = "long",
) -> dict[str, float]:
    """Size a position so modeled stop loss plus fees/slippage fits the risk budget.

    This covers a stop filled at its trigger price, not a gap-through-stop loss.
    Notional is capped at 1x equity; funding and portfolio-level exposure are
    not included.
    """
    if side not in ("long", "short"):
        raise ValueError("side must be 'long' or 'short'")
    if equity <= 0 or entry_price <= 0 or stop_distance <= 0 or not 0 < risk_pct <= 0.05:
        raise ValueError("invalid equity, risk percentage, entry price or stop distance")
    stop_price = entry_price - stop_distance if side == "long" else entry_price + stop_distance
    if stop_price <= 0:
        raise ValueError("stop price must be positive")
    risk_budget = equity * risk_pct
    price_loss_per_unit = stop_distance
    entry_fee_per_unit = entry_price * MAKER_FEE
    stop_exit_fee_per_unit = stop_price * TAKER_FEE
    stop_slippage_per_unit = stop_price * TAKER_SLIPPAGE
    total_stop_loss_per_unit = (
        price_loss_per_unit + entry_fee_per_unit + stop_exit_fee_per_unit + stop_slippage_per_unit
    )
    qty_by_price_risk = risk_budget / price_loss_per_unit
    qty_by_total_risk = risk_budget / total_stop_loss_per_unit
    qty_by_notional = equity / entry_price
    qty = min(qty_by_total_risk, qty_by_notional)
    planned_stop_loss = qty * price_loss_per_unit
    estimated_stop_cost = qty * (entry_fee_per_unit + stop_exit_fee_per_unit + stop_slippage_per_unit)
    total_estimated_stop_loss = planned_stop_loss + estimated_stop_cost
    return {
        "risk_budget": risk_budget,
        "qty_by_price_risk": qty_by_price_risk,
        "qty_by_total_risk": qty_by_total_risk,
        "qty_by_notional": qty_by_notional,
        "qty": qty,
        "notional": qty * entry_price,
        "planned_stop_loss": planned_stop_loss,
        "estimated_stop_cost": estimated_stop_cost,
        "total_estimated_stop_loss": total_estimated_stop_loss,
        "planned_stop_loss_pct_equity": planned_stop_loss / equity,
        "total_estimated_stop_loss_pct_equity": total_estimated_stop_loss / equity,
    }

def backtest_symbol(
    bars: Sequence[Bar],
    symbol: str = "UNKNOWN",
    starting_equity: float = 10_000.0,
    risk_pct: float = 0.01,
    donchian_period: int = 48,
    ema_fast_period: int = 50,
    ema_slow_period: int = 200,
    atr_period: int = 14,
    min_stop_pct: float = 0.018,
    stop_atr_multiple: float = 2.0,
    entry_pullback_atr: float = 0.15,
    limit_valid_bars: int = 3,
    breakeven_trigger_r: float = 0.95,
    target_r: float = 4.2,
    max_hold_bars: int = 96,
) -> dict[str, Any]:
    """Run one-symbol simulation; entries are resting limit orders after signal close.

    Position notional is capped at 1x current equity. This is a per-symbol test,
    not a multi-symbol shared-equity portfolio simulation.
    """
    if starting_equity <= 0 or not 0 < risk_pct <= 0.05:
        raise ValueError("invalid starting equity or risk_pct")
    if limit_valid_bars < 1 or max_hold_bars < 1 or target_r <= 0:
        raise ValueError("invalid order lifetime, holding period, or target")
    for i, b in enumerate(bars):
        if min(b.open, b.high, b.low, b.close) <= 0 or b.high < max(b.open, b.close, b.low) or b.low > min(b.open, b.close, b.high):
            raise ValueError(f"invalid OHLC at bar {i}")
        if i and bars[i].ts <= bars[i - 1].ts:
            raise ValueError("timestamps must be strictly increasing")

    if len(bars) < max(donchian_period, ema_slow_period, atr_period) + 2:
        return {"symbol": symbol, "bars": len(bars), "trades": [], "starting_equity": starting_equity, "ending_equity": starting_equity, "net_pnl": 0.0, "max_dd_pct": 0.0}

    atr = rolling_atr(bars, atr_period)
    candle_dicts = [{"open": b.open, "high": b.high, "low": b.low, "close": b.close} for b in bars]
    closes = [b.close for b in bars]
    fast_ema = ema(closes, ema_fast_period)
    slow_ema = ema(closes, ema_slow_period)
    equity = float(starting_equity)
    peak = equity
    max_dd = 0.0
    trades: list[Trade] = []
    pending = None
    pos = None

    def close_position(bar: Bar, raw_exit: float, reason: str, maker_exit: bool = False) -> None:
        nonlocal equity, pos, peak, max_dd
        if pos is None:
            return
        # Entry is a resting limit; stops/time exits pay taker fee and slippage.
        economics = trade_economics(pos["side"], pos["entry"], raw_exit, pos["qty"], maker_entry=True, maker_exit=maker_exit)
        exit_price = economics["exit_price"]
        gross = economics["gross_pnl"]
        fees = economics["fees"]
        slip_cost = economics["slippage"]
        net = economics["net_pnl"]
        equity += net
        trades.append(Trade(pos["side"], pos["entry_ts"], bar.ts, pos["entry"], exit_price, pos["qty"], pos["risk_usdt"], gross, fees, slip_cost, net, net / pos["risk_usdt"] if pos["risk_usdt"] else 0.0, reason))
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0.0)
        pos = None

    for i, bar in enumerate(bars):
        # Process a resting limit from an earlier completed signal. No same-close fill.
        if pos is None and pending is not None:
            age = i - pending["signal_index"]
            if limit_order_expired(age, limit_valid_bars):
                pending = None
            else:
                side = pending["side"]
                entry = limit_order_fill(bar, side, pending["limit"])
                if entry is None:
                    entry = 0.0
                if entry > 0:
                    stop_distance = max(entry * min_stop_pct, pending["atr"] * stop_atr_multiple)
                    stop = entry - stop_distance if side == "long" else entry + stop_distance
                    sizing = position_size(equity, risk_pct, entry, stop_distance, side)
                    qty = sizing["qty"]
                    if qty > 0:
                        pos = {"side": side, "entry": entry, "entry_ts": bar.ts, "entry_index": i, "stop": stop, "initial_stop": stop, "risk_usdt": sizing["planned_stop_loss"], "risk_budget": sizing["risk_budget"], "qty": qty, "target": entry + target_r * stop_distance if side == "long" else entry - target_r * stop_distance, "be_moved": False}
                    pending = None

        if pos is not None:
            side = pos["side"]
            sign = 1.0 if side == "long" else -1.0
            # Conservative OHLC handling: stop wins when intrabar order is ambiguous.
            stop_hit = bar.low <= pos["stop"] if side == "long" else bar.high >= pos["stop"]
            target_hit = (bar.high >= pos["target"] if side == "long" else bar.low <= pos["target"]) and i > pos["entry_index"]
            be_action = breakeven_action(
                bar, side, pos["entry"], pos["risk_usdt"] / pos["qty"],
                breakeven_trigger_r, pos["be_moved"], entry_bar=(i == pos["entry_index"]),
            )
            if stop_hit:
                raw_exit = stop_order_fill(bar, side, pos["stop"])
                close_position(bar, raw_exit, "stop_or_gap", maker_exit=False)
            elif be_action == "exit":
                close_position(bar, pos["entry"], "breakeven_stop_intrabar_ambiguous", maker_exit=False)
            elif target_hit:
                # The stop was already checked above; target is safe to resolve alone here.
                resolved = resolve_stop_target(bar, side, pos["stop"], pos["target"], target_allowed=True)
                if resolved is not None and resolved[1] == "target":
                    close_position(bar, resolved[0], resolved[1], maker_exit=resolved[2])
            elif i - pos["entry_index"] >= max_hold_bars:
                close_position(bar, bar.close, "time_stop", maker_exit=False)
            elif be_action == "move":
                # Lock entry price; future bars only see the updated stop.
                # The stop never moves back toward the initial risk.
                pos["stop"] = pos["entry"]
                pos["be_moved"] = True

        # Signal at close i creates an order eligible from bar i+1.
        if pos is None and pending is None and i + 1 < len(bars) and i >= max(donchian_period, ema_slow_period, atr_period):
            breakout = donchian_breakout(candle_dicts, i, donchian_period)
            signal = breakout if ((breakout == "long" and fast_ema[i] > slow_ema[i]) or (breakout == "short" and fast_ema[i] < slow_ema[i])) else None
            if signal:
                limit_price = bar.close - atr[i] * entry_pullback_atr if signal == "long" else bar.close + atr[i] * entry_pullback_atr
                pending = {"side": signal, "limit": limit_price, "atr": atr[i], "signal_index": i}

        marked_equity = equity
        if pos is not None:
            mark_sign = 1.0 if pos["side"] == "long" else -1.0
            marked_equity += (bar.close - pos["entry"]) * pos["qty"] * mark_sign
        peak = max(peak, marked_equity)
        max_dd = max(max_dd, (peak - marked_equity) / peak if peak > 0 else 0.0)

    if pos is not None:
        close_position(bars[-1], bars[-1].close, "end_of_data", maker_exit=False)

    net_pnl = equity - starting_equity
    gross_pnl = sum(t.gross_pnl for t in trades)
    costs = sum(t.fees + t.slippage for t in trades)
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl < 0]
    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = abs(sum(t.net_pnl for t in losses))
    return {
        "symbol": symbol, "bars": len(bars), "starting_equity": round(starting_equity, 2),
        "ending_equity": round(equity, 2), "net_pnl": round(net_pnl, 2),
        "gross_pnl": round(gross_pnl, 2), "costs_including_slippage": round(costs, 2),
        "trades_count": len(trades), "win_rate_pct": round(100 * len(wins) / len(trades), 2) if trades else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else (float("inf") if gross_profit else 0.0),
        "expectancy_r": round(sum(t.r_multiple for t in trades) / len(trades), 4) if trades else 0.0,
        "max_dd_pct": round(max_dd * 100, 2), "trades": [t.as_dict() for t in trades],
        "assumptions": {"maker_fee": MAKER_FEE, "taker_fee": TAKER_FEE, "taker_slippage_per_exit": TAKER_SLIPPAGE, "funding_included": False, "shared_portfolio_equity": False},
    }
