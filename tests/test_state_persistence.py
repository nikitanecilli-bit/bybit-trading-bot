"""Fail-closed tests for Plan B state persistence."""
from pathlib import Path
import os
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
        strategy="state-test", entry_ts=1_790_000_000_000,
        entry_price=100.0, stop_price=95.0, tp1_price=106.0,
        tp2_price=112.0, initial_stop_dist=5.0, size_usdt=1_000.0,
        risk_usdt=60.0, order_type="market", breakout_level=101.0,
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
            risk.max_drawdown_pct = (10_200.0 - 9_375.0) / 10_200.0 * 100.0
            risk.kill_switch_triggered = True
            risk.daily_stop_triggered = True
            position = sample_position()
            position.risk_tier_id = 2
            position.risk_limit_value = "500000"
            position.maintenance_margin_rate = "0.01"
            position.maintenance_margin_deduction = "500"
            pending = {
                "ETHUSDT": {
                    "symbol": "ETHUSDT", "direction": "short",
                    "strategy": "state-test", "signal_ts": 1_790_000_000_000,
                    "entry_price": 2000.0, "stop_price": 2100.0,
                    "tp1_price": 1900.0, "tp2_price": 1800.0,
                    "stop_dist": 100.0, "atr": 50.0, "vol_ratio": 1.25,
                    "session": "eu", "order_type": "limit",
                    "breakout_level": 2010.0,
                }
            }
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            writer.save_state(cfg, risk, {"BTCUSDT": position}, pending, trade_seq=42,
                               last_mark_prices={"BTCUSDT": 87.5})

            restored_risk = engine.AdaptiveRiskManager(engine.BotConfig())
            restored_writer = engine.PlanBStatePersistence(str(path))
            positions, restored_pending, seq = restored_writer.load_state(restored_risk)
            self.assertEqual(restored_writer.last_mark_prices, {"BTCUSDT": 87.5})

            self.assertEqual(seq, 42)
            self.assertEqual(restored_pending, pending)
            self.assertEqual(positions["BTCUSDT"], position)
            self.assertEqual(positions["BTCUSDT"].risk_tier_id, 2)
            self.assertEqual(positions["BTCUSDT"].risk_limit_value, "500000")
            self.assertEqual(positions["BTCUSDT"].maintenance_margin_rate, "0.01")
            self.assertEqual(positions["BTCUSDT"].maintenance_margin_deduction, "500")
            self.assertEqual(positions["BTCUSDT"].breakout_level, 101.0)
            self.assertEqual(restored_pending["ETHUSDT"]["breakout_level"], 2010.0)
            self.assertEqual(restored_risk.realized_equity, 9_500.0)
            self.assertEqual(restored_risk.unrealized_pnl, -125.0)
            self.assertEqual(restored_risk.current_equity, 9_375.0)
            self.assertEqual(restored_risk.peak_equity, 10_200.0)
            self.assertTrue(restored_risk.kill_switch_triggered)
            self.assertTrue(restored_risk.daily_stop_triggered)


    def test_restored_engine_uses_persisted_mark_before_first_new_candle(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "marked-state.json"
            cfg = engine.BotConfig()
            position = sample_position()
            mark_price = 87.5
            mark_ts = position.entry_ts + 3_600_000

            source = engine.UnifiedQuantEngine.__new__(engine.UnifiedQuantEngine)
            source.open_positions = {"BTCUSDT": position}
            source._last_mark_prices = {"BTCUSDT": mark_price}
            source._intrabar_risk_marks = {}
            source._intrabar_risk_marks_ts = mark_ts
            source.funding_dir = None
            unrealized = source._unrealized_pnl_at_marks(mark_ts)
            risk = engine.AdaptiveRiskManager(cfg)
            risk.mark_to_market(unrealized, mark_ts)

            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": position}, {}, 42,
                last_mark_prices={"BTCUSDT": mark_price},
            )
            restored = engine.UnifiedQuantEngine(
                restore_plan_b=True, state_path=str(path),
            )

            self.assertEqual(restored._last_mark_prices, {"BTCUSDT": mark_price})
            self.assertAlmostEqual(
                restored._unrealized_pnl_at_marks(mark_ts), unrealized, places=8,
            )
            self.assertAlmostEqual(restored.risk_mgr.current_equity, risk.current_equity, places=4)

    def test_open_position_backup_without_last_mark_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-mark.json"
            cfg = engine.BotConfig()
            position = sample_position()
            risk = engine.AdaptiveRiskManager(cfg)
            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": position}, {}, 42,
                last_mark_prices={"BTCUSDT": position.entry_price},
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.pop("last_mark_prices")
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(
                    engine.AdaptiveRiskManager(cfg)
                )



    def test_engine_persist_writes_last_marks_for_open_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "engine-persist.json"
            bot = engine.UnifiedQuantEngine.__new__(engine.UnifiedQuantEngine)
            bot.cfg = engine.BotConfig()
            bot.risk_mgr = engine.AdaptiveRiskManager(bot.cfg)
            bot.plan_b = engine.PlanBStatePersistence(str(path), enabled=True)
            bot.open_positions = {"BTCUSDT": sample_position()}
            bot.pending = {}
            bot.trade_seq = 42
            bot._last_mark_prices = {"BTCUSDT": 103.25}

            bot._persist()

            restored_risk = engine.AdaptiveRiskManager(engine.BotConfig())
            restored_writer = engine.PlanBStatePersistence(str(path))
            positions, _, seq = restored_writer.load_state(restored_risk)
            self.assertEqual(seq, 42)
            self.assertEqual(positions["BTCUSDT"], bot.open_positions["BTCUSDT"])
            self.assertEqual(restored_writer.last_mark_prices, {"BTCUSDT": 103.25})

    def test_save_open_position_requires_last_mark(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-save-mark.json"
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            with self.assertRaisesRegex(RuntimeError, "last marks"):
                writer.save_state(
                    engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                    {"BTCUSDT": sample_position()}, {}, 42,
                )
            self.assertFalse(path.exists())

    def test_save_rejects_non_positive_or_non_finite_last_mark(self):
        for invalid_mark in (0.0, -1.0, float("nan"), float("inf"), True):
            with self.subTest(mark=invalid_mark), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "invalid-mark.json"
                writer = engine.PlanBStatePersistence(str(path), enabled=True)
                with self.assertRaisesRegex(RuntimeError, "last mark"):
                    writer.save_state(
                        engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                        {"BTCUSDT": sample_position()}, {}, 42,
                        last_mark_prices={"BTCUSDT": invalid_mark},
                    )
                self.assertFalse(path.exists())


    def test_restored_state_cannot_be_reused_for_a_fresh_backtest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "restored-backtest.json"
            cfg = engine.BotConfig()
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            writer.save_state(
                cfg, engine.AdaptiveRiskManager(cfg), {}, {}, 0,
                last_mark_prices={},
            )
            restored = engine.UnifiedQuantEngine(
                restore_plan_b=True, state_path=str(path),
            )
            self.assertTrue(restored._state_restored)
            with self.assertRaisesRegex(RuntimeError, "восстановленного состояния"):
                engine.run_simulation_pass(restored, {}, [])

    def test_disabled_persistence_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "disabled.json"
            engine.PlanBStatePersistence(str(path), enabled=False).save_state(
                engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                {}, {}, 0,
            )
            self.assertFalse(path.exists())

    def test_successful_save_fsyncs_file_and_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            real_fsync = os.fsync
            with patch("os.fsync", wraps=real_fsync) as fsync_mock:
                writer.save_state(
                    engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                    {}, {}, 0,
                )
            self.assertEqual(fsync_mock.call_count, 2 if os.name == "posix" else 1)
            self.assertTrue(path.exists())

    @unittest.skipUnless(os.name == "posix", "parent-directory fsync is POSIX-only")
    def test_parent_directory_fsync_failure_raises_after_atomic_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            real_fsync = os.fsync
            calls = {"count": 0}

            def fail_directory_fsync(fd):
                calls["count"] += 1
                if calls["count"] == 1:
                    return real_fsync(fd)
                raise OSError("simulated directory fsync failure")

            with patch("os.fsync", side_effect=fail_directory_fsync):
                with self.assertRaisesRegex(RuntimeError, "Не удалось сохранить"):
                    writer.save_state(
                        engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                        {}, {}, 0,
                    )
            # Rename already happened before directory fsync failed; caller must
            # still stop because durability of the directory entry was not confirmed.
            self.assertTrue(path.exists())
            json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(Path(str(path) + ".tmp").exists())
            self.assertEqual(calls["count"], 2)

    def test_file_fsync_failure_preserves_previous_backup_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            previous = '{"previous": "durable"}'
            path.write_text(previous, encoding="utf-8")
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            with patch("os.fsync", side_effect=OSError("simulated fsync failure")):
                with self.assertRaisesRegex(RuntimeError, "Не удалось сохранить"):
                    writer.save_state(
                        engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                        {}, {}, 0,
                    )
            self.assertEqual(path.read_text(encoding="utf-8"), previous)
            self.assertFalse(Path(str(path) + ".tmp").exists())

    def test_atomic_replace_failure_raises_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            with patch("os.replace", side_effect=OSError("simulated disk failure")):
                with self.assertRaisesRegex(RuntimeError, "Не удалось сохранить"):
                    writer.save_state(
                        engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                        {"BTCUSDT": sample_position()}, {}, 42,
                        last_mark_prices={"BTCUSDT": sample_position().entry_price},
                    )
            self.assertFalse(path.exists())
            self.assertFalse(Path(str(path) + ".tmp").exists())

    def test_non_finite_state_save_preserves_previous_backup_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            previous = '{"previous": "known-good"}'
            path.write_text(previous, encoding="utf-8")
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            risk.unrealized_pnl = float("nan")
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            with self.assertRaisesRegex(RuntimeError, "Не удалось сохранить"):
                writer.save_state(cfg, risk, {}, {}, 0)
            self.assertEqual(path.read_text(encoding="utf-8"), previous)
            self.assertFalse(Path(str(path) + ".tmp").exists())

    def test_infinite_position_value_cannot_be_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "infinite-position.json"
            position = sample_position()
            position.max_favorable_px = float("inf")
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            with self.assertRaisesRegex(RuntimeError, "Не удалось сохранить"):
                writer.save_state(engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                                  {"BTCUSDT": position}, {}, 42,
                                  last_mark_prices={"BTCUSDT": position.entry_price})
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
                "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": sample_risk_data(),
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
                "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": sample_risk_data(), "open_positions": {},
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
                "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": sample_risk_data(),
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

    def test_exchange_sized_contract_quantities_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exchange-sized-state.json"
            position = sample_position()
            position.exchange_sized = True
            position.leverage = 5.0
            position.contract_qty = "1.0"
            position.tp1_contract_qty = "0.5"
            position.remaining_contract_qty = "0.5"
            position.qty_step = "0.1"
            position.min_order_qty = "0.1"
            position.min_notional_value = "5"
            position.risk_tier_max_leverage = "5"
            position.initial_margin_usdt = "20"
            position.maintenance_margin_usdt = "0.5"
            position.tp1_hit = True
            position.remaining_fraction = 0.5
            position.realized_tp1_gross_usdt = 30.0
            position.tp1_ts_ms = 1_790_000_003_600
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            writer.save_state(engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                              {"BTCUSDT": position}, {}, 42,
                              last_mark_prices={"BTCUSDT": position.entry_price})
            restored, _, _ = engine.PlanBStatePersistence(str(path)).load_state(
                engine.AdaptiveRiskManager(engine.BotConfig())
            )
            self.assertEqual(restored["BTCUSDT"], position)

    def test_exchange_sized_state_rejects_fractional_contract_quantity(self):
        def mutate(position):
            position.update({
                "exchange_sized": True, "contract_qty": "1.0",
                "tp1_contract_qty": None, "remaining_contract_qty": "0.55",
                "qty_step": "0.1", "min_order_qty": "0.1",
                "min_notional_value": "5",
            })
        self._assert_invalid_position_payload(mutate)

    def test_valid_tp1_partial_position_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tp1-state.json"
            position = sample_position()
            position.tp1_hit = True
            position.remaining_fraction = 0.5
            position.realized_tp1_gross_usdt = 30.0
            position.tp1_ts_ms = 1_790_000_003_600
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            writer.save_state(engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                              {"BTCUSDT": position}, {}, 42,
                              last_mark_prices={"BTCUSDT": position.entry_price})
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

    def test_tp1_hit_requires_event_timestamp(self):
        def mutate(position):
            position.update({"tp1_hit": True, "remaining_fraction": 0.5,
                             "realized_tp1_gross_usdt": 10.0, "tp1_ts_ms": None})
        self._assert_invalid_position_payload(mutate)

    def test_tp1_timestamp_cannot_precede_entry(self):
        def mutate(position):
            position.update({"tp1_hit": True, "remaining_fraction": 0.5,
                             "realized_tp1_gross_usdt": 10.0,
                             "tp1_ts_ms": position["entry_ts"] - 1})
        self._assert_invalid_position_payload(mutate)

    def test_tp1_timestamp_requires_tp1_hit(self):
        def mutate(position):
            position.update({"tp1_ts_ms": position["entry_ts"] + 3_600_000})
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
                "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": sample_risk_data(),
                "open_positions": {"BTCUSDT": engine.asdict(sample_position())},
                "last_mark_prices": {"BTCUSDT": 100.0},
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
                "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": sample_risk_data(),
                "open_positions": {"BTCUSDT": first, "ETHUSDT": second},
                "last_mark_prices": {"BTCUSDT": 100.0, "ETHUSDT": 2000.0},
                "pending_orders": {},
                "trade_seq": 42,
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            before = risk.to_dict().copy()
            with self.assertRaisesRegex(RuntimeError, "Не удалось безопасно восстановить"):
                engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(risk.to_dict(), before)

    def _write_pending_fixture(self, path, signal, add_signal_ts=True):
        if isinstance(signal, dict) and add_signal_ts:
            signal = {"signal_ts": 1_790_000_000_000, **signal}
        path.write_text(json.dumps({
            "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": sample_risk_data(), "open_positions": {},
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

    def test_future_position_entry_timestamp_is_rejected(self):
        self._assert_invalid_position_payload(
            lambda position: position.update({"entry_ts": 1_800_000_000_000})
        )

    def test_future_tp1_timestamp_is_rejected(self):
        def mutate(position):
            position.update({
                "tp1_hit": True, "remaining_fraction": 0.5,
                "realized_tp1_gross_usdt": 10.0,
                "tp1_ts_ms": 1_800_000_000_000,
            })
        self._assert_invalid_position_payload(mutate)

    def test_future_pending_signal_timestamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "future-pending.json"
            self._write_pending_fixture(path, {
                "symbol": "BTCUSDT", "direction": "long", "strategy": "test",
                "entry_price": 100, "stop_dist": 2, "order_type": "market",
                "signal_ts": 1_800_000_000_000,
            })
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(
                    engine.AdaptiveRiskManager(engine.BotConfig())
                )

    def test_pending_signal_timestamp_must_be_positive_integer(self):
        for bad_ts in (None, 0, -1, True, "1800000000000"):
            with self.subTest(signal_ts=bad_ts), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "pending-ts.json"
                self._write_pending_fixture(path, {
                    "symbol": "BTCUSDT", "direction": "long",
                    "strategy": "test", "entry_price": 100, "stop_dist": 2,
                    "order_type": "market", "signal_ts": bad_ts,
                })
                with self.assertRaises(RuntimeError):
                    engine.PlanBStatePersistence(str(path)).load_state(
                        engine.AdaptiveRiskManager(engine.BotConfig())
                    )

    def test_pending_unknown_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending-unknown.json"
            self._write_pending_fixture(path, {
                "symbol": "BTCUSDT", "direction": "long", "strategy": "test",
                "entry_price": 100, "stop_dist": 2, "order_type": "market",
                "future_field": 1,
            })
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(
                    engine.AdaptiveRiskManager(engine.BotConfig())
                )

    def test_pending_signal_timestamp_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending-no-ts.json"
            self._write_pending_fixture(path, {
                "symbol": "BTCUSDT", "direction": "long", "strategy": "test",
                "entry_price": 100, "stop_dist": 2, "order_type": "market",
            }, add_signal_ts=False)
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(
                    engine.AdaptiveRiskManager(engine.BotConfig())
                )

    def test_stale_pending_signal_is_discarded_instead_of_filled(self):
        bot = engine.UnifiedQuantEngine(persist_state=False)
        bot.cfg.timeframe = "1h"
        signal_ts = 1_800_000_000_000
        bot.pending["BTCUSDT"] = {
            "symbol": "BTCUSDT", "direction": "long", "strategy": "test",
            "signal_ts": signal_ts, "entry_price": 100.0, "stop_dist": 5.0,
            "order_type": "market",
        }
        stale_candle = engine.Candle(
            ts=signal_ts + 2 * 3_600_000, open=100.0, high=101.0,
            low=99.0, close=100.0, volume=10.0,
        )
        self.assertFalse(bot._try_fill_pending("BTCUSDT", stale_candle))
        self.assertNotIn("BTCUSDT", bot.pending)
        self.assertNotIn("BTCUSDT", bot.open_positions)

    def test_pending_signal_fills_only_on_immediately_next_bar(self):
        bot = engine.UnifiedQuantEngine(persist_state=False)
        bot.cfg.timeframe = "1h"
        signal_ts = 1_800_000_000_000
        bot.pending["BTCUSDT"] = {
            "symbol": "BTCUSDT", "direction": "long", "strategy": "test",
            "signal_ts": signal_ts, "entry_price": 100.0, "stop_dist": 5.0,
            "order_type": "market",
        }
        next_candle = engine.Candle(
            ts=signal_ts + 3_600_000, open=100.0, high=101.0,
            low=99.0, close=100.0, volume=10.0,
        )
        with (
            patch.object(bot.risk_mgr, "can_open_new_trade", return_value=(True, "ok")),
            patch.object(bot.risk_mgr, "calculate_position_size", return_value=(1_000.0, 50.0)),
        ):
            self.assertTrue(bot._try_fill_pending("BTCUSDT", next_candle))
        self.assertNotIn("BTCUSDT", bot.pending)
        self.assertIn("BTCUSDT", bot.open_positions)

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
                    "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": complete_risk,
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

    def test_risk_current_equity_must_match_realized_plus_unrealized(self):
        self._assert_invalid_risk_payload({"current_equity": 9_999.0})

    def test_risk_peak_equity_cannot_be_below_current_equity(self):
        self._assert_invalid_risk_payload({"peak_equity": 9_000.0})

    def test_risk_max_drawdown_must_cover_implied_current_drawdown(self):
        self._assert_invalid_risk_payload({
            "current_equity": 9_000.0, "realized_equity": 9_000.0,
            "unrealized_pnl": 0.0, "peak_equity": 10_000.0,
            "max_drawdown_pct": 2.0,
        })

    def test_risk_historical_max_drawdown_above_current_drawdown_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "historical-dd.json"
            risk_data = sample_risk_data()
            risk_data.update({
                "realized_equity": 9_900.0, "unrealized_pnl": 0.0,
                "current_equity": 9_900.0, "peak_equity": 10_000.0,
                "max_drawdown_pct": 5.0,
            })
            path.write_text(json.dumps({
                "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": risk_data, "open_positions": {},
                "pending_orders": {}, "trade_seq": 0,
            }), encoding="utf-8")
            restored = engine.AdaptiveRiskManager(engine.BotConfig())
            engine.PlanBStatePersistence(str(path)).load_state(restored)
            self.assertEqual(restored.current_equity, 9_900.0)
            self.assertEqual(restored.max_drawdown_pct, 5.0)

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

    def test_each_required_backup_envelope_field_is_mandatory(self):
        for field in ("saved_at_utc", "bot_version", "risk", "open_positions", "pending_orders", "trade_seq"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "incomplete-envelope.json"
                payload = {
                    "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": sample_risk_data(), "open_positions": {},
                    "pending_orders": {}, "trade_seq": 0,
                }
                payload.pop(field)
                path.write_text(json.dumps(payload), encoding="utf-8")
                risk = engine.AdaptiveRiskManager(engine.BotConfig())
                before = risk.to_dict().copy()
                with self.assertRaises(RuntimeError):
                    engine.PlanBStatePersistence(str(path)).load_state(risk)
                self.assertEqual(risk.to_dict(), before)

    def test_backup_metadata_requires_utc_timestamp_and_version(self):
        invalid_metadata = (
            {"saved_at_utc": "not-a-date", "bot_version": "test"},
            {"saved_at_utc": "2026-11-02T00:00:00", "bot_version": "test"},
            {"saved_at_utc": "2026-11-02T03:00:00+03:00", "bot_version": "test"},
            {"saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": ""},
        )
        for metadata in invalid_metadata:
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "metadata.json"
                payload = {
                    "saved_at_utc": metadata["saved_at_utc"],
                    "bot_version": metadata["bot_version"],
                    "risk": sample_risk_data(), "open_positions": {},
                    "pending_orders": {}, "trade_seq": 0,
                }
                path.write_text(json.dumps(payload), encoding="utf-8")
                risk = engine.AdaptiveRiskManager(engine.BotConfig())
                before = risk.to_dict().copy()
                with self.assertRaises(RuntimeError):
                    engine.PlanBStatePersistence(str(path)).load_state(risk)
                self.assertEqual(risk.to_dict(), before)

    def test_missing_protective_risk_flag_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-risk-flag.json"
            risk_data = sample_risk_data()
            risk_data.pop("kill_switch_triggered")
            path.write_text(json.dumps({
                "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": risk_data, "open_positions": {},
                "pending_orders": {}, "trade_seq": 0,
            }), encoding="utf-8")
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            before = risk.to_dict().copy()
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(risk)
            self.assertEqual(risk.to_dict(), before)

    def test_invalid_breakout_level_in_backup_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-breakout-level.json"
            cfg = engine.BotConfig()
            position = sample_position()
            risk = engine.AdaptiveRiskManager(cfg)
            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": position}, {}, 42,
                last_mark_prices={"BTCUSDT": position.entry_price},
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["open_positions"]["BTCUSDT"]["breakout_level"] = "invalid"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(
                    engine.AdaptiveRiskManager(cfg)
                )

    def test_invalid_trade_sequence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sequence.json"
            path.write_text(json.dumps({
                "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": sample_risk_data(), "open_positions": {},
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
                "saved_at_utc": "2026-11-02T00:00:00+00:00", "bot_version": "test", "risk": sample_risk_data(),
                "open_positions": {"BTCUSDT": {"symbol": "BTCUSDT"}},
                "pending_orders": {}, "trade_seq": 0,
            }), encoding="utf-8")
            risk = engine.AdaptiveRiskManager(engine.BotConfig())
            with self.assertRaisesRegex(RuntimeError, "Не удалось безопасно восстановить"):
                engine.PlanBStatePersistence(str(path)).load_state(risk)


if __name__ == "__main__":
    unittest.main(verbosity=2)
