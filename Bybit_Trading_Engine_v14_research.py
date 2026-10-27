#!/usr/bin/env python3
"""
Bybit Quant Engine v14.0 (Audit-Fixed)
======================================
ВАЖНО: это по-прежнему СИМУЛЯТОР/бэктест-движок. Подключения к Bybit (данные, ордера) здесь нет.
Статистика на синтетических свечах НЕ доказывает прибыльность стратегии: используйте --data-dir
с реальной историей (CSV) и сравнивайте с --no-planted-edge (рынок без заложенного "эджа").

ИСПРАВЛЕНИЯ ПО АУДИТУ v13.1 + v3:
 1. Конфиг: битый/недописанный JSON больше НЕ сбрасывает настройки на дефолты (старый конфиг остаётся),
    добавлена валидация значений, повторная загрузка того же испорченного файла не зацикливается.
 2. Конфиг: читаются leverage_val (из leverage_mode "ISOLATED_3X" или risk_management.leverage_val),
    max_concurrent_positions и параметры стратегии (секция "strategy").
 3. Plan B: сохраняются kill_switch/daily_stop/pause, день, trade_seq и pending-ордера; ID сделок не дублируются.
    Бэктест НЕ трогает файл состояния (только --persist-state).
 4. Kill-Switch теперь реально закрывает открытые позиции (exit_reason=kill_switch).
 5. r_multiple = NET R (с учётом издержек); добавлены gross_r_multiple, risk_usdt, risk_pct.
    MFE/MAE больше не искажаются искусственными порогами.
 6. Лимит 5000 сделок убран (он ломал доходность/DD/PF и стирал журнал).
 7. Блок "узкое место": при проваленных KPI больше не пишет "Зелёный коридор".
 8. Издержки считаются по ногам: вход, TP1, финальный выход. Стопы/time-stop/kill-switch = taker всегда.
 9. Maker: лимитный вход исполняется только если следующая свеча коснулась цены (иначе сделка пропущена).
10. Вход по сигналу закрытой свечи исполняется на ОТКРЫТИИ следующей (market) или лимиткой, а не по её close.
    Max Chase проверяется по гэпу к цене сигнала.
11. TP2 в одной свече с невзятым TP1 -> сначала фиксируется 50% на TP1, остаток на TP2 (а не 100% по 2.4R).
12. Стоп при гэпе исполняется по худшей из цен (open/stop), а не по "лучшей".
13. Ожидание (expectancy) считается по R каждой сделки от её фактического риска, а не от стартового капитала.
14. Синхронизация баров по символам проверяется; окно свечей для расчёта ограничено (скорость).
15. Размер позиции учитывает оценку комиссий и проскальзывания на входе и стоп-выходе.
"""

import argparse
import csv
import dataclasses
import glob
import json
import logging
import math
import os
from decimal import Decimal, ROUND_HALF_UP
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("QuantEngineV14")

# Тарифы Bybit USDT-перпов (базовый уровень): за одну ногу сделки
TAKER_FEE = 0.00055
MAKER_FEE = 0.00020
TAKER_SLIP = 0.000225   # проскальзывание на одну taker-ногу (round-trip ~0.045%)
TP1_FRACTION = 0.5
CALC_WINDOW = 200       # сколько последних свечей достаточно для ATR/Дончиана


