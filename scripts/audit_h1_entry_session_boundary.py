#!/usr/bin/env python3
"""Compare signal-candle vs actual-next-bar entry-session blocking (H1 only)."""
from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import Bybit_Trading_Engine_v14_research as em
from scripts.run_uploaded_dataset_backtests import read_zip_datasets

WINDOWS = (
    ("screen", "2025-10-27T00:00:00+00:00", "2026-04-29T00:00:00+00:00"),
    ("forward", "2026-04-29T00:00:00+00:00", "2026-10-27T00:00:00+00:00"),
)
HOUR = 3_600_000
VARIANTS = ("baseline", "signal_us_block", "entry_us_block", "aligned_entry_us_block")

def ms(value):
    return int(datetime.fromisoformat(value).timestamp() * 1000)

def run_one(symbol, part, period, variant):
    engine = em.UnifiedQuantEngine(journal_output_path="/tmp/ignored_session_boundary.json")
    cfg = engine.cfg
    cfg.bot_version = "h1-session-boundary-audit"
    cfg.timeframe = "1h"
    cfg.active_trading_pool = [symbol]
    cfg.capital_usdt = 10000.0
    cfg.max_risk_trade_pct = 1.0
    cfg.max_portfolio_risk_pct = 2.0
    cfg.max_concurrent_positions = 1
    cfg.daily_stop_loss_pct = 5.0
    cfg.emergency_kill_switch_pct = 30.0
    cfg.donchian_period = 20
    cfg.atr_period = 14
    cfg.min_volume_ratio = 1.6
    cfg.stop_atr_mult = 2.5
    cfg.tp1_r_multiple = 2.0
    cfg.tp2_r_multiple = 5.0
    cfg.atr_trail_mult = 3.0
    cfg.max_hold_bars = 32
    cfg.maker_entry_and_tp1 = False
    cfg.enable_h2_range_fade = False
    # Keep native engine block only for the original signal-time variant.
    if variant == "signal_us_block":
        cfg.blocked_sessions_utc = ["us"]
    cfg.validate()
    engine.risk_mgr.cfg = cfg
    engine.tg.send_message = lambda *_a, **_k: None

    original = em.QuantStrategyCore.evaluate_signal
    def filtered(sym, candles, current_cfg):
        signal = original(sym, candles, current_cfg)
        if signal is None:
            return None
        if variant in ("baseline", "signal_us_block"):
            return signal
        # A signal is evaluated on the completed candle, but its market entry
        # is at the OPEN of the following H1 candle. Block using that entry bar.
        entry_ts = candles[-1].ts + HOUR
        entry_session = em.QuantStrategyCore.get_utc_session(entry_ts)
        if entry_session == "us":
            return None
        if variant == "aligned_entry_us_block":
            prior = candles[:-1]
            if len(prior) < 25:
                return None
            ret24 = prior[-1].close / prior[-25].close - 1.0
            aligned = ret24 > 0 if signal["direction"] == "long" else ret24 < 0
            if not aligned:
                return None
        return signal

    em.QuantStrategyCore.evaluate_signal = staticmethod(filtered)
    try:
        em.check_alignment({symbol: part})
        audit = em.run_simulation_pass(
            engine, {symbol: part}, [symbol], data_label=f"{period} {variant} {symbol}"
        )
        trades = engine.closed_trades
        return {
            "period": period, "variant": variant, "symbol": symbol,
            "trades": len(trades), "net": sum(t.pnl_usdt for t in trades),
            "gross": sum(t.gross_pnl for t in trades),
            "fees": sum(t.exchange_fees_usdt for t in trades),
            "slippage": sum(t.slippage_cost_usdt for t in trades),
            "pf": audit["pf"], "expectancy_r": audit["expectancy_r"],
            "entry_us_trades": sum(t.session == "us" for t in trades),
        }
    finally:
        em.QuantStrategyCore.evaluate_signal = staticmethod(original)

def main():
    datasets = read_zip_datasets()
    eligible = {}
    start_all, end_all = ms(WINDOWS[0][1]), ms(WINDOWS[1][2])
    for (symbol, timeframe), (_, _, candles) in datasets.items():
        if timeframe == "1h" and candles[0].ts <= start_all and candles[-1].ts >= end_all - HOUR:
            eligible[symbol] = candles
    print(f"ELIGIBLE_SYMBOLS={len(eligible)}")
    results = []
    for symbol, full in sorted(eligible.items()):
        for period, start, end in WINDOWS:
            lo, hi = ms(start), ms(end)
            part = [c for c in full if lo <= c.ts < hi]
            if len(part) < 200:
                continue
            for variant in VARIANTS:
                results.append(run_one(symbol, part, period, variant))
    print("period,variant,symbol,trades,net,gross,fees,slippage,pf,expectancy_r,entry_us_trades")
    for row in results:
        print(",".join(str(row[k]) for k in (
            "period", "variant", "symbol", "trades", "net", "gross",
            "fees", "slippage", "pf", "expectancy_r", "entry_us_trades"
        )))
    for period, _, _ in WINDOWS:
        for variant in VARIANTS:
            rows = [r for r in results if r["period"] == period and r["variant"] == variant]
            if not rows:
                continue
            print(
                f"SUMMARY period={period} variant={variant} symbols={len(rows)} "
                f"trades={sum(r['trades'] for r in rows)} "
                f"profitable_symbols={sum(r['net'] > 0 for r in rows)} "
                f"net_sum={sum(r['net'] for r in rows):.2f} "
                f"median_pf={sorted(r['pf'] for r in rows)[len(rows)//2]:.4f} "
                f"entry_us_trades={sum(r['entry_us_trades'] for r in rows)}"
            )

if __name__ == "__main__":
    main()
