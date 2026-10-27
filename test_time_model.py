"""Focused regression tests for candle-time semantics in research engine copy."""
import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).with_name("Bybit_Trading_Engine_v14_research.py")
spec = importlib.util.spec_from_file_location("research_engine", ENGINE_PATH)
engine_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine_mod
spec.loader.exec_module(engine_mod)


def bare_engine(timeframe="15m"):
    # Avoid notifier/config I/O; exercise only step_candle's timestamp contract.
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(timeframe=timeframe)
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e._intrabar_risk_marks_ts = None
    e.open_positions = {}
    e.pending = {}
    seen = []
    risk_timestamps = []
    e.risk_mgr = type("RiskSpy", (), {"on_new_timestamp": lambda self, ts: risk_timestamps.append(ts)})()
    e._update_mark_to_market = lambda ts: seen.append(ts)
    e._risk_timestamps = risk_timestamps
    e._persist = lambda: None
    e.step_candle = engine_mod.UnifiedQuantEngine.step_candle.__get__(e, engine_mod.UnifiedQuantEngine)
    e._try_fill_pending = lambda symbol, curr: False
    e.risk_mgr.can_open_new_trade = lambda count: (False, "test")
    return e, seen


def test_mtm_uses_close_timestamp_for_15m_bar():
    e, seen = bare_engine("15m")
    ts_open = 1_800_000_000_000
    candle = engine_mod.Candle(ts=ts_open, open=100, high=101, low=99, close=100.5, volume=10)
    e.step_candle("BTCUSDT", [candle])
    assert seen == [ts_open + 900_000], seen
    assert e._risk_timestamps == [ts_open + 900_000], e._risk_timestamps
    assert e._last_mark_prices["BTCUSDT"] == 100.5


def test_mtm_respects_configured_1h_close_boundary():
    e, seen = bare_engine("1h")
    ts_open = 1_800_000_000_000
    candle = engine_mod.Candle(ts=ts_open, open=100, high=102, low=98, close=101, volume=10)
    e.step_candle("ETHUSDT", [candle])
    assert seen == [ts_open + 3_600_000], seen
    assert e._risk_timestamps == [ts_open + 3_600_000], e._risk_timestamps



def test_open_position_management_receives_bar_close_timestamp_across_utc_midnight():
    e, _ = bare_engine("15m")
    calls = []
    e.open_positions["BTCUSDT"] = object()
    e._manage_position = lambda symbol, history, fill_bar, exit_ts: calls.append(exit_ts)
    ts_open = int(engine_mod.datetime(2026, 1, 1, 23, 45, tzinfo=engine_mod.timezone.utc).timestamp() * 1000)
    candle = engine_mod.Candle(ts=ts_open, open=100, high=101, low=99, close=100.5, volume=10)

    e.step_candle("BTCUSDT", [candle])

    expected_close_ts = ts_open + 900_000
    assert calls == [expected_close_ts], calls
    close_day = engine_mod.datetime.fromtimestamp(expected_close_ts / 1000, tz=engine_mod.timezone.utc).date()
    assert close_day.isoformat() == "2026-01-02", close_day


def test_h2_range_fade_is_disabled_by_default_and_enabled_explicitly():
    from unittest.mock import patch

    candles = [
        engine_mod.Candle(ts=1_800_000_000_000 + i * 900_000,
                          open=94.0, high=96.0, low=92.0, close=95.0, volume=10.0)
        for i in range(4)
    ]
    candles[-1] = engine_mod.Candle(ts=candles[-1].ts, open=94.0, high=96.0,
                                   low=92.0, close=95.0, volume=10.0)
    with patch.object(engine_mod.QuantStrategyCore, "compute_donchian_and_volume",
                      return_value=(110.0, 90.0, 10.0)), \
         patch.object(engine_mod.QuantStrategyCore, "compute_atr", return_value=1.0):
        disabled_cfg = engine_mod.BotConfig(donchian_period=2, atr_period=2)
        disabled = engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", candles, disabled_cfg)
        assert disabled is None, disabled

        enabled_cfg = engine_mod.BotConfig(donchian_period=2, atr_period=2,
                                           enable_h2_range_fade=True)
        enabled = engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", candles, enabled_cfg)
        assert enabled is not None, enabled
        assert enabled["strategy"] == "H2-range-fade", enabled
        assert enabled["direction"] == "long", enabled


def test_h2_range_fade_config_is_read_from_strategy_section():
    cfg = engine_mod.BotConfig()
    cfg._apply({"strategy": {"enable_h2_range_fade": True}})
    assert cfg.enable_h2_range_fade is True
    cfg._apply({"strategy": {"enable_h2_range_fade": False}})
    assert cfg.enable_h2_range_fade is False


def test_config_rejects_unimplemented_strategy_keys():
    cfg = engine_mod.BotConfig()
    try:
        cfg._apply({"strategy": {"cooldown_bars": 4}})
    except ValueError as exc:
        assert "cooldown_bars" in str(exc), exc
    else:
        raise AssertionError("unsupported strategy key was silently accepted")


def test_config_rejects_unknown_top_level_keys():
    cfg = engine_mod.BotConfig()
    try:
        cfg._apply({"mystery_setting": True})
    except ValueError as exc:
        assert "mystery_setting" in str(exc), exc
    else:
        raise AssertionError("unknown top-level key was silently accepted")


def test_config_rejects_extreme_tp2_and_non_finite_numbers():
    extreme = engine_mod.BotConfig(tp1_r_multiple=50.0, tp2_r_multiple=100.0)
    try:
        extreme.validate()
    except ValueError as exc:
        assert "tp2_r_multiple > 10R" in str(exc), exc
    else:
        raise AssertionError("extreme TP2 target was accepted")

    non_finite = engine_mod.BotConfig(capital_usdt=float("nan"))
    try:
        non_finite.validate()
    except ValueError as exc:
        assert "capital_usdt must be finite" in str(exc), exc
    else:
        raise AssertionError("NaN capital was accepted")


