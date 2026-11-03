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
    e._bar_entry_equity = None
    e.instrument_spec_history = None
    e.max_instrument_spec_age_ms = 30 * 24 * 60 * 60 * 1000
    e.risk_tier_history = None
    e.max_risk_tier_age_ms = 30 * 24 * 60 * 60 * 1000
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
    # TP1 closed 50% at 106; remaining 50% is marked at 102.
    e.open_positions["BTCUSDT"] = make_position(
        size=2_000.0, remaining=0.5, tp1_hit=True, tp1_gross=10.0,
    )
    e._last_mark_prices["BTCUSDT"] = 102.0
    value = e._unrealized_pnl_at_marks()
    expected_gross = 10.0 + 2_000.0 * 0.5 * 0.02
    # 20 base units: entry notional 2,000; TP1 notional 1,060; remaining mark notional 1,020.
    expected_costs = (
        2_000.0 * (engine_mod.TAKER_FEE + engine_mod.TAKER_SLIP)
        + 1_060.0 * (engine_mod.TAKER_FEE + engine_mod.TAKER_SLIP)
        + 1_020.0 * (engine_mod.TAKER_FEE + engine_mod.TAKER_SLIP)
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


def test_short_exit_costs_use_lower_executed_notional():
    e = make_engine()
    pos = make_position(direction="short", size=1_000.0, order_type="market", maker_exits=False)
    e.open_positions["BTCUSDT"] = pos
    e._close_position(
        pos, exit_price=90.0, exit_reason="take_profit",
        exit_ts=1_800_003_600_000, mae_r=0.0, mfe_r=2.0,
    )
    trade = e.closed_trades[-1]
    expected_fees = 1_000.0 * engine_mod.TAKER_FEE + 900.0 * engine_mod.TAKER_FEE
    expected_slippage = 1_000.0 * engine_mod.TAKER_SLIP + 900.0 * engine_mod.TAKER_SLIP
    assert trade.exchange_fees_usdt == round(expected_fees, 2)
    assert trade.slippage_cost_usdt == round(expected_slippage, 2)


def test_stop_risk_uses_exit_notional_at_stop_price():
    cfg = engine_mod.BotConfig(
        capital_usdt=10_000.0, max_risk_trade_pct=5.0,
        leverage_val=5.0, max_concurrent_positions=2,
    )
    risk = engine_mod.AdaptiveRiskManager(cfg)
    long_size, long_risk = risk.calculate_position_size(
        100.0, 95.0, order_type="market", risk_budget_usdt=100.0,
    )
    short_size, short_risk = risk.calculate_position_size(
        100.0, 105.0, order_type="market", risk_budget_usdt=100.0,
    )
    long_rate = 0.05 + engine_mod.TAKER_FEE + engine_mod.TAKER_SLIP + 0.95 * (
        engine_mod.TAKER_FEE + engine_mod.TAKER_SLIP
    )
    short_rate = 0.05 + engine_mod.TAKER_FEE + engine_mod.TAKER_SLIP + 1.05 * (
        engine_mod.TAKER_FEE + engine_mod.TAKER_SLIP
    )
    assert long_risk > 0
    assert short_risk > 0
    assert short_size < long_size
    assert long_risk <= 100.0
    assert short_risk <= 100.0


def test_close_trade_reconciles_net_pnl_fees_slippage_and_realized_equity():
    e = make_engine()
    pos = make_position(size=1_000.0, order_type="market", maker_exits=False)
    e.open_positions["BTCUSDT"] = pos
    e._last_mark_prices["BTCUSDT"] = 110.0
    gross = 1_000.0 * (110.0 - 100.0) / 100.0
    # 10 base units: entry notional 1,000; exit notional 1,100 at 110.
    expected_fees = 1_000.0 * engine_mod.TAKER_FEE + 1_100.0 * engine_mod.TAKER_FEE
    expected_slippage = 1_000.0 * engine_mod.TAKER_SLIP + 1_100.0 * engine_mod.TAKER_SLIP

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


def test_engine_applies_dated_bybit_qty_step_and_minimums_when_spec_history_enabled():
    from bybit_instrument_specs import InstrumentSpec

    instrument = {
        "symbol": "BTCUSDT", "category": "linear", "status": "Trading",
        "priceFilter": {"minPrice": "0.05", "maxPrice": "1000000", "tickSize": "0.05"},
        "lotSizeFilter": {
            "qtyStep": "0.1", "minOrderQty": "0.1",
            "maxOrderQty": "1000", "maxMktOrderQty": "800",
            "minNotionalValue": "5",
        },
        "leverageFilter": {
            "minLeverage": "1", "maxLeverage": "50", "leverageStep": "0.01",
        },
    }
    spec = InstrumentSpec.from_snapshot({"instrument": instrument})

    class History:
        def get_spec(self, symbol, as_of_ts, *, max_age_ms):
            assert symbol == "BTCUSDT"
            assert as_of_ts == 1_800_000_000_000
            assert max_age_ms is not None
            return spec

    e = make_engine()
    e.instrument_spec_history = History()
    e.pending["BTCUSDT"] = {
        "direction": "long", "entry_price": 100.0, "order_type": "market",
        "strategy": "exchange-sizing-test", "stop_dist": 5.0,
        "signal_ts": 1_799_996_400_000,
    }
    bar = engine_mod.Candle(
        ts=1_800_000_000_000, open=100.0, high=101.0,
        low=99.0, close=100.5, volume=10.0,
    )
    e._prepare_pending_entry_risk_budgets()
    assert e._try_fill_pending("BTCUSDT", bar)
    position = e.open_positions["BTCUSDT"]
    quantity = position.size_usdt / position.entry_price
    assert abs(quantity / 0.1 - round(quantity / 0.1)) < 1e-8
    assert position.exchange_sized
    assert position.contract_qty is not None
    assert position.remaining_contract_qty == position.contract_qty
    assert position.qty_step == "0.1"
    assert position.size_usdt >= 5.0
    assert position.risk_usdt <= 100.0


def test_engine_enforces_dated_risk_tier_and_persists_selected_tier():
    from decimal import Decimal
    from bybit_instrument_specs import InstrumentSpec

    instrument = {
        "symbol": "BTCUSDT", "category": "linear", "status": "Trading",
        "priceFilter": {"minPrice": "0.05", "maxPrice": "1000000", "tickSize": "0.05"},
        "lotSizeFilter": {
            "qtyStep": "0.1", "minOrderQty": "0.1",
            "maxOrderQty": "1000", "maxMktOrderQty": "800",
            "minNotionalValue": "5",
        },
        "leverageFilter": {
            "minLeverage": "1", "maxLeverage": "50", "leverageStep": "0.01",
        },
    }
    spec = InstrumentSpec.from_snapshot({"instrument": instrument})

    class InstrumentHistory:
        def get_spec(self, symbol, as_of_ts, *, max_age_ms):
            return spec

    class Tier:
        tier_id = 2
        risk_limit_value = Decimal("500000")
        maintenance_margin_rate = Decimal("0.01")
        mm_deduction = Decimal("500")

    class TierHistory:
        def calculate_margin_requirements(self, symbol, as_of_ts, position_value, *, leverage, max_age_ms):
            assert symbol == "BTCUSDT"
            assert position_value <= Decimal("500000")
            assert leverage == Decimal("5")
            return type("Margin", (), {
                "tier_id": 2, "risk_limit_value": Decimal("500000"),
                "maintenance_margin_rate": Decimal("0.01"),
                "mm_deduction": Decimal("500"), "leverage": leverage,
                "max_leverage": Decimal("50"),
                "initial_margin": position_value / leverage,
                "maintenance_margin": position_value * Decimal("0.01") - Decimal("500"),
            })()

    e = make_engine()
    e.instrument_spec_history = InstrumentHistory()
    e.risk_tier_history = TierHistory()
    e.pending["BTCUSDT"] = {
        "direction": "long", "entry_price": 100.0, "order_type": "market",
        "strategy": "risk-tier-test", "stop_dist": 5.0,
        "signal_ts": 1_799_996_400_000,
    }
    bar = engine_mod.Candle(
        ts=1_800_000_000_000, open=100.0, high=101.0,
        low=99.0, close=100.5, volume=10.0,
    )
    e._prepare_pending_entry_risk_budgets()
    assert e._try_fill_pending("BTCUSDT", bar)
    position = e.open_positions["BTCUSDT"]
    assert position.risk_tier_id == 2
    assert position.risk_limit_value == "500000"
    assert position.maintenance_margin_rate == "0.01"
    assert position.maintenance_margin_deduction == "500"
    assert position.risk_tier_max_leverage == "50"
    assert Decimal(position.initial_margin_usdt) == Decimal(str(position.size_usdt)) / Decimal("5")
    assert Decimal(position.maintenance_margin_usdt) == Decimal(str(position.size_usdt)) * Decimal("0.01") - Decimal("500")


def test_engine_fails_closed_when_dated_risk_tier_is_missing_or_leverage_exceeded():
    class RejectingTierHistory:
        def calculate_margin_requirements(self, symbol, as_of_ts, position_value, *, leverage, max_age_ms):
            raise ValueError("configured leverage exceeds selected tier maxLeverage")

    e = make_engine()
    e.risk_tier_history = RejectingTierHistory()
    e.pending["BTCUSDT"] = {
        "direction": "long", "entry_price": 100.0, "order_type": "market",
        "strategy": "risk-tier-test", "stop_dist": 5.0,
        "signal_ts": 1_799_996_400_000,
    }
    bar = engine_mod.Candle(
        ts=1_800_000_000_000, open=100.0, high=101.0,
        low=99.0, close=100.5, volume=10.0,
    )
    e._prepare_pending_entry_risk_budgets()
    assert not e._try_fill_pending("BTCUSDT", bar)
    assert "BTCUSDT" not in e.open_positions


def test_engine_fails_closed_when_dated_instrument_spec_is_missing():
    class MissingHistory:
        def get_spec(self, symbol, as_of_ts, *, max_age_ms):
            raise ValueError("no dated snapshot for symbol")

    e = make_engine()
    e.instrument_spec_history = MissingHistory()
    e.pending["BTCUSDT"] = {
        "direction": "long", "entry_price": 100.0, "order_type": "market",
        "strategy": "exchange-sizing-test", "stop_dist": 5.0,
        "signal_ts": 1_799_996_400_000,
    }
    bar = engine_mod.Candle(
        ts=1_800_000_000_000, open=100.0, high=101.0,
        low=99.0, close=100.5, volume=10.0,
    )
    e._prepare_pending_entry_risk_budgets()
    assert not e._try_fill_pending("BTCUSDT", bar)
    assert "BTCUSDT" not in e.open_positions


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
        - round(e.risk_mgr.realized_equity + expected, 4)
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
            - round(e.risk_mgr.realized_equity + expected_unrealized, 4)
        ) < 1e-8

    assert first.closed_trades[0].pnl_usdt == reverse.closed_trades[0].pnl_usdt
    assert abs(first.risk_mgr.realized_equity - reverse.risk_mgr.realized_equity) < 1e-8
    assert abs(first.risk_mgr.unrealized_pnl - reverse.risk_mgr.unrealized_pnl) < 1e-8
    assert abs(first.risk_mgr.current_equity - reverse.risk_mgr.current_equity) < 1e-8
    # Max-DD differs only by <=1e-6 percentage points from 4dp equity rounding
    # at sequential same-timestamp closes; final equity and trade PnL remain invariant.
    assert abs(first.risk_mgr.max_drawdown_pct - reverse.risk_mgr.max_drawdown_pct) <= 2e-6, (
        first.risk_mgr.max_drawdown_pct, reverse.risk_mgr.max_drawdown_pct
    )



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


