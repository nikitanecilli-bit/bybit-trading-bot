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


def execution_page_chain(start_ms, count, *, final_has_next=False):
    from exchange_execution_identity import ExchangeExecutionPageObservation
    return tuple(
        ExchangeExecutionPageObservation(
            page_index=index,
            request_started_at_ms=start_ms + index * 10,
            request_completed_at_ms=start_ms + index * 10 + 5,
            row_count=0,
            has_next_page=(index < count - 1) or final_has_next,
        )
        for index in range(count)
    )


class StatePersistenceTests(unittest.TestCase):
    def _restored_engine_with_joined_histories(self):
        from types import SimpleNamespace
        bot = engine.UnifiedQuantEngine.__new__(engine.UnifiedQuantEngine)
        bot.open_positions = {"BTCUSDT": sample_position()}
        bot.instrument_spec_history = object()
        bot.risk_tier_history = object()
        bot.max_market_state_skew_ms = 1500
        bot.max_instrument_spec_age_ms = 86_400_000
        bot.max_risk_tier_age_ms = 86_400_000
        position = bot.open_positions["BTCUSDT"]
        position.leverage = 5.0
        position.risk_tier_id = 2
        position.risk_limit_value = "500000"
        position.maintenance_margin_rate = "0.01"
        position.maintenance_margin_deduction = "500"
        position.risk_tier_max_leverage = "10"
        position.initial_margin_usdt = "200"
        position.maintenance_margin_usdt = "5"
        spec = SimpleNamespace(validate_leverage=lambda value: value)
        state = SimpleNamespace(instrument_spec=spec, risk_tiers=("dated-tier-ladder",))
        margin = SimpleNamespace(
            tier_id=2, risk_limit_value=engine.Decimal("500000"),
            maintenance_margin_rate=engine.Decimal("0.01"),
            mm_deduction=engine.Decimal("500"), max_leverage=engine.Decimal("10"),
            initial_margin=engine.Decimal("200"), maintenance_margin=engine.Decimal("5"),
        )
        return bot, state, margin

    def test_restored_position_is_checked_against_joined_entry_time_market_state(self):
        bot, state, margin = self._restored_engine_with_joined_histories()
        with patch.object(engine, "get_linear_market_state", return_value=state) as joined, patch.object(engine, "calculate_margin_requirements_from_tiers", return_value=margin) as calc:
            bot._validate_restored_positions_market_state()
        joined.assert_called_once_with(
            bot.instrument_spec_history, bot.risk_tier_history, "BTCUSDT",
            bot.open_positions["BTCUSDT"].entry_ts,
            max_snapshot_skew_ms=1500,
            max_instrument_age_ms=86_400_000,
            max_risk_tier_age_ms=86_400_000,
        )
        calc.assert_called_once_with(
            "BTCUSDT", engine.Decimal("1000.0"),
            leverage=engine.Decimal("5.0"), tiers=state.risk_tiers,
        )

    def test_restored_position_rejects_mismatched_entry_risk_tier(self):
        bot, state, margin = self._restored_engine_with_joined_histories()
        bot.open_positions["BTCUSDT"].risk_tier_id = 1
        with patch.object(engine, "get_linear_market_state", return_value=state), patch.object(engine, "calculate_margin_requirements_from_tiers", return_value=margin):
            with self.assertRaisesRegex(ValueError, "risk_tier_id differs"):
                bot._validate_restored_positions_market_state()

    def test_restored_position_requires_entry_risk_provenance_in_joined_mode(self):
        bot, state, margin = self._restored_engine_with_joined_histories()
        bot.open_positions["BTCUSDT"].risk_tier_id = None
        with patch.object(engine, "get_linear_market_state", return_value=state):
            with self.assertRaisesRegex(ValueError, "lacks entry risk-tier provenance"):
                bot._validate_restored_positions_market_state()

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
            position.signal_ts_ms = 1_789_996_400_000
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
            self.assertEqual(positions["BTCUSDT"].signal_ts_ms, 1_789_996_400_000)
            self.assertEqual(restored_pending["ETHUSDT"]["breakout_level"], 2010.0)
            self.assertEqual(restored_risk.realized_equity, 9_500.0)
            self.assertEqual(restored_risk.unrealized_pnl, -125.0)
            self.assertEqual(restored_risk.current_equity, 9_375.0)
            self.assertEqual(restored_risk.peak_equity, 10_200.0)
            self.assertTrue(restored_risk.kill_switch_triggered)
            self.assertTrue(restored_risk.daily_stop_triggered)



    def test_actual_tp1_taker_classification_round_trips_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tp1-liquidity.json"
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            position = sample_position()
            position.maker_exits = True
            position.tp1_hit = True
            position.tp1_ts_ms = position.entry_ts + 3_600_000
            position.remaining_fraction = 0.5
            position.realized_tp1_gross_usdt = 30.0
            position.tp1_maker = False

            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": position}, {}, 42,
                last_mark_prices={"BTCUSDT": position.entry_price},
            )
            restored = engine.PlanBStatePersistence(str(path)).load_state(
                engine.AdaptiveRiskManager(cfg)
            )[0]["BTCUSDT"]
            self.assertTrue(restored.maker_exits)
            self.assertIs(restored.tp1_maker, False)



    def test_legacy_position_backup_without_signal_timestamp_loads_as_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy-no-signal-ts.json"
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            position = sample_position()
            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": position}, {}, 42,
                last_mark_prices={"BTCUSDT": position.entry_price},
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["open_positions"]["BTCUSDT"].pop("signal_ts_ms", None)
            path.write_text(json.dumps(payload), encoding="utf-8")

            restored = engine.PlanBStatePersistence(str(path)).load_state(
                engine.AdaptiveRiskManager(cfg)
            )[0]
            self.assertIsNone(restored["BTCUSDT"].signal_ts_ms)


    def test_position_signal_timestamp_cannot_follow_entry_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "future-signal-ts.json"
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            position = sample_position()
            position.signal_ts_ms = position.entry_ts + 1
            with self.assertRaisesRegex(ValueError, "signal_ts_ms"):
                engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                    cfg, risk, {"BTCUSDT": position}, {}, 42,
                    last_mark_prices={"BTCUSDT": position.entry_price},
                )


    def test_save_rejects_future_position_entry_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "future-entry-save.json"
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            position = sample_position()
            position.entry_ts = 1_800_000_000_000
            with self.assertRaisesRegex(ValueError, "entry_ts"):
                engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                    cfg, risk, {"BTCUSDT": position}, {}, 42,
                    last_mark_prices={"BTCUSDT": position.entry_price},
                )
            self.assertFalse(path.exists())

    def test_save_rejects_future_tp1_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "future-tp1-save.json"
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            position = sample_position()
            position.tp1_hit = True
            position.remaining_fraction = 0.5
            position.realized_tp1_gross_usdt = 10.0
            position.tp1_ts_ms = 1_800_000_000_000
            with self.assertRaisesRegex(ValueError, "tp1_ts_ms"):
                engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                    cfg, risk, {"BTCUSDT": position}, {}, 42,
                    last_mark_prices={"BTCUSDT": position.entry_price},
                )
            self.assertFalse(path.exists())

    def test_save_rejects_position_payload_reader_would_reject_and_preserves_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            persistence = engine.PlanBStatePersistence(str(path), enabled=True)
            valid = sample_position()
            persistence.save_state(
                cfg, risk, {"BTCUSDT": valid}, {}, 42,
                last_mark_prices={"BTCUSDT": valid.entry_price},
            )
            previous = path.read_bytes()

            invalid = sample_position()
            invalid.direction = "sideways"
            with self.assertRaisesRegex(ValueError, "строгую проверку восстановления"):
                persistence.save_state(
                    cfg, risk, {"BTCUSDT": invalid}, {}, 43,
                    last_mark_prices={"BTCUSDT": invalid.entry_price},
                )
            self.assertEqual(path.read_bytes(), previous)
            self.assertFalse(Path(str(path) + ".tmp").exists())

    def test_save_rejects_pending_payload_reader_would_reject_and_preserves_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            persistence = engine.PlanBStatePersistence(str(path), enabled=True)
            persistence.save_state(cfg, risk, {}, {}, 42, last_mark_prices={})
            previous = path.read_bytes()

            with self.assertRaisesRegex(ValueError, "строгую проверку восстановления"):
                persistence.save_state(
                    cfg, risk, {}, {"BTCUSDT": {"direction": "long"}}, 43,
                    last_mark_prices={},
                )
            self.assertEqual(path.read_bytes(), previous)
            self.assertFalse(Path(str(path) + ".tmp").exists())

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

    def test_tp1_trailing_stop_and_realized_leg_survive_restart_without_double_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tp1-trailing-state.json"
            cfg = engine.BotConfig()
            position = sample_position()
            position.tp1_hit = True
            position.tp1_ts_ms = position.entry_ts + 3_600_000
            position.realized_tp1_gross_usdt = 30.0
            position.remaining_fraction = 0.5
            position.stop_price = 102.0
            position.max_favorable_px = 110.0
            position.max_adverse_px = 98.0
            position.tp1_maker = False
            mark_price = 105.0
            mark_ts = position.entry_ts + 7_200_000

            source = engine.UnifiedQuantEngine.__new__(engine.UnifiedQuantEngine)
            source.open_positions = {"BTCUSDT": position}
            source._last_mark_prices = {"BTCUSDT": mark_price}
            source._intrabar_mtm_marks = {}
            source._intrabar_risk_marks = {}
            source._intrabar_risk_marks_ts = mark_ts
            source.funding_dir = None
            expected_unrealized = source._unrealized_pnl_at_marks(mark_ts)
            risk = engine.AdaptiveRiskManager(cfg)
            risk.mark_to_market(expected_unrealized, mark_ts)

            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": position}, {}, 43,
                last_mark_prices={"BTCUSDT": mark_price},
            )
            restored = engine.UnifiedQuantEngine(
                restore_plan_b=True, state_path=str(path),
            )
            restored_position = restored.open_positions["BTCUSDT"]

            self.assertEqual(restored_position.stop_price, 102.0)
            self.assertEqual(restored_position.max_favorable_px, 110.0)
            self.assertEqual(restored_position.tp1_hit, True)
            self.assertEqual(restored_position.realized_tp1_gross_usdt, 30.0)
            self.assertEqual(restored_position.remaining_fraction, 0.5)
            self.assertEqual(restored_position.tp1_maker, False)
            self.assertAlmostEqual(
                restored._unrealized_pnl_at_marks(mark_ts), expected_unrealized, places=8,
            )
            self.assertAlmostEqual(
                restored.risk_mgr.current_equity, risk.current_equity, places=4,
            )

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

    def _backup_with_exchange_identity(self, path):
        from exchange_execution_identity import ExchangePositionIdentity
        cfg = engine.BotConfig()
        risk = engine.AdaptiveRiskManager(cfg)
        position = sample_position()
        position.set_exchange_position_identity(ExchangePositionIdentity(
            category="linear", settle_coin="USDT", symbol="BTCUSDT",
            position_idx=0, position_mode="one_way", side="Buy",
            qty="0.1", avg_price="100", entry_order_id="entry-1",
            entry_order_link_id="",
        ))
        writer = engine.PlanBStatePersistence(str(path), enabled=True)
        writer.save_state(
            cfg, risk, {"BTCUSDT": position}, {}, 42,
            last_mark_prices={"BTCUSDT": 100.0},
        )
        return writer, cfg, risk

    @staticmethod
    def _canonical_backup_sha256(payload):
        import hashlib
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def test_reconciliation_candidate_is_atomically_persisted_and_restorable(self):
        from exchange_execution_identity import ExchangeExecutionIdentity
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            writer, cfg, risk = self._backup_with_exchange_identity(path)
            current = json.loads(path.read_text(encoding="utf-8"))
            expected = self._canonical_backup_sha256(current)
            candidate = json.loads(json.dumps(current))
            candidate["open_positions"]["BTCUSDT"]["exchange_executions"] = [
                ExchangeExecutionIdentity(
                    exec_id="exec-reconciled-1", order_id="entry-1",
                    order_link_id="", symbol="BTCUSDT", side="Buy",
                    exec_qty="0.1", exec_price="100", exec_time_ms=1_790_000_000_001,
                    exec_fee="0.01",
                ).to_dict()
            ]
            new_digest = writer.save_reconciliation_candidate(
                candidate, expected_backup_sha256=expected, risk_mgr=risk,
            )
            restored, _, _ = writer.load_state(engine.AdaptiveRiskManager(cfg), log_restore=False)
            self.assertEqual(
                restored["BTCUSDT"].exchange_executions[0]["exec_id"],
                "exec-reconciled-1",
            )
            self.assertEqual(new_digest, self._canonical_backup_sha256(candidate))
            self.assertFalse(list(Path(tmp).glob("state.json.reconcile.*.tmp")))

    def test_reconciliation_candidate_rejects_stale_backup_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            writer, _, risk = self._backup_with_exchange_identity(path)
            current = json.loads(path.read_text(encoding="utf-8"))
            expected = self._canonical_backup_sha256(current)
            candidate = json.loads(json.dumps(current))
            candidate["trade_seq"] += 1
            current["trade_seq"] += 1
            path.write_text(json.dumps(current), encoding="utf-8")
            latest = path.read_text(encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "stale reconciliation candidate"):
                writer.save_reconciliation_candidate(
                    candidate, expected_backup_sha256=expected, risk_mgr=risk,
                )
            self.assertEqual(path.read_text(encoding="utf-8"), latest)

    def test_reconciliation_candidate_validation_failure_preserves_previous_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            writer, _, risk = self._backup_with_exchange_identity(path)
            current = json.loads(path.read_text(encoding="utf-8"))
            expected = self._canonical_backup_sha256(current)
            candidate = json.loads(json.dumps(current))
            candidate["risk"]["current_equity"] = float("nan")
            previous = path.read_text(encoding="utf-8")
            with self.assertRaises((ValueError, RuntimeError)):
                writer.save_reconciliation_candidate(
                    candidate, expected_backup_sha256=expected, risk_mgr=risk,
                )
            self.assertEqual(path.read_text(encoding="utf-8"), previous)
            self.assertFalse(list(Path(tmp).glob("state.json.reconcile.*.tmp")))

    def test_reconciliation_candidate_replace_failure_preserves_previous_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            writer, _, risk = self._backup_with_exchange_identity(path)
            current = json.loads(path.read_text(encoding="utf-8"))
            expected = self._canonical_backup_sha256(current)
            candidate = json.loads(json.dumps(current))
            candidate["trade_seq"] += 1
            previous = path.read_text(encoding="utf-8")
            with patch("os.replace", side_effect=OSError("simulated replace failure")):
                with self.assertRaisesRegex(OSError, "simulated replace failure"):
                    writer.save_reconciliation_candidate(
                        candidate, expected_backup_sha256=expected, risk_mgr=risk,
                    )
            self.assertEqual(path.read_text(encoding="utf-8"), previous)
            self.assertFalse(list(Path(tmp).glob("state.json.reconcile.*.tmp")))

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
            position.realized_tp1_gross_usdt = 3.0
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

    def test_exchange_sized_restore_uses_planned_exit_not_entry_for_min_notional(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trailing-stop-above-entry.json"
            position = sample_position()
            position.stop_price = 110.0
            position.exchange_sized = True
            position.leverage = 5.0
            position.contract_qty = "1.0"
            position.remaining_contract_qty = "1.0"
            position.qty_step = "0.1"
            position.min_order_qty = "0.1"
            position.min_notional_value = "105"
            writer = engine.PlanBStatePersistence(str(path), enabled=True)
            writer.save_state(
                engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                {"BTCUSDT": position}, {}, 42,
                last_mark_prices={"BTCUSDT": position.entry_price},
            )
            restored, _, _ = engine.PlanBStatePersistence(str(path)).load_state(
                engine.AdaptiveRiskManager(engine.BotConfig())
            )
            # Entry notional is 100, but both actual planned exit prices
            # (stop 110 and TP2 112) meet minNotionalValue 105.
            self.assertEqual(restored["BTCUSDT"], position)

    def test_exchange_sized_restore_rejects_remaining_below_min_order_qty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "remaining-below-min-qty.json"
            position = sample_position()
            position.exchange_sized = True
            position.leverage = 5.0
            position.contract_qty = "1.0"
            position.tp1_contract_qty = "0.5"
            position.remaining_contract_qty = "0.5"
            position.qty_step = "0.1"
            position.min_order_qty = "0.1"
            position.min_notional_value = "5"
            position.tp1_hit = True
            position.remaining_fraction = 0.5
            position.realized_tp1_gross_usdt = 3.0
            position.tp1_ts_ms = position.entry_ts + 3_600_000
            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                {"BTCUSDT": position}, {}, 42,
                last_mark_prices={"BTCUSDT": position.entry_price},
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["open_positions"]["BTCUSDT"]["min_order_qty"] = "0.6"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(
                    engine.AdaptiveRiskManager(engine.BotConfig())
                )

    def test_exchange_sized_restore_rejects_remaining_below_min_notional_at_planned_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "remaining-below-min-notional.json"
            position = sample_position()
            position.exchange_sized = True
            position.leverage = 5.0
            position.contract_qty = "1.0"
            position.tp1_contract_qty = "0.5"
            position.remaining_contract_qty = "0.5"
            position.qty_step = "0.1"
            position.min_order_qty = "0.1"
            position.min_notional_value = "5"
            position.tp1_hit = True
            position.remaining_fraction = 0.5
            position.realized_tp1_gross_usdt = 3.0
            position.tp1_ts_ms = position.entry_ts + 3_600_000
            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                engine.BotConfig(), engine.AdaptiveRiskManager(engine.BotConfig()),
                {"BTCUSDT": position}, {}, 42,
                last_mark_prices={"BTCUSDT": position.entry_price},
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            # TP1 leg remains valid: 0.5 * 106 = 53. Remaining leg at the
            # lowest planned exit (stop 95) is only 47.5, below minNotional 50.
            payload["open_positions"]["BTCUSDT"]["min_notional_value"] = "50"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(
                    engine.AdaptiveRiskManager(engine.BotConfig())
                )

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

    def test_tp1_realized_gross_must_match_closed_quantity_and_tp1_price(self):
        def mutate(position):
            position.update({
                "tp1_hit": True, "remaining_fraction": 0.5,
                "realized_tp1_gross_usdt": 31.0,
                "tp1_ts_ms": position["entry_ts"] + 3_600_000,
            })
        self._assert_invalid_position_payload(mutate)

    def test_tp1_realized_pnl_requires_tp1_hit(self):
        self._assert_invalid_position_payload(
            lambda position: position.update({"realized_tp1_gross_usdt": 12.0})
        )

    def test_restore_rejects_zero_favorable_extreme(self):
        self._assert_invalid_position_payload(
            lambda position: position.update({"max_favorable_px": 0.0})
        )

    def test_restore_rejects_long_favorable_extreme_below_entry(self):
        self._assert_invalid_position_payload(
            lambda position: position.update({"max_favorable_px": 99.0})
        )

    def test_restore_rejects_short_adverse_extreme_below_entry(self):
        def mutate(position):
            position.update({
                "direction": "short", "tp1_price": 94.0, "tp2_price": 88.0,
                "max_adverse_px": 99.0,
            })
        self._assert_invalid_position_payload(mutate)

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

    def test_risk_kill_switch_latch_required_when_emergency_drawdown_is_breached(self):
        self._assert_invalid_risk_payload({
            "realized_equity": 6_900.0, "unrealized_pnl": 0.0,
            "current_equity": 6_900.0, "peak_equity": 10_000.0,
            "max_drawdown_pct": 31.0, "kill_switch_triggered": False,
        })

    def test_risk_kill_switch_latch_required_after_historical_emergency_drawdown_recovers(self):
        self._assert_invalid_risk_payload({
            "realized_equity": 9_000.0, "unrealized_pnl": 0.0,
            "current_equity": 9_000.0, "peak_equity": 10_000.0,
            "max_drawdown_pct": 31.0, "kill_switch_triggered": False,
        })

    def test_risk_daily_stop_latch_required_when_daily_drawdown_is_breached(self):
        self._assert_invalid_risk_payload({
            "realized_equity": 9_400.0, "unrealized_pnl": 0.0,
            "current_equity": 9_400.0, "peak_equity": 10_000.0,
            "max_drawdown_pct": 6.0, "day_start_equity": 10_000.0,
            "current_day_str": "2026-11-02", "daily_stop_triggered": False,
        })

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

    def test_legacy_backup_without_breakout_level_remains_loadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy-state.json"
            cfg = engine.BotConfig()
            position = sample_position()
            pending = {
                "ETHUSDT": {
                    "symbol": "ETHUSDT", "direction": "short",
                    "strategy": "state-test", "signal_ts": 1_790_000_000_000,
                    "entry_price": 2000.0, "stop_price": 2100.0,
                    "tp1_price": 1900.0, "tp2_price": 1800.0,
                    "stop_dist": 100.0, "order_type": "market",
                }
            }
            risk = engine.AdaptiveRiskManager(cfg)
            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": position}, pending, 42,
                last_mark_prices={"BTCUSDT": position.entry_price},
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["open_positions"]["BTCUSDT"].pop("breakout_level")
            path.write_text(json.dumps(payload), encoding="utf-8")
            restored, restored_pending, _ = engine.PlanBStatePersistence(str(path)).load_state(
                engine.AdaptiveRiskManager(cfg)
            )
            self.assertIsNone(restored["BTCUSDT"].breakout_level)
            self.assertNotIn("breakout_level", restored_pending["ETHUSDT"])

    def test_invalid_pending_breakout_level_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-pending-breakout-level.json"
            cfg = engine.BotConfig()
            pending = {
                "ETHUSDT": {
                    "symbol": "ETHUSDT", "direction": "short",
                    "strategy": "state-test", "signal_ts": 1_790_000_000_000,
                    "entry_price": 2000.0, "stop_price": 2100.0,
                    "tp1_price": 1900.0, "tp2_price": 1800.0,
                    "stop_dist": 100.0, "order_type": "market",
                    "breakout_level": "invalid",
                }
            }
            risk = engine.AdaptiveRiskManager(cfg)
            persistence = engine.PlanBStatePersistence(str(path), enabled=True)
            persistence.save_state(cfg, risk, {}, {}, 42, last_mark_prices={})
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["pending_orders"] = pending
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(
                    engine.AdaptiveRiskManager(cfg)
                )

    def test_hc_enabled_rejects_open_breakout_without_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hc-open-without-boundary.json"
            cfg = engine.BotConfig(timeframe="1h", enable_post_break_invalidation=True)
            position = sample_position()
            position.strategy = "H1-momentum-breakout"
            risk = engine.AdaptiveRiskManager(cfg)
            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": position}, {}, 42,
                last_mark_prices={"BTCUSDT": position.entry_price},
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["open_positions"]["BTCUSDT"].pop("breakout_level")
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                engine.PlanBStatePersistence(str(path)).load_state(
                    engine.AdaptiveRiskManager(cfg)
                )

    def test_hc_enabled_rejects_pending_breakout_without_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hc-pending-without-boundary.json"
            cfg = engine.BotConfig(timeframe="1h", enable_post_break_invalidation=True)
            pending = {
                "BTCUSDT": {
                    "symbol": "BTCUSDT", "direction": "long",
                    "strategy": "H1-momentum-breakout", "signal_ts": 1_790_000_000_000,
                    "entry_price": 100.0, "stop_price": 95.0,
                    "tp1_price": 110.0, "tp2_price": 120.0,
                    "stop_dist": 5.0, "order_type": "market",
                }
            }
            risk = engine.AdaptiveRiskManager(cfg)
            persistence = engine.PlanBStatePersistence(str(path), enabled=True)
            persistence.save_state(cfg, risk, {}, {}, 42, last_mark_prices={})
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["pending_orders"] = pending
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



    def test_exchange_identity_position_orders_and_executions_round_trip(self):
        from exchange_execution_identity import (
            ExchangeExecutionIdentity, ExchangeOrderIdentity, ExchangePositionIdentity,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exchange-identities.json"
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            position = sample_position()
            position.set_exchange_position_identity(ExchangePositionIdentity(
                "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
                "0.010", "100.00", "entry-order-1", "bot-entry-1",
            ))
            initial_order = ExchangeOrderIdentity(
                "stop-order-1", "bot-stop-1", "BTCUSDT", "Sell", 0,
                "0.010", "0.010", "0", "New", True, True, "95.00",
            )
            self.assertTrue(position.record_exchange_order(initial_order))
            self.assertFalse(position.record_exchange_order(initial_order))
            updated_order = ExchangeOrderIdentity(
                "stop-order-1", "bot-stop-1", "BTCUSDT", "Sell", 0,
                "0.010", "0.006", "0.004", "PartiallyFilled", True, True, "95.00",
            )
            self.assertTrue(position.record_exchange_order(updated_order))
            execution = ExchangeExecutionIdentity(
                "exec-1", "stop-order-1", "bot-stop-1", "BTCUSDT",
                "Sell", "0.004", "95.00", position.entry_ts + 1000, "-0.01",
            )
            self.assertTrue(position.record_exchange_execution(execution))
            self.assertFalse(position.record_exchange_execution(execution))

            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": position}, {}, 7,
                last_mark_prices={"BTCUSDT": 100.0},
            )
            restored = engine.PlanBStatePersistence(str(path)).load_state(
                engine.AdaptiveRiskManager(cfg)
            )[0]["BTCUSDT"]
            self.assertEqual(restored.exchange_position_identity, position.exchange_position_identity)
            self.assertEqual(restored.exchange_orders, [updated_order.to_dict()])
            self.assertEqual(restored.exchange_executions, [execution.to_dict()])

    def test_exchange_execution_duplicate_id_with_conflicting_payload_is_rejected(self):
        from exchange_execution_identity import ExchangeExecutionIdentity
        position = sample_position()
        first = ExchangeExecutionIdentity(
            "exec-dup", "order-1", "", "BTCUSDT", "Buy",
            "0.1", "100", position.entry_ts + 1,
        )
        conflicting = ExchangeExecutionIdentity(
            "exec-dup", "order-1", "", "BTCUSDT", "Buy",
            "0.2", "100", position.entry_ts + 1,
        )
        from exchange_execution_identity import ExchangeOrderIdentity
        position.record_exchange_order(ExchangeOrderIdentity(
            "order-1", "", "BTCUSDT", "Buy", 0,
            "1", "0.9", "0.1", "PartiallyFilled", False, False,
        ))
        self.assertTrue(position.record_exchange_execution(first))
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            position.record_exchange_execution(conflicting)

    def test_exchange_order_update_cannot_change_order_identity(self):
        from exchange_execution_identity import ExchangeOrderIdentity
        position = sample_position()
        first = ExchangeOrderIdentity(
            "order-1", "link-1", "BTCUSDT", "Sell", 0,
            "1", "1", "0", "New", True, True,
        )
        changed_identity = ExchangeOrderIdentity(
            "order-1", "link-1", "BTCUSDT", "Buy", 0,
            "1", "1", "0", "New", True, True,
        )
        position.record_exchange_order(first)
        with self.assertRaisesRegex(ValueError, "identity fields changed"):
            position.record_exchange_order(changed_identity)

    def test_legacy_backup_without_exchange_identity_fields_remains_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy-exchange-fields.json"
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": sample_position()}, {}, 3,
                last_mark_prices={"BTCUSDT": 100.0},
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw = payload["open_positions"]["BTCUSDT"]
            raw.pop("exchange_position_identity", None)
            raw.pop("exchange_orders", None)
            raw.pop("exchange_executions", None)
            path.write_text(json.dumps(payload), encoding="utf-8")
            restored = engine.PlanBStatePersistence(str(path)).load_state(
                engine.AdaptiveRiskManager(cfg)
            )[0]["BTCUSDT"]
            self.assertIsNone(restored.exchange_position_identity)
            self.assertEqual(restored.exchange_orders, [])
            self.assertEqual(restored.exchange_executions, [])


    def test_execution_sum_cannot_exceed_order_cumulative_fill_and_failure_rolls_back(self):
        from exchange_execution_identity import ExchangeExecutionIdentity, ExchangeOrderIdentity
        position = sample_position()
        order = ExchangeOrderIdentity(
            "order-overfill", "", "BTCUSDT", "Sell", 0,
            "1", "0.7", "0.3", "PartiallyFilled", True, True,
        )
        position.record_exchange_order(order)
        first = ExchangeExecutionIdentity(
            "exec-a", "order-overfill", "", "BTCUSDT", "Sell",
            "0.2", "95", position.entry_ts + 1,
        )
        second = ExchangeExecutionIdentity(
            "exec-b", "order-overfill", "", "BTCUSDT", "Sell",
            "0.2", "95", position.entry_ts + 2,
        )
        self.assertTrue(position.record_exchange_execution(first))
        with self.assertRaisesRegex(ValueError, "sum exceeds order cumExecQty"):
            position.record_exchange_execution(second)
        self.assertEqual([x["exec_id"] for x in position.exchange_executions], ["exec-a"])

    def test_execution_must_reference_known_order_and_match_side(self):
        from exchange_execution_identity import ExchangeExecutionIdentity, ExchangeOrderIdentity
        position = sample_position()
        orphan = ExchangeExecutionIdentity(
            "orphan", "missing-order", "", "BTCUSDT", "Sell",
            "0.1", "95", position.entry_ts + 1,
        )
        with self.assertRaisesRegex(ValueError, "unknown orderId"):
            position.record_exchange_execution(orphan)
        self.assertEqual(position.exchange_executions, [])

        position.record_exchange_order(ExchangeOrderIdentity(
            "known-order", "link-1", "BTCUSDT", "Sell", 0,
            "1", "0.9", "0.1", "PartiallyFilled", True, True,
        ))
        wrong_side = ExchangeExecutionIdentity(
            "wrong-side", "known-order", "link-1", "BTCUSDT", "Buy",
            "0.1", "95", position.entry_ts + 1,
        )
        with self.assertRaisesRegex(ValueError, "side differs"):
            position.record_exchange_execution(wrong_side)
        self.assertEqual(position.exchange_executions, [])

    def test_order_lifecycle_update_cannot_reduce_cumulative_fill_or_increase_leaves(self):
        from exchange_execution_identity import ExchangeOrderIdentity
        position = sample_position()
        first = ExchangeOrderIdentity(
            "monotonic-order", "", "BTCUSDT", "Sell", 0,
            "3", "2.5", "0.3", "PartiallyFilled", True, True,
        )
        position.record_exchange_order(first)
        lower_cumulative = ExchangeOrderIdentity(
            "monotonic-order", "", "BTCUSDT", "Sell", 0,
            "3", "2.6", "0.2", "PartiallyFilled", True, True,
        )
        with self.assertRaisesRegex(ValueError, "cumExecQty cannot decrease"):
            position.record_exchange_order(lower_cumulative)
        self.assertEqual(position.exchange_orders, [first.to_dict()])
        increased_leaves = ExchangeOrderIdentity(
            "monotonic-order", "", "BTCUSDT", "Sell", 0,
            "3", "2.6", "0.3", "PartiallyFilled", True, True,
        )
        with self.assertRaisesRegex(ValueError, "leavesQty cannot increase"):
            position.record_exchange_order(increased_leaves)
        self.assertEqual(position.exchange_orders, [first.to_dict()])

    def test_execution_link_id_must_match_order_link_id(self):
        from exchange_execution_identity import ExchangeExecutionIdentity, ExchangeOrderIdentity
        position = sample_position()
        position.record_exchange_order(ExchangeOrderIdentity(
            "linked-order", "expected-link", "BTCUSDT", "Sell", 0,
            "1", "0.9", "0.1", "PartiallyFilled", True, True,
        ))
        execution = ExchangeExecutionIdentity(
            "linked-exec", "linked-order", "different-link", "BTCUSDT", "Sell",
            "0.1", "95", position.entry_ts + 1,
        )
        with self.assertRaisesRegex(ValueError, "orderLinkId differs"):
            position.record_exchange_execution(execution)
        self.assertEqual(position.exchange_executions, [])


    def test_exchange_order_position_idx_must_match_hedge_position(self):
        from exchange_execution_identity import ExchangeOrderIdentity, ExchangePositionIdentity
        position = sample_position()
        identity = ExchangePositionIdentity(
            "linear", "USDT", "BTCUSDT", 1, "hedge", "Buy",
            "0.5", "100", "entry-hedge", "",
        )
        position.set_exchange_position_identity(identity)
        wrong_index = ExchangeOrderIdentity(
            "wrong-index", "", "BTCUSDT", "Sell", 2,
            "0.5", "0.5", "0", "New", True, True, "95",
        )
        with self.assertRaisesRegex(ValueError, "positionIdx differs"):
            position.record_exchange_order(wrong_index)
        self.assertEqual(position.exchange_orders, [])

        valid_close = ExchangeOrderIdentity(
            "valid-hedge-close", "", "BTCUSDT", "Sell", 1,
            "0.5", "0.5", "0", "New", True, True, "95",
        )
        self.assertTrue(position.record_exchange_order(valid_close))

    def test_exchange_order_side_must_match_reduce_only_intent(self):
        from exchange_execution_identity import ExchangeOrderIdentity, ExchangePositionIdentity
        position = sample_position()
        position.set_exchange_position_identity(ExchangePositionIdentity(
            "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
            "0.5", "100", "entry-oneway", "",
        ))
        same_side_reduce_only = ExchangeOrderIdentity(
            "invalid-entry", "", "BTCUSDT", "Buy", 0,
            "0.5", "0.5", "0", "New", True, False,
        )
        with self.assertRaisesRegex(ValueError, "same-side order cannot be reduceOnly"):
            position.record_exchange_order(same_side_reduce_only)

        opposite_side_not_reduce_only = ExchangeOrderIdentity(
            "invalid-exit", "", "BTCUSDT", "Sell", 0,
            "0.5", "0.5", "0", "New", False, False,
        )
        with self.assertRaisesRegex(ValueError, "opposite-side order must be reduceOnly"):
            position.record_exchange_order(opposite_side_not_reduce_only)

    def test_close_on_trigger_requires_reduce_only(self):
        from exchange_execution_identity import ExchangeOrderIdentity, ExchangePositionIdentity
        position = sample_position()
        position.set_exchange_position_identity(ExchangePositionIdentity(
            "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
            "0.5", "100", "entry-oneway", "",
        ))
        invalid = ExchangeOrderIdentity(
            "invalid-trigger", "", "BTCUSDT", "Buy", 0,
            "0.5", "0.5", "0", "New", False, True,
        )
        with self.assertRaisesRegex(ValueError, "closeOnTrigger order must be reduceOnly"):
            position.record_exchange_order(invalid)
        self.assertEqual(position.exchange_orders, [])


    def test_multiple_orders_partial_fills_cancel_and_replacement_remain_distinct(self):
        from exchange_execution_identity import (
            ExchangeExecutionIdentity, ExchangeOrderIdentity, ExchangePositionIdentity,
        )
        position = sample_position()
        position.set_exchange_position_identity(ExchangePositionIdentity(
            "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
            "1.0", "100", "entry-main", "entry-link",
        ))

        first = ExchangeOrderIdentity(
            "exit-old", "exit-link-old", "BTCUSDT", "Sell", 0,
            "1.0", "0.7", "0.3", "PartiallyFilled", True, False,
        )
        second = ExchangeOrderIdentity(
            "exit-parallel", "exit-link-parallel", "BTCUSDT", "Sell", 0,
            "0.5", "0.4", "0.1", "PartiallyFilled", True, False,
        )
        self.assertTrue(position.record_exchange_order(first))
        self.assertTrue(position.record_exchange_order(second))
        self.assertTrue(position.record_exchange_execution(ExchangeExecutionIdentity(
            "fill-old-a", "exit-old", "exit-link-old", "BTCUSDT",
            "Sell", "0.1", "99", position.entry_ts + 1,
        )))
        self.assertTrue(position.record_exchange_execution(ExchangeExecutionIdentity(
            "fill-old-b", "exit-old", "exit-link-old", "BTCUSDT",
            "Sell", "0.2", "98", position.entry_ts + 2,
        )))
        self.assertTrue(position.record_exchange_execution(ExchangeExecutionIdentity(
            "fill-parallel", "exit-parallel", "exit-link-parallel", "BTCUSDT",
            "Sell", "0.1", "97", position.entry_ts + 3,
        )))

        cancelled_partial = ExchangeOrderIdentity(
            "exit-old", "exit-link-old", "BTCUSDT", "Sell", 0,
            "1.0", "0", "0.3", "Cancelled", True, False,
        )
        self.assertTrue(position.record_exchange_order(cancelled_partial))
        replacement = ExchangeOrderIdentity(
            "exit-replacement", "exit-link-replacement", "BTCUSDT", "Sell", 0,
            "0.7", "0.7", "0", "New", True, False,
        )
        self.assertTrue(position.record_exchange_order(replacement))

        self.assertEqual(
            {order["order_id"] for order in position.exchange_orders},
            {"exit-old", "exit-parallel", "exit-replacement"},
        )
        self.assertEqual(
            {fill["exec_id"] for fill in position.exchange_executions},
            {"fill-old-a", "fill-old-b", "fill-parallel"},
        )
        self.assertEqual(
            next(o for o in position.exchange_orders if o["order_id"] == "exit-old")["cum_exec_qty"],
            "0.3",
        )
        exact_terminal_duplicate = ExchangeOrderIdentity(
            "exit-old", "exit-link-old", "BTCUSDT", "Sell", 0,
            "1.0", "0", "0.3", "Cancelled", True, False,
        )
        self.assertFalse(position.record_exchange_order(exact_terminal_duplicate))
        with self.assertRaisesRegex(ValueError, "terminal exchange order"):
            position.record_exchange_order(ExchangeOrderIdentity(
                "exit-old", "exit-link-old", "BTCUSDT", "Sell", 0,
                "1.0", "0.7", "0.3", "PartiallyFilled", True, False,
            ))

    def test_filled_order_requires_full_cumulative_quantity_and_zero_leaves(self):
        from exchange_execution_identity import ExchangeOrderIdentity
        position = sample_position()
        incomplete = ExchangeOrderIdentity(
            "bad-filled", "", "BTCUSDT", "Sell", 0,
            "1", "0", "0.8", "Filled", True, False,
        )
        with self.assertRaisesRegex(ValueError, "Filled order must have"):
            position.record_exchange_order(incomplete)
        self.assertEqual(position.exchange_orders, [])

    def test_cancelled_order_requires_zero_leaves_but_preserves_partial_fill(self):
        from exchange_execution_identity import ExchangeOrderIdentity
        position = sample_position()
        partial = ExchangeOrderIdentity(
            "cancel-check", "", "BTCUSDT", "Sell", 0,
            "1", "0.6", "0.4", "PartiallyFilled", True, False,
        )
        position.record_exchange_order(partial)
        invalid_cancel = ExchangeOrderIdentity(
            "cancel-check", "", "BTCUSDT", "Sell", 0,
            "1", "0.1", "0.4", "Cancelled", True, False,
        )
        with self.assertRaisesRegex(ValueError, "terminal order must have zero leavesQty"):
            position.record_exchange_order(invalid_cancel)
        self.assertEqual(position.exchange_orders, [partial.to_dict()])


    def test_exchange_quantity_audit_matches_entry_minus_partial_exit_fills(self):
        from exchange_execution_identity import (
            ExchangeExecutionIdentity, ExchangeOrderIdentity, ExchangePositionIdentity,
        )
        position = sample_position()
        position.set_exchange_position_identity(ExchangePositionIdentity(
            "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
            "0.6", "100", "entry-audit", "entry-audit-link",
        ))
        position.record_exchange_order(ExchangeOrderIdentity(
            "close-audit", "close-audit-link", "BTCUSDT", "Sell", 0,
            "0.5", "0.1", "0.4", "PartiallyFilled", True, False,
        ))
        position.record_exchange_execution(ExchangeExecutionIdentity(
            "entry-fill-audit", "entry-audit", "entry-audit-link", "BTCUSDT",
            "Buy", "1.0", "100", position.entry_ts + 1,
        ))
        position.record_exchange_execution(ExchangeExecutionIdentity(
            "exit-fill-audit", "close-audit", "close-audit-link", "BTCUSDT",
            "Sell", "0.4", "101", position.entry_ts + 2,
        ))
        audit = position.audit_exchange_position_quantity(execution_history_complete=True)
        self.assertEqual(audit["status"], "MATCH")
        self.assertEqual(audit["entry_exec_qty"], "1.0")
        self.assertEqual(audit["exit_exec_qty"], "0.4")
        self.assertEqual(audit["net_exec_qty"], "0.6")
        self.assertEqual(audit["position_qty"], "0.6")
        self.assertEqual(audit["difference_qty"], "0.0")

    def test_exchange_quantity_audit_does_not_claim_match_for_incomplete_history(self):
        from exchange_execution_identity import ExchangePositionIdentity
        position = sample_position()
        position.set_exchange_position_identity(ExchangePositionIdentity(
            "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
            "0.6", "100", "entry-incomplete", "",
        ))
        audit = position.audit_exchange_position_quantity()
        self.assertEqual(audit["status"], "INCOMPLETE")
        self.assertEqual(audit["net_exec_qty"], "0")
        self.assertEqual(audit["difference_qty"], "0.6")

    def test_exchange_quantity_audit_reports_mismatch_when_history_is_complete(self):
        from exchange_execution_identity import (
            ExchangeExecutionIdentity, ExchangePositionIdentity,
        )
        position = sample_position()
        position.set_exchange_position_identity(ExchangePositionIdentity(
            "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
            "0.5", "100", "entry-mismatch", "",
        ))
        position.record_exchange_execution(ExchangeExecutionIdentity(
            "entry-fill-mismatch", "entry-mismatch", "", "BTCUSDT",
            "Buy", "0.6", "100", position.entry_ts + 1,
        ))
        audit = position.audit_exchange_position_quantity(execution_history_complete=True)
        self.assertEqual(audit["status"], "MISMATCH")
        self.assertEqual(audit["net_exec_qty"], "0.6")
        self.assertEqual(audit["difference_qty"], "-0.1")

    def test_exchange_quantity_audit_rejects_closing_fills_above_opening_fills(self):
        from exchange_execution_identity import (
            ExchangeExecutionIdentity, ExchangeOrderIdentity, ExchangePositionIdentity,
        )
        position = sample_position()
        position.set_exchange_position_identity(ExchangePositionIdentity(
            "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
            "0.1", "100", "entry-overclose", "",
        ))
        position.record_exchange_order(ExchangeOrderIdentity(
            "close-overclose", "", "BTCUSDT", "Sell", 0,
            "0.2", "0", "0.2", "Filled", True, False,
        ))
        position.record_exchange_execution(ExchangeExecutionIdentity(
            "entry-overclose-fill", "entry-overclose", "", "BTCUSDT",
            "Buy", "0.1", "100", position.entry_ts + 1,
        ))
        position.record_exchange_execution(ExchangeExecutionIdentity(
            "exit-overclose-fill", "close-overclose", "", "BTCUSDT",
            "Sell", "0.2", "99", position.entry_ts + 2,
        ))
        with self.assertRaisesRegex(ValueError, "closing execution quantity exceeds"):
            position.audit_exchange_position_quantity(execution_history_complete=True)


    def test_execution_batch_merge_deduplicates_overlapping_pages_and_sorts_late_fills(self):
        from exchange_execution_identity import ExchangeExecutionIdentity, ExchangePositionIdentity
        position = sample_position()
        position.set_exchange_position_identity(ExchangePositionIdentity(
            "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
            "0.6", "100", "batch-entry", "",
        ))
        late = ExchangeExecutionIdentity(
            "exec-late", "batch-entry", "", "BTCUSDT", "Buy",
            "0.2", "100", position.entry_ts + 1,
        )
        recent = ExchangeExecutionIdentity(
            "exec-recent", "batch-entry", "", "BTCUSDT", "Buy",
            "0.4", "101", position.entry_ts + 3,
        )
        first = position.merge_exchange_execution_batch([recent])
        self.assertEqual(first, {"inserted": 1, "duplicates": 0, "total": 1})
        overlap = position.merge_exchange_execution_batch([late, recent])
        self.assertEqual(overlap, {"inserted": 1, "duplicates": 1, "total": 2})
        self.assertEqual(
            [item["exec_id"] for item in position.exchange_executions],
            ["exec-late", "exec-recent"],
        )
        audit = position.audit_exchange_position_quantity()
        self.assertEqual(audit["net_exec_qty"], "0.6")
        self.assertEqual(audit["status"], "INCOMPLETE")

    def test_execution_batch_merge_conflict_or_invalid_row_rolls_back_entire_batch(self):
        from exchange_execution_identity import ExchangeExecutionIdentity
        position = sample_position()
        from exchange_execution_identity import ExchangeOrderIdentity
        position.record_exchange_order(ExchangeOrderIdentity(
            "entry-order", "", "BTCUSDT", "Buy", 0,
            "0.3", "0.2", "0.1", "PartiallyFilled", False, False,
        ))
        valid = ExchangeExecutionIdentity(
            "batch-valid", "entry-order", "", "BTCUSDT", "Buy",
            "0.1", "100", position.entry_ts + 1,
        )
        orphan = ExchangeExecutionIdentity(
            "batch-orphan", "unknown-order", "", "BTCUSDT", "Buy",
            "0.1", "100", position.entry_ts + 2,
        )
        with self.assertRaisesRegex(ValueError, "unknown orderId"):
            position.merge_exchange_execution_batch([valid, orphan])
        self.assertEqual(position.exchange_executions, [])

        position.record_exchange_execution(valid)
        conflict = ExchangeExecutionIdentity(
            "batch-valid", "entry-order", "", "BTCUSDT", "Buy",
            "0.2", "100", position.entry_ts + 1,
        )
        before = list(position.exchange_executions)
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            position.merge_exchange_execution_batch([valid, conflict])
        self.assertEqual(position.exchange_executions, before)

    def test_execution_coverage_merges_overlapping_complete_windows(self):
        from exchange_execution_identity import ExchangeExecutionCoverage
        position = sample_position()
        start = position.entry_ts
        first = ExchangeExecutionCoverage("page-set-1", "BTCUSDT", start, start + 100, execution_page_chain(start, 3))
        second = ExchangeExecutionCoverage("page-set-2", "BTCUSDT", start + 90, start + 200, execution_page_chain(start + 90, 2))
        self.assertTrue(position.record_exchange_execution_coverage(first))
        self.assertFalse(position.record_exchange_execution_coverage(first))
        self.assertTrue(position.record_exchange_execution_coverage(second))
        audit = position.audit_exchange_execution_coverage(
            lifecycle_start_ms=start, audit_end_ms=start + 200,
        )
        self.assertEqual(audit["status"], "COMPLETE")
        self.assertEqual(audit["gaps"], [])
        self.assertEqual(audit["complete_window_count"], 2)

    def test_execution_coverage_detects_gaps_and_incomplete_pagination(self):
        from exchange_execution_identity import ExchangeExecutionCoverage
        position = sample_position()
        start = position.entry_ts
        position.record_exchange_execution_coverage(ExchangeExecutionCoverage(
            "complete-before-gap", "BTCUSDT", start, start + 40, execution_page_chain(start, 1),
        ))
        position.record_exchange_execution_coverage(ExchangeExecutionCoverage(
            "incomplete-after-gap", "BTCUSDT", start + 60, start + 100, execution_page_chain(start + 60, 2, final_has_next=True),
        ))
        audit = position.audit_exchange_execution_coverage(
            lifecycle_start_ms=start, audit_end_ms=start + 100,
        )
        self.assertEqual(audit["status"], "INCOMPLETE")
        self.assertEqual(audit["gaps"], [
            {"start_ms": start + 40, "end_ms": start + 100},
        ])

    def test_execution_coverage_rejects_broken_page_chain(self):
        from exchange_execution_identity import (
            ExchangeExecutionCoverage, ExchangeExecutionPageObservation,
        )
        start = sample_position().entry_ts
        broken = (
            ExchangeExecutionPageObservation(0, start, start + 2, 1, False),
            ExchangeExecutionPageObservation(1, start + 3, start + 5, 0, False),
        )
        with self.assertRaisesRegex(ValueError, "non-terminal page"):
            ExchangeExecutionCoverage("broken-chain", "BTCUSDT", start, start + 100, broken)
        overlapping_requests = (
            ExchangeExecutionPageObservation(0, start, start + 10, 1, True),
            ExchangeExecutionPageObservation(1, start + 9, start + 12, 0, False),
        )
        with self.assertRaisesRegex(ValueError, "sequential and non-overlapping"):
            ExchangeExecutionCoverage("overlap-pages", "BTCUSDT", start, start + 100, overlapping_requests)

    def test_execution_coverage_requires_actual_position_entry_boundary(self):
        position = sample_position()
        with self.assertRaisesRegex(ValueError, "must equal the position entry_ts"):
            position.audit_exchange_execution_coverage(
                lifecycle_start_ms=position.entry_ts + 1,
                audit_end_ms=position.entry_ts + 100,
            )

    def test_execution_coverage_rejects_conflicting_ids_and_wrong_symbol(self):
        from exchange_execution_identity import ExchangeExecutionCoverage
        position = sample_position()
        start = position.entry_ts
        original = ExchangeExecutionCoverage("coverage-x", "BTCUSDT", start, start + 10, execution_page_chain(start, 1))
        self.assertTrue(position.record_exchange_execution_coverage(original))
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            position.record_exchange_execution_coverage(ExchangeExecutionCoverage(
                "coverage-x", "BTCUSDT", start, start + 20, execution_page_chain(start, 1),
            ))
        with self.assertRaisesRegex(ValueError, "symbol mismatch"):
            position.record_exchange_execution_coverage(ExchangeExecutionCoverage(
                "coverage-y", "ETHUSDT", start, start + 10, execution_page_chain(start, 1),
            ))

    def test_exchange_quantity_audit_survives_plan_b_restart(self):
        from exchange_execution_identity import (
            ExchangeExecutionIdentity, ExchangeOrderIdentity, ExchangePositionIdentity,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exchange-quantity-audit.json"
            position = sample_position()
            position.set_exchange_position_identity(ExchangePositionIdentity(
                "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
                "0.75", "100", "entry-restart", "",
            )) 
            from exchange_execution_identity import ExchangeExecutionCoverage
            position.record_exchange_execution_coverage(ExchangeExecutionCoverage(
                "restart-coverage", "BTCUSDT", position.entry_ts,
                position.entry_ts + 10_000, execution_page_chain(position.entry_ts, 2),
            ))
            position.record_exchange_order(ExchangeOrderIdentity(
                "exit-restart", "", "BTCUSDT", "Sell", 0,
                "0.5", "0.25", "0.25", "PartiallyFilled", True, False,
            ))
            position.record_exchange_execution(ExchangeExecutionIdentity(
                "entry-restart-fill", "entry-restart", "", "BTCUSDT",
                "Buy", "1.0", "100", position.entry_ts + 1,
            ))
            position.record_exchange_execution(ExchangeExecutionIdentity(
                "exit-restart-fill", "exit-restart", "", "BTCUSDT",
                "Sell", "0.25", "101", position.entry_ts + 2,
            ))
            cfg = engine.BotConfig()
            risk = engine.AdaptiveRiskManager(cfg)
            engine.PlanBStatePersistence(str(path), enabled=True).save_state(
                cfg, risk, {"BTCUSDT": position}, {}, 11,
                last_mark_prices={"BTCUSDT": 100.0},
            )
            restored = engine.PlanBStatePersistence(str(path)).load_state(
                engine.AdaptiveRiskManager(cfg)
            )[0]["BTCUSDT"]
            audit = restored.audit_exchange_position_quantity(execution_history_complete=True)
            self.assertEqual(audit["status"], "MATCH")
            self.assertEqual(audit["net_exec_qty"], "0.75")
            self.assertEqual(restored.exchange_position_identity, position.exchange_position_identity)
            self.assertEqual(restored.exchange_executions, position.exchange_executions)
            self.assertEqual(restored.exchange_execution_coverage, position.exchange_execution_coverage)


if __name__ == "__main__":
    unittest.main(verbosity=2)
