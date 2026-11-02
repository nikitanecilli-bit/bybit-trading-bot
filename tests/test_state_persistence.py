"""Fail-closed tests for Plan B state persistence."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import Bybit_Trading_Engine_v14_research as engine


def sample_position():
    return engine.OpenPositionState(
        trade_id="T-0042", symbol="BTCUSDT", direction="long",
        strategy="state-test", entry_ts=1_800_000_000_000,
        entry_price=100.0, stop_price=95.0, tp1_price=106.0,
        tp2_price=112.0, initial_stop_dist=5.0, size_usdt=1_000.0,
        risk_usdt=60.0, order_type="market",
    )


class StatePersistenceTests(unittest.TestCase):
    def test_missing_backup_is_a_clean_cold_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.json"
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            positions, pending, seq = engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(positions, {})
            self.assertEqual(pending, {})
            self.assertEqual(seq, 0)

    def test_valid_backup_round_trips_risk_positions_pending_and_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            risk.realized_equity = 9_500.0
            risk.unrealized_pnl = -125.0
            risk.current_equity = 9_375.0
            risk.peak_equity = 10_200.0
            risk.kill_switch_triggered = True
            risk.daily_stop_triggered = True
            position = sample_position()
            pending = {
                "ETHUSDT": {
                    "direction": "short", "entry_price": 2000.0,
                    "order_type": "limit", "strategy": "state-test",
                    "stop_dist": 100.0,
                }
            }
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            writer.save_state(cfg, risk, {"BTCUSDT": position}, pending, trade_seq=42)

            restored_risk = engine.AdaptiveRiskManager(engine.BotConfig())
            positions, restored_pending, seq = engine.PlanBStatePersistence(str(path)).load_state(restored_risk)

            self.assertEqual(seq, 42)
            self.assertEqual(restored_pending, pending)
            self.assertEqual(positions["BTCUSDT"], position)
            self.assertEqual(restored_risk.realized_equity, 9_500.0)
            self.assertEqual(restored_risk.unrealized_pnl, -125.0)
            self.assertEqual(restored_risk.current_equity, 9_375.0)
            self.assertEqual(restored_risk.peak_equity, 10_200.0)
            self.assertTrue(restored_risk.kill_switch_triggered)
            self.assertTrue(restored_risk.daily_stop_triggered)

    def test_corrupt_json_raises_instead_of_returning_empty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrupt.json"
            path.write_text('{"open_positions": ', encoding="utf-8")
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            with self.assertRaisesRegex(RuntimeError, "Не удалось безопасно восстановить"):
                engine.PlanBStatePersistence(str(path)).load_state(risk)

    def test_invalid_position_shape_raises_instead_of_dropping_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            path.write_text(
                '{"risk": {}, "open_positions": {"BTCUSDT": {"symbol": "BTCUSDT"}}}',
                encoding="utf-8",
            )
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            with self.assertRaisesRegex(RuntimeError, "Не удалось безопасно восстановить"):
                engine.PlanBStatePersistence(str(path)).load_state(risk)


if __name__ == "__main__":
    unittest.main(verbosity=2)
