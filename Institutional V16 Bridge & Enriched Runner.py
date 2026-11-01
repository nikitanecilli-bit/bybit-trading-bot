#!/usr/bin/env python3
"""
Мост v16.0: Подключает стохастическое ядро (quant_math_lab_v16.py) и майнер
закономерностей (quant_pattern_miner_v16.py) напрямую к свинговому движку v15.0.

Запуск:
  python quant_engine_v16_bridge.py --data-dir data
  python quant_engine_v16_bridge.py   # автономный тест на калиброванных данных
"""
import argparse
import dataclasses
import json
import os
from typing import Dict, List, Optional

import Bybit_Trading_Engine_v14_Audit_Fixed as E
import quant_math_lab_v16 as M
import quant_pattern_miner_v16 as P


classQuantV16SignalGate:
    """Надстройка v16 над QuantStrategyCore: фильтрация по Калману, KER, Хоуксу и CRR."""

    @staticmethod
    def evaluate_v16(symbol: str, candles: List[E.Candle], cfg: E.BotConfig) -> Optional[Dict]:
        sig = E.QuantStrategyCore.evaluate_signal(symbol, candles, cfg)
        if not sig:
            return None

        closes = [c.close for c in candles[-64:]]
        opens = [c.open for c in candles[-64:]]
        highs = [c.high for c in candles[-64:]]
        lows = [c.low for c in candles[-64:]]
        vols = [c.volume for c in candles[-64:]]

        # 1. Фильтр фрактальной эффективности Кауфмана (KER >= 0.22 против "пилы")
        ker = M.kaufman_efficiency_ratio(closes, period=20)
        if ker < 0.22:
            return None

        # 2. Кинематический фильтр Калмана (скорость тренда должна совпадать со стороной входа)
        _, vel_z = M.kalman_velocity_filter(closes[-40:])
        kz = vel_z[-1] if vel_z else 0.0
        if (sig["direction"] == "long" and kz < -0.15) or (sig["direction"] == "short" and kz > 0.15):
            return None

        # 3. Интенсивность Хоукса (защита от входа в уже выгоревшую кульминацию H_t > 2.8)
        h_series = M.hawkes_cascade_intensity(opens, highs, lows, closes, vols)
        h_now = h_series[-1] if h_series else 0.0
        if h_now > 2.8:
            return None

        # 4. Жёсткий инвариант бюджета трения (Тождество #1: CRR <= 6%)
        crr_check = M.check_friction_budget_crr(
            sig["entry_price"], sig["stop_price"],
            is_maker=(sig["order_type"] == "limit"), max_crr=0.06
        )
        if crr_check["passed"] < 1.0:
            return None

        sig["v16_features"] = {
            "ker_20": round(ker, 3),
            "kalman_vel_z": round(kz, 3),
            "hawkes_h": round(h_now, 3),
            "crr_ratio": crr_check["crr_ratio"],
            "stop_pct": crr_check["stop_pct"],
        }
        return sig


class QuantV16Engine(E.UnifiedQuantEngine):
    """Расширяет UnifiedQuantEngine защитой лимиток Глостена-Милгрома и логгером признаков v16."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trade_features_map: Dict[str, Dict] = {}

    def _try_fill_pending(self, symbol: str, curr: E.Candle) -> bool:
        sig = self.pending.get(symbol)
        if sig and sig.get("order_type") == "limit":
            # Тождество #4 (Глостен-Милгром): отмена лимитки при токсичном встречном ударе
            avg_v = sig.get("atr", 1.0)
            if M.is_pullback_toxic(curr.open, curr.close, curr.volume, max(1.0, curr.volume * 0.65), sig["atr"], sig["direction"]):
                self.pending.pop(symbol, None)
                return False

        feats = sig.get("v16_features", {}) if sig else {}
        filled = super()._try_fill_pending(symbol, curr)
        if filled and symbol in self.open_positions:
            t_id = self.open_positions[symbol].trade_id
            self.trade_features_map[t_id] = feats
        return filled


def run_v16_pipeline(data_dir: Optional[str], journal_out: str, tensor_out: str) -> None:
    # Подключаем фильтр v16 в ядро стратегии
    E.QuantStrategyCore.evaluate_signal = staticmethod(classQuantV16SignalGate.evaluate_v16)

    candles = (
        E.load_candles_csv(data_dir)
        if data_dir
        else E.generate_synthetic_candles(["DOGEUSDT", "SOLUSDT", "XRPUSDT", "ETHUSDT"], bars_count=2400)
    )
    syms = [s for s in ["DOGEUSDT", "SOLUSDT", "XRPUSDT", "ETHUSDT"] if s in candles] or list(candles.keys())

    cfg = dataclasses.replace(E.BotConfig(), bot_version="v16.0-institutional-alpha", active_trading_pool=syms)
    eng = QuantV16Engine(journal_output_path=journal_out)
    eng.cfg = cfg
    eng.risk_mgr = E.AdaptiveRiskManager(cfg)
    eng.reset_state_for_new_run()

    bars_total = min(len(candles[s]) for s in syms)
    for bar in range(65, bars_total):
        lo = max(0, bar + 1 - E.CALC_WINDOW)
        for s in syms:
            eng.step_candle(s, candles[s][lo:bar + 1])

    audit = eng.export_journal_for_dashboard()
    trades_dicts = [dataclasses.asdict(t) for t in eng.closed_trades]
    for td in trades_dicts:
        td["features"] = eng.trade_features_map.get(td["id"], {})

    r_vals = [float(t.net_r_multiple) for t in eng.closed_trades]
    tensor = {
        "bot_version": cfg.bot_version,
        "summary": audit,
        "deflated_sharpe": P.compute_deflated_sharpe(r_vals, n_trials=24),
        "survival_mae_mfe": P.optimize_mae_mfe_survival(trades_dicts),
        "prim_subgroups": P.discover_subgroups_split_half(trades_dicts),
    }
    with open(tensor_out, "w", encoding="utf-8") as f:
        json.dump(tensor, f, indent=2, ensure_ascii=False)

    print(
        f"✅ V16.0 ЗАВЕРШЕН | Сделок: {audit['total_trades']} | Net PnL: ${audit['net_pnl']:+.2f} "
        f"({audit['ret_pct']:+.1f}%) | PF: {audit['pf']:.2f} | DSR: {tensor['deflated_sharpe']['dsr_prob']}%"
    )
    print(f"📂 Журнал: {journal_out} | Математический тензор для ИИ: {tensor_out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--journal", default="bybit_trade_journal_v6_1.json")
    ap.add_argument("--tensor", default="ai_research_tensor.json")
    a = ap.parse_args()
    run_v16_pipeline(a.data_dir, a.journal, a.tensor)