def test_blocked_weekdays_utc_suppresses_signal_and_validates_values():
    from unittest.mock import patch

    ts_monday = int(engine_mod.datetime(2026, 1, 5, 12, 0, tzinfo=engine_mod.timezone.utc).timestamp() * 1000)
    candles = [
        engine_mod.Candle(ts=ts_monday + i * 900_000,
                          open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0)
        for i in range(4)
    ]
    candles[-1] = engine_mod.Candle(ts=ts_monday + 3 * 900_000,
                                    open=110.5, high=112.0, low=109.0, close=111.0, volume=100.0)
    with patch.object(engine_mod.QuantStrategyCore, "compute_donchian_and_volume", return_value=(110.0, 90.0, 10.0)), \
         patch.object(engine_mod.QuantStrategyCore, "compute_atr", return_value=1.0):
        cfg = engine_mod.BotConfig(donchian_period=2, atr_period=2, min_volume_ratio=1.6)
        assert engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", candles, cfg) is not None
        cfg.blocked_weekdays_utc = [0]
        assert engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", candles, cfg) is None

    invalid = engine_mod.BotConfig(blocked_weekdays_utc=[7])
    try:
        invalid.validate()
    except ValueError as exc:
        assert "blocked_weekdays_utc" in str(exc), exc
    else:
        raise AssertionError("invalid UTC weekday was accepted")


def test_blocked_weekdays_config_rejects_wrong_type():
    cfg = engine_mod.BotConfig()
    try:
        cfg._apply({"blocked_weekdays_utc": "Monday"})
    except ValueError as exc:
        assert "blocked_weekdays_utc" in str(exc), exc
    else:
        raise AssertionError("invalid blocked_weekdays_utc type was accepted")


def test_blocked_signal_hours_utc_suppresses_signal_and_validates_values():
    from unittest.mock import patch

    ts = int(engine_mod.datetime(2026, 1, 5, 12, 0, tzinfo=engine_mod.timezone.utc).timestamp() * 1000)
    candles = [
        engine_mod.Candle(ts=ts + i * 900_000, open=100.0, high=101.0,
                          low=99.0, close=100.5, volume=10.0)
        for i in range(4)
    ]
    candles[-1] = engine_mod.Candle(ts=ts + 3 * 900_000, open=110.5,
                                    high=112.0, low=109.0, close=111.0, volume=100.0)
    with patch.object(engine_mod.QuantStrategyCore, "compute_donchian_and_volume", return_value=(110.0, 90.0, 10.0)), \
         patch.object(engine_mod.QuantStrategyCore, "compute_atr", return_value=1.0):
        cfg = engine_mod.BotConfig(donchian_period=2, atr_period=2, min_volume_ratio=1.6)
        assert engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", candles, cfg) is not None
        cfg.blocked_signal_hours_utc = [12]
        assert engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", candles, cfg) is None

    invalid = engine_mod.BotConfig(blocked_signal_hours_utc=[24])
    try:
        invalid.validate()
    except ValueError as exc:
        assert "blocked_signal_hours_utc" in str(exc), exc
    else:
        raise AssertionError("invalid UTC hour was accepted")


def test_portfolio_risk_cap_limits_new_position_size():
    e = _bare_fill_engine()
    e.cfg.max_portfolio_risk_pct = 1.0
    e.risk_mgr = engine_mod.AdaptiveRiskManager(e.cfg)
    e.open_positions["ETHUSDT"] = type(
        "ExistingPosition", (), {"risk_usdt": 90.0, "remaining_fraction": 1.0}
    )()
    e.pending["BTCUSDT"] = _pending_signal("market", "long", 100.0)
    candle = engine_mod.Candle(
        ts=1_800_000_000_000, open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0
    )
    assert e._try_fill_pending("BTCUSDT", candle) is True
    opened = e.open_positions["BTCUSDT"]
    assert opened.risk_usdt <= 10.0, opened.risk_usdt
    assert e._open_portfolio_risk_usdt() <= 100.0, e._open_portfolio_risk_usdt()


def test_position_size_respects_remaining_portfolio_risk_budget():
    cfg = engine_mod.BotConfig(capital_usdt=10_000.0, max_risk_trade_pct=1.0)
    rm = engine_mod.AdaptiveRiskManager(cfg)
    size, risk = rm.calculate_position_size(100.0, 98.0, risk_budget_usdt=25.0)
    assert size > 0
    assert risk <= 25.0, risk


def test_max_portfolio_risk_config_is_loaded_and_validated():
    cfg = engine_mod.BotConfig()
    cfg._apply({"risk_management": {"max_portfolio_risk_pct": 1.75}})
    assert cfg.max_portfolio_risk_pct == 1.75
    for bad in (0.0, 10.1):
        invalid = engine_mod.BotConfig(max_portfolio_risk_pct=bad)
        try:
            invalid.validate()
        except ValueError as exc:
            assert "max_portfolio_risk_pct" in str(exc), exc
        else:
            raise AssertionError(f"invalid portfolio risk cap accepted: {bad}")


def test_daily_stop_blocks_entries_until_next_utc_day():
    cfg = engine_mod.BotConfig(
        capital_usdt=10_000.0,
        daily_stop_loss_pct=5.0,
        emergency_kill_switch_pct=30.0,
    )
    rm = engine_mod.AdaptiveRiskManager(cfg)
    day1_close = 1_767_311_100_000  # 2026-01-01 23:45 UTC
    day2_open = 1_767_312_000_000   # 2026-01-02 00:00 UTC
    alerts = rm.register_closed_trade_pnl(-600.0, day1_close)
    assert alerts["daily_stop_hit"] is True
    assert rm.can_open_new_trade(0) == (False, "DAILY_STOP_ACTIVE")
    rm.mark_to_market(0.0, day2_open)
    assert rm.daily_stop_triggered is False
    assert rm.can_open_new_trade(0) == (True, "OK")


