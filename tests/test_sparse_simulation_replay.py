"""Deterministic tests for sparse shared-capital replay event ordering."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import Bybit_Trading_Engine_v14_research as em


class _Risk:
    current_equity = 10_000.0

    @staticmethod
    def can_open_new_trade(_count):
        return True, "OK"


class _Notifier:
    @staticmethod
    def format_check_engine_alert(*_args):
        return "audit"


class _Telegram:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(message)


class _SparseEngine:
    def __init__(self):
        self.cfg = em.BotConfig(timeframe="1h", active_trading_pool=["AAAUSDT", "BBBUSDT"])
        self._state_restored = False
        self.open_positions = {}
        self.pending = {}
        self.risk_mgr = _Risk()
        self.tg = _Telegram()
        self._bar_entry_risk_budgets = {}
        self.mark_batches = []
        self.processed = []
        self.final_marks = None
        self.reset_calls = 0

    def reset_state_for_new_run(self):
        self.reset_calls += 1
        self.open_positions.clear()
        self.pending.clear()
        self.mark_batches.clear()
        self.processed.clear()

    def _prepare_portfolio_intrabar_marks(self, candles):
        self.mark_batches.append((next(iter(candles.values())).ts, tuple(sorted(candles))))

    def _update_mark_to_market(self, _ts):
        pass

    def _prepare_pending_entry_risk_budgets(self):
        self._bar_entry_risk_budgets = {}

    def step_candle(self, symbol, history, *, evaluate_new_signal=False):
        assert evaluate_new_signal is False
        self.processed.append((symbol, history[-1].ts, len(history)))
        return len(history) >= 26

    def _persist(self):
        pass

    def finalize_open_positions(self, marks, exit_reason):
        assert exit_reason == "end_of_test"
        self.final_marks = dict(marks)

    def export_journal_for_dashboard(self):
        return {
            "total_trades": 0, "net_pnl": 0.0, "ret_pct": 0.0,
            "pf": 0.0, "expectancy_r": 0.0, "max_dd_pct": 0.0,
            "passed_count": 0, "all_ok": False,
        }


def _series(start_index, end_index, base_ts):
    return [
        em.Candle(
            ts=base_ts + i * 3_600_000,
            open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0,
        )
        for i in range(start_index, end_index + 1)
    ]


def test_sparse_replay_uses_union_grid_and_common_terminal_cutoff():
    original_notifier = em.CarDashboardTelegramNotifier
    em.CarDashboardTelegramNotifier = _Notifier
    base_ts = 1_700_002_800_000  # aligned UTC hour
    engine = _SparseEngine()
    context_calls = []
    callback_calls = []

    def context_provider(bar_close_ts, histories, _cfg):
        context_calls.append((bar_close_ts, tuple(sorted(histories))))
        return {"as_of": bar_close_ts}

    def signal_evaluator(symbol, history, _cfg, context):
        assert context["as_of"] == history[-1].ts + 3_600_000
        return None

    def callback(bar_close_ts, _engine):
        callback_calls.append(bar_close_ts)

    audit = em.run_sparse_simulation_pass(
        engine,
        {
            "AAAUSDT": _series(0, 35, base_ts),
            "BBBUSDT": _series(5, 30, base_ts),
        },
        ["AAAUSDT", "BBBUSDT"],
        signal_evaluator=signal_evaluator,
        signal_context_provider=context_provider,
        bar_complete_callback=callback,
    )

    assert audit["total_trades"] == 0
    assert engine.reset_calls == 1
    assert engine.mark_batches[0] == (
        base_ts + 25 * 3_600_000, ("AAAUSDT",)
    )
    assert engine.mark_batches[-1] == (
        base_ts + 30 * 3_600_000, ("AAAUSDT", "BBBUSDT")
    )
    assert all(ts <= base_ts + 30 * 3_600_000 for _, ts, _ in engine.processed)
    assert callback_calls == [
        base_ts + i * 3_600_000 + 3_600_000 for i in range(25, 31)
    ]
    assert context_calls[0] == (
        base_ts + 26 * 3_600_000, ("AAAUSDT",)
    )
    assert context_calls[-1] == (
        base_ts + 31 * 3_600_000, ("AAAUSDT", "BBBUSDT")
    )
    assert engine.final_marks == {}
    em.CarDashboardTelegramNotifier = original_notifier


def test_sparse_replay_rejects_empty_or_duplicate_symbol_universe():
    base_ts = 1_700_002_800_000
    engine = _SparseEngine()
    rows = _series(0, 26, base_ts)
    for symbols in ([], ["AAAUSDT", "AAAUSDT"]):
        try:
            em.run_sparse_simulation_pass(engine, {"AAAUSDT": rows}, symbols)
        except ValueError as exc:
            assert "non-empty unique" in str(exc)
        else:
            raise AssertionError(f"invalid sparse universe accepted: {symbols!r}")


if __name__ == "__main__":
    for test in (
        test_sparse_replay_uses_union_grid_and_common_terminal_cutoff,
        test_sparse_replay_rejects_empty_or_duplicate_symbol_universe,
    ):
        test()
        print(f"PASS {test.__name__}")