def test_finalize_rejects_missing_open_position_marks():
    e = make_engine()
    e.open_positions["BTCUSDT"] = make_position(symbol="BTCUSDT", size=1_000.0)
    incomplete_marks = {
        "ETHUSDT": engine_mod.Candle(
            ts=1_800_003_600_000, open=100.0, high=101.0,
            low=99.0, close=100.0, volume=10.0,
        )
    }

    try:
        e.finalize_open_positions(incomplete_marks)
    except ValueError as exc:
        assert "BTCUSDT" in str(exc)
    else:
        raise AssertionError("finalization must reject missing marks for an open position")







def _exchange_sized_position(qty="1.0"):
    pos = make_position(size=100.0)
    pos.exchange_sized = True
    pos.contract_qty = qty
    pos.remaining_contract_qty = qty
    pos.qty_step = "0.1"
    pos.min_order_qty = "0.1"
    pos.min_notional_value = "5"
    return pos


def test_exchange_sized_tp1_uses_step_aligned_qty_and_exact_remaining_contracts():
    pos = _exchange_sized_position()
    assert engine_mod.UnifiedQuantEngine._apply_tp1(pos, 1_800_003_600_000)
    assert pos.tp1_contract_qty == "0.5"
    assert pos.remaining_contract_qty == "0.5"
    assert pos.contract_qty == "1.0"
    assert pos.remaining_fraction == 0.5
    assert pos.realized_tp1_gross_usdt == 3.0
    assert pos.tp1_hit


