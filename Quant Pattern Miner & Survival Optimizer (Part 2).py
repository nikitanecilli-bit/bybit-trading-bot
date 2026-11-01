#!/usr/bin/env python3
"""
Часть 2: Автономный искатель закономерностей PRIM, выживаемости MAE/MFE и DSR (v16.0).
Работает напрямую с журналом сделок bybit_trade_journal_v6_1.json.
"""
import json
import math
import os
from typing import Dict, List, Any


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def compute_deflated_sharpe(r_list: List[float], n_trials: int = 25) -> Dict[str, float]:
    """Дефлированный Шарп (DSR, Lopez de Prado) с учётом асимметрии, эксцесса и числа гипотез K."""
    n = len(r_list)
    if n < 10:
        return {"sr": 0.0, "dsr_prob": 0.0, "skew": 0.0, "kurt": 3.0}
    mu = sum(r_list) / n
    var = sum((x - mu) ** 2 for x in r_list) / max(1, n - 1)
    sd = math.sqrt(max(1e-12, var))
    sr = mu / sd
    skew = sum(((x - mu) / sd) ** 3 for x in r_list) / n
    kurt = sum(((x - mu) / sd) ** 4 for x in r_list) / n

    # Ожидаемый максимум ложного Шарпа при K независимых испытаниях
    euler_gamma = 0.5772156649
    z1 = math.sqrt(2.0 * math.log(max(2, n_trials)))
    sr_benchmark = sd * ((1.0 - euler_gamma) * z1 + euler_gamma * math.sqrt(2.0 * math.log(max(2, n_trials) * math.e))) / max(1.0, math.sqrt(n))

    denom_sq = max(1e-9, 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * (sr ** 2))
    z_dsr = ((sr - sr_benchmark) * math.sqrt(n - 1.0)) / math.sqrt(denom_sq)
    return {
        "sr_per_trade": round(sr, 4),
        "sr_benchmark": round(sr_benchmark, 4),
        "dsr_prob": round(_norm_cdf(z_dsr) * 100.0, 2),
        "skew": round(skew, 3),
        "kurt": round(kurt, 3),
    }


def optimize_mae_mfe_survival(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Непараметрический анализ выживаемости Каплана-Мейера по распределениям MAE и MFE."""
    valid = [t for t in trades if t.get("mae") is not None and t.get("mfe") is not None]
    if len(valid) < 10:
        return {"optimal_mae_stop_r": 1.0, "mae_saved_usdt": 0.0, "optimal_be_mfe_r": 1.0, "be_saved_usdt": 0.0}

    best_s, best_gain = 1.0, 0.0
    for step in range(40, 115, 5):
        s = step / 100.0
        delta_usd = 0.0
        for t in valid:
            r_val = float(t.get("r_multiple", 0.0))
            pnl = float(t.get("pnl_usdt", 0.0))
            risk_u = abs(pnl / r_val) if abs(r_val) > 0.05 else 100.0
            mae = float(t["mae"])
            if mae > s:
                new_pnl = -s * risk_u
                delta_usd += (new_pnl - pnl)
        if delta_usd > best_gain:
            best_gain, best_s = delta_usd, s

    # Поиск оптимального триггера безубытка (сделки с высоким MFE, закрывшиеся в минус)
    best_be, best_be_gain = 1.0, 0.0
    for step in range(70, 160, 10):
        be_trig = step / 100.0
        saved = 0.0
        for t in valid:
            pnl = float(t.get("pnl_usdt", 0.0))
            mfe = float(t["mfe"])
            if pnl < 0 and mfe >= be_trig:
                saved += abs(pnl)
        if saved > best_be_gain:
            best_be_gain, best_be = saved, be_trig

    return {
        "optimal_mae_stop_r": round(best_s, 2),
        "mae_saved_usdt": round(best_gain, 2),
        "optimal_be_mfe_r": round(best_be, 2),
        "be_saved_usdt": round(best_be_gain, 2),
    }


def discover_subgroups_split_half(trades: List[Dict[str, Any]], min_count: int = 8) -> Dict[str, List[Dict]]:
    """
    Ищет устойчивые Золотые и Токсичные правила (1D и 2D комбинации),
    проверяя сохранение знака ожидания на 1-й и 2-й половинах истории (Split-Half Invariance).
    """
    n = len(trades)
    if n < min_count * 2:
        return {"toxic_clusters": [], "golden_clusters": []}
    mid = n // 2

    def extract_tags(t: Dict[str, Any]) -> List[str]:
        tags = [
            f"token={t.get('token', 'UNK')}",
            f"dir={t.get('direction', 'long')}",
            f"session={t.get('session', 'eu')}",
            f"order={t.get('order_type', 'market')}",
        ]
        fees_slip = float(t.get("exchange_fees_usdt", 0.0)) + float(t.get("slippage_cost_usdt", 0.0))
        gross = float(t.get("gross_pnl", t.get("pnl_usdt", 0.0)))
        r_mult = float(t.get("r_multiple", 0.0))
        risk_u = abs(gross / r_mult) if abs(r_mult) > 0.05 else 100.0
        crr = fees_slip / max(1.0, risk_u)
        tags.append("crr>12%" if crr > 0.12 else "crr<=12%")
        return tags

    buckets: Dict[str, List[Tuple[int, float]]] = {}
    for idx, t in enumerate(trades):
        pnl = float(t.get("pnl_usdt", 0.0))
        t_tags = extract_tags(t)
        for tg in t_tags:
            buckets.setdefault(tg, []).append((idx, pnl))
        for i in range(len(t_tags)):
            for j in range(i + 1, len(t_tags)):
                pair = f"{t_tags[i]} AND {t_tags[j]}"
                buckets.setdefault(pair, []).append((idx, pnl))

    toxic, golden = [], []
    for rule, items in buckets.items():
        if len(items) < min_count or len(items) > n * 0.85:
            continue
        h1 = [p for idx, p in items if idx < mid]
        h2 = [p for idx, p in items if idx >= mid]
        if len(h1) < 3 or len(h2) < 3:
            continue
        m1, m2 = sum(h1) / len(h1), sum(h2) / len(h2)
        vals = [p for _, p in items]
        tot = sum(vals)
        mean_v = tot / len(vals)
        var_v = sum((x - mean_v) ** 2 for x in vals) / max(1, len(vals) - 1)
        t_stat = mean_v / (math.sqrt(max(1e-9, var_v)) / math.sqrt(len(vals)))

        rec = {
            "rule": rule, "trades": len(vals), "total_pnl": round(tot, 2),
            "avg_pnl": round(mean_v, 2), "t_stat": round(t_stat, 2),
        }
        if m1 < 0 and m2 < 0 and tot < 0:
            toxic.append(rec)
        elif m1 > 0 and m2 > 0 and tot > 0:
            golden.append(rec)

    toxic.sort(key=lambda x: x["total_pnl"])
    golden.sort(key=lambda x: x["total_pnl"], reverse=True)
    return {"toxic_clusters": toxic[:6], "golden_clusters": golden[:6]}


if __name__ == "__main__":
    j_path = "bybit_trade_journal_v6_1.json"
    if os.path.exists(j_path):
        with open(j_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        tr_list = data.get("trades", data if isinstance(data, list) else [])
        r_vals = [float(t.get("net_r_multiple", t.get("r_multiple", 0.0))) for t in tr_list]
        report = {
            "dsr": compute_deflated_sharpe(r_vals),
            "survival_opt": optimize_mae_mfe_survival(tr_list),
            "subgroups": discover_subgroups_split_half(tr_list),
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))