def test_kill_switch_remains_latched_across_utc_day_change():
    cfg = engine_mod.BotConfig(
        capital_usdt=10_000.0,
        daily_stop_loss_pct=5.0,
        emergency_kill_switch_pct=30.0,
    )
    rm = engine_mod.AdaptiveRiskManager(cfg)
    day1_close = 1_767_311_100_000
    day2_open = 1_767_312_000_000
    alerts = rm.mark_to_market(-3_100.0, day1_close)
    assert alerts["kill_switch_hit"] is True
    assert rm.can_open_new_trade(0) == (False, "KILL_SWITCH_ACTIVE")
    rm.mark_to_market(0.0, day2_open)
    assert rm.kill_switch_triggered is True
    assert rm.can_open_new_trade(0) == (False, "KILL_SWITCH_ACTIVE")

def test_unsupported_timeframe_fails_closed():
    e, seen = bare_engine("7m")
    ts_open = 1_800_000_000_000
    candle = engine_mod.Candle(ts=ts_open, open=100, high=101, low=99, close=100, volume=10)
    try:
        e.step_candle("SOLUSDT", [candle])
    except ValueError as exc:
        assert "Неподдерживаемый timeframe" in str(exc)
    else:
        raise AssertionError("unsupported timeframe must raise ValueError")
    assert seen == [], seen




def _signal_test_candles(last_open, last_high, last_low, last_close):
    # Tiny deterministic history; indicator calculations are stubbed in the tests below.
    return [
        engine_mod.Candle(ts=1_800_000_000_000 + i * 900_000,
                          open=99.5, high=100.0, low=99.0, close=99.5, volume=10)
        for i in range(3)
    ] + [engine_mod.Candle(ts=1_800_002_700_000, open=last_open,
                           high=last_high, low=last_low, close=last_close, volume=20)]


def test_wick_above_donchian_without_close_does_not_trigger_long_breakout():
    cfg = engine_mod.BotConfig(donchian_period=2, atr_period=2, min_volume_ratio=1.6)
    candles = _signal_test_candles(last_open=99.5, last_high=105.0, last_low=99.2, last_close=99.8)
    from unittest.mock import patch
    with patch.object(engine_mod.QuantStrategyCore, "compute_donchian_and_volume", return_value=(100.0, 99.0, 10.0)), \
         patch.object(engine_mod.QuantStrategyCore, "compute_atr", return_value=1.0):
        signal = engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", candles, cfg)
    assert signal is None, signal


def test_wick_below_donchian_without_close_does_not_trigger_short_breakout():
    cfg = engine_mod.BotConfig(donchian_period=2, atr_period=2, min_volume_ratio=1.6)
    candles = _signal_test_candles(last_open=99.5, last_high=99.8, last_low=94.0, last_close=99.2)
    from unittest.mock import patch
    with patch.object(engine_mod.QuantStrategyCore, "compute_donchian_and_volume", return_value=(101.0, 99.0, 10.0)), \
         patch.object(engine_mod.QuantStrategyCore, "compute_atr", return_value=1.0):
        signal = engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", candles, cfg)
    assert signal is None, signal


def test_close_above_donchian_with_volume_confirms_long_breakout():
    cfg = engine_mod.BotConfig(donchian_period=2, atr_period=2, min_volume_ratio=1.6)
    candles = _signal_test_candles(last_open=99.5, last_high=101.0, last_low=99.2, last_close=100.5)
    from unittest.mock import patch
    with patch.object(engine_mod.QuantStrategyCore, "compute_donchian_and_volume", return_value=(100.0, 99.0, 10.0)), \
         patch.object(engine_mod.QuantStrategyCore, "compute_atr", return_value=1.0):
        signal = engine_mod.QuantStrategyCore.evaluate_signal("BTCUSDT", candles, cfg)
    assert signal is not None, signal
    assert signal["direction"] == "long", signal


def test_signal_is_not_filled_until_next_candle():
    """A signal formed from bar N must not attempt execution on bar N itself."""
    from unittest.mock import patch

    e, _ = bare_engine("15m")
    e.risk_mgr.can_open_new_trade = lambda count: (True, "ok")
    e._persist = lambda: None

    signal = {
        "direction": "long", "entry_price": 100.0, "order_type": "market",
        "strategy": "test", "stop_dist": 2.0,
    }
    signal_calls = []
    def fake_signal(symbol, history, cfg):
        signal_calls.append(history[-1].ts)
        return signal if len(signal_calls) == 1 else None

    fill_attempts = []
    def fake_fill(symbol, candle):
        fill_attempts.append((symbol, candle.ts))
        # Simulate a not-filled order, keeping this test focused on timing only.
        e.pending.pop(symbol, None)
        return False

    e._try_fill_pending = fake_fill
    t0 = 1_800_000_000_000
    c1 = engine_mod.Candle(ts=t0, open=100, high=101, low=99, close=100.5, volume=10)
    c2 = engine_mod.Candle(ts=t0 + 900_000, open=100.5, high=102, low=100, close=101, volume=11)

    with patch.object(engine_mod.QuantStrategyCore, "evaluate_signal", side_effect=fake_signal):
        e.step_candle("BTCUSDT", [c1])
        assert fill_attempts == [], fill_attempts
        assert "BTCUSDT" in e.pending, e.pending

        e.step_candle("BTCUSDT", [c1, c2])

    assert fill_attempts == [("BTCUSDT", c2.ts)], fill_attempts
    assert signal_calls == [c1.ts, c2.ts], signal_calls



def _bare_fill_engine(max_chase=1.5):
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(timeframe="15m", max_chase_limit_pct=max_chase)
    e.open_positions = {}
    e.pending = {}
    e.trade_seq = 0
    e._persist = lambda: None
    class RiskSpy:
        def can_open_new_trade(self, count):
            return True, "OK"
        def calculate_position_size(self, entry_price, stop_price, order_type="market", risk_budget_usdt=None):
            if risk_budget_usdt is not None:
                return 1000.0, min(50.0, risk_budget_usdt)
            return 1000.0, 50.0
        current_equity = 10_000.0
    e.risk_mgr = RiskSpy()
    return e


def _pending_signal(order_type="market", direction="long", entry=100.0):
    return {
        "direction": direction, "entry_price": entry, "order_type": order_type,
        "strategy": "test", "stop_dist": 2.0,
    }


