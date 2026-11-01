#!/usr/bin/env python3
"""
Часть 1: Институциональное математическое ядро (quant_math_lab_v16.py)
Реализует стохастическую фильтрацию, сигнатуры путей и законы сохранения трения.
"""
import math
from typing import Dict, List, Tuple


def frac_diff_ffd(series: List[float], d: float = 0.38, thres: float = 1e-3) -> List[float]:
    """Дробное дифференцирование с фиксированным окном (FFD, Lopez de Prado)."""
    w = [1.0]
    k = 1
    while True:
        w_k = -w[-1] * (d - k + 1.0) / k
        if abs(w_k) < thres or k >= 64:
            break
        w.append(w_k)
        k += 1
    width = len(w)
    out = [0.0] * len(series)
    for i in range(width - 1, len(series)):
        val = 0.0
        for j in range(width):
            val += w[j] * series[i - j]
        out[i] = val
    return out


def kalman_velocity_filter(prices: List[float], q_var: float = 1e-4, r_var: float = 1e-2) -> Tuple[List[float], List[float]]:
    """2D Кинематический фильтр Калмана: возвращает сглаженный уровень и Z-скорость тренда."""
    if not prices:
        return [], []
    p_est, v_est = math.log(max(1e-9, prices[0])), 0.0
    p00, p01, p11 = 1.0, 0.0, 1.0
    levels, vel_z = [], []

    for px in prices:
        y = math.log(max(1e-9, px))
        # Предсказание: s_{t|t-1} = F * s_{t-1}
        p_pred = p_est + v_est
        v_pred = v_est
        p00_p = p00 + 2.0 * p01 + p11 + q_var
        p01_p = p01 + p11
        p11_p = p11 + q_var

        # Обновление по наблюдению
        innov = y - p_pred
        s_cov = p00_p + r_var
        k0 = p00_p / s_cov
        k1 = p01_p / s_cov

        p_est = p_pred + k0 * innov
        v_est = v_pred + k1 * innov
        p00 = (1.0 - k0) * p00_p
        p01 = (1.0 - k0) * p01_p
        p11 = p11_p - k1 * p01_p

        levels.append(math.exp(p_est))
        vel_z.append(v_est / math.sqrt(max(1e-12, p11)))
    return levels, vel_z


def kaufman_efficiency_ratio(closes: List[float], period: int = 20) -> float:
    """Коэффициент фрактальной эффективности Кауфмана KER in [0, 1]."""
    if len(closes) < period + 1:
        return 0.5
    tail = closes[-(period + 1):]
    net_move = abs(tail[-1] - tail[0])
    path_len = sum(abs(tail[i] - tail[i - 1]) for i in range(1, len(tail)))
    return net_move / path_len if path_len > 1e-12 else 0.0


def hawkes_cascade_intensity(
    opens: List[float], highs: List[float], lows: List[float],
    closes: List[float], volumes: List[float], alpha: float = 0.35, beta: float = 0.25
) -> List[float]:
    """Самовозбуждающийся процесс Хоукса H_t для детекции каскадов и их выгорания."""
    n = len(closes)
    if n == 0:
        return []
    out = [0.0] * n
    decay = math.exp(-beta)
    h_val = 0.0
    for i in range(1, n):
        w0 = max(0, i - 20)
        atr = sum(highs[j] - lows[j] for j in range(w0, i)) / max(1, i - w0)
        avg_v = sum(volumes[w0:i]) / max(1, i - w0)
        stretch = abs(closes[i] - opens[i]) / max(1e-9, atr)
        v_rel = volumes[i] / max(1e-9, avg_v)
        shock = max(0.0, stretch * v_rel - 1.2)
        h_val = h_val * decay + alpha * shock
        out[i] = round(h_val, 4)
    return out


def levy_area_2d(series_x: List[float], series_y: List[float]) -> float:
    """
    Ориентированная Площадь Леви A_{X,Y} (Сигнатура 2-го порядка Лайонса).
    Если X = Цена, Y = Открытый Интерес:
      A > 0 -> Сначала накапливался OI, затем пошла цена (умное накопление).
      A < 0 -> Сначала скакнула цена, затем набилась толпа на хаях (ловушка).
    """
    n = min(len(series_x), len(series_y))
    if n < 3:
        return 0.0
    x0, y0 = series_x[0], series_y[0]
    sx = max(1e-9, max(series_x) - min(series_x))
    sy = max(1e-9, max(series_y) - min(series_y))
    x_norm = [(v - x0) / sx for v in series_x[:n]]
    y_norm = [(v - y0) / sy for v in series_y[:n]]

    area = 0.0
    for i in range(1, n):
        dx = x_norm[i] - x_norm[i - 1]
        dy = y_norm[i] - y_norm[i - 1]
        area += 0.5 * (x_norm[i - 1] * dy - y_norm[i - 1] * dx)
    return round(area, 4)


def check_friction_budget_crr(
    entry_price: float, stop_price: float, is_maker: bool = True,
    taker_fee: float = 0.00055, maker_fee: float = 0.00020,
    taker_slip: float = 0.00025, max_crr: float = 0.06
) -> Dict[str, float]:
    """Тождество #1: Контроль сгорания риска в комиссиях (CRR = C_rt / stop_pct <= max_crr)."""
    stop_pct = abs(entry_price - stop_price) / max(1e-9, entry_price)
    c_rt = (2.0 * maker_fee) if is_maker else (2.0 * (taker_fee + taker_slip))
    crr = c_rt / max(1e-9, stop_pct)
    min_safe_stop_pct = c_rt / max_crr
    return {
        "stop_pct": round(stop_pct * 100.0, 3),
        "crr_ratio": round(crr, 4),
        "min_safe_stop_pct": round(min_safe_stop_pct * 100.0, 3),
        "passed": 1.0 if crr <= max_crr else 0.0,
    }


def is_pullback_toxic(bar_open: float, bar_close: float, bar_vol: float, avg_vol: float, atr: float, direction: str) -> bool:
    """Тождество #4 (Глостен-Милгром): Отмена лимитки, если откат идёт на взрывном встречном объёме."""
    adv_move = (bar_open - bar_close) if direction == "long" else (bar_close - bar_open)
    if adv_move <= 0:
        return False
    toxicity = (bar_vol / max(1e-9, avg_vol)) * (adv_move / max(1e-9, atr))
    return toxicity >= 1.35