"""Conservative, isolated v15 H1 backtest simulator.

Research-only. Assumptions are deliberately explicit; no live orders are sent.
Intrabar ambiguity is resolved against the strategy (stop before target).
Funding is not modelled and must be added before interpreting results as net-realistic.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Sequence

from research_v15.donchian_signal import v15_signal

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
    if len(bars) < max(donchian_period, ema_slow_period, atr_period) + 2:
        return {"symbol": symbol, "bars": len(bars), "trades": [], "starting_equity": starting_equity, "ending_equity": starting_equity, "net_pnl": 0.0, "max_dd_pct": 0.0}

    for i, b in enumerate(bars):
        if min(b.open, b.high, b.low, b.close) <= 0 or b.high < max(b.open, b.close, b.low) or b.low > min(b.open, b.close, b.high):
            raise ValueError(f"invalid OHLC at bar {i}")
        if i and bars[i].ts <= bars[i - 1].ts:
            raise ValueError("timestamps must be strictly increasing")

    atr = rolling_atr(bars, atr_period)
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
        side_sign = 1.0 if pos["side"] == "long" else -1.0
        # Stops pay taker fee and adverse slippage; target limits pay maker fee.
        exit_price = raw_exit if maker_exit else raw_exit * (1.0 - side_sign * TAKER_SLIPPAGE)
        gross = (raw_exit - pos["entry"]) * pos["qty"] * side_sign
        entry_fee = pos["entry"] * pos["qty"] * MAKER_FEE
        exit_fee = exit_price * pos["qty"] * (MAKER_FEE if maker_exit else TAKER_FEE)
        fees = entry_fee + exit_fee
        slip_cost = 0.0 if maker_exit else abs(raw_exit - exit_price) * pos["qty"]
        net = gross - fees - slip_cost
        equity += net
        trades.append(Trade(pos["side"], pos["entry_ts"], bar.ts, pos["entry"], exit_price, pos["qty"], pos["risk_usdt"], gross, fees, slip_cost, net, net / pos["risk_usdt"] if pos["risk_usdt"] else 0.0, reason))
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0.0)
        pos = None

    for i, bar in enumerate(bars):
        # Process a resting limit from an earlier completed signal. No same-close fill.
        if pos is None and pending is not None:
            age = i - pending["signal_index"]
            if age > limit_valid_bars:
                pending = None
            elif bar.low <= pending["limit"] <= bar.high:
                side = pending["side"]
                entry = pending["limit"]
                stop_distance = max(entry * min_stop_pct, pending["atr"] * stop_atr_multiple)
                stop = entry - stop_distance if side == "long" else entry + stop_distance
                risk_cash = equity * risk_pct
                qty_by_risk = risk_cash / stop_distance
                qty_by_notional = equity / entry
                qty = min(qty_by_risk, qty_by_notional)
                if qty > 0:
                    pos = {"side": side, "entry": entry, "entry_ts": bar.ts, "entry_index": i, "stop": stop, "initial_stop": stop, "risk_usdt": stop_distance * qty, "qty": qty, "target": entry + target_r * stop_distance if side == "long" else entry - target_r * stop_distance, "be_moved": False}
                pending = None

        if pos is not None:
            side = pos["side"]
            sign = 1.0 if side == "long" else -1.0
            # Conservative OHLC handling: if stop and target both touch, stop wins.
            stop_hit = bar.low <= pos["stop"] if side == "long" else bar.high >= pos["stop"]
            target_hit = (bar.high >= pos["target"] if side == "long" else bar.low <= pos["target"]) and i > pos["entry_index"]
            if stop_hit:
                raw_exit = min(bar.open, pos["stop"]) if side == "long" else max(bar.open, pos["stop"])
                close_position(bar, raw_exit, "stop_or_gap", maker_exit=False)
            elif target_hit:
                close_position(bar, pos["target"], "target", maker_exit=True)
            elif i - pos["entry_index"] >= max_hold_bars:
                close_position(bar, bar.close, "time_stop", maker_exit=False)
            else:
                favorable = (bar.high - pos["entry"]) * sign
                if favorable >= breakeven_trigger_r * pos["risk_usdt"] / pos["qty"] and not pos["be_moved"]:
                    # Lock entry price; future bars only see the updated stop.
                    pos["stop"] = pos["entry"]
                    pos["be_moved"] = True

        # Signal at close i creates an order eligible from bar i+1.
        if pos is None and pending is None and i + 1 < len(bars) and i >= max(donchian_period, ema_slow_period, atr_period):
            candle_dicts = [{"open": x.open, "high": x.high, "low": x.low, "close": x.close} for x in bars[:i + 1]]
            signal = v15_signal(candle_dicts, i, donchian_period, ema_fast_period, ema_slow_period)
            if signal:
                limit_price = bar.close - atr[i] * entry_pullback_atr if signal == "long" else bar.close + atr[i] * entry_pullback_atr
                pending = {"side": signal, "limit": limit_price, "atr": atr[i], "signal_index": i}

        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0.0)

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