def test_market_entry_rejected_when_next_open_gaps_beyond_chase_limit():
    e = _bare_fill_engine(max_chase=1.5)
    e.pending["BTCUSDT"] = _pending_signal("market", "long", 100.0)
    candle = engine_mod.Candle(ts=1_800_000_000_000, open=103.0, high=104.0, low=102.0, close=103.5, volume=10)
    filled = e._try_fill_pending("BTCUSDT", candle)
    assert filled is False
    assert "BTCUSDT" not in e.open_positions
    assert "BTCUSDT" not in e.pending


def test_market_entry_fills_at_next_open_when_gap_is_within_limit():
    e = _bare_fill_engine(max_chase=1.5)
    e.pending["BTCUSDT"] = _pending_signal("market", "long", 100.0)
    candle = engine_mod.Candle(ts=1_800_000_000_000, open=101.0, high=102.0, low=100.5, close=101.5, volume=10)
    filled = e._try_fill_pending("BTCUSDT", candle)
    assert filled is True
    assert e.open_positions["BTCUSDT"].entry_price == 101.0


def test_limit_entry_uses_limit_price_when_bar_opens_above_and_trades_through():
    e = _bare_fill_engine(max_chase=1.5)
    e.pending["BTCUSDT"] = _pending_signal("limit", "long", 100.0)
    candle = engine_mod.Candle(ts=1_800_000_000_000, open=103.0, high=104.0, low=99.0, close=101.0, volume=10)
    filled = e._try_fill_pending("BTCUSDT", candle)
    assert filled is True
    assert e.open_positions["BTCUSDT"].entry_price == 100.0


def test_intrabar_risk_mark_uses_adverse_extreme_when_stop_not_hit():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(timeframe="15m")
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e._intrabar_risk_marks_ts = None
    e.open_positions = {}
    e.pending = {}
    e.risk_mgr = type("RiskSpy", (), {"on_new_timestamp": lambda self, ts: None})()
    seen = []
    e._update_mark_to_market = lambda ts: seen.append(e._intrabar_risk_marks.copy())
    e._persist = lambda: None
    e._try_fill_pending = lambda symbol, curr: False
    e._manage_position = lambda *args, **kwargs: None
    e.risk_mgr.can_open_new_trade = lambda count: (False, "test")
    pos = type("Pos", (), {"direction": "long", "stop_price": 90.0})()
    e.open_positions["BTCUSDT"] = pos
    candle = engine_mod.Candle(ts=1_800_000_000_000, open=100, high=105, low=92, close=101, volume=10)
    e.step_candle("BTCUSDT", [candle])
    assert seen == [{"BTCUSDT": 92}], seen


def test_intrabar_risk_mark_uses_gap_adjusted_stop_fill_when_stop_crossed():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(timeframe="15m")
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e._intrabar_risk_marks_ts = None
    e.open_positions = {}
    e.pending = {}
    e.risk_mgr = type("RiskSpy", (), {"on_new_timestamp": lambda self, ts: None})()
    seen = []
    e._update_mark_to_market = lambda ts: seen.append(e._intrabar_risk_marks.copy())
    e._persist = lambda: None
    e._try_fill_pending = lambda symbol, curr: False
    e._manage_position = lambda *args, **kwargs: None
    e.risk_mgr.can_open_new_trade = lambda count: (False, "test")
    pos = type("Pos", (), {"direction": "long", "stop_price": 95.0})()
    e.open_positions["BTCUSDT"] = pos
    candle = engine_mod.Candle(ts=1_800_000_000_000, open=90, high=100, low=85, close=98, volume=10)
    e.step_candle("BTCUSDT", [candle])
    assert seen == [{"BTCUSDT": 90}], seen





def test_intrabar_marks_accumulate_for_symbols_at_same_timestamp():
    e, _ = bare_engine("15m")
    ts = 1_800_000_000_000
    e._update_mark_to_market = lambda timestamp: None
    e._last_mark_prices = {"ETHUSDT": 100.0}
    e._intrabar_risk_marks = {}
    e._intrabar_risk_marks_ts = None
    e._manage_position = lambda *args, **kwargs: None
    e.open_positions["BTCUSDT"] = type("Pos", (), {"direction": "long", "stop_price": 80.0})()
    e.open_positions["ETHUSDT"] = type("Pos", (), {"direction": "short", "stop_price": 120.0})()
    e.step_candle("BTCUSDT", [engine_mod.Candle(ts=ts, open=100, high=102, low=90, close=101, volume=10)])
    assert e._intrabar_risk_marks == {"BTCUSDT": 90.0}, e._intrabar_risk_marks
    e.step_candle("ETHUSDT", [engine_mod.Candle(ts=ts, open=100, high=115, low=98, close=102, volume=10)])
    assert e._intrabar_risk_marks == {"BTCUSDT": 90.0, "ETHUSDT": 115.0}, e._intrabar_risk_marks
    e.step_candle("BTCUSDT", [engine_mod.Candle(ts=ts + 900_000, open=101, high=103, low=99, close=102, volume=10)])
    assert e._intrabar_risk_marks == {"BTCUSDT": 99.0}, e._intrabar_risk_marks




def test_portfolio_intrabar_marks_prepared_for_all_open_symbols_before_risk_check():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(timeframe="15m")
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e._intrabar_risk_marks_ts = None
    e.open_positions = {
        "BTCUSDT": type("Pos", (), {"direction": "long", "stop_price": 80.0})(),
        "ETHUSDT": type("Pos", (), {"direction": "short", "stop_price": 120.0})(),
    }
    ts = 1_800_000_000_000
    e._prepare_portfolio_intrabar_marks({
        "BTCUSDT": engine_mod.Candle(ts=ts, open=100, high=105, low=90, close=101, volume=10),
        "ETHUSDT": engine_mod.Candle(ts=ts, open=100, high=115, low=95, close=102, volume=10),
    })
    assert e._intrabar_risk_marks == {"BTCUSDT": 90.0, "ETHUSDT": 115.0}, e._intrabar_risk_marks
    assert e._intrabar_risk_marks_ts == ts + 900_000




