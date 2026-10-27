"""Focused tests for next-bar entry behavior under gaps in the research engine copy."""
import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).with_name("Bybit_Trading_Engine_v14_research.py")
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

        @staticmethod
        def can_open_new_trade(count):
            return True, "OK"

        @staticmethod
        def calculate_position_size(entry_price, stop_price, order_type="market"):
            return 1000.0, 10.0

    e.risk_mgr = RiskSpy()
    return e


def pending_signal(order_type="market", ref=100.0):
    return {
        "direction": "long", "entry_price": ref, "order_type": order_type,
        "strategy": "test", "stop_dist": 2.0,
    }


def candle(open_, high, low, close, ts=1_800_000_000_000):
    return engine_mod.Candle(ts=ts, open=open_, high=high, low=low, close=close, volume=10)


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


def test_limit_buy_gapped_below_limit_fills_at_open_not_worse_limit():
    e = make_engine(max_chase_pct=1.5)
    e.pending["BTCUSDT"] = pending_signal("limit", 100.0)
    opened = e._try_fill_pending("BTCUSDT", candle(98.0, 99.0, 97.0, 98.5))
    assert opened is True
    assert e.open_positions["BTCUSDT"].entry_price == 98.0


def test_limit_buy_not_touched_is_not_filled():
    e = make_engine(max_chase_pct=1.5)
    e.pending["BTCUSDT"] = pending_signal("limit", 100.0)
    opened = e._try_fill_pending("BTCUSDT", candle(101.0, 102.0, 100.2, 101.5))
    assert opened is False
    assert "BTCUSDT" not in e.open_positions
    assert "BTCUSDT" not in e.pending


if __name__ == "__main__":
    tests = [
        test_market_long_gap_above_chase_limit_is_cancelled,
        test_market_long_gap_within_limit_fills_at_next_open,
        test_limit_buy_gapped_below_limit_fills_at_open_not_worse_limit,
        test_limit_buy_not_touched_is_not_filled,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"{len(tests)}/{len(tests)} tests passed")