"""Deterministic accounting and portfolio-risk regression tests for v14 research engine."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).resolve().parent.parent / "Bybit_Trading_Engine_v14_research.py"
spec = importlib.util.spec_from_file_location("research_engine_accounting", ENGINE_PATH)
engine_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine_mod
spec.loader.exec_module(engine_mod)


def make_position(symbol="BTCUSDT", direction="long", entry=100.0, size=1000.0,
                  remaining=1.0, tp1_hit=False, tp1_gross=0.0, order_type="market",
                  maker_exits=False):
    return engine_mod.OpenPositionState(
        trade_id=f"T-{symbol}", symbol=symbol, direction=direction, strategy="test",
        entry_ts=1_800_000_000_000, entry_price=entry, stop_price=95.0 if direction == "long" else 105.0,
        tp1_price=106.0 if direction == "long" else 94.0,
        tp2_price=112.0 if direction == "long" else 88.0,
        initial_stop_dist=5.0, size_usdt=size, risk_usdt=50.0,
        order_type=order_type, maker_exits=maker_exits, tp1_hit=tp1_hit,
        realized_tp1_gross_usdt=tp1_gross, remaining_fraction=remaining,
        equity_at_entry=10_000.0,
    )


def make_engine():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(capital_usdt=10_000.0, timeframe="1h")
    e.risk_mgr = engine_mod.AdaptiveRiskManager(e.cfg)
    e.open_positions = {}
    e.pending = {}
    e.trade_seq = 0
    e._bar_entry_risk_budgets = {}
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e.closed_trades = []
    e._persist = lambda: None
    e.tg = type("TelegramSpy", (), {"send_message": staticmethod(lambda *_: None)})()
    return e


def test_final_close_funding_receipt_is_not_credited_on_ambiguous_exit_boundary():
    e = make_engine()
    e.funding_dir = "fixture"
    pos = make_position(size=1_000.0, remaining=0.5, tp1_hit=True, tp1_gross=10.0)
    exit_ts = 1_800_003_600_000
    pos.tp1_ts_ms = exit_ts
    e.open_positions["BTCUSDT"] = pos
    e.funding_by_symbol = {"BTCUSDT": [{"ts": exit_ts, "rate": "-0.01"}]}
    e._funding_mark_prices = {"BTCUSDT": {exit_ts: "100"}}

    e._close_position(
        pos, exit_price=100.0, exit_reason="take_profit",
        exit_ts=exit_ts, mae_r=0.0, mfe_r=1.0,
    )

    assert e.closed_trades[-1].funding_cost_usdt == 0.0


def test_final_close_funding_payment_uses_full_initial_quantity_on_boundary():
    e = make_engine()
    e.funding_dir = "fixture"
    pos = make_position(size=1_000.0, remaining=0.5, tp1_hit=True, tp1_gross=10.0)
    exit_ts = 1_800_003_600_000
    pos.tp1_ts_ms = exit_ts
    e.open_positions["BTCUSDT"] = pos
    e.funding_by_symbol = {"BTCUSDT": [{"ts": exit_ts, "rate": "0.01"}]}
    e._funding_mark_prices = {"BTCUSDT": {exit_ts: "100"}}

    e._close_position(
        pos, exit_price=100.0, exit_reason="take_profit",
        exit_ts=exit_ts, mae_r=0.0, mfe_r=1.0,
    )

    assert e.closed_trades[-1].funding_cost_usdt == 10.0


def test_mtm_defers_funding_receipt_at_current_boundary_until_next_mark():
    e = make_engine()
    e.funding_dir = "fixture"
    pos = make_position(size=1_000.0)
    boundary = pos.entry_ts + 3_600_000
    e.open_positions["BTCUSDT"] = pos
    e.funding_by_symbol = {"BTCUSDT": [{"ts": boundary, "rate": "-0.01"}]}
    e._funding_mark_prices = {"BTCUSDT": {boundary: "100"}}
    e._last_mark_prices["BTCUSDT"] = 100.0

    at_boundary = e._unrealized_pnl_at_marks(boundary)
    after_boundary = e._unrealized_pnl_at_marks(boundary + 3_600_000)

    assert abs((after_boundary - at_boundary) - 10.0) < 1e-8


def test_mtm_does_not_defer_funding_payments_at_current_boundary():
    e = make_engine()
    e.funding_dir = "fixture"
    pos = make_position(size=1_000.0)
    boundary = pos.entry_ts + 3_600_000
    e.open_positions["BTCUSDT"] = pos
    e.funding_by_symbol = {"BTCUSDT": [{"ts": boundary, "rate": "0.01"}]}
    e._funding_mark_prices = {"BTCUSDT": {boundary: "100"}}
    e._last_mark_prices["BTCUSDT"] = 100.0

    at_boundary = e._unrealized_pnl_at_marks(boundary)
    after_boundary = e._unrealized_pnl_at_marks(boundary + 3_600_000)

    assert abs(at_boundary - after_boundary) < 1e-8


def test_mtm_defers_short_funding_receipt_at_current_boundary():
    e = make_engine()
    e.funding_dir = "fixture"
    pos = make_position(symbol="ETHUSDT", direction="short", size=1_000.0)
    boundary = pos.entry_ts + 3_600_000
    e.open_positions["ETHUSDT"] = pos
    e.funding_by_symbol = {"ETHUSDT": [{"ts": boundary, "rate": "0.01"}]}
    e._funding_mark_prices = {"ETHUSDT": {boundary: "100"}}
    e._last_mark_prices["ETHUSDT"] = 100.0

    at_boundary = e._unrealized_pnl_at_marks(boundary)
    after_boundary = e._unrealized_pnl_at_marks(boundary + 3_600_000)

    assert abs((after_boundary - at_boundary) - 10.0) < 1e-8


def test_mtm_defers_tp1_receipt_and_later_credits_only_remaining_quantity():
    e = make_engine()
    e.funding_dir = "fixture"
    pos = make_position(size=1_000.0, remaining=0.5, tp1_hit=True, tp1_gross=10.0)
    boundary = pos.entry_ts + 3_600_000
    pos.tp1_ts_ms = boundary
    e.open_positions["BTCUSDT"] = pos
    e.funding_by_symbol = {"BTCUSDT": [{"ts": boundary, "rate": "-0.01"}]}
    e._funding_mark_prices = {"BTCUSDT": {boundary: "100"}}
    e._last_mark_prices["BTCUSDT"] = 100.0

    at_boundary = e._unrealized_pnl_at_marks(boundary)
    after_boundary = e._unrealized_pnl_at_marks(boundary + 3_600_000)

    assert abs((after_boundary - at_boundary) - 5.0) < 1e-8


def test_mark_to_market_equity_equals_realized_plus_unrealized():
    e = make_engine()
    e.open_positions["BTCUSDT"] = make_position(size=2_000.0)
    e._last_mark_prices["BTCUSDT"] = 103.0
    unrealized = e._unrealized_pnl_at_marks()
    e.risk_mgr.mark_to_market(unrealized, 1_800_000_000_000)
    assert e.risk_mgr.current_equity == round(
        e.risk_mgr.realized_equity + e.risk_mgr.unrealized_pnl, 4
    )
    assert e.risk_mgr.current_equity < e.risk_mgr.realized_equity + 60.0


def test_tp1_partial_position_mark_includes_realized_leg_and_remaining_leg():
    e = make_engine()
    # TP1 has realized 1% on 50% notional; remaining 50% is marked 2% above entry.
    e.open_positions["BTCUSDT"] = make_position(
        size=2_000.0, remaining=0.5, tp1_hit=True, tp1_gross=10.0,
    )
    e._last_mark_prices["BTCUSDT"] = 102.0
    value = e._unrealized_pnl_at_marks()
    expected_gross = 10.0 + 2_000.0 * 0.5 * 0.02
    expected_costs = (
        2_000.0 * engine_mod.TAKER_FEE
        + 2_000.0 * engine_mod.TAKER_SLIP
        + 2_000.0 * engine_mod.TP1_FRACTION * engine_mod.TAKER_FEE
        + 2_000.0 * engine_mod.TP1_FRACTION * engine_mod.TAKER_SLIP
        + 2_000.0 * 0.5 * (engine_mod.TAKER_FEE + engine_mod.TAKER_SLIP)
    )
    assert abs(value - (expected_gross - expected_costs)) < 1e-8


def test_portfolio_risk_budget_caps_new_position_size():
    cfg = engine_mod.BotConfig(
        capital_usdt=10_000.0, max_risk_trade_pct=1.0,
        max_portfolio_risk_pct=2.0, leverage_val=5.0, max_concurrent_positions=2,
    )
    risk = engine_mod.AdaptiveRiskManager(cfg)
    size, estimated_risk = risk.calculate_position_size(
        100.0, 95.0, order_type="market", risk_budget_usdt=37.0,
    )
    assert estimated_risk <= 37.0
    assert size > 0


def test_zero_or_negative_remaining_portfolio_budget_rejects_position():
    cfg = engine_mod.BotConfig(capital_usdt=10_000.0)
    risk = engine_mod.AdaptiveRiskManager(cfg)
    assert risk.calculate_position_size(100.0, 95.0, risk_budget_usdt=0.0) == (0.0, 0.0)
    assert risk.calculate_position_size(100.0, 95.0, risk_budget_usdt=-1.0) == (0.0, 0.0)


def test_long_and_short_unrealized_pnl_have_opposite_signs():
    e = make_engine()
    e.open_positions["BTCUSDT"] = make_position(direction="long", size=1_000.0)
    e.open_positions["ETHUSDT"] = make_position(
        symbol="ETHUSDT", direction="short", size=1_000.0,
    )
    e._last_mark_prices.update({"BTCUSDT": 101.0, "ETHUSDT": 101.0})
    both = e._unrealized_pnl_at_marks()
    e.open_positions.pop("ETHUSDT")
    long_only = e._unrealized_pnl_at_marks()
    assert both < long_only
    assert long_only > 0


def test_close_trade_reconciles_net_pnl_fees_slippage_and_realized_equity():
    e = make_engine()
    pos = make_position(size=1_000.0, order_type="market", maker_exits=False)
    e.open_positions["BTCUSDT"] = pos
    e._last_mark_prices["BTCUSDT"] = 110.0
    gross = 1_000.0 * (110.0 - 100.0) / 100.0
    expected_fees = 1_000.0 * engine_mod.TAKER_FEE + 1_000.0 * engine_mod.TAKER_FEE
    expected_slippage = 1_000.0 * engine_mod.TAKER_SLIP + 1_000.0 * engine_mod.TAKER_SLIP

    e._close_position(
        pos, exit_price=110.0, exit_reason="take_profit",
        exit_ts=1_800_003_600_000, mae_r=0.0, mfe_r=2.0,
    )

    trade = e.closed_trades[-1]
    assert trade.gross_pnl == round(gross, 2)
    assert trade.exchange_fees_usdt == round(expected_fees, 2)
    assert trade.slippage_cost_usdt == round(expected_slippage, 2)
    assert trade.pnl_usdt == round(gross - expected_fees - expected_slippage, 2)
    assert e.risk_mgr.realized_equity == round(10_000.0 + trade.pnl_usdt, 4)
    assert e.risk_mgr.current_equity == round(
        e.risk_mgr.realized_equity + e.risk_mgr.unrealized_pnl, 4
    )
    assert "BTCUSDT" not in e.open_positions


def run_simultaneous_entries(order):
    e = make_engine()
    e.cfg.max_portfolio_risk_pct = 2.0
    e.cfg.max_risk_trade_pct = 1.0
    e.cfg.max_concurrent_positions = 3
    e.risk_mgr.cfg = e.cfg
    for symbol in order:
        e.pending[symbol] = {
            "direction": "long", "entry_price": 100.0, "order_type": "market",
            "strategy": "simultaneous-test", "stop_dist": 5.0, "signal_ts": 1_799_996_400_000,
        }
    bar = engine_mod.Candle(
        ts=1_800_000_000_000, open=100.0, high=101.0,
        low=99.0, close=100.5, volume=10.0,
    )
    e._prepare_pending_entry_risk_budgets()
    for symbol in order:
        e._try_fill_pending(symbol, bar)
    return e


def test_simultaneous_entries_share_risk_budget_independent_of_symbol_order():
    first_order = run_simultaneous_entries(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    reversed_order = run_simultaneous_entries(["SOLUSDT", "ETHUSDT", "BTCUSDT"])
    assert set(first_order.open_positions) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    assert set(reversed_order.open_positions) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    first_risk = sum(p.risk_usdt for p in first_order.open_positions.values())
    reverse_risk = sum(p.risk_usdt for p in reversed_order.open_positions.values())
    assert first_risk <= 200.0
    assert reverse_risk <= 200.0
    assert abs(first_risk - reverse_risk) < 0.01


def test_position_slot_priority_uses_signal_strength_not_iteration_order():
    def selected(order):
        e = make_engine()
        e.cfg.max_concurrent_positions = 2
        e.pending = {
            "BTCUSDT": {"direction": "long", "entry_price": 100.0, "order_type": "market", "strategy": "test", "stop_dist": 5.0, "signal_ts": 1_799_996_400_000, "vol_ratio": 1.8},
            "ETHUSDT": {"direction": "long", "entry_price": 100.0, "order_type": "market", "strategy": "test", "stop_dist": 5.0, "signal_ts": 1_799_996_400_000, "vol_ratio": 2.4},
            "SOLUSDT": {"direction": "long", "entry_price": 100.0, "order_type": "market", "strategy": "test", "stop_dist": 5.0, "signal_ts": 1_799_996_400_000, "vol_ratio": 2.1},
        }
        bar = engine_mod.Candle(ts=1_800_000_000_000, open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0)
        e._prepare_pending_entry_risk_budgets()
        for symbol in order:
            e._try_fill_pending(symbol, bar)
        return set(e.open_positions)
    assert selected(["BTCUSDT", "ETHUSDT", "SOLUSDT"]) == {"ETHUSDT", "SOLUSDT"}
    assert selected(["SOLUSDT", "ETHUSDT", "BTCUSDT"]) == {"ETHUSDT", "SOLUSDT"}


def test_stopped_long_mae_uses_stop_fill_and_does_not_count_later_wick_as_mfe():
    e = make_engine()
    pos = make_position(direction="long", entry=100.0, size=1_000.0)
    e.open_positions["BTCUSDT"] = pos
    captured = {}
    e._close_position = lambda p, px, reason, ts, mae, mfe: captured.update(
        exit_price=px, reason=reason, mae=mae, mfe=mfe
    )
    history = [
        engine_mod.Candle(ts=1_800_000_000_000, open=100, high=101, low=99, close=100, volume=10),
        engine_mod.Candle(ts=1_800_003_600_000, open=100, high=120, low=90, close=110, volume=10),
    ]
    e._manage_position("BTCUSDT", history, fill_bar=False, exit_ts=1_800_007_200_000)
    assert captured["exit_price"] == 95.0
    assert captured["mae"] == 1.0
    assert captured["mfe"] == 0.0


def test_stopped_short_mae_uses_stop_fill_and_does_not_count_later_wick_as_mfe():
    e = make_engine()
    pos = make_position(symbol="ETHUSDT", direction="short", entry=100.0, size=1_000.0)
    e.open_positions["ETHUSDT"] = pos
    captured = {}
    e._close_position = lambda p, px, reason, ts, mae, mfe: captured.update(
        exit_price=px, reason=reason, mae=mae, mfe=mfe
    )
    history = [
        engine_mod.Candle(ts=1_800_000_000_000, open=100, high=101, low=99, close=100, volume=10),
        engine_mod.Candle(ts=1_800_003_600_000, open=100, high=110, low=80, close=90, volume=10),
    ]
    e._manage_position("ETHUSDT", history, fill_bar=False, exit_ts=1_800_007_200_000)
    assert captured["exit_price"] == 105.0
    assert captured["mae"] == 1.0
    assert captured["mfe"] == 0.0



def test_mtm_daily_stop_transition_is_persisted_without_trade_close():
    e = make_engine()
    e.cfg.daily_stop_loss_pct = 5.0
    e.risk_mgr.cfg = e.cfg
    e.risk_mgr.realized_equity = 10_000.0
    e.risk_mgr.unrealized_pnl = 0.0
    e.risk_mgr.current_equity = 10_000.0
    e.risk_mgr.day_start_equity = 10_000.0
    e.risk_mgr.peak_equity = 10_000.0
    e._unrealized_pnl_at_marks = lambda _ts: -600.0
    persisted = []
    e._persist = lambda: persisted.append(e.risk_mgr.to_dict().copy())

    e._update_mark_to_market(1_800_003_600_000)

    assert e.risk_mgr.daily_stop_triggered
    assert len(persisted) == 1
    assert persisted[0]["daily_stop_triggered"] is True


def test_mtm_kill_switch_transition_is_persisted_without_trade_close():
    e = make_engine()
    e.cfg.daily_stop_loss_pct = 99.0
    e.cfg.emergency_kill_switch_pct = 35.0
    e.risk_mgr.cfg = e.cfg
    e.risk_mgr.realized_equity = 10_000.0
    e.risk_mgr.unrealized_pnl = 0.0
    e.risk_mgr.current_equity = 10_000.0
    e.risk_mgr.day_start_equity = 10_000.0
    e.risk_mgr.peak_equity = 10_000.0
    e._unrealized_pnl_at_marks = lambda _ts: -3_600.0
    persisted = []
    e._persist = lambda: persisted.append(e.risk_mgr.to_dict().copy())

    e._update_mark_to_market(1_800_003_600_000)

    assert e.risk_mgr.kill_switch_triggered
    assert len(persisted) == 1
    assert persisted[0]["kill_switch_triggered"] is True



def test_tp1_transition_refreshes_and_persists_portfolio_mtm():
    e = make_engine()
    pos = make_position(size=1_000.0)
    e.open_positions["BTCUSDT"] = pos
    exit_ts = pos.entry_ts + 3_600_000
    history = [
        engine_mod.Candle(
            ts=pos.entry_ts - 14 * 3_600_000 + i * 3_600_000,
            open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0,
        )
        for i in range(15)
    ]
    history.append(engine_mod.Candle(
        ts=pos.entry_ts + 3_600_000,
        open=106.7, high=107.0, low=106.5, close=106.8, volume=10.0,
    ))
    e._last_mark_prices["BTCUSDT"] = 106.8
    e._intrabar_risk_marks["BTCUSDT"] = 106.5
    e._intrabar_risk_marks_ts = exit_ts
    e._update_mark_to_market(exit_ts)
    persisted = []
    e._persist = lambda: persisted.append({
        "risk": e.risk_mgr.to_dict().copy(),
        "tp1_hit": e.open_positions["BTCUSDT"].tp1_hit,
    })

    e._manage_position("BTCUSDT", history, fill_bar=False, exit_ts=exit_ts)

    assert pos.tp1_hit is True
    expected = e._unrealized_pnl_at_marks(exit_ts)
    assert abs(e.risk_mgr.unrealized_pnl - expected) < 1e-8
    assert abs(
        e.risk_mgr.current_equity
        - (e.risk_mgr.realized_equity + expected)
    ) < 1e-8
    assert persisted and persisted[-1]["tp1_hit"] is True
    assert abs(persisted[-1]["risk"]["unrealized_pnl"] - expected) < 1e-8



def test_surviving_position_candle_state_is_persisted():
    e = make_engine()
    pos = make_position(size=1_000.0)
    e.open_positions["BTCUSDT"] = pos
    exit_ts = pos.entry_ts + 3_600_000
    history = [
        engine_mod.Candle(
            ts=pos.entry_ts - 14 * 3_600_000 + i * 3_600_000,
            open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0,
        )
        for i in range(15)
    ]
    history.append(engine_mod.Candle(
        ts=pos.entry_ts + 3_600_000,
        open=100.0, high=102.0, low=99.5, close=101.0, volume=10.0,
    ))
    e._last_mark_prices["BTCUSDT"] = 101.0
    e._intrabar_risk_marks["BTCUSDT"] = 99.5
    e._intrabar_risk_marks_ts = exit_ts
    e._update_mark_to_market(exit_ts)
    persisted = []
    e._persist = lambda: persisted.append({
        "bars_held": pos.bars_held,
        "max_favorable_px": pos.max_favorable_px,
        "max_adverse_px": pos.max_adverse_px,
        "stop_price": pos.stop_price,
    })

    e._manage_position("BTCUSDT", history, fill_bar=False, exit_ts=exit_ts)

    assert pos.bars_held == 1
    assert persisted and persisted[-1]["bars_held"] == 1
    assert persisted[-1]["max_favorable_px"] == pos.max_favorable_px
    assert persisted[-1]["max_adverse_px"] == pos.max_adverse_px



def _run_same_bar_tp1_and_stop(order):
    e = make_engine()
    tp1_pos = make_position(symbol="BTCUSDT", size=1_000.0)
    stop_pos = make_position(symbol="ETHUSDT", size=1_000.0)
    e.open_positions = {"BTCUSDT": tp1_pos, "ETHUSDT": stop_pos}
    exit_ts = tp1_pos.entry_ts + 3_600_000

    def history_for(candle):
        prior = [
            engine_mod.Candle(
                ts=tp1_pos.entry_ts - 14 * 3_600_000 + i * 3_600_000,
                open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0,
            )
            for i in range(15)
        ]
        return prior + [candle]

    histories = {
        "BTCUSDT": history_for(engine_mod.Candle(
            ts=tp1_pos.entry_ts + 3_600_000,
            open=106.7, high=107.0, low=106.5, close=106.8, volume=10.0,
        )),
        "ETHUSDT": history_for(engine_mod.Candle(
            ts=tp1_pos.entry_ts + 3_600_000,
            open=100.0, high=101.0, low=94.0, close=96.0, volume=10.0,
        )),
    }
    e._last_mark_prices.update({"BTCUSDT": 106.8, "ETHUSDT": 96.0})
    e._intrabar_risk_marks.update({"BTCUSDT": 106.5, "ETHUSDT": 95.0})
    e._intrabar_risk_marks_ts = exit_ts
    e._update_mark_to_market(exit_ts)

    for symbol in order:
        e._manage_position(symbol, histories[symbol], fill_bar=False, exit_ts=exit_ts)

    return e


def test_same_bar_tp1_on_one_symbol_and_stop_on_another_is_order_independent():
    first = _run_same_bar_tp1_and_stop(["BTCUSDT", "ETHUSDT"])
    reverse = _run_same_bar_tp1_and_stop(["ETHUSDT", "BTCUSDT"])

    for e in (first, reverse):
        assert len(e.closed_trades) == 1
        assert e.closed_trades[0].token == "ETHUSDT"
        assert e.closed_trades[0].exit_reason == "stop_loss"
        assert "BTCUSDT" in e.open_positions
        assert "ETHUSDT" not in e.open_positions
        assert e.open_positions["BTCUSDT"].tp1_hit is True
        expected_unrealized = e._unrealized_pnl_at_marks(
            e._intrabar_risk_marks_ts
        )
        assert abs(e.risk_mgr.unrealized_pnl - expected_unrealized) < 1e-8
        assert abs(
            e.risk_mgr.current_equity
            - (e.risk_mgr.realized_equity + expected_unrealized)
        ) < 1e-8

    assert first.closed_trades[0].pnl_usdt == reverse.closed_trades[0].pnl_usdt
    assert abs(first.risk_mgr.realized_equity - reverse.risk_mgr.realized_equity) < 1e-8
    assert abs(first.risk_mgr.unrealized_pnl - reverse.risk_mgr.unrealized_pnl) < 1e-8
    assert abs(first.risk_mgr.current_equity - reverse.risk_mgr.current_equity) < 1e-8
    assert abs(first.risk_mgr.max_drawdown_pct - reverse.risk_mgr.max_drawdown_pct) < 1e-8



def _run_two_same_bar_stops(order):
    e = make_engine()
    e.open_positions = {
        "BTCUSDT": make_position(symbol="BTCUSDT", size=1_000.0),
        "ETHUSDT": make_position(symbol="ETHUSDT", size=1_000.0),
    }
    exit_ts = 1_800_003_600_000
    histories = {}
    for symbol in ("BTCUSDT", "ETHUSDT"):
        pos = e.open_positions[symbol]
        prior = [
            engine_mod.Candle(
                ts=pos.entry_ts - 14 * 3_600_000 + i * 3_600_000,
                open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0,
            )
            for i in range(15)
        ]
        histories[symbol] = prior + [engine_mod.Candle(
            ts=pos.entry_ts + 3_600_000,
            open=100.0, high=101.0, low=94.0, close=96.0, volume=10.0,
        )]
    e._last_mark_prices.update({"BTCUSDT": 96.0, "ETHUSDT": 96.0})
    e._intrabar_risk_marks.update({"BTCUSDT": 95.0, "ETHUSDT": 95.0})
    e._intrabar_risk_marks_ts = exit_ts
    e._update_mark_to_market(exit_ts)
    for symbol in order:
        e._manage_position(symbol, histories[symbol], fill_bar=False, exit_ts=exit_ts)
    return e


def test_two_positions_stopped_on_same_bar_reconcile_once_independent_of_order():
    first = _run_two_same_bar_stops(["BTCUSDT", "ETHUSDT"])
    reverse = _run_two_same_bar_stops(["ETHUSDT", "BTCUSDT"])

    for e in (first, reverse):
        assert not e.open_positions
        assert len(e.closed_trades) == 2
        assert {trade.token for trade in e.closed_trades} == {"BTCUSDT", "ETHUSDT"}
        assert len({trade.id for trade in e.closed_trades}) == 2
        expected_realized = 10_000.0 + sum(t.pnl_usdt for t in e.closed_trades)
        assert abs(e.risk_mgr.realized_equity - expected_realized) < 1e-8
        assert e.risk_mgr.unrealized_pnl == 0.0
        assert abs(e.risk_mgr.current_equity - expected_realized) < 1e-8

    assert sorted(t.pnl_usdt for t in first.closed_trades) == sorted(
        t.pnl_usdt for t in reverse.closed_trades
    )
    assert abs(first.risk_mgr.realized_equity - reverse.risk_mgr.realized_equity) < 1e-8
    assert abs(first.risk_mgr.current_equity - reverse.risk_mgr.current_equity) < 1e-8
    assert abs(first.risk_mgr.max_drawdown_pct - reverse.risk_mgr.max_drawdown_pct) < 1e-8




def _metric_trade(trade_id, pnl, exit_date):
    return engine_mod.TradeRecord(
        id=trade_id, token=trade_id, direction="long",
        entry_date="2026-10-01T00:00:00Z", exit_date=exit_date,
        entry_price=100.0, exit_price=100.0, size_usdt=1_000.0,
        strategy="metric-order-test", pnl_usdt=pnl, gross_pnl=pnl,
        r_multiple=pnl / 100.0, exchange_fees_usdt=0.0,
        slippage_cost_usdt=0.0, mae=0.0, mfe=0.0,
        exit_reason="test", order_type="market", risk_usdt=100.0,
        risk_pct=1.0,
    )


def test_drawdown_is_order_independent_for_simultaneous_trade_closes():
    cfg = engine_mod.BotConfig(capital_usdt=10_000.0)
    ts = "2026-10-02T12:00:00Z"
    simultaneous = [
        _metric_trade("WIN", 100.0, ts),
        _metric_trade("LOSS", -200.0, ts),
    ]
    forward = engine_mod.MaintenanceGateAuditor.evaluate_portfolio(simultaneous, cfg)
    reverse = engine_mod.MaintenanceGateAuditor.evaluate_portfolio(list(reversed(simultaneous)), cfg)

    assert forward["net_pnl"] == reverse["net_pnl"] == -100.0
    assert forward["max_dd_pct"] == reverse["max_dd_pct"] == 1.0


def test_drawdown_uses_exit_chronology_not_input_list_order():
    cfg = engine_mod.BotConfig(capital_usdt=10_000.0)
    early = _metric_trade("EARLY", -200.0, "2026-10-02T10:00:00Z")
    late = _metric_trade("LATE", 100.0, "2026-10-02T11:00:00Z")

    chronological = engine_mod.MaintenanceGateAuditor.evaluate_portfolio([early, late], cfg)
    shuffled = engine_mod.MaintenanceGateAuditor.evaluate_portfolio([late, early], cfg)

    assert chronological["net_pnl"] == shuffled["net_pnl"] == -100.0
    assert chronological["max_dd_pct"] == shuffled["max_dd_pct"] == 2.0


if __name__ == "__main__":
    tests = [(name, value) for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for name, test in tests:
        test()
        print("PASS", name)
    print(f"{len(tests)}/{len(tests)} tests passed")