def test_combined_intrabar_losses_trigger_daily_stop_and_kill_switch():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(
        timeframe="15m", capital_usdt=10_000.0,
        daily_stop_loss_pct=5.0, emergency_kill_switch_pct=30.0,
    )
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e._intrabar_risk_marks_ts = None
    e.open_positions = {
        "BTCUSDT": engine_mod.OpenPositionState(
            trade_id="btc", symbol="BTCUSDT", direction="long", strategy="test",
            entry_ts=1_800_000_000_000, entry_price=100.0, stop_price=70.0,
            tp1_price=110.0, tp2_price=120.0, initial_stop_dist=30.0,
            size_usdt=10_000.0, risk_usdt=3_000.0, order_type="market",
            equity_at_entry=10_000.0,
        ),
        "ETHUSDT": engine_mod.OpenPositionState(
            trade_id="eth", symbol="ETHUSDT", direction="short", strategy="test",
            entry_ts=1_800_000_000_000, entry_price=100.0, stop_price=130.0,
            tp1_price=90.0, tp2_price=80.0, initial_stop_dist=30.0,
            size_usdt=10_000.0, risk_usdt=3_000.0, order_type="market",
            equity_at_entry=10_000.0,
        ),
    }
    ts = 1_800_000_000_000
    e._prepare_portfolio_intrabar_marks({
        "BTCUSDT": engine_mod.Candle(ts=ts, open=100, high=102, low=70, close=100, volume=10),
        "ETHUSDT": engine_mod.Candle(ts=ts, open=100, high=130, low=98, close=100, volume=10),
    })
    combined_unrealized = e._unrealized_pnl_at_marks()
    rm = engine_mod.AdaptiveRiskManager(e.cfg)
    alerts = rm.mark_to_market(combined_unrealized, ts + 900_000)
    assert combined_unrealized < -3_000.0, combined_unrealized
    assert alerts["daily_stop_hit"] is True, alerts
    assert alerts["kill_switch_hit"] is True, alerts
    assert rm.current_equity < 7_000.0, rm.current_equity


def test_kill_switch_exit_price_is_written_to_closed_trade_journal():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(
        timeframe="15m", capital_usdt=10_000.0,
        daily_stop_loss_pct=5.0, emergency_kill_switch_pct=30.0,
    )
    e._last_mark_prices = {"BTCUSDT": 100.0}
    e._intrabar_risk_marks = {"BTCUSDT": 90.0}
    e._intrabar_risk_marks_ts = 1_800_000_900_000
    pos = engine_mod.OpenPositionState(
        trade_id="btc-kill", symbol="BTCUSDT", direction="long", strategy="test",
        entry_ts=1_800_000_000_000, entry_price=100.0, stop_price=80.0,
        tp1_price=110.0, tp2_price=120.0, initial_stop_dist=20.0,
        size_usdt=1_000.0, risk_usdt=200.0, order_type="market",
        equity_at_entry=10_000.0,
    )
    e.open_positions = {"BTCUSDT": pos}
    e.closed_trades = []
    e.risk_mgr = engine_mod.AdaptiveRiskManager(e.cfg)
    e.risk_mgr.kill_switch_triggered = True
    e.risk_mgr.peak_equity = 10_000.0
    e.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    e._persist = lambda: None
    exit_ts = 1_800_000_900_000
    engine_mod.UnifiedQuantEngine._close_position(
        e, pos, e._intrabar_risk_marks["BTCUSDT"], "kill_switch",
        exit_ts, mae_r=0.5, mfe_r=0.0,
    )
    assert len(e.closed_trades) == 1
    assert e.closed_trades[0].exit_price == 90.0, e.closed_trades[0].exit_price
    assert e.closed_trades[0].exit_reason == "kill_switch"
    assert e.closed_trades[0].exit_date == "2027-01-15T08:15:00Z"
    assert "BTCUSDT" not in e.open_positions
    assert e.risk_mgr.current_equity < 10_000.0




def test_sequential_kill_switch_closes_do_not_double_count_unrealized_pnl():
    cfg = engine_mod.BotConfig(
        timeframe="15m", capital_usdt=10_000.0,
        daily_stop_loss_pct=5.0, emergency_kill_switch_pct=30.0,
    )
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = cfg
    ts = 1_800_000_900_000
    e._last_mark_prices = {"BTCUSDT": 90.0, "ETHUSDT": 110.0}
    e._intrabar_risk_marks = {"BTCUSDT": 90.0, "ETHUSDT": 110.0}
    e._intrabar_risk_marks_ts = ts
    e.open_positions = {
        "BTCUSDT": engine_mod.OpenPositionState(
            trade_id="btc-kill", symbol="BTCUSDT", direction="long", strategy="test",
            entry_ts=ts - 900_000, entry_price=100.0, stop_price=80.0,
            tp1_price=110.0, tp2_price=120.0, initial_stop_dist=20.0,
            size_usdt=1_000.0, risk_usdt=200.0, order_type="market",
            equity_at_entry=10_000.0,
        ),
        "ETHUSDT": engine_mod.OpenPositionState(
            trade_id="eth-kill", symbol="ETHUSDT", direction="short", strategy="test",
            entry_ts=ts - 900_000, entry_price=100.0, stop_price=120.0,
            tp1_price=90.0, tp2_price=80.0, initial_stop_dist=20.0,
            size_usdt=1_000.0, risk_usdt=200.0, order_type="market",
            equity_at_entry=10_000.0,
        ),
    }
    e.closed_trades = []
    e.risk_mgr = engine_mod.AdaptiveRiskManager(cfg)
    e.risk_mgr.kill_switch_triggered = True
    e.risk_mgr.peak_equity = 10_000.0
    e.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    e._persist = lambda: None

    positions = list(e.open_positions.values())
    for pos in positions:
        exit_px = e._intrabar_risk_marks[pos.symbol]
        engine_mod.UnifiedQuantEngine._close_position(
            e, pos, exit_px, "kill_switch", ts, mae_r=0.5, mfe_r=0.0,
        )

    assert len(e.closed_trades) == 2, len(e.closed_trades)
    assert not e.open_positions, e.open_positions
    assert {r.token: r.exit_price for r in e.closed_trades} == {
        "BTCUSDT": 90.0, "ETHUSDT": 110.0,
    }
    total_journal_net = round(sum(r.pnl_usdt for r in e.closed_trades), 2)
    assert e.risk_mgr.realized_equity == round(cfg.capital_usdt + total_journal_net, 4), (
        e.risk_mgr.realized_equity, total_journal_net,
    )
    assert e.risk_mgr.unrealized_pnl == 0.0, e.risk_mgr.unrealized_pnl
    assert e.risk_mgr.current_equity == round(cfg.capital_usdt + total_journal_net, 4), (
        e.risk_mgr.current_equity, total_journal_net,
    )




