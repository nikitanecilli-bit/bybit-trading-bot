"""Focused tests for next-bar entry behavior under gaps in the research engine copy."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).resolve().parent.parent / "Bybit_Trading_Engine_v14_research.py"
spec = importlib.util.spec_from_file_location("research_engine_gap", ENGINE_PATH)
engine_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine_mod
spec.loader.exec_module(engine_mod)


def make_engine(max_chase_pct=1.5):
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(timeframe="15m", max_chase_limit_pct=max_chase_pct)
    e.open_positions = {}
    e.pending = {}
    e.trade_seq = 0
    e._persist = lambda: None

    class RiskSpy:
        current_equity = 10_000.0
        kill_switch_triggered = False

        def __init__(self):
            self.order_types = []

        @staticmethod
        def can_open_new_trade(count):
            return True, "OK"

        def calculate_position_size(
            self, entry_price, stop_price, order_type="market",
            risk_budget_usdt=None, equity_override=None,
        ):
            self.order_types.append(order_type)
            return 1000.0, min(10.0, risk_budget_usdt) if risk_budget_usdt is not None else 10.0

        @staticmethod
        def mark_to_market(unrealized_pnl_usdt, ts_ms):
            return {"daily_stop_hit": False, "kill_switch_hit": False}

    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e._intrabar_mtm_marks = {}
    e._intrabar_liquidation_exits = {}
    e._mark_price_candles = {}
    e.liquidation_model_enabled = False
    e._intrabar_risk_marks_ts = None
    e._intrabar_mtm_marks_ts = None
    e.risk_mgr = RiskSpy()
    return e


def pending_signal(order_type="market", ref=100.0, direction="long"):
    return {
        "direction": direction, "entry_price": ref, "order_type": order_type,
        "strategy": "test", "stop_dist": 2.0,
        "breakout_level": ref - 1.0 if direction == "long" else ref + 1.0,
        "signal_ts": 1_800_000_000_000 - 15 * 60_000,
    }


def candle(open_, high, low, close, ts=1_800_000_000_000):
    return engine_mod.Candle(ts=ts, open=open_, high=high, low=low, close=close, volume=10)


def test_baseline_long_signal_records_prior_donchian_boundary():
    cfg = engine_mod.BotConfig(
        timeframe="1h", active_trading_pool=["BTCUSDT"],
        max_chase_limit_pct=3.0, min_volume_ratio=1.6,
    )
    start = 1_800_000_000_000
    history = [
        engine_mod.Candle(start + i * 3_600_000, 100.0, 101.0, 99.0, 100.0, 10.0)
        for i in range(21)
    ]
    signal = engine_mod.Candle(start + 21 * 3_600_000, 100.0, 102.5, 99.5, 102.0, 20.0)
    result = engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", history + [signal], cfg)
    assert result is not None
    assert result["direction"] == "long"
    assert result["breakout_level"] == 101.0


def test_baseline_short_signal_records_prior_donchian_boundary():
    cfg = engine_mod.BotConfig(
        timeframe="1h", active_trading_pool=["BTCUSDT"],
        max_chase_limit_pct=3.0, min_volume_ratio=1.6,
    )
    start = 1_800_000_000_000
    history = [
        engine_mod.Candle(start + i * 3_600_000, 100.0, 101.0, 99.0, 100.0, 10.0)
        for i in range(21)
    ]
    signal = engine_mod.Candle(start + 21 * 3_600_000, 100.0, 100.5, 97.5, 98.0, 20.0)
    result = engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", history + [signal], cfg)
    assert result is not None
    assert result["direction"] == "short"
    assert result["breakout_level"] == 99.0


def test_market_long_gap_above_chase_limit_is_cancelled():
    e = make_engine(max_chase_pct=1.5)
    e.pending["BTCUSDT"] = pending_signal("market", 100.0)
    opened = e._try_fill_pending("BTCUSDT", candle(103.0, 104.0, 102.5, 103.5))
    assert opened is False
    assert "BTCUSDT" not in e.open_positions
    assert "BTCUSDT" not in e.pending


def test_market_long_gap_within_limit_fills_at_next_open():
    e = make_engine(max_chase_pct=1.5)
    e.pending["BTCUSDT"] = pending_signal("market", 100.0)
    opened = e._try_fill_pending("BTCUSDT", candle(101.0, 102.0, 100.5, 101.5))
    assert opened is True
    pos = e.open_positions["BTCUSDT"]
    assert pos.entry_price == 101.0
    assert pos.stop_price == 99.0
    assert pos.breakout_level == 99.0


def test_limit_buy_gapped_below_limit_fills_at_open_not_worse_limit():
    e = make_engine(max_chase_pct=1.5)
    e.pending["BTCUSDT"] = pending_signal("limit", 100.0)
    opened = e._try_fill_pending("BTCUSDT", candle(98.0, 99.0, 97.0, 98.5))
    assert opened is True
    assert e.open_positions["BTCUSDT"].entry_price == 98.0


def test_marketable_buy_limit_gap_through_uses_taker_entry_classification():
    e = make_engine()
    e.pending["BTCUSDT"] = pending_signal("limit", 100.0, "long")
    opened = e._try_fill_pending("BTCUSDT", candle(98.0, 99.0, 97.0, 98.5))

    assert opened is True
    pos = e.open_positions["BTCUSDT"]
    assert pos.entry_price == 98.0
    assert pos.order_type == "market"
    assert e.risk_mgr.order_types == ["market"]

    # Journal accounting must also charge taker entry fee and slippage.
    record = _close_with_real_accounting(pos, 96.0, "stop_loss")
    assert record.order_type == "market"
    assert record.exchange_fees_usdt == 1.09
    assert record.slippage_cost_usdt == 0.45


def test_marketable_sell_limit_gap_through_uses_taker_entry_classification():
    e = make_engine()
    e.pending["BTCUSDT"] = pending_signal("limit", 100.0, "short")
    opened = e._try_fill_pending("BTCUSDT", candle(102.0, 103.0, 101.0, 102.5))

    assert opened is True
    pos = e.open_positions["BTCUSDT"]
    assert pos.entry_price == 102.0
    assert pos.order_type == "market"
    assert e.risk_mgr.order_types == ["market"]


def test_non_gap_limit_touch_remains_maker_proxy():
    e = make_engine()
    e.pending["BTCUSDT"] = pending_signal("limit", 100.0, "long")
    opened = e._try_fill_pending("BTCUSDT", candle(101.0, 102.0, 99.5, 100.5))

    assert opened is True
    pos = e.open_positions["BTCUSDT"]
    assert pos.entry_price == 100.0
    assert pos.order_type == "limit"
    assert e.risk_mgr.order_types == ["limit"]


def test_limit_buy_not_touched_is_not_filled():
    e = make_engine(max_chase_pct=1.5)
    e.pending["BTCUSDT"] = pending_signal("limit", 100.0)
    opened = e._try_fill_pending("BTCUSDT", candle(101.0, 102.0, 100.2, 101.5))
    assert opened is False
    assert "BTCUSDT" not in e.open_positions
    assert "BTCUSDT" not in e.pending


def make_position(direction, entry=100.0, stop=95.0):
    return engine_mod.OpenPositionState(
        trade_id="gap-stop-test",
        symbol="BTCUSDT",
        direction=direction,
        strategy="test",
        entry_ts=1_799_999_100_000,
        entry_price=entry,
        stop_price=stop,
        tp1_price=entry + 10.0 if direction == "long" else entry - 10.0,
        tp2_price=entry + 20.0 if direction == "long" else entry - 20.0,
        initial_stop_dist=abs(entry - stop),
        size_usdt=1000.0,
        risk_usdt=50.0,
        order_type="market",
    )


def test_long_stop_gap_fills_at_open_below_stop():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_998_200_000),
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_999_100_000),
        candle(90.0, 93.0, 88.0, 91.0),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1] == 90.0, captured[0][1]
    assert captured[0][2] == "stop_loss", captured[0][2]


def test_short_stop_gap_fills_at_open_above_stop():
    e = make_engine()
    pos = make_position("short", entry=100.0, stop=105.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_998_200_000),
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_999_100_000),
        candle(110.0, 112.0, 108.0, 109.0),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1] == 110.0, captured[0][1]
    assert captured[0][2] == "stop_loss", captured[0][2]


def test_long_stop_without_gap_fills_at_stop_price():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_998_200_000),
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_999_100_000),
        candle(98.0, 99.0, 94.0, 96.0),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1] == 95.0, captured[0][1]
    assert captured[0][2] == "stop_loss", captured[0][2]


def test_long_stop_wins_when_same_candle_hits_tp1():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 112, 94, 101),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1:3] == (95.0, "stop_loss")
    assert pos.tp1_hit is False
    assert pos.remaining_fraction == 1.0


def test_long_stop_wins_when_same_candle_hits_tp2():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 125, 94, 101),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1:3] == (95.0, "stop_loss")
    assert pos.tp1_hit is False
    assert pos.remaining_fraction == 1.0


def test_short_stop_wins_when_same_candle_hits_tp1():
    e = make_engine()
    pos = make_position("short", entry=100.0, stop=105.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 106, 88, 99),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1:3] == (105.0, "stop_loss")
    assert pos.tp1_hit is False
    assert pos.remaining_fraction == 1.0


def test_short_stop_wins_when_same_candle_hits_tp2():
    e = make_engine()
    pos = make_position("short", entry=100.0, stop=105.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 106, 75, 99),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1:3] == (105.0, "stop_loss")
    assert pos.tp1_hit is False
    assert pos.remaining_fraction == 1.0


def test_partial_tp1_then_stop_closes_only_remaining_fraction():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    pos.tp1_price = 110.0
    pos.tp2_price = 120.0
    e.open_positions["BTCUSDT"] = pos
    # First candle reaches TP1 but not the original stop.
    first = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 111, 98, 110),
    ]
    e._close_position = lambda *args: None
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", first, False, first[-1].ts + 900_000)
    assert pos.tp1_hit is True
    assert pos.remaining_fraction == 0.5
    assert pos.realized_tp1_gross_usdt == 50.0

    # A later candle crosses the moved trailing stop; close should account for only the remainder.
    captured = []
    e._close_position = lambda *args: captured.append(args)
    second = [
        first[0], first[1],
        candle(100, 111, 98, 110),
        candle(110, 112, 99, 101),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", second, False, second[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1] == pos.stop_price
    assert captured[0][2] == "trailing_stop"
    assert pos.remaining_fraction == 0.5
    assert pos.realized_tp1_gross_usdt == 50.0



def _close_with_real_accounting(pos, exit_price, exit_reason):
    e = make_engine()
    e.cfg.capital_usdt = 10_000.0
    e.open_positions[pos.symbol] = pos
    e.closed_trades = []
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e.risk_mgr = engine_mod.AdaptiveRiskManager(e.cfg)
    e.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    e._persist = lambda: None
    exit_ts = 1_800_000_000_000
    engine_mod.UnifiedQuantEngine._close_position(
        e, pos, exit_price, exit_reason, exit_ts, mae_r=1.0, mfe_r=2.0,
    )
    assert len(e.closed_trades) == 1
    assert not e.open_positions
    return e.closed_trades[0]


def test_market_long_stop_journal_matches_independent_fee_and_slippage_math():
    pos = make_position("long", entry=100.0, stop=95.0)
    pos.size_usdt = 1_000.0
    record = _close_with_real_accounting(pos, 95.0, "stop_loss")

    gross = round(1_000.0 * (95.0 - 100.0) / 100.0, 2)
    fees = round(1_000.0 * engine_mod.TAKER_FEE + 950.0 * engine_mod.TAKER_FEE, 2)
    slip = round(1_000.0 * engine_mod.TAKER_SLIP + 950.0 * engine_mod.TAKER_SLIP, 2)
    assert record.gross_pnl == gross == -50.0
    assert record.exchange_fees_usdt == fees
    assert record.slippage_cost_usdt == slip
    assert record.pnl_usdt == round(gross - fees - slip, 2)
    assert record.pnl_usdt == -51.51


def test_limit_tp2_after_tp1_journal_accounts_for_three_execution_legs():
    pos = make_position("long", entry=100.0, stop=95.0)
    pos.order_type = "limit"
    pos.size_usdt = 1_000.0
    pos.tp1_price = 110.0
    pos.tp2_price = 120.0
    engine_mod.UnifiedQuantEngine._apply_tp1(pos)
    record = _close_with_real_accounting(pos, 120.0, "take_profit")

    gross = round(1_000.0 * 0.5 * (110.0 - 100.0) / 100.0
                  + 1_000.0 * 0.5 * (120.0 - 100.0) / 100.0, 2)
    fees = round(1_000.0 * engine_mod.MAKER_FEE
                 + 550.0 * engine_mod.MAKER_FEE
                 + 600.0 * engine_mod.MAKER_FEE, 2)
    slip = 0.0
    assert record.gross_pnl == gross == 150.0
    assert record.exchange_fees_usdt == fees == 0.43
    assert record.slippage_cost_usdt == slip
    assert record.pnl_usdt == round(gross - fees - slip, 2) == 149.57


def test_limit_tp1_then_market_trailing_stop_charges_correct_exit_fee_types():
    pos = make_position("long", entry=100.0, stop=95.0)
    pos.order_type = "limit"
    pos.size_usdt = 1_000.0
    pos.tp1_price = 110.0
    pos.tp2_price = 120.0
    engine_mod.UnifiedQuantEngine._apply_tp1(pos)
    # Remaining half exits at 105 via a taker stop; TP1 was a maker leg.
    record = _close_with_real_accounting(pos, 105.0, "trailing_stop")

    gross = round(50.0 + 500.0 * (105.0 - 100.0) / 100.0, 2)
    fees = round(1_000.0 * engine_mod.MAKER_FEE
                 + 550.0 * engine_mod.MAKER_FEE
                 + 525.0 * engine_mod.TAKER_FEE, 2)
    slip = round(525.0 * engine_mod.TAKER_SLIP, 2)
    assert record.gross_pnl == gross == 75.0
    assert record.exchange_fees_usdt == 0.60
    # Exact decimal fee sum is 0.575 USDT, rounded half-up to cents.
    assert record.slippage_cost_usdt == slip == 0.12
    assert record.pnl_usdt == 74.28



def test_market_short_stop_journal_matches_independent_fee_and_slippage_math():
    pos = make_position("short", entry=100.0, stop=105.0)
    pos.size_usdt = 1_000.0
    record = _close_with_real_accounting(pos, 105.0, "stop_loss")

    gross = round(1_000.0 * -1.0 * (105.0 - 100.0) / 100.0, 2)
    fees = round(1_000.0 * engine_mod.TAKER_FEE + 1_050.0 * engine_mod.TAKER_FEE, 2)
    slip = round(1_000.0 * engine_mod.TAKER_SLIP + 1_050.0 * engine_mod.TAKER_SLIP, 2)
    assert record.gross_pnl == gross == -50.0
    assert record.exchange_fees_usdt == fees == 1.13
    assert record.slippage_cost_usdt == slip == 0.46
    assert record.pnl_usdt == -51.59


def test_long_gap_stop_journal_uses_actual_gap_fill_price():
    pos = make_position("long", entry=100.0, stop=95.0)
    pos.size_usdt = 1_000.0
    # Stop at 95, but a gap through it fills at the candle open 90.
    record = _close_with_real_accounting(pos, 90.0, "stop_loss")

    assert record.exit_price == 90.0
    assert record.gross_pnl == -100.0
    assert record.exchange_fees_usdt == 1.05
    assert record.slippage_cost_usdt == 0.43
    assert record.pnl_usdt == -101.48


def test_financial_rounding_uses_half_up_at_half_cent():
    assert engine_mod._money_round(0.575) == 0.58
    assert engine_mod._money_round(-0.575) == -0.58
    assert engine_mod._money_round(1.005) == 1.01
    assert engine_mod._money_round(-1.005) == -1.01



def test_pending_entry_cannot_reuse_slot_freed_later_in_same_bar():
    e = make_engine()
    e.cfg.max_concurrent_positions = 1
    e.open_positions["BTCUSDT"] = make_position("long", entry=100.0, stop=95.0)
    ts = 1_800_000_000_000
    e.pending["ETHUSDT"] = {
        "direction": "long", "entry_price": 100.0, "order_type": "market",
        "strategy": "test", "stop_dist": 2.0, "signal_ts": ts - 15 * 60_000,
    }

    # Portfolio slots and risk are reserved from the bar-open state.
    budgets = e._prepare_pending_entry_risk_budgets()
    assert budgets["ETHUSDT"] == 0.0

    # Even if the existing position is processed/closed first, the pending
    # entry cannot use a slot that was unavailable at this bar's open.
    e.open_positions.pop("BTCUSDT")
    opened = e._try_fill_pending("ETHUSDT", candle(100.0, 101.0, 99.0, 100.5, ts=ts))
    assert opened is False
    assert "ETHUSDT" not in e.open_positions
    assert "ETHUSDT" not in e.pending



def test_pending_original_signal_timestamp_cannot_follow_freshness_guard():
    e = make_engine()
    signal = pending_signal("market", 100.0)
    signal["signal_origin_ts"] = signal["signal_ts"] + 1
    e.pending["BTCUSDT"] = signal

    opened = e._try_fill_pending(
        "BTCUSDT", candle(100.0, 101.0, 99.0, 100.5, ts=1_800_000_000_000),
    )
    assert opened is False
    assert "BTCUSDT" not in e.open_positions
    assert "BTCUSDT" not in e.pending


def test_pending_signal_is_removed_when_risk_gate_rejects_entry():
    e = make_engine()
    e.pending["BTCUSDT"] = pending_signal("market", 100.0)

    class RejectingRiskSpy:
        current_equity = 10_000.0
        kill_switch_triggered = False

        @staticmethod
        def can_open_new_trade(count):
            return False, "risk limit"

    e.risk_mgr = RejectingRiskSpy()
    opened = e._try_fill_pending("BTCUSDT", candle(100.0, 101.0, 99.0, 100.5))
    assert opened is False
    assert "BTCUSDT" not in e.open_positions
    assert "BTCUSDT" not in e.pending


def test_fill_bar_long_stop_does_not_count_pre_entry_or_later_favorable_wick():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    e.open_positions["BTCUSDT"] = pos
    captured = {}
    e._close_position = lambda p, px, reason, ts, mae, mfe: captured.update(
        exit_price=px, reason=reason, mae=mae, mfe=mfe
    )
    history = [
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 120, 90, 110),
    ]
    e._manage_position("BTCUSDT", history, fill_bar=True, exit_ts=history[-1].ts + 900_000)
    assert captured["exit_price"] == 95.0
    assert captured["reason"] == "stop_loss"
    assert captured["mae"] == 1.0
    assert captured["mfe"] == 0.0


def test_fill_bar_short_stop_does_not_count_pre_entry_or_later_favorable_wick():
    e = make_engine()
    pos = make_position("short", entry=100.0, stop=105.0)
    e.open_positions["BTCUSDT"] = pos
    captured = {}
    e._close_position = lambda p, px, reason, ts, mae, mfe: captured.update(
        exit_price=px, reason=reason, mae=mae, mfe=mfe
    )
    history = [
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 110, 80, 90),
    ]
    e._manage_position("BTCUSDT", history, fill_bar=True, exit_ts=history[-1].ts + 900_000)
    assert captured["exit_price"] == 105.0
    assert captured["reason"] == "stop_loss"
    assert captured["mae"] == 1.0
    assert captured["mfe"] == 0.0


def test_new_trailing_stop_is_not_applied_retroactively_to_same_candle():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    pos.tp1_hit = True
    pos.remaining_fraction = 0.5
    pos.tp1_price = 105.0
    pos.tp2_price = 130.0
    pos.max_favorable_px = 100.0
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 102, 98, 100, ts=1_799_999_100_000),
        # Low is above the old stop (95) but below the new trail computed
        # from this candle's high. The new stop must only apply next candle.
        candle(100, 111, 98, 105),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(
        e, "BTCUSDT", history, fill_bar=False, exit_ts=history[-1].ts + 900_000
    )
    assert captured == []
    assert pos.stop_price > history[-1].low
    assert "BTCUSDT" in e.open_positions


def test_short_partial_tp1_then_trailing_stop_closes_remaining_fraction():
    e = make_engine()
    pos = make_position("short", entry=100.0, stop=105.0)
    pos.tp1_price = 90.0
    pos.tp2_price = 80.0
    e.open_positions["BTCUSDT"] = pos

    first = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 101, 89, 90),
    ]
    e._close_position = lambda *args: None
    engine_mod.UnifiedQuantEngine._manage_position(
        e, "BTCUSDT", first, fill_bar=False, exit_ts=first[-1].ts + 900_000
    )
    assert pos.tp1_hit is True
    assert pos.remaining_fraction == 0.5
    assert pos.realized_tp1_gross_usdt == 50.0

    captured = []
    e._close_position = lambda *args: captured.append(args)
    second = [
        first[0], first[1], first[2],
        candle(90, 97, 88, 94),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(
        e, "BTCUSDT", second, fill_bar=False, exit_ts=second[-1].ts + 900_000
    )
    assert len(captured) == 1
    assert captured[0][1] == pos.stop_price
    assert captured[0][2] == "trailing_stop"
    assert pos.remaining_fraction == 0.5
    assert pos.realized_tp1_gross_usdt == 50.0


def _fill_bar_mtm_case(direction):
    e = make_engine()
    ts = 1_800_000_000_000
    signal = pending_signal("market", 100.0, direction)
    signal["stop_dist"] = 20.0
    e.pending["BTCUSDT"] = signal
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e._intrabar_risk_marks_ts = None
    e._bar_entry_risk_budgets = {}
    marks = []

    class FillBarRiskSpy:
        current_equity = 10_000.0
        kill_switch_triggered = False

        @staticmethod
        def on_new_timestamp(_ts):
            return None

        @staticmethod
        def can_open_new_trade(_count):
            return True, "OK"

        @staticmethod
        def calculate_position_size(_entry, _stop, order_type="market", risk_budget_usdt=None):
            return 1_000.0, 10.0

        def mark_to_market(self, unrealized_pnl, mark_ts):
            marks.append((unrealized_pnl, mark_ts))
            hit = unrealized_pnl <= -50.0
            if hit:
                self.kill_switch_triggered = True
            return {"kill_switch_hit": hit, "daily_stop_hit": False}

    e.risk_mgr = FillBarRiskSpy()
    e._unrealized_pnl_at_marks = lambda _as_of_ts=None: sum(
        pos.size_usdt
        * (1.0 if pos.direction == "long" else -1.0)
        * (e._intrabar_risk_marks.get(sym, pos.entry_price) - pos.entry_price)
        / pos.entry_price
        for sym, pos in e.open_positions.items()
    )
    e._update_mark_to_market = engine_mod.UnifiedQuantEngine._update_mark_to_market.__get__(
        e, engine_mod.UnifiedQuantEngine
    )
    e._manage_position = lambda *_args, **_kwargs: None
    e._persist = lambda: None
    e.tg = type("Notifier", (), {"send_message": lambda self, _message: None})()

    if direction == "long":
        curr = candle(100.0, 102.0, 90.0, 100.5, ts=ts)
    else:
        curr = candle(100.0, 110.0, 98.0, 99.5, ts=ts)

    e.step_candle("BTCUSDT", [curr])
    return e, marks, ts + 900_000


def test_new_long_fill_bar_adverse_mark_triggers_portfolio_kill_switch():
    e, marks, close_ts = _fill_bar_mtm_case("long")
    assert marks == [(0.0, close_ts), (-100.0, close_ts)], marks
    assert e.risk_mgr.kill_switch_triggered is True
    assert "BTCUSDT" in e.open_positions


def test_new_short_fill_bar_adverse_mark_triggers_portfolio_kill_switch():
    e, marks, close_ts = _fill_bar_mtm_case("short")
    assert marks == [(0.0, close_ts), (-100.0, close_ts)], marks
    assert e.risk_mgr.kill_switch_triggered is True
    assert "BTCUSDT" in e.open_positions


def test_portfolio_kill_switch_flattens_all_positions_and_blocks_pending_entries():
    e = make_engine()
    long_pos = make_position("long", entry=100.0, stop=90.0)
    short_pos = make_position("short", entry=100.0, stop=110.0)
    short_pos.symbol = "ETHUSDT"
    e.open_positions = {"BTCUSDT": long_pos, "ETHUSDT": short_pos}
    e._intrabar_mtm_marks = {"BTCUSDT": 90.0, "ETHUSDT": 110.0}
    e._intrabar_risk_marks = {"BTCUSDT": 90.0, "ETHUSDT": 110.0}
    e._intrabar_risk_marks_ts = 1_800_000_900_000
    e._intrabar_mtm_marks_ts = 1_800_000_900_000
    e._liquidation_exit_price = lambda *_args, **_kwargs: None
    e.tg = type("Notifier", (), {"send_message": lambda self, _message: None})()

    def trigger_kill_switch(unrealized_pnl_usdt, ts_ms):
        hit = unrealized_pnl_usdt <= -50.0
        if hit:
            e.risk_mgr.kill_switch_triggered = True
        return {"kill_switch_hit": hit, "daily_stop_hit": False}

    e.risk_mgr.mark_to_market = trigger_kill_switch
    close_ts = 1_800_000_900_000
    e._update_mark_to_market(close_ts)
    assert e.risk_mgr.kill_switch_triggered is True

    closed = []
    def capture_close(pos, price, reason, exit_ts, mae_r, mfe_r):
        closed.append((pos.symbol, price, reason, exit_ts))
        e.open_positions.pop(pos.symbol)

    e._close_position = capture_close
    start = 1_800_000_000_000 - 15 * 900_000
    history = [
        candle(100.0, 101.0, 99.0, 100.0, ts=start + i * 900_000)
        for i in range(15)
    ]
    current = candle(100.0, 101.0, 99.0, 100.0, ts=1_800_000_000_000)
    history.append(current)
    for symbol in ("BTCUSDT", "ETHUSDT"):
        engine_mod.UnifiedQuantEngine._manage_position(
            e, symbol, history, False, close_ts,
        )

    assert sorted(closed) == sorted([
        ("BTCUSDT", 90.0, "kill_switch", close_ts),
        ("ETHUSDT", 110.0, "kill_switch", close_ts),
    ])
    assert e.open_positions == {}

    e.pending["XRPUSDT"] = pending_signal()
    e.risk_mgr.can_open_new_trade = lambda _count: (False, "KILL_SWITCH")
    opened = e._try_fill_pending(
        "XRPUSDT", candle(100.0, 101.0, 99.0, 100.0, ts=1_800_000_000_000),
    )
    assert opened is False
    assert "XRPUSDT" not in e.open_positions
    assert "XRPUSDT" not in e.pending


if __name__ == "__main__":
    tests = [
        test_baseline_long_signal_records_prior_donchian_boundary,
        test_baseline_short_signal_records_prior_donchian_boundary,
        test_market_long_gap_above_chase_limit_is_cancelled,
        test_market_long_gap_within_limit_fills_at_next_open,
        test_limit_buy_gapped_below_limit_fills_at_open_not_worse_limit,
        test_marketable_buy_limit_gap_through_uses_taker_entry_classification,
        test_marketable_sell_limit_gap_through_uses_taker_entry_classification,
        test_non_gap_limit_touch_remains_maker_proxy,
        test_limit_buy_not_touched_is_not_filled,
        test_long_stop_gap_fills_at_open_below_stop,
        test_short_stop_gap_fills_at_open_above_stop,
        test_long_stop_without_gap_fills_at_stop_price,
        test_long_stop_wins_when_same_candle_hits_tp1,
        test_long_stop_wins_when_same_candle_hits_tp2,
        test_short_stop_wins_when_same_candle_hits_tp1,
        test_short_stop_wins_when_same_candle_hits_tp2,
        test_partial_tp1_then_stop_closes_only_remaining_fraction,
        test_market_long_stop_journal_matches_independent_fee_and_slippage_math,
        test_limit_tp2_after_tp1_journal_accounts_for_three_execution_legs,
        test_limit_tp1_then_market_trailing_stop_charges_correct_exit_fee_types,
        test_market_short_stop_journal_matches_independent_fee_and_slippage_math,
        test_long_gap_stop_journal_uses_actual_gap_fill_price,
        test_financial_rounding_uses_half_up_at_half_cent,
        test_pending_signal_is_removed_when_risk_gate_rejects_entry,
        test_pending_original_signal_timestamp_cannot_follow_freshness_guard,
        test_pending_entry_cannot_reuse_slot_freed_later_in_same_bar,
        test_fill_bar_long_stop_does_not_count_pre_entry_or_later_favorable_wick,
        test_fill_bar_short_stop_does_not_count_pre_entry_or_later_favorable_wick,
        test_new_trailing_stop_is_not_applied_retroactively_to_same_candle,
        test_new_long_fill_bar_adverse_mark_triggers_portfolio_kill_switch,
        test_new_short_fill_bar_adverse_mark_triggers_portfolio_kill_switch,
        test_portfolio_kill_switch_flattens_all_positions_and_blocks_pending_entries,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"{len(tests)}/{len(tests)} tests passed")