def _money_round(value: float) -> float:
    """Round financial values to cents using conventional half-up rounding."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _as_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "true", "yes", "on", "да"):
            return True
        if s in ("0", "false", "no", "off", "нет", ""):
            return False
    return default


# =====================================================================
# 1. КОНФИГУРАЦИЯ И МОСТ С ДАШБОРДОМ
# =====================================================================

@dataclass
class BotConfig:
    bot_version: str = "v6.1"
    maintenance_gate_status: str = "ACTIVE_MONITORING"
    capital_usdt: float = 10000.0

    target_ret_pct: float = 15.0
    target_win_rate: float = 40.0
    max_dd_pct: float = 10.0
    max_risk_trade_pct: float = 1.0
    target_pf: float = 1.35
    min_expectancy_r: float = 0.15
    max_cost_drag_pct: float = 22.0

    leverage_mode: str = "ISOLATED_5X"
    leverage_val: float = 5.0
    daily_stop_loss_pct: float = 5.0
    emergency_kill_switch_pct: float = 30.0
    max_chase_limit_pct: float = 1.5
    max_concurrent_positions: int = 3
    max_portfolio_risk_pct: float = 2.0

    timeframe: str = "15m"
    donchian_period: int = 20
    atr_period: int = 14
    min_volume_ratio: float = 1.6
    stop_atr_mult: float = 1.5
    tp1_r_multiple: float = 1.2
    tp2_r_multiple: float = 2.4
    atr_trail_mult: float = 2.5
    max_hold_bars: int = 16

    maker_entry_and_tp1: bool = False
    accelerated_atr_trail_after_1_5r: bool = False
    enable_h2_range_fade: bool = False

    active_trading_pool: List[str] = field(
        default_factory=lambda: ["SOLUSDT", "BTCUSDT", "ETHUSDT", "AVAXUSDT", "DOGEUSDT"]
    )
    disabled_instruments: List[str] = field(default_factory=list)
    blocked_sessions_utc: List[str] = field(default_factory=list)
    blocked_signal_hours_utc: List[int] = field(default_factory=list)  # 0..23 UTC
    blocked_weekdays_utc: List[int] = field(default_factory=list)  # Monday=0 ... Sunday=6
    blocked_directions: List[str] = field(default_factory=list)
    applied_patches_log: List[Dict] = field(default_factory=list)

    source_filepath: Optional[str] = None
    loaded_mtime: float = 0.0

    @property
    def one_r_usdt(self) -> float:
        """Ориентир 1R от СТАРТОВОГО капитала (только для порогов диагностики)."""
        return round(self.capital_usdt * (self.max_risk_trade_pct / 100.0), 2)

    def validate(self) -> None:
        errs = []
        numeric_values = {
            "capital_usdt": self.capital_usdt,
            "max_risk_trade_pct": self.max_risk_trade_pct,
            "leverage_val": self.leverage_val,
            "daily_stop_loss_pct": self.daily_stop_loss_pct,
            "emergency_kill_switch_pct": self.emergency_kill_switch_pct,
            "max_portfolio_risk_pct": self.max_portfolio_risk_pct,
            "max_chase_limit_pct": self.max_chase_limit_pct,
            "stop_atr_mult": self.stop_atr_mult,
            "tp1_r_multiple": self.tp1_r_multiple,
            "tp2_r_multiple": self.tp2_r_multiple,
            "atr_trail_mult": self.atr_trail_mult,
            "min_volume_ratio": self.min_volume_ratio,
        }
        for name, value in numeric_values.items():
            if not math.isfinite(value):
                errs.append(f"{name} must be finite")
        if self.capital_usdt <= 0: errs.append("capital_usdt <= 0")
        if not (0 < self.max_risk_trade_pct <= 5): errs.append("риск на сделку вне (0; 5]%")
        if not (0 < self.max_portfolio_risk_pct <= 10): errs.append("max_portfolio_risk_pct вне (0; 10]%")
        if not (1 <= self.leverage_val <= 125): errs.append("плечо вне [1; 125]")
        if self.daily_stop_loss_pct <= 0: errs.append("daily_stop_loss_pct <= 0")
        if self.emergency_kill_switch_pct <= 0: errs.append("emergency_kill_switch_pct <= 0")
        if self.max_chase_limit_pct <= 0: errs.append("max_chase_limit_pct <= 0")
        if self.max_concurrent_positions < 1: errs.append("max_concurrent_positions < 1")
        if self.donchian_period < 2 or self.atr_period < 2: errs.append("периоды индикаторов < 2")
        if self.stop_atr_mult <= 0: errs.append("stop_atr_mult <= 0")
        if not (0 < self.tp1_r_multiple < self.tp2_r_multiple): errs.append("нужно 0 < TP1 < TP2")
        # Defensive guard: extreme targets can silently turn the strategy into a
        # trailing/time-stop system. Raise this limit only after explicit research.
        if self.tp2_r_multiple > 10.0:
            errs.append("tp2_r_multiple > 10R: extreme targets require explicit strategy review")
        if self.atr_trail_mult <= 0: errs.append("atr_trail_mult <= 0")
        if self.max_hold_bars < 1: errs.append("max_hold_bars < 1")
        if any(day not in range(7) for day in self.blocked_weekdays_utc):
            errs.append("blocked_weekdays_utc must contain only integers 0..6 (Monday=0)")
        if any(hour not in range(24) for hour in self.blocked_signal_hours_utc):
            errs.append("blocked_signal_hours_utc must contain only integers 0..23")
        if self.min_volume_ratio <= 0: errs.append("min_volume_ratio <= 0")
        if errs:
            raise ValueError("; ".join(errs))

    def _apply(self, data: Dict) -> None:
        allowed_top = {
            "_note", "bot_version", "maintenance_gate_status", "capital_usdt", "goals_plan",
            "risk_management", "strategy", "strategy_params", "execution_and_exits",
            "active_trading_pool", "disabled_instruments", "blocked_sessions_utc",
            "blocked_signal_hours_utc", "blocked_weekdays_utc", "blocked_directions", "applied_patches_log",
        }
        unknown_top = sorted(set(data) - allowed_top)
        if unknown_top:
            raise ValueError(f"unsupported top-level config keys: {', '.join(unknown_top)}")

        allowed_goals = {
            "targetRetPct", "maxRiskTradePct", "maxDDPct", "targetWinRate",
            "targetPF", "minExpectancyR", "maxCostDragPct",
        }
        goals = data.get("goals_plan", {}) or {}
        if not isinstance(goals, dict):
            raise ValueError("goals_plan must be an object")
        unknown_goals = sorted(set(goals) - allowed_goals)
        if unknown_goals:
            raise ValueError(f"unsupported goals_plan keys: {', '.join(unknown_goals)}")

        allowed_risk = {
            "risk_per_trade_pct", "leverage_mode", "leverage_val", "daily_stop_loss_pct",
            "emergency_kill_switch_pct", "max_chase_limit_pct", "max_concurrent_positions",
            "max_portfolio_risk_pct",
        }
        rm_check = data.get("risk_management", {}) or {}
        if not isinstance(rm_check, dict):
            raise ValueError("risk_management must be an object")
        unknown_risk = sorted(set(rm_check) - allowed_risk)
        if unknown_risk:
            raise ValueError(f"unsupported risk_management keys: {', '.join(unknown_risk)}")

        allowed_strategy = {
            "donchian_period", "atr_period", "max_hold_bars", "min_volume_ratio",
            "stop_atr_mult", "tp1_r_multiple", "tp2_r_multiple", "atr_trail_mult",
            "timeframe", "enable_h2_range_fade",
        }
        strategy_check = data.get("strategy", data.get("strategy_params", {})) or {}
        if not isinstance(strategy_check, dict):
            raise ValueError("strategy must be an object")
        unknown_strategy = sorted(set(strategy_check) - allowed_strategy)
        if unknown_strategy:
            raise ValueError(f"unsupported strategy keys (not implemented): {', '.join(unknown_strategy)}")

        allowed_execution = {"maker_entry_and_tp1", "accelerated_atr_trail_after_1_5r"}
        ex_check = data.get("execution_and_exits", {}) or {}
        if not isinstance(ex_check, dict):
            raise ValueError("execution_and_exits must be an object")
        unknown_execution = sorted(set(ex_check) - allowed_execution)
        if unknown_execution:
            raise ValueError(f"unsupported execution_and_exits keys: {', '.join(unknown_execution)}")

        self.bot_version = str(data.get("bot_version", self.bot_version))
        self.maintenance_gate_status = str(data.get("maintenance_gate_status", self.maintenance_gate_status))
        self.capital_usdt = float(data.get("capital_usdt", self.capital_usdt))

        goals = data.get("goals_plan", {}) or {}
        for attr, key in (
            ("target_ret_pct", "targetRetPct"), ("max_risk_trade_pct", "maxRiskTradePct"),
            ("max_dd_pct", "maxDDPct"), ("target_win_rate", "targetWinRate"),
            ("target_pf", "targetPF"), ("min_expectancy_r", "minExpectancyR"),
            ("max_cost_drag_pct", "maxCostDragPct"),
        ):
            if key in goals:
                setattr(self, attr, float(goals[key]))

        rm = data.get("risk_management", {}) or {}
        if "risk_per_trade_pct" in rm:
            self.max_risk_trade_pct = float(rm["risk_per_trade_pct"])
        if "leverage_mode" in rm:
            self.leverage_mode = str(rm["leverage_mode"])
            m = re.search(r"(\d+(?:\.\d+)?)\s*[xXхХ]", self.leverage_mode)
            if m:
                self.leverage_val = float(m.group(1))
        if "leverage_val" in rm:
            self.leverage_val = float(rm["leverage_val"])
        for attr in ("daily_stop_loss_pct", "emergency_kill_switch_pct", "max_chase_limit_pct"):
            if attr in rm:
                setattr(self, attr, float(rm[attr]))
        if "max_concurrent_positions" in rm:
            self.max_concurrent_positions = int(rm["max_concurrent_positions"])
        if "max_portfolio_risk_pct" in rm:
            self.max_portfolio_risk_pct = float(rm["max_portfolio_risk_pct"])

        st = data.get("strategy", data.get("strategy_params", {})) or {}
        for attr in ("donchian_period", "atr_period", "max_hold_bars"):
            if attr in st:
                setattr(self, attr, int(st[attr]))
        for attr in ("min_volume_ratio", "stop_atr_mult", "tp1_r_multiple", "tp2_r_multiple", "atr_trail_mult"):
            if attr in st:
                setattr(self, attr, float(st[attr]))
        if "timeframe" in st:
            self.timeframe = str(st["timeframe"])
        self.enable_h2_range_fade = _as_bool(st.get("enable_h2_range_fade", False))

        ex = data.get("execution_and_exits", {}) or {}
        self.maker_entry_and_tp1 = _as_bool(ex.get("maker_entry_and_tp1", False))
        self.accelerated_atr_trail_after_1_5r = _as_bool(ex.get("accelerated_atr_trail_after_1_5r", False))

        if isinstance(data.get("active_trading_pool"), list):
            self.active_trading_pool = [str(x) for x in data["active_trading_pool"]]
        if isinstance(data.get("disabled_instruments"), list):
            self.disabled_instruments = [str(x) for x in data["disabled_instruments"]]
        if "blocked_sessions_utc" in data:
            if not isinstance(data["blocked_sessions_utc"], list):
                raise ValueError("blocked_sessions_utc must be a list")
            self.blocked_sessions_utc = [str(x).lower() for x in data["blocked_sessions_utc"]]
        if "blocked_signal_hours_utc" in data:
            hours = data["blocked_signal_hours_utc"]
            if not isinstance(hours, list) or any(isinstance(hour, bool) or not isinstance(hour, int) for hour in hours):
                raise ValueError("blocked_signal_hours_utc must be a list of integers 0..23")
            self.blocked_signal_hours_utc = hours[:]
        if "blocked_weekdays_utc" in data:
            days = data["blocked_weekdays_utc"]
            if not isinstance(days, list) or any(isinstance(day, bool) or not isinstance(day, int) for day in days):
                raise ValueError("blocked_weekdays_utc must be a list of integers 0..6 (Monday=0)")
            self.blocked_weekdays_utc = days[:]
        if isinstance(data.get("blocked_directions"), list):
            self.blocked_directions = [str(x).lower() for x in data["blocked_directions"]]
        if isinstance(data.get("applied_patches_log"), list):
            self.applied_patches_log = data["applied_patches_log"]

    @classmethod
    def find_latest_config_file(cls, directory: str = ".") -> Optional[str]:
        pattern = os.path.join(directory, "bot_live_config*.json")
        candidates = [f for f in glob.glob(pattern) if os.path.isfile(f)]
        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0] if candidates else None

    @classmethod
    def try_load(cls, filepath: str) -> Optional["BotConfig"]:
        """Строгая загрузка: при ЛЮБОЙ ошибке возвращает None (вызывающий оставляет прежний конфиг)."""
        try:
            mtime = os.path.getmtime(filepath)   # читаем ДО файла: изменение во время чтения вызовет перезагрузку
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("корень JSON должен быть объектом")
            cfg = cls()
            cfg._apply(data)
            cfg.validate()
            cfg.source_filepath = filepath
            cfg.loaded_mtime = mtime
            logger.info("🧬 КОНФИГ ЗАГРУЖЕН [%s] из '%s' | Патчей: %d | плечо %.1fx",
                        cfg.bot_version, os.path.basename(filepath),
                        len(cfg.applied_patches_log), cfg.leverage_val)
            return cfg
        except Exception as e:
            logger.error("Конфиг '%s' ОТКЛОНЁН (%s: %s)", filepath, type(e).__name__, e)
            return None

    @classmethod
    def load_from_dashboard_json(cls, filepath: Optional[str] = None) -> "BotConfig":
        """Для старта. Если файла нет/он битый — дефолты с громким предупреждением."""
        if not filepath:
            filepath = cls.find_latest_config_file()
        if not filepath or not os.path.exists(filepath):
            return cls()
        cfg = cls.try_load(filepath)
        if cfg is None:
            logger.warning("⚠️ Старт на ДЕФОЛТНОМ конфиге: файл '%s' не прошёл проверку!", filepath)
            return cls()
        return cfg


# =====================================================================
# 2. СТРУКТУРЫ
# =====================================================================

@dataclass
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class OpenPositionState:
    trade_id: str
    symbol: str
    direction: str
    strategy: str
    entry_ts: int
    entry_price: float
    stop_price: float
    tp1_price: float
    tp2_price: float
    initial_stop_dist: float
    size_usdt: float
    risk_usdt: float
    order_type: str
    tp1_hit: bool = False
    realized_tp1_gross_usdt: float = 0.0
    remaining_fraction: float = 1.0
    bars_held: int = 0
    max_favorable_px: float = 0.0
    max_adverse_px: float = 0.0
    equity_at_entry: float = 0.0

    def __post_init__(self) -> None:
        if self.max_favorable_px <= 0.0:
            self.max_favorable_px = self.entry_price
        if self.max_adverse_px <= 0.0:
            self.max_adverse_px = self.entry_price


@dataclass
class TradeRecord:
    id: str
    token: str
    direction: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    size_usdt: float
    strategy: str
    pnl_usdt: float
    gross_pnl: float
    r_multiple: float            # NET R (после издержек) от фактического риска сделки
    exchange_fees_usdt: float
    slippage_cost_usdt: float
    mae: float
    mfe: float
    exit_reason: str
    order_type: str
    bot_version: str = "v6.1"
    session: str = "eu"
    gross_r_multiple: float = 0.0
    risk_usdt: float = 0.0
    risk_pct: float = 0.0        # фактический риск в % от эквити на входе


# =====================================================================
# 3. МАТЕМАТИЧЕСКОЕ ЯДРО
# =====================================================================

class QuantStrategyCore:

    @staticmethod
    def get_utc_session(ts_ms: int) -> str:
        h = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).hour
        if h < 8:
            return "asia"
        elif h < 16:
            return "eu"
        return "us"

    @staticmethod
    def compute_atr(candles: List[Candle], period: int = 14) -> float:
        if not candles:
            return 1.0
        if len(candles) < 2:
            return max(candles[-1].high - candles[-1].low, candles[-1].close * 0.005)
        tail = candles[-(period + 1):]
        trs: List[float] = []
        for i in range(1, len(tail)):
            c, prev = tail[i], tail[i - 1]
            trs.append(max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close)))
        return sum(trs) / len(trs)

    @staticmethod
    def compute_donchian_and_volume(candles: List[Candle], period: int = 20) -> Tuple[float, float, float]:
        window = candles[-period:] if len(candles) >= period else candles
        hi = max(c.high for c in window)
        lo = min(c.low for c in window)
        avg_vol = sum(c.volume for c in window) / len(window) if window else 1.0
        return hi, lo, avg_vol

    @staticmethod
    def build_levels(direction: str, price: float, stop_dist: float, cfg: BotConfig) -> Tuple[float, float, float]:
        if direction == "long":
            return (price - stop_dist, price + stop_dist * cfg.tp1_r_multiple, price + stop_dist * cfg.tp2_r_multiple)
        return (price + stop_dist, price - stop_dist * cfg.tp1_r_multiple, price - stop_dist * cfg.tp2_r_multiple)

    @staticmethod
    def evaluate_signal(symbol: str, candles: List[Candle], cfg: BotConfig) -> Optional[Dict]:
        min_bars = max(cfg.donchian_period, cfg.atr_period) + 2
        if len(candles) < min_bars:
            return None
        if symbol in cfg.disabled_instruments or symbol not in cfg.active_trading_pool:
            return None

        curr = candles[-1]
        history = candles[:-1]
        session = QuantStrategyCore.get_utc_session(curr.ts)
        if session in cfg.blocked_sessions_utc:
            return None
        signal_dt_utc = datetime.fromtimestamp(curr.ts / 1000.0, tz=timezone.utc)
        if signal_dt_utc.weekday() in cfg.blocked_weekdays_utc:
            return None
        if signal_dt_utc.hour in cfg.blocked_signal_hours_utc:
            return None

        if curr.open > 0:
            if abs(curr.close - curr.open) / curr.open * 100.0 > cfg.max_chase_limit_pct:
                return None

        hi_ch, lo_ch, avg_vol = QuantStrategyCore.compute_donchian_and_volume(history, cfg.donchian_period)
        vol_ratio = curr.volume / avg_vol if avg_vol > 0 else 1.0
        atr = QuantStrategyCore.compute_atr(history, cfg.atr_period)
        if atr <= 0:
            return None

        direction: Optional[str] = None
        strategy_name: Optional[str] = None

        if curr.close > hi_ch and vol_ratio >= cfg.min_volume_ratio:
            direction, strategy_name = "long", "H1-momentum-breakout"
        elif curr.close < lo_ch and vol_ratio >= cfg.min_volume_ratio:
            direction, strategy_name = "short", "H1-momentum-breakout"
        elif cfg.enable_h2_range_fade and 0.75 <= vol_ratio < cfg.min_volume_ratio:
            ch_range = hi_ch - lo_ch
            if ch_range > atr * 2.2:
                if curr.low <= lo_ch + 0.15 * ch_range and curr.close > curr.open:
                    direction, strategy_name = "long", "H2-range-fade"
                elif curr.high >= hi_ch - 0.15 * ch_range and curr.close < curr.open:
                    direction, strategy_name = "short", "H2-range-fade"

        if not direction or not strategy_name or direction in cfg.blocked_directions:
            return None

        stop_dist = atr * cfg.stop_atr_mult
        stop_price, tp1_price, tp2_price = QuantStrategyCore.build_levels(direction, curr.close, stop_dist, cfg)
        return {
            "symbol": symbol, "direction": direction, "strategy": strategy_name,
            "signal_ts": curr.ts, "entry_price": curr.close,
            "stop_price": stop_price, "tp1_price": tp1_price, "tp2_price": tp2_price,
            "stop_dist": stop_dist, "atr": atr, "vol_ratio": round(vol_ratio, 2),
            "session": session,
            "order_type": "limit" if cfg.maker_entry_and_tp1 else "market",
        }


# =====================================================================
# 4. РИСК-МЕНЕДЖМЕНТ, ПЛАН Б, TELEGRAM
# =====================================================================

class AdaptiveRiskManager:
    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self.reset_for_backtest(cfg)

    def reset_for_backtest(self, cfg: BotConfig) -> None:
        self.cfg = cfg
        self.realized_equity: float = cfg.capital_usdt
        self.unrealized_pnl: float = 0.0
        self.current_equity: float = cfg.capital_usdt  # realized + mark-to-market unrealized PnL
        self.peak_equity: float = cfg.capital_usdt
        self.max_drawdown_pct: float = 0.0
        self.day_start_equity: float = cfg.capital_usdt
        self.current_day_str: str = ""
        self.is_paused_manual: bool = False
        self.daily_stop_triggered: bool = False
        self.kill_switch_triggered: bool = False

    def on_new_timestamp(self, ts_ms: int) -> None:
        dt_str = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
        if dt_str != self.current_day_str:
            self.current_day_str = dt_str
            self.day_start_equity = self.current_equity
            self.daily_stop_triggered = False

    def register_closed_trade_pnl(self, net_pnl_usdt: float, ts_ms: int) -> Dict[str, bool]:
        self.on_new_timestamp(ts_ms)
        self.realized_equity = round(self.realized_equity + net_pnl_usdt, 4)
        self.current_equity = round(self.realized_equity + self.unrealized_pnl, 4)
        return self._evaluate_drawdown_stops()

    def mark_to_market(self, unrealized_pnl_usdt: float, ts_ms: int) -> Dict[str, bool]:
        """Обновляет equity с учётом плавающего PnL и проверяет лимиты риска."""
        self.on_new_timestamp(ts_ms)
        self.unrealized_pnl = float(unrealized_pnl_usdt)
        self.current_equity = round(self.realized_equity + self.unrealized_pnl, 4)
        return self._evaluate_drawdown_stops()

    def _evaluate_drawdown_stops(self) -> Dict[str, bool]:
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity
        alerts = {"daily_stop_hit": False, "kill_switch_hit": False}
        if self.day_start_equity > 0:
            daily_dd = (self.day_start_equity - self.current_equity) / self.day_start_equity * 100.0
            if daily_dd >= self.cfg.daily_stop_loss_pct and not self.daily_stop_triggered:
                self.daily_stop_triggered = True
                alerts["daily_stop_hit"] = True
        if self.peak_equity > 0:
            total_dd = max(0.0, (self.peak_equity - self.current_equity) / self.peak_equity * 100.0)
            self.max_drawdown_pct = max(self.max_drawdown_pct, total_dd)
            if total_dd >= self.cfg.emergency_kill_switch_pct and not self.kill_switch_triggered:
                self.kill_switch_triggered = True
                alerts["kill_switch_hit"] = True
        return alerts

    def can_open_new_trade(self, open_positions_count: int) -> Tuple[bool, str]:
        if self.kill_switch_triggered:
            return False, "KILL_SWITCH_ACTIVE"
        if self.is_paused_manual:
            return False, "MANUAL_PAUSE"
        if self.daily_stop_triggered:
            return False, "DAILY_STOP_ACTIVE"
        if open_positions_count >= self.cfg.max_concurrent_positions:
            return False, "MAX_POSITIONS"
        return True, "OK"

    def calculate_position_size(
        self, entry_price: float, stop_price: float, order_type: str = "market",
        risk_budget_usdt: Optional[float] = None,
    ) -> Tuple[float, float]:
        """Размер позиции с учётом ожидаемого убытка на стопе И базовых издержек.

        Возвращаемый risk_usdt — оценка потери до стопа после комиссии входа,
        комиссии стоп-выхода и заложенного проскальзывания. Это всё ещё модель,
        а не гарантия: гэпы, funding и фактическое исполнение могут увеличить убыток.
        """
        stop_dist = abs(entry_price - stop_price)
        if entry_price <= 0 or stop_dist <= 0 or self.current_equity <= 0:
            return 0.0, 0.0

        stop_pct = stop_dist / entry_price
        is_limit_entry = order_type == "limit"
        entry_fee_rate = MAKER_FEE if is_limit_entry else TAKER_FEE
        entry_slip_rate = 0.0 if is_limit_entry else TAKER_SLIP
        # Стоп-выход моделируется как taker независимо от типа входа.
        estimated_loss_rate = stop_pct + entry_fee_rate + entry_slip_rate + TAKER_FEE + TAKER_SLIP
        if not math.isfinite(estimated_loss_rate) or estimated_loss_rate <= 0:
            return 0.0, 0.0

        per_trade_budget = self.current_equity * (self.cfg.max_risk_trade_pct / 100.0)
        if risk_budget_usdt is not None:
            if not math.isfinite(risk_budget_usdt) or risk_budget_usdt <= 0:
                return 0.0, 0.0
            per_trade_budget = min(per_trade_budget, risk_budget_usdt)
        raw_size_usdt = per_trade_budget / estimated_loss_rate
        max_notional = (self.current_equity * self.cfg.leverage_val) / max(1, self.cfg.max_concurrent_positions)
        capped_size = min(raw_size_usdt, max_notional * 0.95)
        # Round size DOWN to cents so rounding cannot exceed the risk budget.
        capped_size = math.floor(capped_size * 100.0) / 100.0
        actual_estimated_risk = capped_size * estimated_loss_rate
        return round(capped_size, 2), round(actual_estimated_risk, 4)

    def to_dict(self) -> Dict:
        return {
            "current_equity": self.current_equity, "realized_equity": self.realized_equity,
            "unrealized_pnl": self.unrealized_pnl, "peak_equity": self.peak_equity,
            "max_drawdown_pct": self.max_drawdown_pct,
            "day_start_equity": self.day_start_equity, "current_day_str": self.current_day_str,
            "is_paused_manual": self.is_paused_manual,
            "daily_stop_triggered": self.daily_stop_triggered,
            "kill_switch_triggered": self.kill_switch_triggered,
        }

    def from_dict(self, d: Dict) -> None:
        self.realized_equity = float(d.get("realized_equity", d.get("current_equity", self.realized_equity)))
        self.unrealized_pnl = float(d.get("unrealized_pnl", 0.0))
        self.current_equity = float(d.get("current_equity", self.realized_equity + self.unrealized_pnl))
        self.peak_equity = float(d.get("peak_equity", self.current_equity))
        self.max_drawdown_pct = float(d.get("max_drawdown_pct", 0.0))
        self.day_start_equity = float(d.get("day_start_equity", self.day_start_equity))
        self.current_day_str = str(d.get("current_day_str", self.current_day_str))
        self.is_paused_manual = _as_bool(d.get("is_paused_manual", False))
        self.daily_stop_triggered = _as_bool(d.get("daily_stop_triggered", False))
        self.kill_switch_triggered = _as_bool(d.get("kill_switch_triggered", False))


class PlanBStatePersistence:
    """Сохранение/восстановление состояния. enabled=False -> ничего не пишет (бэктест не трогает live-файл)."""

    def __init__(self, backup_filepath: str = "bot_state_backup.json", enabled: bool = False):
        self.backup_filepath = backup_filepath
        self.enabled = enabled

    def save_state(self, cfg: BotConfig, risk_mgr: AdaptiveRiskManager,
                   open_positions: Dict[str, "OpenPositionState"],
                   pending: Optional[Dict[str, Dict]] = None, trade_seq: int = 0) -> None:
        if not self.enabled:
            return
        payload = {
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
            "bot_version": cfg.bot_version,
            "risk": risk_mgr.to_dict(),
            "trade_seq": trade_seq,
            "pending_orders": pending or {},
            "open_positions": {sym: asdict(pos) for sym, pos in open_positions.items()},
        }
        tmp_path = self.backup_filepath + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.backup_filepath)
        except Exception as e:
            logger.error("Ошибка сохранения План Б: %s", e)

    def load_state(self, risk_mgr: AdaptiveRiskManager) -> Tuple[Dict[str, "OpenPositionState"], Dict[str, Dict], int]:
        if not os.path.exists(self.backup_filepath):
            return {}, {}, 0
        try:
            with open(self.backup_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            risk_mgr.from_dict(data.get("risk", {}))
            known = {f.name for f in dataclasses.fields(OpenPositionState)}
            restored: Dict[str, OpenPositionState] = {}
            for sym, pos_dict in data.get("open_positions", {}).items():
                restored[sym] = OpenPositionState(**{k: v for k, v in pos_dict.items() if k in known})
            pending = data.get("pending_orders", {}) or {}
            seq = int(data.get("trade_seq", 0))
            # не даём новым ID совпасть с восстановленными
            for p in restored.values():
                m = re.search(r"(\d+)$", p.trade_id)
                if m:
                    seq = max(seq, int(m.group(1)))
            if restored:
                logger.info("🛡️ План Б: восстановлено %d позиций, kill_switch=%s, daily_stop=%s",
                            len(restored), risk_mgr.kill_switch_triggered, risk_mgr.daily_stop_triggered)
            return restored, pending, seq
        except Exception as e:
            logger.error("Ошибка загрузки состояния План Б: %s", e)
            return {}, {}, 0


class CarDashboardTelegramNotifier:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    @staticmethod
    def format_daily_odometer_report(cfg: BotConfig, risk_mgr: AdaptiveRiskManager, audit: Dict) -> str:
        ret_pct = (risk_mgr.current_equity - cfg.capital_usdt) / cfg.capital_usdt * 100.0
        status_str = ("🟢 All Systems Normal (Зелёный коридор)" if audit["all_ok"]
                      else f"🟡 Требуется внимание ({audit['passed_count']}/6 целей)")
        return (
            f"📊 Ежедневный отчёт BOT-{cfg.bot_version.upper()} (00:00 UTC)\n"
            f"• Статус: {status_str}\n"
            f"• Баланс счёта: ${risk_mgr.current_equity:,.2f} ({ret_pct:+.2f}%)\n"
            f"• Сделок: {audit.get('total_trades', 0)} (WinRate: {audit.get('win_rate', 0.0):.1f}%)\n"
            f"• Профит-фактор: {audit.get('pf', 0.0):.2f} | Ожидание: {audit.get('expectancy_r', 0.0):+.2f} R\n"
            f"• Макс. просадка: {audit.get('max_dd_pct', 0.0):.1f}% (Лимит ≤ {cfg.max_dd_pct:.1f}%)"
        )

    @staticmethod
    def format_check_engine_alert(cfg: BotConfig, audit: Dict, headline: str) -> str:
        return (
            f"🟠 CHECK ENGINE ALERT [{cfg.bot_version.upper()}]: {headline}\n"
            f"• Выполнено целей План/Факт: {audit.get('passed_count', 0)}/6\n"
            f"• Главный узкий узел: {audit.get('top_bottleneck_title', '-')}\n"
            f"• Рекомендуемый патч: {audit.get('top_bottleneck_patch', 'Проверьте дашборд')}"
        )

    def send_message(self, text: str) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.info("📱 [Telegram Одометр]:\n%s", text)
            return True
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": self.chat_id, "text": text}).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error("Ошибка отправки в Telegram: %s", type(e).__name__)
            return False


# =====================================================================
# 5. АУДИТОР ПЛАН/ФАКТ
# =====================================================================

class MaintenanceGateAuditor:
    @staticmethod
    def evaluate_portfolio(trades: List[TradeRecord], cfg: BotConfig,
                           mark_to_market_max_dd_pct: Optional[float] = None) -> Dict:
        n = len(trades)
        if n == 0:
            return {
                "total_trades": 0, "net_pnl": 0.0, "ret_pct": 0.0, "win_rate": 0.0,
                "pf": 0.0, "expectancy_r": 0.0,
                "max_dd_pct": max(0.0, float(mark_to_market_max_dd_pct or 0.0)), "avg_risk_pct": 0.0,
                "cost_drag_pct": 0.0, "passed_count": 0, "all_ok": False, "checks": {},
                "top_bottleneck_title": "Нет сделок", "top_bottleneck_patch": "Ожидание сигналов"
            }

        net_pnl = sum(t.pnl_usdt for t in trades)
        gross_pnl = sum(t.gross_pnl for t in trades)
        total_costs = sum(t.exchange_fees_usdt + t.slippage_cost_usdt for t in trades)
        ret_pct = (net_pnl / cfg.capital_usdt) * 100.0

        wins = [t for t in trades if t.pnl_usdt > 0]
        losses = [t for t in trades if t.pnl_usdt <= 0]
        win_rate = len(wins) / n * 100.0
        wins_sum = sum(t.pnl_usdt for t in wins)
        loss_sum = sum(abs(t.pnl_usdt) for t in losses)
        pf = (wins_sum / loss_sum) if loss_sum > 0 else (99.9 if wins_sum > 0 else 0.0)

        # Фактический риск на сделку (% от эквити на входе)
        risks = [t.risk_pct for t in trades if t.risk_pct > 0]
        avg_risk_pct = (sum(risks) / len(risks)) if risks else 0.0

        # Ожидание: NET R каждой сделки от её собственного риска
        expectancy_r = sum(t.r_multiple for t in trades) / n

        if gross_pnl > 0:
            cost_drag_pct = total_costs / gross_pnl * 100.0
        else:
            cost_drag_pct = 100.0 if total_costs > 0 else 0.0

        eq = peak = cfg.capital_usdt
        max_dd_pct = 0.0
        for t in trades:
            eq += t.pnl_usdt
            peak = max(peak, eq)
            if peak > 0:
                max_dd_pct = max(max_dd_pct, (peak - eq) / peak * 100.0)

        if mark_to_market_max_dd_pct is not None:
            max_dd_pct = max(max_dd_pct, float(mark_to_market_max_dd_pct))

        checks = {
            "ret_ok": ret_pct >= cfg.target_ret_pct,
            "win_ok": win_rate >= cfg.target_win_rate,
            "dd_ok": max_dd_pct <= cfg.max_dd_pct,
            "risk_ok": avg_risk_pct <= cfg.max_risk_trade_pct * 1.15,
            "pf_ok": pf >= cfg.target_pf,
            "exp_ok": expectancy_r >= cfg.min_expectancy_r,
        }
        passed_count = sum(1 for v in checks.values() if v)
        all_ok = (passed_count == 6) and (expectancy_r > 0) and (net_pnl > 0)
        cost_ok = cost_drag_pct <= cfg.max_cost_drag_pct   # справочно, в 6 целей не входит

        names = {"ret_ok": "доходность", "win_ok": "Win Rate", "dd_ok": "просадка",
                 "risk_ok": "риск/сделку", "pf_ok": "профит-фактор", "exp_ok": "ожидание"}
        failed = [names[k] for k, v in checks.items() if not v]

        bn_title = "Система в Зелёном коридоре (Утечек нет)"
        bn_patch = "Не чиним то, что работает"

        if not all_ok:
            one_r = max(0.01, cfg.one_r_usdt)
            by_tok: Dict[str, float] = {}
            by_sess: Dict[str, float] = {}
            for t in trades:
                by_tok[t.token] = by_tok.get(t.token, 0.0) + t.pnl_usdt
                by_sess[t.session] = by_sess.get(t.session, 0.0) + t.pnl_usdt
            worst_tok, worst_val = min(by_tok.items(), key=lambda x: x[1])
            worst_sess, worst_sess_val = min(by_sess.items(), key=lambda x: x[1])
            total_slip = sum(t.slippage_cost_usdt for t in trades)

            if worst_val < -one_r * 1.5:
                bn_title = f"Актив {worst_tok} тянет портфель в минус (${worst_val:,.2f})"
                bn_patch = f"Отключить инструмент {worst_tok} в дашборде"
            elif worst_sess_val < -one_r * 1.5:
                bn_title = f"Сессия '{worst_sess.upper()}' приносит системный убыток (${worst_sess_val:,.2f})"
                bn_patch = f"Заблокировать входы в сессию '{worst_sess}' в дашборде"
            elif total_slip > one_r * 1.2 and not cfg.maker_entry_and_tp1:
                bn_title = f"Высокие потери на проскальзывании рыночных ордеров (-${total_slip:,.2f})"
                bn_patch = "Включить Maker-исполнение входов и TP1"
            elif not cfg.accelerated_atr_trail_after_1_5r:
                bn_title = "Поздний выход по тренду (возврат прибыли от пика MFE)"
                bn_patch = "Включить ранний подтяг ATR-трала после +1.5R"
            else:
                bn_title = "Не выполнены цели: " + ", ".join(failed) + ". Автоматических патчей не осталось"
                bn_patch = ("Пересмотреть параметры/фильтры стратегии вручную"
                            + ("; издержки выше лимита" if not cost_ok else ""))

        return {
            "total_trades": n, "net_pnl": round(net_pnl, 2), "gross_pnl": round(gross_pnl, 2),
            "total_costs": round(total_costs, 2), "ret_pct": round(ret_pct, 2),
            "win_rate": round(win_rate, 1), "pf": round(pf, 2),
            "expectancy_r": expectancy_r, "max_dd_pct": round(max_dd_pct, 2),
            "avg_risk_pct": round(avg_risk_pct, 2), "cost_drag_pct": round(cost_drag_pct, 1),
            "cost_ok": cost_ok, "checks": checks, "failed_checks": failed,
            "passed_count": passed_count, "all_ok": all_ok,
            "top_bottleneck_title": bn_title, "top_bottleneck_patch": bn_patch,
        }


# =====================================================================
# 6. ЕДИНЫЙ ДВИЖОК
# =====================================================================

class UnifiedQuantEngine:
    def __init__(
        self,
        config_path: Optional[str] = None,
        journal_output_path: str = "bybit_trade_journal_v6_1.json",
        restore_plan_b: bool = False,
        persist_state: bool = False,
        state_path: str = "bot_state_backup.json",
    ):
        self._explicit_config = config_path
        self.cfg = BotConfig.load_from_dashboard_json(config_path)
        self.risk_mgr = AdaptiveRiskManager(self.cfg)
        self.plan_b = PlanBStatePersistence(state_path, enabled=persist_state)
        self.tg = CarDashboardTelegramNotifier()
        self.journal_output_path = journal_output_path

        self.open_positions: Dict[str, OpenPositionState] = {}
        self.pending: Dict[str, Dict] = {}
        self.closed_trades: List[TradeRecord] = []
        self.trade_seq: int = 0
        self._rejected_cfg: Dict[str, float] = {}
        self._last_mark_prices: Dict[str, float] = {}
        self._intrabar_risk_marks: Dict[str, float] = {}
        self._intrabar_risk_marks_ts: Optional[int] = None
        self._state_restored = False

        if restore_plan_b:
            self.open_positions, self.pending, self.trade_seq = self.plan_b.load_state(self.risk_mgr)
            # Даже если файл содержит только risk state, это не свежий backtest.
            self._state_restored = True

    def reset_state_for_new_run(self) -> None:
        self.risk_mgr.reset_for_backtest(self.cfg)
        self.open_positions.clear()
        self.pending.clear()
        self.closed_trades.clear()
        self.trade_seq = 0
        self._last_mark_prices.clear()
        self._intrabar_risk_marks.clear()
        self._intrabar_risk_marks_ts = None
        self._state_restored = False

    @staticmethod
    def _risk_mark_for_position(pos, candle: Candle) -> float:
        """Adverse intrabar mark, using stop fill rather than later wick after stop."""
        is_long = pos.direction == "long"
        stop_crossed = candle.low <= pos.stop_price if is_long else candle.high >= pos.stop_price
        if stop_crossed:
            return min(pos.stop_price, candle.open) if is_long else max(pos.stop_price, candle.open)
        return candle.low if is_long else candle.high

    def _prepare_portfolio_intrabar_marks(self, bar_candles: Dict[str, Candle]) -> None:
        """Pre-mark all currently open symbols before evaluating portfolio risk for this bar."""
        if not bar_candles:
            return
        timeframe_ms = {
            "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
            "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
            "4h": 14_400_000, "6h": 21_600_000, "12h": 43_200_000,
            "1d": 86_400_000,
        }
        timeframe = str(self.cfg.timeframe).strip().lower()
        if timeframe not in timeframe_ms:
            raise ValueError(f"Неподдерживаемый timeframe для intrabar marks: {self.cfg.timeframe!r}")
        first_candle = next(iter(bar_candles.values()))
        bar_close_ts = first_candle.ts + timeframe_ms[timeframe]
        if any(c.ts != first_candle.ts for c in bar_candles.values()):
            raise ValueError("Нельзя агрегировать portfolio risk marks: свечи не синхронизированы")
        self._intrabar_risk_marks.clear()
        self._intrabar_risk_marks_ts = bar_close_ts
        for sym, candle in bar_candles.items():
            self._last_mark_prices[sym] = candle.close
            pos = self.open_positions.get(sym)
            if pos is not None:
                self._intrabar_risk_marks[sym] = self._risk_mark_for_position(pos, candle)

    def _unrealized_pnl_at_marks(self) -> float:
        """Оценка equity по консервативным внутрисвечным risk marks; выходные издержки — taker."""
        total = 0.0
        for sym, pos in self.open_positions.items():
            mark = self._intrabar_risk_marks.get(sym, self._last_mark_prices.get(sym, pos.entry_price))
            sign = 1.0 if pos.direction == "long" else -1.0
            remaining_gross = pos.size_usdt * pos.remaining_fraction * sign * (mark - pos.entry_price) / pos.entry_price
            # Включаем уже реализованную часть TP1 и вычитаем ориентировочные расходы сделки.
            gross = pos.realized_tp1_gross_usdt + remaining_gross
            entry_cost = pos.size_usdt * (MAKER_FEE if pos.order_type == "limit" else TAKER_FEE)
            entry_slip = 0.0 if pos.order_type == "limit" else pos.size_usdt * TAKER_SLIP
            tp1_cost = (pos.size_usdt * TP1_FRACTION * (MAKER_FEE if pos.order_type == "limit" else TAKER_FEE)) if pos.tp1_hit else 0.0
            # Предполагаем taker на выходе для консервативной оценки плавающего equity.
            exit_cost = pos.size_usdt * pos.remaining_fraction * (TAKER_FEE + TAKER_SLIP)
            total += gross - entry_cost - entry_slip - tp1_cost - exit_cost
        return total

    def _update_mark_to_market(self, ts_ms: int) -> None:
        alerts = self.risk_mgr.mark_to_market(self._unrealized_pnl_at_marks(), ts_ms)
        if alerts.get("kill_switch_hit"):
            self.tg.send_message(
                f"🚨 KILL-SWITCH [{self.cfg.bot_version}]: mark-to-market drawdown достиг лимита "
                f"-{self.cfg.emergency_kill_switch_pct}%. Новые входы заблокированы.")
        elif alerts.get("daily_stop_hit"):
            self.tg.send_message(
                f"⏸ ДНЕВНОЙ СТОП [{self.cfg.bot_version}]: mark-to-market дневная просадка достигла "
                f"-{self.cfg.daily_stop_loss_pct}%. Новые входы заблокированы до 00:00 UTC.")

    def _persist(self) -> None:
        self.plan_b.save_state(self.cfg, self.risk_mgr, self.open_positions, self.pending, self.trade_seq)

    # ---------------- Hot-reload ----------------
    def check_and_hot_reload_config(self) -> bool:
        latest = self._explicit_config or BotConfig.find_latest_config_file()
        if not latest or not os.path.exists(latest):
            return False
        try:
            mtime = os.path.getmtime(latest)
        except OSError:
            return False
        if latest == self.cfg.source_filepath and mtime <= self.cfg.loaded_mtime:
            return False
        if self._rejected_cfg.get(latest) == mtime:      # этот испорченный файл уже отклонён
            return False
        new_cfg = BotConfig.try_load(latest)
        if new_cfg is None:
            self._rejected_cfg[latest] = mtime
            logger.error("🔒 Остаётся прежний конфиг [%s]; ждём исправленный файл.", self.cfg.bot_version)
            return False
        logger.info("🔄 Hot-Reload нового конфига из дашборда: '%s'", latest)
        self.cfg = new_cfg
        self.risk_mgr.cfg = new_cfg
        return True

    # ---------------- Основной шаг ----------------
    def step_candle(self, symbol: str, candles_history: List[Candle]) -> None:
        if not candles_history:
            return
        curr = candles_history[-1]
        # Candle.ts is the bar OPEN timestamp in the Bybit OHLCV CSV format.
        # Since curr.close is only known at the end of the bar, all equity/risk
        # bookkeeping for this close must use the bar-close boundary.
        timeframe_ms = {
            "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
            "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
            "4h": 14_400_000, "6h": 21_600_000, "12h": 43_200_000,
            "1d": 86_400_000,
        }
        timeframe = str(self.cfg.timeframe).strip().lower()
        if timeframe not in timeframe_ms:
            raise ValueError(f"Неподдерживаемый timeframe для mark-to-market: {self.cfg.timeframe!r}")
        bar_close_ts = curr.ts + timeframe_ms[timeframe]
        self._last_mark_prices[symbol] = curr.close
        # Risk controls must not ignore adverse intrabar excursions that recover by close.
        # If the protective stop was crossed, use the modeled stop fill (including gap),
        # not the candle extreme: the position would have exited at the stop first.
        risk_mark = curr.close
        pos_for_risk = self.open_positions.get(symbol)
        if pos_for_risk is not None and hasattr(pos_for_risk, "direction") and hasattr(pos_for_risk, "stop_price"):
            risk_mark = self._risk_mark_for_position(pos_for_risk, curr)
        # Symbols are stepped one at a time. Preserve adverse marks for other symbols
        # processed at the same bar-close timestamp, but never carry an old candle's
        # extreme into a later bar.
        if self._intrabar_risk_marks_ts != bar_close_ts:
            self._intrabar_risk_marks.clear()
            self._intrabar_risk_marks_ts = bar_close_ts
        self._intrabar_risk_marks[symbol] = risk_mark
        self.risk_mgr.on_new_timestamp(bar_close_ts)
        self._update_mark_to_market(bar_close_ts)

        if symbol in self.open_positions:
            self._manage_position(symbol, candles_history, fill_bar=False, exit_ts=bar_close_ts)
            return

        if symbol in self.pending:
            if self._try_fill_pending(symbol, curr):
                self._manage_position(symbol, candles_history, fill_bar=True, exit_ts=bar_close_ts)
                return

        can_open, _ = self.risk_mgr.can_open_new_trade(len(self.open_positions) + len(self.pending))
        if not can_open:
            return
        sig = QuantStrategyCore.evaluate_signal(symbol, candles_history, self.cfg)
        if not sig:
            return
        self.pending[symbol] = sig        # исполнение — на СЛЕДУЮЩЕЙ свече
        self._persist()

    def _open_portfolio_risk_usdt(self) -> float:
        """Conservative sum of estimated stop risk on remaining open position sizes."""
        return sum(max(0.0, pos.risk_usdt) * max(0.0, min(1.0, pos.remaining_fraction))
                   for pos in self.open_positions.values())

    def _try_fill_pending(self, symbol: str, curr: Candle) -> bool:
        """Исполняет отложенный сигнал на свече, следующей за сигнальной. True если позиция открыта."""
        sig = self.pending.pop(symbol)
        ok, _ = self.risk_mgr.can_open_new_trade(len(self.open_positions))
        if not ok:
            self._persist()
            return False

        direction = sig["direction"]
        ref = sig["entry_price"]
        is_long = direction == "long"

        if sig["order_type"] == "limit":
            touched = curr.low <= ref if is_long else curr.high >= ref
            if not touched:
                self._persist()
                return False                       # лимитка не исполнилась — сделка пропущена
            fill = min(ref, curr.open) if is_long else max(ref, curr.open)
        else:
            if ref > 0 and abs(curr.open - ref) / ref * 100.0 > self.cfg.max_chase_limit_pct:
                self._persist()
                return False                       # гэп/погоня за ценой — отмена
            fill = curr.open

        stop_price, tp1, tp2 = QuantStrategyCore.build_levels(direction, fill, sig["stop_dist"], self.cfg)
        portfolio_risk_cap = self.risk_mgr.current_equity * (self.cfg.max_portfolio_risk_pct / 100.0)
        remaining_portfolio_risk = max(0.0, portfolio_risk_cap - self._open_portfolio_risk_usdt())
        size_usdt, risk_usdt = self.risk_mgr.calculate_position_size(
            fill, stop_price, order_type=sig["order_type"],
            risk_budget_usdt=remaining_portfolio_risk,
        )
        if size_usdt <= 0 or risk_usdt <= 0:
            self._persist()
            return False

        self.trade_seq += 1
        self.open_positions[symbol] = OpenPositionState(
            trade_id=f"T-{self.trade_seq:04d}", symbol=symbol, direction=direction,
            strategy=sig["strategy"], entry_ts=curr.ts, entry_price=fill,
            stop_price=stop_price, tp1_price=tp1, tp2_price=tp2,
            initial_stop_dist=sig["stop_dist"], size_usdt=size_usdt, risk_usdt=risk_usdt,
            order_type=sig["order_type"], max_favorable_px=fill, max_adverse_px=fill,
            equity_at_entry=self.risk_mgr.current_equity,
        )
        self._persist()
        return True

    @staticmethod
    def _apply_tp1(pos: OpenPositionState) -> None:
        tp1_move = abs(pos.tp1_price - pos.entry_price) / pos.entry_price
        pos.realized_tp1_gross_usdt = round(pos.size_usdt * TP1_FRACTION * tp1_move, 4)
        pos.remaining_fraction = 1.0 - TP1_FRACTION
        pos.tp1_hit = True

    def _manage_position(self, symbol: str, hist: List[Candle], fill_bar: bool, exit_ts: int) -> None:
        pos = self.open_positions[symbol]
        curr = hist[-1]
        cfg = self.cfg
        is_long = pos.direction == "long"
        pos.bars_held += 1
        atr = QuantStrategyCore.compute_atr(hist[:-1], cfg.atr_period)
        stop_dist = max(1e-8, pos.initial_stop_dist)

        # На свече исполнения учитываем только часть, которая заведомо после входа (консервативно):
        # благоприятный экстремум не обновляем, неблагоприятный — да.
        if is_long:
            if not fill_bar:
                pos.max_favorable_px = max(pos.max_favorable_px, curr.high)
            pos.max_adverse_px = min(pos.max_adverse_px, curr.low)
            mfe_r = (pos.max_favorable_px - pos.entry_price) / stop_dist
            mae_r = (pos.entry_price - pos.max_adverse_px) / stop_dist
        else:
            if not fill_bar:
                pos.max_favorable_px = min(pos.max_favorable_px, curr.low)
            pos.max_adverse_px = max(pos.max_adverse_px, curr.high)
            mfe_r = (pos.entry_price - pos.max_favorable_px) / stop_dist
            mae_r = (pos.max_adverse_px - pos.entry_price) / stop_dist

        exit_price: Optional[float] = None
        exit_reason: Optional[str] = None

        # 1) Стоп (приоритет над целями внутри одной свечи — консервативно)
        stop_hit = (curr.low <= pos.stop_price) if is_long else (curr.high >= pos.stop_price)
        if stop_hit:
            if fill_bar:
                exit_price = pos.stop_price
            elif is_long:
                exit_price = min(pos.stop_price, curr.open)    # гэп вниз -> худшая цена
            else:
                exit_price = max(pos.stop_price, curr.open)    # гэп вверх -> худшая цена
            exit_reason = "trailing_stop" if pos.tp1_hit else "stop_loss"

        elif not fill_bar:
            tp2_hit = (curr.high >= pos.tp2_price) if is_long else (curr.low <= pos.tp2_price)
            if tp2_hit:
                if not pos.tp1_hit:
                    self._apply_tp1(pos)          # TP1 лежит между входом и TP2 — он тоже взят
                exit_price, exit_reason = pos.tp2_price, "take_profit"
            else:
                if not pos.tp1_hit:
                    tp1_hit = (curr.high >= pos.tp1_price) if is_long else (curr.low <= pos.tp1_price)
                    if tp1_hit:
                        self._apply_tp1(pos)

                if pos.tp1_hit:
                    trail_mult = (1.15 if (cfg.accelerated_atr_trail_after_1_5r and mfe_r >= 1.5)
                                  else cfg.atr_trail_mult)
                    if is_long:
                        be_plus = pos.entry_price + stop_dist * 0.25
                        dyn_trail = pos.max_favorable_px - atr * trail_mult
                        pos.stop_price = max(pos.stop_price, be_plus, dyn_trail)
                    else:
                        be_plus = pos.entry_price - stop_dist * 0.25
                        dyn_trail = pos.max_favorable_px + atr * trail_mult
                        pos.stop_price = min(pos.stop_price, be_plus, dyn_trail)

                if pos.bars_held >= cfg.max_hold_bars:
                    exit_price, exit_reason = curr.close, "time_stop"

        if exit_price is None and self.risk_mgr.kill_switch_triggered:            exit_price, exit_reason = self._intrabar_risk_marks.get(symbol, curr.close), "kill_switch"

        if exit_price is not None and exit_reason is not None:
            self._close_position(pos, exit_price, exit_reason, exit_ts, mae_r, mfe_r)

    @staticmethod
    def _leg_cost(notional: float, maker: bool) -> Tuple[float, float]:
        return (notional * (MAKER_FEE if maker else TAKER_FEE),
                0.0 if maker else notional * TAKER_SLIP)

    def _close_position(self, pos: OpenPositionState, exit_price: float, exit_reason: str,
                        exit_ts: int, mae_r: float, mfe_r: float) -> None:
        sign = 1.0 if pos.direction == "long" else -1.0
        rem_chg = sign * (exit_price - pos.entry_price) / pos.entry_price
        rem_gross = pos.size_usdt * pos.remaining_fraction * rem_chg
        gross_pnl = _money_round(pos.realized_tp1_gross_usdt + rem_gross)

        # Издержки по ногам. Сначала суммируем точные значения всех ног,
        # затем округляем итог в денежном формате (half-up), а не каждую ногу отдельно.
        maker_mode = pos.order_type == "limit"
        fees = slip = 0.0
        f, s = self._leg_cost(pos.size_usdt, maker_mode)                      # вход
        fees += f; slip += s
        if pos.tp1_hit:                                                        # TP1-нога
            f, s = self._leg_cost(pos.size_usdt * TP1_FRACTION, maker_mode)
            fees += f; slip += s
        final_maker = maker_mode and exit_reason == "take_profit"              # финальная нога
        f, s = self._leg_cost(pos.size_usdt * pos.remaining_fraction, final_maker)
        fees += f; slip += s
        fees, slip = _money_round(fees), _money_round(slip)

        net_pnl = _money_round(gross_pnl - fees - slip)
        risk = max(1e-6, pos.risk_usdt)
        eq0 = pos.equity_at_entry if pos.equity_at_entry > 0 else self.cfg.capital_usdt

        record = TradeRecord(
            id=pos.trade_id, token=pos.symbol, direction=pos.direction,
            entry_date=datetime.fromtimestamp(pos.entry_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            exit_date=datetime.fromtimestamp(exit_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            entry_price=round(pos.entry_price, 6), exit_price=round(exit_price, 6),
            size_usdt=pos.size_usdt, strategy=pos.strategy,
            pnl_usdt=net_pnl, gross_pnl=gross_pnl,
            r_multiple=net_pnl / risk,
            exchange_fees_usdt=fees, slippage_cost_usdt=slip,
            mae=round(max(0.0, mae_r), 2), mfe=round(max(0.0, mfe_r), 2),
            exit_reason=exit_reason, order_type=pos.order_type,
            bot_version=self.cfg.bot_version,
            session=QuantStrategyCore.get_utc_session(pos.entry_ts),
            gross_r_multiple=gross_pnl / risk,
            risk_usdt=round(pos.risk_usdt, 4),
            risk_pct=round(pos.risk_usdt / eq0 * 100.0, 3),
        )
        self.closed_trades.append(record)
        del self.open_positions[pos.symbol]

        # Учитываем закрытый PnL и переоцениваем оставшиеся позиции без двойного счёта закрываемой.
        self.risk_mgr.unrealized_pnl = self._unrealized_pnl_at_marks()
        alerts = self.risk_mgr.register_closed_trade_pnl(net_pnl, exit_ts)
        if alerts.get("kill_switch_hit"):
            self.tg.send_message(
                f"🚨 KILL-SWITCH [{self.cfg.bot_version}]: просадка от пика достигла -{self.cfg.emergency_kill_switch_pct}%. "
                f"Новые входы заблокированы, открытые позиции закрываются по рынку.")
        elif alerts.get("daily_stop_hit"):
            self.tg.send_message(
                f"⏸ ДНЕВНОЙ СТОП [{self.cfg.bot_version}]: дневная просадка превысила -{self.cfg.daily_stop_loss_pct}%. "
                f"Новые входы заблокированы до 00:00 UTC (открытые позиции ведутся по плану).")
        self._persist()

    def finalize_open_positions(self, marks: Dict[str, Candle],
                                exit_reason: str = "end_of_test") -> None:
        """Закрывает оставшиеся позиции по последним доступным close для честного отчёта бэктеста.

        marks должны содержать свечи одной временной метки для всех тестируемых символов.
        Все финальные выходы считаются taker (консервативная модель издержек).
        """
        if not self.open_positions:
            return
        if not marks:
            raise ValueError("Для финализации открытых позиций нужны последние свечи (marks)")
        timestamps = {c.ts for c in marks.values()}
        if len(timestamps) != 1:
            raise ValueError("Финальные свечи для символов должны иметь одинаковый timestamp")
        timeframe_ms = {
            "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
            "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
            "4h": 14_400_000, "6h": 21_600_000, "12h": 43_200_000,
            "1d": 86_400_000,
        }
        timeframe = str(self.cfg.timeframe).strip().lower()
        if timeframe not in timeframe_ms:
            raise ValueError(f"Неподдерживаемый timeframe для финализации: {self.cfg.timeframe!r}")
        # Candle.ts is the bar-open timestamp everywhere in this engine.
        # Final journal exits and daily risk accounting must use the bar-close boundary.
        final_ts = next(iter(timestamps)) + timeframe_ms[timeframe]
        for sym, candle in marks.items():
            self._last_mark_prices[sym] = candle.close
        self.risk_mgr.mark_to_market(self._unrealized_pnl_at_marks(), final_ts)

        for pos in list(self.open_positions.values()):
            exit_px = self._last_mark_prices.get(pos.symbol, pos.entry_price)
            stop_dist = max(1e-8, pos.initial_stop_dist)
            if pos.direction == "long":
                mfe_r = max(0.0, (pos.max_favorable_px - pos.entry_price) / stop_dist)
                mae_r = max(0.0, (pos.entry_price - pos.max_adverse_px) / stop_dist)
            else:
                mfe_r = max(0.0, (pos.entry_price - pos.max_favorable_px) / stop_dist)
                mae_r = max(0.0, (pos.max_adverse_px - pos.entry_price) / stop_dist)
            self._close_position(pos, exit_px, exit_reason, final_ts, mae_r, mfe_r)

    def export_journal_for_dashboard(self) -> Dict:
        audit = MaintenanceGateAuditor.evaluate_portfolio(
            self.closed_trades, self.cfg, mark_to_market_max_dd_pct=self.risk_mgr.max_drawdown_pct)
        payload = {
            "bot_version": self.cfg.bot_version,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "summary": audit,
            "trades": [asdict(t) for t in self.closed_trades],
        }
        tmp = self.journal_output_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.journal_output_path)
        return audit


# =====================================================================
# 7. ДАННЫЕ (СИНТЕТИКА / CSV) И ЗАПУСК
# =====================================================================

def generate_synthetic_candles(symbols: List[str], bars_count: int = 1200, seed: int = 42,
                               planted_edge: bool = True) -> Dict[str, List[Candle]]:
    """
    Синтетические 15m-свечи. planted_edge=True: после импульса идёт продолжение в ту же сторону
    (стратегия получает искусственный "эдж" — результат ничего не доказывает).
    planted_edge=False: направление продолжения случайно -> честный тест "нет эджа".
    """
    base_prices = {"SOLUSDT": 152.0, "BTCUSDT": 68500.0, "ETHUSDT": 3420.0, "AVAXUSDT": 37.5, "DOGEUSDT": 0.145}
    start_ts = int(datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    step_ms = 15 * 60 * 1000
    market_data: Dict[str, List[Candle]] = {}

    for sym_idx, sym in enumerate(symbols):
        s = seed + sym_idx * 97
        px = base_prices.get(sym, 100.0)
        candles: List[Candle] = []
        trend_dir = 1.0
        trend_bars_left = 0

        for i in range(bars_count):
            ts = start_ts + i * step_ms
            s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
            r = (s / 0xFFFFFFFF) - 0.5
            vol = 1000.0 + (s % 450)
            session = QuantStrategyCore.get_utc_session(ts)

            if trend_bars_left > 0:
                trend_bars_left -= 1
                step_move = trend_dir * 0.0085 + r * 0.002
                close_px = px * (1.0 + step_move)
                high_px = max(px, close_px) * (1.003 if trend_dir > 0 else 1.001)
                low_px = min(px, close_px) * (0.999 if trend_dir > 0 else 0.997)
            elif i > 30 and (i + sym_idx * 7) % 26 == 0:
                vol *= 2.35
                is_good_setup = (sym != "DOGEUSDT") and (session != "asia" or (i % 3 == 0))
                if is_good_setup:
                    impulse_dir = 1.0 if (i % 2 == 0) else -1.0
                    close_px = px * (1.0 + impulse_dir * 0.011)
                    trend_dir = impulse_dir if planted_edge else (1.0 if ((s >> 16) & 1) else -1.0)
                    trend_bars_left = 5
                else:
                    trend_dir = -1.0 if (i % 2 == 0) else 1.0
                    trend_bars_left = 3
                    close_px = px * (1.0 - trend_dir * 0.010)
                high_px = max(px, close_px) * 1.002
                low_px = min(px, close_px) * 0.998
            else:
                close_px = px * (1.0 + r * 0.004)
                high_px = max(px, close_px) * 1.0015
                low_px = min(px, close_px) * 0.9985

            candles.append(Candle(ts=ts, open=px, high=high_px, low=low_px, close=close_px, volume=vol))
            px = close_px
        market_data[sym] = candles
    return market_data


def load_candles_csv(data_dir: str, symbols: List[str]) -> Dict[str, List[Candle]]:
    """CSV <SYMBOL>.csv: ts(мс), open, high, low, close, volume. Ошибочные данные отклоняются."""
    out: Dict[str, List[Candle]] = {}
    required = {"ts", "open", "high", "low", "close", "volume"}
    for sym in symbols:
        path = os.path.join(data_dir, f"{sym}.csv")
        if not os.path.isfile(path):
            logger.warning("Нет файла данных %s — символ пропущен", path)
            continue
        rows: List[Candle] = []
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError(f"{path}: обязательные колонки CSV: {sorted(required)}")
            for line_no, r in enumerate(reader, start=2):
                try:
                    vals = [float(r[k]) for k in ("ts", "open", "high", "low", "close", "volume")]
                    if not all(math.isfinite(v) for v in vals):
                        raise ValueError("NaN/Inf")
                    ts_f, op, hi, lo, cl, vol = vals
                    if ts_f <= 0 or not ts_f.is_integer():
                        raise ValueError("ts должен быть положительным целым числом миллисекунд")
                    if min(op, hi, lo, cl) <= 0:
                        raise ValueError("цены должны быть > 0")
                    if vol < 0:
                        raise ValueError("volume не может быть отрицательным")
                    if hi < max(op, cl, lo) or lo > min(op, cl, hi):
                        raise ValueError("некорректные границы OHLC")
                    rows.append(Candle(int(ts_f), op, hi, lo, cl, vol))
                except (KeyError, TypeError, ValueError, OverflowError) as exc:
                    raise ValueError(f"{path}:{line_no}: некорректная свеча: {exc}") from exc
        rows.sort(key=lambda c: c.ts)
        timestamps = [c.ts for c in rows]
        if len(set(timestamps)) != len(timestamps):
            raise ValueError(f"{path}: обнаружены повторяющиеся timestamps")
        if len(rows) < 2:
            raise ValueError(f"{path}: нужно минимум 2 свечи")
        deltas = [b.ts - a.ts for a, b in zip(rows, rows[1:])]
        if any(d <= 0 for d in deltas):
            raise ValueError(f"{path}: timestamps должны строго возрастать")
        if len(set(deltas)) > 1:
            raise ValueError(f"{path}: пропуски/неравномерные интервалы свечей: {sorted(set(deltas))[:8]}")
        out[sym] = rows
    return out


def check_alignment(candles: Dict[str, List[Candle]]) -> None:
    if not candles:
        raise ValueError("Нет свечных данных для проверки")
    ref_sym = next(iter(candles))
    ref_ts = [c.ts for c in candles[ref_sym]]
    for sym, arr in candles.items():
        if not arr:
            raise ValueError(f"Нет свечей для {sym}")
        ts = [c.ts for c in arr]
        if len(set(ts)) != len(ts):
            raise ValueError(f"Свечи {sym}: повторяющиеся timestamps")
        if ts != ref_ts:
            raise ValueError(f"Свечи {sym} не синхронизированы с {ref_sym} (разные ts/длина)")


def run_simulation_pass(engine: UnifiedQuantEngine, candles: Dict[str, List[Candle]],
                        symbols: List[str], data_label: str = "СИНТЕТИКА") -> Dict:
    # Это именно новый независимый бэктест, не восстановление live-сессии.
    if engine._state_restored:
        raise RuntimeError("Нельзя запускать backtest поверх восстановленного состояния. "
                           "Для live-resume нужен отдельный цикл с reconciliation по бирже.")
    engine.reset_state_for_new_run()
    bars_total = len(candles[symbols[0]])
    for bar in range(25, bars_total):
        lo = max(0, bar + 1 - CALC_WINDOW)
        # Evaluate portfolio drawdown against all symbols' adverse marks for this
        # synchronized bar before any single symbol can trigger a risk decision.
        engine._prepare_portfolio_intrabar_marks({sym: candles[sym][bar] for sym in symbols})
        for sym in symbols:
            engine.step_candle(sym, candles[sym][lo:bar + 1])

    # Не оставляем открытые позиции вне статистики: закрываем их по последнему close.
    engine.finalize_open_positions({sym: candles[sym][-1] for sym in symbols}, exit_reason="end_of_test")
    audit = engine.export_journal_for_dashboard()
    logger.info(
        "🎯 ПРОГОН [%s | данные: %s] | Сделок: %d | Итог: $%+.2f (%+.1f%%) | PF: %.2f | E: %+.2fR | DD: %.1f%% | Целей: %d/6",
        engine.cfg.bot_version, data_label, audit["total_trades"], audit["net_pnl"], audit["ret_pct"],
        audit["pf"], audit["expectancy_r"], audit["max_dd_pct"], audit["passed_count"]
    )
    prefix = f"🧪 [БЭКТЕСТ, данные: {data_label}]\n"
    if audit["all_ok"]:
        engine.tg.send_message(prefix + CarDashboardTelegramNotifier.format_daily_odometer_report(
            engine.cfg, engine.risk_mgr, audit))
    else:
        engine.tg.send_message(prefix + CarDashboardTelegramNotifier.format_check_engine_alert(
            engine.cfg, audit, "Отклонение от целевых показателей План/Факт"))
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Bybit Quant Engine v14.0 (симулятор + мост с дашбордом)")
    parser.add_argument("--mode", choices=["backtest", "watch"], default="backtest")
    parser.add_argument("--config", type=str, default=None, help="Путь к bot_live_config_*.json")
    parser.add_argument("--journal", type=str, default="bybit_trade_journal_v6_1.json")
    parser.add_argument("--data-dir", type=str, default=None, help="Папка с <SYMBOL>.csv (ts,open,high,low,close,volume)")
    parser.add_argument("--bars", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-planted-edge", action="store_true", help="Синтетика без заложенного эджа")
    parser.add_argument("--persist-state", action="store_true", help="Писать план Б (для live-цикла; бэктесту не нужно)")
    parser.add_argument("--state-path", type=str, default="bot_state_backup.json")
    args = parser.parse_args()

    engine = UnifiedQuantEngine(config_path=args.config, journal_output_path=args.journal,
                                persist_state=args.persist_state, state_path=args.state_path)
    pool = list(dict.fromkeys(engine.cfg.active_trading_pool))

    if args.data_dir:
        candles = load_candles_csv(args.data_dir, pool)
        label = "РЕАЛЬНЫЕ CSV"
    else:
        candles = generate_synthetic_candles(pool, bars_count=args.bars, seed=args.seed,
                                             planted_edge=not args.no_planted_edge)
        label = "СИНТЕТИКА" + (" (без эджа)" if args.no_planted_edge else " (с заложенным эджем)")
        logger.warning("⚠️ Данные синтетические: статистика не доказывает прибыльность стратегии.")
    if not candles:
        raise SystemExit("Нет данных для прогона")
    check_alignment(candles)
    symbols = list(candles.keys())

    run_simulation_pass(engine, candles, symbols, label)

    if args.mode == "watch":
        logger.info("👀 WATCH: ожидание новых bot_live_config*.json (Ctrl+C для выхода)...")
        try:
            while True:
                time.sleep(2.0)
                if engine.check_and_hot_reload_config():
                    run_simulation_pass(engine, candles, symbols, label)
        except KeyboardInterrupt:
            logger.info("Остановка режима WATCH пользователем.")


if __name__ == "__main__":
    main()