def test_equity_reconciles_journal_and_remaining_open_positions_after_each_close():
    cfg = engine_mod.BotConfig(
        timeframe="15m", capital_usdt=10_000.0,
        daily_stop_loss_pct=50.0, emergency_kill_switch_pct=90.0,
    )
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = cfg
    ts = 1_800_000_900_000
    e._last_mark_prices = {"BTCUSDT": 95.0, "ETHUSDT": 105.0}
    e._intrabar_risk_marks = {"BTCUSDT": 95.0, "ETHUSDT": 105.0}
    e._intrabar_risk_marks_ts = ts
    e.open_positions = {
        "BTCUSDT": engine_mod.OpenPositionState(
            trade_id="btc-reconcile", symbol="BTCUSDT", direction="long", strategy="test",
            entry_ts=ts - 900_000, entry_price=100.0, stop_price=90.0,
            tp1_price=110.0, tp2_price=120.0, initial_stop_dist=10.0,
            size_usdt=1_000.0, risk_usdt=100.0, order_type="market",
            equity_at_entry=10_000.0,
        ),
        "ETHUSDT": engine_mod.OpenPositionState(
            trade_id="eth-reconcile", symbol="ETHUSDT", direction="short", strategy="test",
            entry_ts=ts - 900_000, entry_price=100.0, stop_price=110.0,
            tp1_price=90.0, tp2_price=80.0, initial_stop_dist=10.0,
            size_usdt=1_000.0, risk_usdt=100.0, order_type="market",
            equity_at_entry=10_000.0,
        ),
    }
    e.closed_trades = []
    e.risk_mgr = engine_mod.AdaptiveRiskManager(cfg)
    e.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    e._persist = lambda: None

    # Both open positions have -50 gross and -1.55 estimated execution costs.
    e.risk_mgr.mark_to_market(e._unrealized_pnl_at_marks(), ts)
    assert e.risk_mgr.unrealized_pnl == -103.10
    assert e.risk_mgr.current_equity == 9_896.90

    btc = e.open_positions["BTCUSDT"]
    engine_mod.UnifiedQuantEngine._close_position(
        e, btc, 95.0, "stop_loss", ts, mae_r=0.5, mfe_r=0.0,
    )
    journal_net = round(sum(r.pnl_usdt for r in e.closed_trades), 2)
    assert journal_net == -51.55
    assert e.risk_mgr.realized_equity == 9_948.45
    assert e.risk_mgr.unrealized_pnl == -51.55
    assert e.risk_mgr.current_equity == 9_896.90
    assert e.risk_mgr.current_equity == round(
        cfg.capital_usdt + journal_net + e.risk_mgr.unrealized_pnl, 2,
    )

    eth = e.open_positions["ETHUSDT"]
    engine_mod.UnifiedQuantEngine._close_position(
        e, eth, 105.0, "stop_loss", ts, mae_r=0.5, mfe_r=0.0,
    )
    journal_net = round(sum(r.pnl_usdt for r in e.closed_trades), 2)
    assert journal_net == -103.10
    assert not e.open_positions
    assert e.risk_mgr.unrealized_pnl == 0.0
    assert e.risk_mgr.realized_equity == 9_896.90
    assert e.risk_mgr.current_equity == 9_896.90
    assert e.risk_mgr.current_equity == round(cfg.capital_usdt + journal_net, 2)



def test_tp1_partial_fill_keeps_equity_consistent_with_remaining_position():
    cfg = engine_mod.BotConfig(
        timeframe="15m", capital_usdt=10_000.0,
        daily_stop_loss_pct=50.0, emergency_kill_switch_pct=90.0,
    )
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = cfg
    ts = 1_800_000_900_000
    pos = engine_mod.OpenPositionState(
        trade_id="tp1-equity", symbol="BTCUSDT", direction="long", strategy="test",
        entry_ts=ts - 900_000, entry_price=100.0, stop_price=95.0,
        tp1_price=110.0, tp2_price=120.0, initial_stop_dist=5.0,
        size_usdt=1_000.0, risk_usdt=50.0, order_type="market",
        equity_at_entry=10_000.0,
    )
    e.open_positions = {"BTCUSDT": pos}
    e._last_mark_prices = {"BTCUSDT": 110.0}
    e._intrabar_risk_marks = {"BTCUSDT": 110.0}
    e._intrabar_risk_marks_ts = ts
    e.closed_trades = []
    e.risk_mgr = engine_mod.AdaptiveRiskManager(cfg)
    e.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    e._persist = lambda: None

    engine_mod.UnifiedQuantEngine._apply_tp1(pos)
    e.risk_mgr.mark_to_market(e._unrealized_pnl_at_marks(), ts)

    # +50 realized gross at TP1 and +50 mark-to-market gross on the remaining half.
    assert pos.tp1_hit is True
    assert pos.remaining_fraction == 0.5
    assert pos.realized_tp1_gross_usdt == 50.0
    assert e.risk_mgr.unrealized_pnl == 98.45
    assert e.risk_mgr.current_equity == 10_098.45

    # Closing the remaining half at TP2 reconciles the conservative MTM estimate
    # with the actual modeled maker take-profit execution and journal.
    engine_mod.UnifiedQuantEngine._close_position(
        e, pos, 120.0, "take_profit", ts, mae_r=0.0, mfe_r=4.0,
    )
    assert len(e.closed_trades) == 1
    assert e.closed_trades[0].gross_pnl == 150.0
    assert e.closed_trades[0].pnl_usdt == 149.60
    assert e.risk_mgr.realized_equity == 10_149.60
    assert e.risk_mgr.unrealized_pnl == 0.0
    assert e.risk_mgr.current_equity == 10_149.60