def test_exchange_sized_tp1_is_skipped_when_split_violates_exchange_minimums():
    pos = _exchange_sized_position(qty="0.1")
    assert not engine_mod.UnifiedQuantEngine._apply_tp1(pos, 1_800_003_600_000)
    assert not pos.tp1_hit
    assert pos.tp1_contract_qty is None
    assert pos.remaining_contract_qty == "0.1"
    assert pos.remaining_fraction == 1.0


def test_exchange_sized_final_close_uses_exact_remaining_contract_qty_for_pnl():
    e = make_engine()
    pos = _exchange_sized_position()
    assert engine_mod.UnifiedQuantEngine._apply_tp1(pos, 1_800_003_600_000)
    e.open_positions["BTCUSDT"] = pos
    e._last_mark_prices["BTCUSDT"] = 112.0
    e._close_position(pos, 112.0, "take_profit", 1_800_007_200_000, 0.0, 2.4)
    assert e.closed_trades[-1].gross_pnl == 9.0
    assert "BTCUSDT" not in e.open_positions


def test_exchange_sized_close_rejects_unquantized_final_leg():
    e = make_engine()
    pos = _exchange_sized_position()
    pos.remaining_contract_qty = "0.05"
    e.open_positions["BTCUSDT"] = pos
    e._last_mark_prices["BTCUSDT"] = 100.0
    try:
        e._close_position(pos, 100.0, "stop_loss", 1_800_003_600_000, 0.0, 0.0)
    except RuntimeError as exc:
        assert "qtyStep" in str(exc)
    else:
        raise AssertionError("strict close must reject non-quantized remaining qty")


