#!/usr/bin/env python3
"""
Модуль когнитивной эффективности ИИ (quant_fast_validator_v16.py):
1. Автоматический контрактный самотест (Smoke-Test Gate) против багов в коде.
2. Диагностика 3 классов потерь по Тождеству №7 (Toxic Entry vs Giveback vs Friction Death).
3. Расчёт локальных градиентов чувствительности параметров (Jacobian Sensitivity).
4. Генерация сверхсжатого ИИ-брифа (~600 токенов) с реестром проверенных гипотез.
"""
import json
import os
from typing import Any, Dict, List

import Bybit_Trading_Engine_v14_Audit_Fixed as E
import quant_math_lab_v16 as M
import quant_pattern_miner_v16 as P


def run_smoke_test_gate(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Проверяет код и журнал сделок на 4 жёстких математических и программных инварианта."""
    has_build = hasattr(E.QuantStrategyCore, "build_levels")
    has_eval = hasattr(E.QuantStrategyCore, "evaluate_signal")

    # Проверка бухгалтерского тождества: Gross - Fees - Slip == Net
    acc_errors = 0
    crr_list = []
    for t in trades:
        g = float(t.get("gross_pnl", 0.0))
        f = float(t.get("exchange_fees_usdt", 0.0)) + float(t.get("slippage_cost_usdt", 0.0))
        n = float(t.get("pnl_usdt", 0.0))
        if abs((g - f) - n) > 0.05:
            acc_errors += 1
        r_u = float(t.get("risk_usdt", 100.0)) or 100.0
        crr_list.append(f / max(1.0, r_u))

    avg_crr = (sum(crr_list) / len(crr_list)) if crr_list else 0.0
    return {
        "api_integrity_ok": bool(has_build and has_eval),
        "accounting_identity_ok": acc_errors == 0,
        "avg_crr_pct": round(avg_crr * 100.0, 2),
        "friction_budget_ok": avg_crr <= 0.08,
        "all_invariants_passed": bool(has_build and has_eval and acc_errors == 0),
    }


def classify_loss_duality(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Тождество №7: Делит все убыточные сделки на 3 непересекающихся физических класса."""
    c1_toxic, c2_giveback, c3_friction = 0.0, 0.0, 0.0
    n1, n2, n3 = 0, 0, 0
    for t in trades:
        net = float(t.get("pnl_usdt", 0.0))
        if net >= 0:
            continue
        gross = float(t.get("gross_pnl", net))
        mfe = float(t.get("mfe", 0.0))
        if gross > 0 and net < 0:
            c3_friction += abs(net)
            n3 += 1
        elif mfe >= 1.15:
            c2_giveback += abs(net)
            n2 += 1
        elif mfe < 0.35:
            c1_toxic += abs(net)
            n1 += 1
        else:
            c1_toxic += abs(net)
            n1 += 1
    return {
        "class1_toxic_entry": {"trades": n1, "loss_usdt": round(-c1_toxic, 2), "fix": "Входной фильтр KER/Kalman/BTC"},
        "class2_mfe_giveback": {"trades": n2, "loss_usdt": round(-c2_giveback, 2), "fix": "Безубыток BE* и ранний трал"},
        "class3_friction_death": {"trades": n3, "loss_usdt": round(-c3_friction, 2), "fix": "Maker Limit + Stop >= 1.8%"},
    }


def compute_parameter_gradients(trades: List[Dict[str, Any]]) -> Dict[str, float]:
    """Вычисляет контрфактический градиент (чувствительность Net PnL в $) к 3 главным рычагам."""
    grad_maker = 0.0
    grad_stop_tighten = 0.0
    grad_be_lock = 0.0
    for t in trades:
        fees = float(t.get("exchange_fees_usdt", 0.0))
        slip = float(t.get("slippage_cost_usdt", 0.0))
        net = float(t.get("pnl_usdt", 0.0))
        mae = float(t.get("mae", 0.5))
        mfe = float(t.get("mfe", 0.5))
        risk_u = float(t.get("risk_usdt", 100.0)) or 100.0

        if t.get("order_type") == "market":
            grad_maker += slip * 0.85 + fees * 0.55
        if mae > 0.80:
            grad_stop_tighten += (-0.80 * risk_u - (fees + slip) - net)
        if net < 0 and mfe >= 1.0:
            grad_be_lock += abs(net)

    return {
        "dPnL_dMakerLimit_usdt": round(grad_maker, 2),
        "dPnL_dStopAt080R_usdt": round(grad_stop_tighten, 2),
        "dPnL_dBreakevenAt1R_usdt": round(grad_be_lock, 2),
    }


def build_compact_ai_digest(journal_path: str = "bybit_trade_journal_v6_1.json") -> str:
    """Формирует сверхсжатый отчёт (600 токенов) для мгновенной диагностики ИИ без воды."""
    if not os.path.exists(journal_path):
        return "❌ Файл журнала не найден."
    with open(journal_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    trades = data.get("trades", data if isinstance(data, list) else [])
    r_vals = [float(t.get("net_r_multiple", t.get("r_multiple", 0.0))) for t in trades]

    gate = run_smoke_test_gate(trades)
    duality = classify_loss_duality(trades)
    grads = compute_parameter_gradients(trades)
    dsr = P.compute_deflated_sharpe(r_vals)
    surv = P.optimize_mae_mfe_survival(trades)
    prim = P.discover_subgroups_split_half(trades)

    digest = {
        "1_SMOKE_GATE": gate,
        "2_DSR_ROBUSTNESS": dsr,
        "3_LOSS_DUALITY_IDENTITY_7": duality,
        "4_PARAMETER_GRADIENTS_USD": grads,
        "5_SURVIVAL_OPTIMAL_LEVELS": surv,
        "6_PRIM_TOP_CLUSTERS": {
            "golden": prim["golden_clusters"][:3],
            "toxic": prim["toxic_clusters"][:3],
        },
        "7_NEGATIVE_MEMORY_LEDGER": [
            "REJECTED: 15m scalping stop<0.8% market orders (CRR=36% fee death)",
            "REJECTED: PEPEUSDT & SUIUSDT breakout trading (negative gross edge)",
            "ACTIVE: 12-24h swing + Maker pullback 0.18 ATR + CRR<=6% gate",
        ],
    }
    return "=== AI QUANT COMPACT DIGEST (600 TOKENS) ===\n" + json.dumps(digest, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    print(build_compact_ai_digest())