def test_finalize_open_positions_uses_bar_close_timestamp_across_utc_midnight():
    cfg = engine_mod.BotConfig(timeframe="15m", capital_usdt=10_000.0)
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = cfg
    # Candle opens at 23:45 UTC and closes at 00:00 UTC next day.
    candle_open_ts = 1_800_000_000_000
    candle_open_ts = (candle_open_ts // 86_400_000) * 86_400_000 + 23 * 3_600_000 + 45 * 60_000
    pos = engine_mod.OpenPositionState(
        trade_id="finalize-midnight", symbol="BTCUSDT", direction="long", strategy="test",
        entry_ts=candle_open_ts - 900_000, entry_price=100.0, stop_price=90.0,
        tp1_price=110.0, tp2_price=120.0, initial_stop_dist=10.0,
        size_usdt=1_000.0, risk_usdt=100.0, order_type="market",
        equity_at_entry=10_000.0,
    )
    e.open_positions = {"BTCUSDT": pos}
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e._intrabar_risk_marks_ts = None
    e.closed_trades = []
    e.risk_mgr = engine_mod.AdaptiveRiskManager(cfg)
    e.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    e._persist = lambda: None

    engine_mod.UnifiedQuantEngine.finalize_open_positions(
        e, {"BTCUSDT": engine_mod.Candle(
            ts=candle_open_ts, open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0,
        )},
    )

    assert len(e.closed_trades) == 1
    expected_close_ts = candle_open_ts + 900_000
    assert e.closed_trades[0].exit_date == engine_mod.datetime.fromtimestamp(
        expected_close_ts / 1000.0, tz=engine_mod.timezone.utc,
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert e.risk_mgr.current_day_str == engine_mod.datetime.fromtimestamp(
        expected_close_ts / 1000.0, tz=engine_mod.timezone.utc,
    ).strftime("%Y-%m-%d")



def test_full_step_candle_kill_switch_flattens_portfolio_and_blocks_reentry():
    cfg = engine_mod.BotConfig(
        timeframe="15m", capital_usdt=10_000.0,
        daily_stop_loss_pct=5.0, emergency_kill_switch_pct=5.0,
    )
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = cfg
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e._intrabar_risk_marks_ts = None
    ts = 1_800_000_000_000
    e.open_positions = {
        "BTCUSDT": engine_mod.OpenPositionState(
            trade_id="btc-full-cycle", symbol="BTCUSDT", direction="long", strategy="test",
            entry_ts=ts - 1_800_000, entry_price=100.0, stop_price=70.0,
            tp1_price=120.0, tp2_price=130.0, initial_stop_dist=30.0,
            size_usdt=10_000.0, risk_usdt=3_000.0, order_type="market",
            equity_at_entry=10_000.0,
        ),
        "ETHUSDT": engine_mod.OpenPositionState(
            trade_id="eth-full-cycle", symbol="ETHUSDT", direction="short", strategy="test",
            entry_ts=ts - 1_800_000, entry_price=100.0, stop_price=130.0,
            tp1_price=80.0, tp2_price=70.0, initial_stop_dist=30.0,
            size_usdt=10_000.0, risk_usdt=3_000.0, order_type="market",
            equity_at_entry=10_000.0,
        ),
    }
    e.pending = {}
    e.closed_trades = []
    e.trade_seq = 0
    e.risk_mgr = engine_mod.AdaptiveRiskManager(cfg)
    e.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    e._persist = lambda: None

    btc = [
        engine_mod.Candle(ts=ts - 1_800_000, open=100, high=101, low=99, close=100, volume=10),
        engine_mod.Candle(ts=ts - 900_000, open=100, high=101, low=99, close=100, volume=10),
        engine_mod.Candle(ts=ts, open=100, high=102, low=90, close=100, volume=10),
    ]
    eth = [
        engine_mod.Candle(ts=ts - 1_800_000, open=100, high=101, low=99, close=100, volume=10),
        engine_mod.Candle(ts=ts - 900_000, open=100, high=101, low=99, close=100, volume=10),
        engine_mod.Candle(ts=ts, open=100, high=110, low=98, close=100, volume=10),
    ]
    marks = {"BTCUSDT": btc[-1], "ETHUSDT": eth[-1]}
    e._prepare_portfolio_intrabar_marks(marks)

    engine_mod.UnifiedQuantEngine.step_candle(e, "BTCUSDT", btc)
    assert e.risk_mgr.kill_switch_triggered is True
    assert len(e.closed_trades) == 1, len(e.closed_trades)
    assert e.closed_trades[0].token == "BTCUSDT"
    assert e.closed_trades[0].exit_price == 90.0
    assert e.closed_trades[0].exit_reason == "kill_switch"
    assert "ETHUSDT" in e.open_positions

    engine_mod.UnifiedQuantEngine.step_candle(e, "ETHUSDT", eth)
    assert len(e.closed_trades) == 2, len(e.closed_trades)
    assert not e.open_positions, e.open_positions
    assert {r.token: r.exit_price for r in e.closed_trades} == {
        "BTCUSDT": 90.0, "ETHUSDT": 110.0,
    }
    assert all(r.exit_reason == "kill_switch" for r in e.closed_trades)
    assert e.risk_mgr.unrealized_pnl == 0.0, e.risk_mgr.unrealized_pnl
    net_journal = round(sum(r.pnl_usdt for r in e.closed_trades), 2)
    assert e.risk_mgr.realized_equity == round(cfg.capital_usdt + net_journal, 4)

    # Re-processing the same bar must neither recreate entries nor duplicate exits.
    engine_mod.UnifiedQuantEngine.step_candle(e, "BTCUSDT", btc)
    engine_mod.UnifiedQuantEngine.step_candle(e, "ETHUSDT", eth)
    assert len(e.closed_trades) == 2, len(e.closed_trades)
    assert not e.open_positions, e.open_positions
    assert not e.pending, e.pending
    assert e.risk_mgr.can_open_new_trade(0) == (False, "KILL_SWITCH_ACTIVE")



def test_daily_stop_keeps_managing_existing_positions_without_new_entries():
    cfg = engine_mod.BotConfig(
        timeframe="15m", capital_usdt=10_000.0,
        daily_stop_loss_pct=5.0, emergency_kill_switch_pct=30.0,
        atr_period=2,
    )
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = cfg
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e._intrabar_risk_marks_ts = None
    ts = 1_800_000_000_000
    e.open_positions = {
        "BTCUSDT": engine_mod.OpenPositionState(
            trade_id="btc-daily-stop", symbol="BTCUSDT", direction="long", strategy="test",
            entry_ts=ts - 1_800_000, entry_price=100.0, stop_price=80.0,
            tp1_price=110.0, tp2_price=120.0, initial_stop_dist=20.0,
            size_usdt=1_000.0, risk_usdt=200.0, order_type="market",
            equity_at_entry=10_000.0,
        ),
    }
    e.pending = {}
    e.closed_trades = []
    e.trade_seq = 0
    e.risk_mgr = engine_mod.AdaptiveRiskManager(cfg)
    e.risk_mgr.register_closed_trade_pnl(-600.0, ts)
    assert e.risk_mgr.daily_stop_triggered is True
    assert e.risk_mgr.kill_switch_triggered is False
    e.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    e._persist = lambda: None

    candles = [
        engine_mod.Candle(ts=ts - 1_800_000, open=100, high=101, low=99, close=100, volume=10),
        engine_mod.Candle(ts=ts - 900_000, open=100, high=101, low=99, close=100, volume=10),
        engine_mod.Candle(ts=ts, open=100, high=125, low=99, close=115, volume=10),
    ]
    engine_mod.UnifiedQuantEngine.step_candle(e, "BTCUSDT", candles)

    # The daily stop blocks entries, but must not prevent normal management of an open trade.
    assert e.risk_mgr.daily_stop_triggered is True
    assert e.risk_mgr.kill_switch_triggered is False
    assert len(e.closed_trades) == 1, len(e.closed_trades)
    assert e.closed_trades[0].token == "BTCUSDT"
    assert e.closed_trades[0].exit_reason == "take_profit"
    assert e.closed_trades[0].exit_price == 120.0
    assert not e.open_positions, e.open_positions
    assert not e.pending, e.pending
    assert e.risk_mgr.can_open_new_trade(0) == (False, "DAILY_STOP_ACTIVE")

    # On the next UTC day the daily stop resets, unlike the latched kill switch.
    next_day = ((ts // 86_400_000) + 1) * 86_400_000
    e.risk_mgr.mark_to_market(0.0, next_day)
    assert e.risk_mgr.daily_stop_triggered is False
    assert e.risk_mgr.kill_switch_triggered is False
    assert e.risk_mgr.can_open_new_trade(0) == (True, "OK")



if __name__ == "__main__":
    tests = [test_tp1_partial_fill_keeps_equity_consistent_with_remaining_position,
             test_finalize_open_positions_uses_bar_close_timestamp_across_utc_midnight,
             test_equity_reconciles_journal_and_remaining_open_positions_after_each_close,
             test_daily_stop_keeps_managing_existing_positions_without_new_entries,
             test_full_step_candle_kill_switch_flattens_portfolio_and_blocks_reentry,
             test_sequential_kill_switch_closes_do_not_double_count_unrealized_pnl,
             test_combined_intrabar_losses_trigger_daily_stop_and_kill_switch,
             test_kill_switch_exit_price_is_written_to_closed_trade_journal,
             test_portfolio_intrabar_marks_prepared_for_all_open_symbols_before_risk_check,
             test_intrabar_marks_accumulate_for_symbols_at_same_timestamp,
             test_intrabar_risk_mark_uses_adverse_extreme_when_stop_not_hit,
             test_intrabar_risk_mark_uses_gap_adjusted_stop_fill_when_stop_crossed,
             test_mtm_uses_close_timestamp_for_15m_bar,
             test_daily_stop_blocks_entries_until_next_utc_day,
             test_kill_switch_remains_latched_across_utc_day_change,
             test_portfolio_risk_cap_limits_new_position_size,
             test_position_size_respects_remaining_portfolio_risk_budget,
             test_max_portfolio_risk_config_is_loaded_and_validated,
             test_blocked_signal_hours_utc_suppresses_signal_and_validates_values,
             test_blocked_weekdays_utc_suppresses_signal_and_validates_values,
             test_blocked_weekdays_config_rejects_wrong_type,
             test_config_rejects_unimplemented_strategy_keys,
             test_config_rejects_unknown_top_level_keys,
             test_config_rejects_extreme_tp2_and_non_finite_numbers,
             test_h2_range_fade_is_disabled_by_default_and_enabled_explicitly,
             test_h2_range_fade_config_is_read_from_strategy_section,
             test_open_position_management_receives_bar_close_timestamp_across_utc_midnight,
             test_mtm_respects_configured_1h_close_boundary,
             test_unsupported_timeframe_fails_closed,
             test_wick_above_donchian_without_close_does_not_trigger_long_breakout,
             test_wick_below_donchian_without_close_does_not_trigger_short_breakout,
             test_close_above_donchian_with_volume_confirms_long_breakout,
             test_signal_is_not_filled_until_next_candle,
             test_market_entry_rejected_when_next_open_gaps_beyond_chase_limit,
             test_market_entry_fills_at_next_open_when_gap_is_within_limit,
             test_limit_entry_uses_limit_price_when_bar_opens_above_and_trades_through]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"{len(tests)}/{len(tests)} tests passed")