def _run_full_replay_symbol_order(order):
    e = make_engine()
    e._state_restored = False
    e.journal_output_path = "/tmp/ignored_full_replay_symbol_order.json"
    e.cfg.bot_version = "full-replay-symbol-order-regression"
    e.cfg.timeframe = "1h"
    e.cfg.active_trading_pool = list(order)
    e.cfg.max_concurrent_positions = 2
    e.cfg.max_risk_trade_pct = 1.0
    e.cfg.max_portfolio_risk_pct = 2.0
    e.cfg.daily_stop_loss_pct = 1.5
    e.cfg.emergency_kill_switch_pct = 35.0
    e.cfg.max_chase_limit_pct = 1.5
    e.risk_mgr.cfg = e.cfg

    hour = 3_600_000
    start_ts = 1_800_000_000_000
    signal_ts = start_ts + 25 * hour
    vol_ratio = {"BTCUSDT": 1.8, "ETHUSDT": 2.4, "SOLUSDT": 2.1}
    original_evaluate = engine_mod.QuantStrategyCore.evaluate_signal
    original_step = e.step_candle
    equity_path = []

    def deterministic_signal(symbol, history, _cfg):
        if history[-1].ts != signal_ts:
            return None
        return {
            "direction": "long", "entry_price": 100.0, "order_type": "market",
            "strategy": "symbol-order-fixture", "stop_dist": 5.0,
            "signal_ts": signal_ts, "vol_ratio": vol_ratio[symbol],
        }

    def capture_after_symbol(symbol, history, *, evaluate_new_signal=True):
        eligible = original_step(symbol, history, evaluate_new_signal=evaluate_new_signal)
        if symbol == order[-1]:
            risk = e.risk_mgr
            equity_path.append((
                history[-1].ts + hour,
                round(risk.realized_equity, 6),
                round(risk.unrealized_pnl, 6),
                round(risk.current_equity, 6),
                bool(risk.daily_stop_triggered),
                bool(risk.kill_switch_triggered),
            ))
        return eligible

    candles = {}
    for symbol in order:
        rows = []
        for index in range(29):
            low = 90.0 if index == 27 else 99.0
            rows.append(engine_mod.Candle(
                ts=start_ts + index * hour,
                open=100.0, high=101.0, low=low, close=100.0, volume=100.0,
            ))
        candles[symbol] = rows

    engine_mod.QuantStrategyCore.evaluate_signal = staticmethod(deterministic_signal)
    e.step_candle = capture_after_symbol
    try:
        audit = engine_mod.run_simulation_pass(
            e, candles, list(order), data_label="SYNTHETIC_SYMBOL_ORDER_REGRESSION",
        )
    finally:
        engine_mod.QuantStrategyCore.evaluate_signal = staticmethod(original_evaluate)

    ledger = sorted((
        trade.token, trade.direction, trade.entry_date, trade.exit_date,
        round(trade.entry_price, 8), round(trade.exit_price, 8),
        round(trade.gross_pnl, 6), round(trade.exchange_fees_usdt, 6),
        round(trade.slippage_cost_usdt, 6), round(trade.funding_cost_usdt, 6),
        round(trade.pnl_usdt, 6), trade.exit_reason,
    ) for trade in e.closed_trades)
    return {
        "ledger": ledger,
        "equity_path": equity_path,
        "open_symbols": set(e.open_positions),
        "pending_symbols": set(e.pending),
        "daily_stop": e.risk_mgr.daily_stop_triggered,
        "kill_switch": e.risk_mgr.kill_switch_triggered,
        "net_pnl": round(audit["net_pnl"], 6),
        "max_dd": round(audit["max_dd_pct"], 6),
    }


