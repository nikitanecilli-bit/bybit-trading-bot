"""Fail-closed tests for Plan B state persistence."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

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


def sample_risk_data():
    return engine.AdaptiveRiskManager(engine.BotConfig()).to_dict()


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
                    "symbol": "ETHUSDT", "direction": "short",
                    "strategy": "state-test", "signal_ts": 1_800_000_000_000,
                    "entry_price": 2000.0, "stop_price": 2100.0,
                    "tp1_price": 1900.0, "tp2_price": 1800.0,
                    "stop_dist": 100.0, "atr": 50.0, "vol_ratio": 1.25,
                    "session": "eu", "order_type": "limit",
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

    def test_disabled_persistence_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "disabled.json"
            engine.PlanBStatePersistence(str(path), enabled=False).save_state(
                engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                {}, {}, 0,
            )
            self.assertFalse(path.exists())

    def test_atomic_replace_failure_raises_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            with patch("os.replace", side_effect=OSError("simulated disk failure")):
                with self.assertRaisesRegex(RuntimeError, "Не удалось сохранить"):
                    writer.save_state(
                        engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                        {"BTCUSDT": sample_position()}, {}, 42,
                    )
            self.assertFalse(path.exists())
            self.assertFalse(Path(str(path) + ".tmp").exists())

    def test_corrupt_json_raises_instead_of_returning_empty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrupt.json"
            path.write_text('{"open_positions": ', encoding="utf-8")
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            with self.assertRaisesRegex(RuntimeError, "Не удалось безопасно восстановить"):
                engine.PlanBStatePersistence(str(path)).load_state(risk)

    def test_failed_position_restore_does_not_mutate_risk_manager(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "partial.json"
            path.write_text(json.dumps({
                "risk": sample_risk_data(),
                "open_positions": {"BTCUSDT": {"symbol": "BTCUSDT"}},
                "pending_orders": {}, "trade_seq": 0,
            }), encoding="utf-8")
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            before = risk.to_dict().copy()
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(risk.to_dict(), before)

    def test_invalid_pending_payload_does_not_mutate_risk_manager(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending.json"
            path.write_text(json.dumps({
                "risk": sample_risk_data(), "open_positions": {},
                "pending_orders": [], "trade_seq": 0,
            }), encoding="utf-8")
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            before = risk.to_dict().copy()
            with self.assertRaisesRegex(RuntimeError, "Не удалось безопасно восстановить"):
                engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(risk.to_dict(), before)

    def _assert_invalid_position_payload(self, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-position.json"
            payload = {
                "risk": sample_risk_data(),
                "open_positions": {"BTCUSDT": engine.asdict(sample_position())},
                "pending_orders": {},
                "trade_seq": 42,
            }
            mutate(payload["open_positions"]["BTCUSDT"])
            path.write_text(json.dumps(payload, allow_nan=True), encoding="utf-8")
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            before = risk.to_dict().copy()
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(risk.to_dict(), before)

    def test_unknown_position_field_is_rejected_not_silently_dropped(self):
        self._assert_invalid_position_payload(lambda position: position.update({"future_field": 1}))

    def test_invalid_position_direction_is_rejected(self):
        self._assert_invalid_position_payload(lambda position: position.update({"direction": "sideways"}))

    def test_non_finite_position_price_is_rejected(self):
        self._assert_invalid_position_payload(lambda position: position.update({"entry_price": float("nan")}))

    def test_negative_position_size_is_rejected(self):
        self._assert_invalid_position_payload(lambda position: position.update({"size_usdt": -100.0}))

    def test_valid_tp1_partial_position_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tp1-state.json"
            position = sample_position()
            position.tp1_hit = True
            position.remaining_fraction = 0.5
            position.realized_tp1_gross_usdt = 30.0
            position.tp1_ts_ms = 1_800_000_003_600
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            writer.save_state(engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                              {"BTCUSDT": position}, {}, 42)
            restored, _, _ = engine.PlanBStatePersistence(str(path)).load_state(
                engine.AdaptiveRiskManager(engine.BotConfig())
            )
            self.assertEqual(restored["BTCUSDT"], position)

    def test_tp1_not_hit_cannot_restore_partial_remaining_fraction(self):
        self._assert_invalid_position_payload(
            lambda position: position.update({"remaining_fraction": 0.5})
        )

    def test_tp1_hit_requires_partial_remaining_fraction(self):
        def mutate(position):
            position.update({"tp1_hit": True, "remaining_fraction": 1.0,
                             "realized_tp1_gross_usdt": 30.0})
        self._assert_invalid_position_payload(mutate)

    def test_tp1_realized_pnl_requires_tp1_hit(self):
        self._assert_invalid_position_payload(
            lambda position: position.update({"realized_tp1_gross_usdt": 12.0})
        )

    def test_long_targets_must_be_ordered_above_entry(self):
        self._assert_invalid_position_payload(
            lambda position: position.update({"tp1_price": 110.0, "tp2_price": 108.0})
        )

    def test_short_targets_must_be_ordered_below_entry(self):
        def mutate(position):
            position.update({"direction": "short", "tp1_price": 90.0, "tp2_price": 95.0})
        self._assert_invalid_position_payload(mutate)

    def test_restore_rejects_symbol_in_both_open_and_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overlap.json"
            payload = {
                "risk": sample_risk_data(),
                "open_positions": {"BTCUSDT": engine.asdict(sample_position())},
                "pending_orders": {
                    "BTCUSDT": {"symbol": "BTCUSDT", "direction": "long",
                                "strategy": "test", "entry_price": 100.0,
                                "stop_dist": 5.0, "order_type": "market"}
                },
                "trade_seq": 42,
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            before = risk.to_dict().copy()
            with self.assertRaisesRegex(RuntimeError, "Не удалось безопасно восстановить"):
                engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(risk.to_dict(), before)

    def test_restore_rejects_duplicate_trade_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate-id.json"
            first = engine.asdict(sample_position())
            second = engine.asdict(sample_position())
            second.update({"symbol": "ETHUSDT", "entry_price": 2000.0,
                           "stop_price": 1900.0, "tp1_price": 2120.0,
                           "tp2_price": 2240.0})
            payload = {
                "risk": sample_risk_data(),
                "open_positions": {"BTCUSDT": first, "ETHUSDT": second},
                "pending_orders": {},
                "trade_seq": 42,
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            before = risk.to_dict().copy()
            with self.assertRaisesRegex(RuntimeError, "Не удалось безопасно восстановить"):
                engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(risk.to_dict(), before)

    def _write_pending_fixture(self, path, signal):
        path.write_text(json.dumps({
            "risk": sample_risk_data(), "open_positions": {},
            "pending_orders": {"BTCUSDT": signal}, "trade_seq": 0,
        }, allow_nan=True), encoding="utf-8")

    def test_pending_non_object_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending-entry.json"
            self._write_pending_fixture(path, [])
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            before = risk.to_dict().copy()
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(risk.to_dict(), before)

    def test_pending_missing_required_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending-missing.json"
            self._write_pending_fixture(path, {
                "symbol": "BTCUSDT", "direction": "long",
                "strategy": "test", "entry_price": 100, "order_type": "market",
            })
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            with self.assertRaisesRegex(RuntimeError, "Не удалось безопасно восстановить"):
                engine.PlanBStatePersistence(str(path)).load_state(risk)

    def test_pending_invalid_direction_and_numeric_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending-invalid.json"
            self._write_pending_fixture(path, {
                "symbol": "BTCUSDT", "direction": "sideways",
                "strategy": "test", "entry_price": 100, "stop_dist": 2,
                "order_type": "market",
            })
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(risk)

    def test_pending_invalid_order_type_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending-order-type.json"
            self._write_pending_fixture(path, {
                "symbol": "BTCUSDT", "direction": "long",
                "strategy": "test", "entry_price": 100, "stop_dist": 2,
                "order_type": "post_only",
            })
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(risk)

    def test_pending_non_finite_price_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending-nan.json"
            self._write_pending_fixture(path, {
                "symbol": "BTCUSDT", "direction": "long",
                "strategy": "test", "entry_price": float("nan"),
                "stop_dist": 2, "order_type": "market",
            })
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(risk)

    def _assert_invalid_risk_payload(self, risk_payload):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-risk.json"
            complete_risk = sample_risk_data()
            complete_risk.update(risk_payload)
            path.write_text(
                json.dumps({
                    "risk": complete_risk,
                    "open_positions": {},
                    "pending_orders": {},
                    "trade_seq": 0,
                }, allow_nan=True),
                encoding="utf-8",
            )
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            before = risk.to_dict().copy()
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(risk.to_dict(), before)

    def test_risk_nan_equity_is_rejected(self):
        self._assert_invalid_risk_payload({"current_equity": float("nan")})

    def test_risk_negative_equity_is_rejected(self):
        self._assert_invalid_risk_payload({"realized_equity": -1.0})

    def test_risk_drawdown_out_of_range_is_rejected(self):
        self._assert_invalid_risk_payload({"max_drawdown_pct": 101.0})

    def test_risk_invalid_day_and_flag_types_are_rejected(self):
        for payload in (
            {"current_day_str": "2026-02-30"},
            {"kill_switch_triggered": "false"},
        ):
            with self.subTest(payload=payload):
                self._assert_invalid_risk_payload(payload)

    def test_risk_unknown_field_is_rejected(self):
        self._assert_invalid_risk_payload({"equity_usdt": 10000.0})

    def test_invalid_trade_sequence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sequence.json"
            path.write_text(json.dumps({
                "risk": sample_risk_data(), "open_positions": {},
                "pending_orders": {}, "trade_seq": -1,
            }), encoding="utf-8")
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            before = risk.to_dict().copy()
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(risk.to_dict(), before)

    def test_invalid_position_shape_raises_instead_of_dropping_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            path.write_text(json.dumps({
                "risk": sample_risk_data(),
                "open_positions": {"BTCUSDT": {"symbol": "BTCUSDT"}},
                "pending_orders": {}, "trade_seq": 0,
            }), encoding="utf-8")
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            with self.assertRaisesRegex(RuntimeError, "Не удалось безопасно восстановить"):
                engine.PlanBStatePersistence(str(path)).load_state(risk)


if __name__ == "__main__":
    unittest.main(verbosity=2)