def test_full_run_simulation_pass_is_invariant_to_symbol_order():
    forward = _run_full_replay_symbol_order(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    reverse = _run_full_replay_symbol_order(["SOLUSDT", "ETHUSDT", "BTCUSDT"])

    assert forward["open_symbols"] == reverse["open_symbols"] == set()
    assert forward["pending_symbols"] == reverse["pending_symbols"] == set()
    assert len(forward["ledger"]) == len(reverse["ledger"]) == 2
    assert {row[0] for row in forward["ledger"]} == {"ETHUSDT", "SOLUSDT"}
    assert {row[0] for row in forward["ledger"]} == {row[0] for row in reverse["ledger"]}
    assert forward["ledger"] == reverse["ledger"]
    assert forward["equity_path"] == reverse["equity_path"]
    assert forward["daily_stop"] == reverse["daily_stop"]
    assert forward["kill_switch"] == reverse["kill_switch"]
    assert forward["net_pnl"] == reverse["net_pnl"]
    assert forward["max_dd"] == reverse["max_dd"]





def _run_sparse_replay_symbol_order(order):
    e = make_engine()
    e._state_restored = False
    e.journal_output_path = "/tmp/ignored_sparse_replay_symbol_order.json"
    e.cfg.bot_version = "sparse-replay-symbol-order-regression"
    e.cfg.timeframe = "1h"
    e.cfg.active_trading_pool = list(order)
    e.cfg.max_concurrent_positions = 2
    e.cfg.max_risk_trade_pct = 1.0
    e.cfg.max_portfolio_risk_pct = 2.0
    e.cfg.daily_stop_loss_pct = 1.5
    e.cfg.emergency_kill_switch_pct = 35.0
    e.cfg.max_chase_limit_pct = 1.5
    e.risk_mgr.cfg = e.cfg

    hour = 3_600_000
    start_ts = 1_800_000_000_000
    signal_ts = start_ts + 35 * hour
    offsets = {"BTCUSDT": 0, "ETHUSDT": 5, "SOLUSDT": 10}
    vol_ratio = {"BTCUSDT": 1.8, "ETHUSDT": 2.4, "SOLUSDT": 2.1}
    first_seen = {}
    original_evaluate = engine_mod.QuantStrategyCore.evaluate_signal
    original_step = e.step_candle
    equity_path = []
    bar_snapshots = []

    def deterministic_signal(symbol, history, _cfg):
        first_seen.setdefault(symbol, history[-1].ts)
        if history[-1].ts != signal_ts:
            return None
        return {
            "direction": "long", "entry_price": 100.0, "order_type": "market",
            "strategy": "sparse-symbol-order-fixture", "stop_dist": 5.0,
            "signal_ts": signal_ts, "vol_ratio": vol_ratio[symbol],
        }

    def capture_after_symbol(symbol, history, *, evaluate_new_signal=True):
        eligible = original_step(symbol, history, evaluate_new_signal=evaluate_new_signal)
        if symbol == order[-1]:
            risk = e.risk_mgr
            equity_path.append((
                history[-1].ts + hour,
                round(risk.realized_equity, 6),
                round(risk.unrealized_pnl, 6),
                round(risk.current_equity, 6),
                bool(risk.daily_stop_triggered),
                bool(risk.kill_switch_triggered),
            ))
        return eligible

    candles = {}
    for symbol in order:
        rows = []
        for global_index in range(offsets[symbol], 61):
            low = 90.0 if global_index == 37 else 99.0
            rows.append(engine_mod.Candle(
                ts=start_ts + global_index * hour,
                open=100.0, high=101.0, low=low, close=100.0, volume=100.0,
            ))
        candles[symbol] = rows

    engine_mod.QuantStrategyCore.evaluate_signal = staticmethod(deterministic_signal)
    e.step_candle = capture_after_symbol
    try:
        audit = engine_mod.run_simulation_pass(
            e, candles, list(order), data_label="SPARSE_SYMBOL_ORDER_REGRESSION",
            allow_sparse_data=True,
            bar_complete_callback=lambda ts, engine: bar_snapshots.append((
                ts, round(engine.risk_mgr.current_equity, 6),
                round(engine.risk_mgr.realized_equity, 6),
                round(engine.risk_mgr.unrealized_pnl, 6),
                len(engine.open_positions), len(engine.pending),
            )),
        )
    finally:
        engine_mod.QuantStrategyCore.evaluate_signal = staticmethod(original_evaluate)

    ledger = sorted((
        trade.token, trade.direction, trade.entry_date, trade.exit_date,
        round(trade.entry_price, 8), round(trade.exit_price, 8),
        round(trade.gross_pnl, 6), round(trade.exchange_fees_usdt, 6),
        round(trade.slippage_cost_usdt, 6), round(trade.funding_cost_usdt, 6),
        round(trade.pnl_usdt, 6), trade.exit_reason,
    ) for trade in e.closed_trades)
    return {
        "first_seen": first_seen,
        "ledger": ledger,
        "equity_path": equity_path,
        "bar_snapshots": bar_snapshots,
        "daily_stop": e.risk_mgr.daily_stop_triggered,
        "kill_switch": e.risk_mgr.kill_switch_triggered,
        "net_pnl": round(audit["net_pnl"], 6),
        "max_dd": round(audit["max_dd_pct"], 6),
    }


def test_sparse_replay_admits_late_symbols_after_warmup_and_is_order_invariant():
    forward = _run_sparse_replay_symbol_order(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    reverse = _run_sparse_replay_symbol_order(["SOLUSDT", "ETHUSDT", "BTCUSDT"])
    hour = 3_600_000
    start_ts = 1_800_000_000_000

    expected_first_seen = {
        "BTCUSDT": start_ts + 25 * hour,
        "ETHUSDT": start_ts + 30 * hour,
        "SOLUSDT": start_ts + 35 * hour,
    }
    assert forward["first_seen"] == expected_first_seen
    assert reverse["first_seen"] == expected_first_seen
    assert {row[0] for row in forward["ledger"]} == {"ETHUSDT", "SOLUSDT"}
    assert forward["ledger"] == reverse["ledger"]
    # Compare only timestamps after the latest symbol has entered the universe.
    forward_path = [row for row in forward["equity_path"] if row[0] >= start_ts + 36 * hour]
    reverse_path = [row for row in reverse["equity_path"] if row[0] >= start_ts + 36 * hour]
    assert len(forward_path) == len(reverse_path), (len(forward_path), len(reverse_path))
    path_differences = [
        (left, right) for left, right in zip(forward_path, reverse_path)
        if left != right
    ]
    assert not path_differences, path_differences[:5]
    assert forward["daily_stop"] == reverse["daily_stop"]
    assert forward["kill_switch"] == reverse["kill_switch"]
    assert forward["bar_snapshots"] == reverse["bar_snapshots"]
    assert forward["net_pnl"] == reverse["net_pnl"]
    assert forward["max_dd"] == reverse["max_dd"]


if __name__ == "__main__":
    tests = [(name, value) for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for name, test in tests:
        test()
        print("PASS", name)
    print(f"{len(tests)}/{len(tests)} tests passed")
