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
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_FLOOR
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Any, Callable

from funding_accounting import accrued_funding_cost, accrued_funding_cost_for_remaining_margin
from mark_price_liquidation import evaluate_isolated_margin_health, calculate_isolated_usdt_bankruptcy_price
from instrument_spec_history import InstrumentSpecHistory
from bybit_risk_tiers import RiskTierHistory, calculate_margin_requirements_from_tiers
from bybit_market_state import get_linear_market_state
from exchange_order_sizing import size_to_exchange_constraints

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

POST_BREAK_INVALIDATION_BARS = 3  # frozen H-C horizon; not a tunable config parameter


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
    # None preserves legacy coupling to maker_entry_and_tp1; explicit False isolates maker entry.
    maker_tp1_and_target: Optional[bool] = None
    accelerated_atr_trail_after_1_5r: bool = False
    enable_h2_range_fade: bool = False
    enable_post_break_invalidation: bool = False

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
        if self.enable_post_break_invalidation and str(self.timeframe).strip().lower() != "1h":
            errs.append("enable_post_break_invalidation поддерживается только на H1")
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

        allowed_execution = {"maker_entry_and_tp1", "maker_tp1_and_target", "accelerated_atr_trail_after_1_5r", "enable_post_break_invalidation"}
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
        self.maker_tp1_and_target = (_as_bool(ex.get("maker_tp1_and_target", False)) if "maker_tp1_and_target" in ex else None)
        self.accelerated_atr_trail_after_1_5r = _as_bool(ex.get("accelerated_atr_trail_after_1_5r", False))
        self.enable_post_break_invalidation = _as_bool(ex.get("enable_post_break_invalidation", False))

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


@dataclass(frozen=True)
class MarkPriceCandle:
    ts: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


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
    maker_exits: Optional[bool] = None
    breakout_level: Optional[float] = None  # signal-time Donchian boundary
    signal_ts_ms: Optional[int] = None  # original signal close; may precede delayed limit fill
    tp1_hit: bool = False
    tp1_ts_ms: Optional[int] = None  # conservative TP1 candle-close boundary
    realized_tp1_gross_usdt: float = 0.0
    remaining_fraction: float = 1.0
    bars_held: int = 0
    max_favorable_px: float = 0.0
    max_adverse_px: float = 0.0
    equity_at_entry: float = 0.0
    leverage: Optional[float] = None
    risk_tier_id: Optional[int] = None
    risk_limit_value: Optional[str] = None
    maintenance_margin_rate: Optional[str] = None
    maintenance_margin_deduction: Optional[str] = None
    risk_tier_max_leverage: Optional[str] = None
    initial_margin_usdt: Optional[str] = None
    maintenance_margin_usdt: Optional[str] = None
    contract_qty: Optional[str] = None
    tp1_contract_qty: Optional[str] = None
    remaining_contract_qty: Optional[str] = None
    qty_step: Optional[str] = None
    min_order_qty: Optional[str] = None
    min_notional_value: Optional[str] = None
    exchange_sized: bool = False
    # Appended to preserve the positional constructor order of older position fields.
    tp1_maker: Optional[bool] = None

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
    signal_ts_ms: Optional[int] = None  # original signal close timestamp, not delayed fill guard
    session: str = "eu"
    gross_r_multiple: float = 0.0
    risk_usdt: float = 0.0
    risk_pct: float = 0.0        # фактический риск в % от эквити на входе
    funding_cost_usdt: float = 0.0  # positive=paid, negative=received
    # Execution provenance retained after the position leaves OpenPositionState.
    exchange_sized: bool = False
    contract_qty: Optional[str] = None
    tp1_contract_qty: Optional[str] = None
    final_contract_qty: Optional[str] = None
    qty_step: Optional[str] = None
    leverage: Optional[float] = None
    risk_tier_id: Optional[int] = None
    risk_limit_value: Optional[str] = None
    maintenance_margin_rate: Optional[str] = None
    maintenance_margin_deduction: Optional[str] = None
    initial_margin_usdt: Optional[str] = None
    maintenance_margin_usdt: Optional[str] = None
    # TP1/remaining-leg provenance for exact partial-exit attribution.
    initial_stop_dist: float = 0.0
    initial_stop_price: Optional[float] = None
    tp1_price: Optional[float] = None
    tp2_price: Optional[float] = None
    tp1_hit: bool = False
    tp1_ts_ms: Optional[int] = None
    realized_tp1_gross_usdt: float = 0.0
    remaining_fraction_at_exit: float = 1.0
    final_stop_price: Optional[float] = None
    breakout_level: Optional[float] = None
    tp1_maker: Optional[bool] = None
    final_exit_maker: Optional[bool] = None


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
    def compute_donchian_and_volume(
        candles: List[Candle], period: int = 20,
        volume_period: Optional[int] = None,
    ) -> Tuple[float, float, float]:
        """Compute channel extrema and volume baseline on independently frozen windows.

        When volume_period is omitted, preserve the legacy behavior where both
        calculations use the Donchian period.
        """
        if period < 1:
            raise ValueError("Donchian period must be positive")
        volume_period = period if volume_period is None else int(volume_period)
        if volume_period < 1:
            raise ValueError("volume lookback period must be positive")
        channel_window = candles[-period:] if len(candles) >= period else candles
        volume_window = candles[-volume_period:] if len(candles) >= volume_period else candles
        hi = max(c.high for c in channel_window)
        lo = min(c.low for c in channel_window)
        avg_vol = sum(c.volume for c in volume_window) / len(volume_window) if volume_window else 1.0
        return hi, lo, avg_vol

    @staticmethod
    def build_levels(direction: str, price: float, stop_dist: float, cfg: BotConfig) -> Tuple[float, float, float]:
        if direction == "long":
            return (price - stop_dist, price + stop_dist * cfg.tp1_r_multiple, price + stop_dist * cfg.tp2_r_multiple)
        return (price + stop_dist, price - stop_dist * cfg.tp1_r_multiple, price - stop_dist * cfg.tp2_r_multiple)

    @staticmethod
    def evaluate_signal(symbol: str, candles: List[Candle], cfg: BotConfig) -> Optional[Dict]:
        volume_period = int(getattr(cfg, "volume_lookback_period", cfg.donchian_period))
        min_bars = max(cfg.donchian_period, volume_period, cfg.atr_period) + 2
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

        hi_ch, lo_ch, avg_vol = QuantStrategyCore.compute_donchian_and_volume(
            history, cfg.donchian_period, volume_period=volume_period,
        )
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
            "breakout_level": hi_ch if direction == "long" else lo_ch,
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
        # On the first-ever mark, initialize the day from starting/restored
        # equity so losses on that first mark are not silently ignored.
        if not self.current_day_str:
            self.on_new_timestamp(ts_ms)
        # Refresh the mark before rolling an existing day at 00:00 UTC: the
        # new day's baseline must include the mark at that exact boundary,
        # not the previous bar's stale equity.
        self.unrealized_pnl = float(unrealized_pnl_usdt)
        self.current_equity = round(self.realized_equity + self.unrealized_pnl, 4)
        self.on_new_timestamp(ts_ms)
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
        equity_override: Optional[float] = None,
    ) -> Tuple[float, float]:
        """Размер позиции с учётом ожидаемого убытка на стопе И базовых издержек.

        Возвращаемый risk_usdt — оценка потери до стопа после комиссии входа,
        комиссии стоп-выхода и заложенного проскальзывания. Это всё ещё модель,
        а не гарантия: гэпы, funding и фактическое исполнение могут увеличить убыток.
        """
        stop_dist = abs(entry_price - stop_price)
        sizing_equity = self.current_equity if equity_override is None else equity_override
        if (entry_price <= 0 or stop_price <= 0 or stop_dist <= 0
                or not math.isfinite(sizing_equity) or sizing_equity <= 0):
            return 0.0, 0.0

        stop_pct = stop_dist / entry_price
        is_limit_entry = order_type == "limit"
        entry_fee_rate = MAKER_FEE if is_limit_entry else TAKER_FEE
        entry_slip_rate = 0.0 if is_limit_entry else TAKER_SLIP
        # Стоп-выход моделируется как taker независимо от типа входа.
        # Exit fees/slippage are charged on executed exit notional (qty * stop price),
        # not on the original entry notional. qty = entry notional / entry price.
        exit_notional_ratio = stop_price / entry_price
        estimated_loss_rate = (
            stop_pct + entry_fee_rate + entry_slip_rate
            + exit_notional_ratio * (TAKER_FEE + TAKER_SLIP)
        )
        if not math.isfinite(estimated_loss_rate) or estimated_loss_rate <= 0:
            return 0.0, 0.0

        per_trade_budget = sizing_equity * (self.cfg.max_risk_trade_pct / 100.0)
        if risk_budget_usdt is not None:
            if not math.isfinite(risk_budget_usdt) or risk_budget_usdt <= 0:
                return 0.0, 0.0
            per_trade_budget = min(per_trade_budget, risk_budget_usdt)
        raw_size_usdt = per_trade_budget / estimated_loss_rate
        max_notional = (sizing_equity * self.cfg.leverage_val) / max(1, self.cfg.max_concurrent_positions)
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
        self.last_mark_prices: Dict[str, float] = {}

    def save_state(self, cfg: BotConfig, risk_mgr: AdaptiveRiskManager,
                   open_positions: Dict[str, "OpenPositionState"],
                   pending: Optional[Dict[str, Dict]] = None, trade_seq: int = 0,
                   last_mark_prices: Optional[Dict[str, float]] = None) -> None:
        if not self.enabled:
            return
        supplied_marks = last_mark_prices or {}
        missing_marks = set(open_positions).difference(supplied_marks)
        if missing_marks:
            raise RuntimeError(
                f"Не удалось сохранить резервное состояние: отсутствуют last marks для {sorted(missing_marks)}"
            )
        validated_marks: Dict[str, float] = {}
        for symbol in open_positions:
            value = supplied_marks[symbol]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise RuntimeError(
                    f"Не удалось сохранить резервное состояние: last mark {symbol} должен быть конечным числом > 0"
                )
            validated_marks[symbol] = float(value)
        saved_at = datetime.now(timezone.utc)
        saved_at_ms = int(saved_at.timestamp() * 1000)
        for symbol, position in open_positions.items():
            entry_ts = position.entry_ts
            if (isinstance(entry_ts, bool) or not isinstance(entry_ts, int)
                    or entry_ts <= 0 or entry_ts > saved_at_ms):
                raise ValueError(
                    f"позиция {symbol}: entry_ts должен быть положительным целым числом "
                    "не позже saved_at_utc"
                )
            signal_ts_ms = position.signal_ts_ms
            if signal_ts_ms is not None:
                if (isinstance(signal_ts_ms, bool) or not isinstance(signal_ts_ms, int)
                        or signal_ts_ms <= 0 or signal_ts_ms > entry_ts):
                    raise ValueError(
                        f"позиция {symbol}: signal_ts_ms должен быть положительным целым числом "
                        "не позже entry_ts"
                    )
            tp1_ts_ms = position.tp1_ts_ms
            if tp1_ts_ms is not None:
                if (isinstance(tp1_ts_ms, bool) or not isinstance(tp1_ts_ms, int)
                        or tp1_ts_ms < entry_ts or tp1_ts_ms > saved_at_ms):
                    raise ValueError(
                        f"позиция {symbol}: tp1_ts_ms должен быть целым timestamp "
                        "между entry_ts и saved_at_utc"
                    )
            if position.tp1_hit and tp1_ts_ms is None:
                raise ValueError(f"позиция {symbol}: tp1_hit требует tp1_ts_ms")
            if not position.tp1_hit and tp1_ts_ms is not None:
                raise ValueError(f"позиция {symbol}: tp1_ts_ms задан при tp1_hit=false")
        payload = {
            "saved_at_utc": saved_at.isoformat(),
            "bot_version": cfg.bot_version,
            "risk": risk_mgr.to_dict(),
            "trade_seq": trade_seq,
            "pending_orders": pending or {},
            "open_positions": {sym: asdict(pos) for sym, pos in open_positions.items()},
            "last_mark_prices": validated_marks,
        }
        tmp_path = self.backup_filepath + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False, allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                logger.exception("Не удалось удалить временный файл состояния %s", tmp_path)
            logger.critical("Критическая ошибка сохранения состояния План Б: %s", e)
            raise RuntimeError(
                f"Не удалось сохранить резервное состояние в {self.backup_filepath!r}"
            ) from e

        # Validate the exact serialized candidate with the same strict reader
        # before replacing the last known-good recovery point.
        try:
            PlanBStatePersistence(tmp_path, enabled=True).load_state(
                AdaptiveRiskManager(cfg), log_restore=False,
            )
        except RuntimeError as e:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                logger.exception("Не удалось удалить невалидный временный backup %s", tmp_path)
            raise ValueError(
                "Сериализованный backup не проходит строгую проверку восстановления"
            ) from e

        try:
            os.replace(tmp_path, self.backup_filepath)
            if os.name == "posix":
                parent_dir = os.path.dirname(os.path.abspath(self.backup_filepath)) or "."
                dir_fd = os.open(parent_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        except Exception as e:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                logger.exception("Не удалось удалить временный файл состояния %s", tmp_path)
            logger.critical("Критическая ошибка сохранения состояния План Б: %s", e)
            raise RuntimeError(
                f"Не удалось сохранить резервное состояние в {self.backup_filepath!r}"
            ) from e

    def load_state(
        self, risk_mgr: AdaptiveRiskManager, *, log_restore: bool = True,
    ) -> Tuple[Dict[str, "OpenPositionState"], Dict[str, Dict], int]:
        if not os.path.exists(self.backup_filepath):
            return {}, {}, 0
        try:
            with open(self.backup_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("корень backup должен быть JSON-объектом")
            required_envelope = {
                "saved_at_utc", "bot_version", "risk", "open_positions",
                "pending_orders", "trade_seq",
            }
            missing_envelope = required_envelope.difference(data)
            if missing_envelope:
                raise ValueError(f"backup неполный: отсутствуют поля {sorted(missing_envelope)}")
            saved_at = data["saved_at_utc"]
            if not isinstance(saved_at, str) or not saved_at:
                raise ValueError("saved_at_utc должен быть непустой ISO-8601 строкой")
            try:
                parsed_saved_at = datetime.fromisoformat(saved_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("saved_at_utc должен быть корректной ISO-8601 датой") from exc
            if parsed_saved_at.tzinfo is None or parsed_saved_at.utcoffset() is None:
                raise ValueError("saved_at_utc должен содержать явный UTC offset")
            if parsed_saved_at.utcoffset().total_seconds() != 0:
                raise ValueError("saved_at_utc должен быть указан в UTC")
            saved_at_ms = int(parsed_saved_at.timestamp() * 1000)
            if not isinstance(data["bot_version"], str) or not data["bot_version"].strip():
                raise ValueError("bot_version должен быть непустой строкой")
            risk_data = data["risk"]
            positions_data = data["open_positions"]
            pending = data["pending_orders"]
            raw_seq = data["trade_seq"]
            raw_marks = data.get("last_mark_prices", {})
            if not isinstance(raw_marks, dict):
                raise ValueError("last_mark_prices должен быть JSON-объектом")
            if not isinstance(risk_data, dict):
                raise ValueError("risk state должен быть JSON-объектом")
            known_risk = {
                "current_equity", "realized_equity", "unrealized_pnl", "peak_equity",
                "max_drawdown_pct", "day_start_equity", "current_day_str",
                "is_paused_manual", "daily_stop_triggered", "kill_switch_triggered",
            }
            missing_risk = known_risk.difference(risk_data)
            if missing_risk:
                raise ValueError(f"risk state неполный: отсутствуют поля {sorted(missing_risk)}")
            unknown_risk = set(risk_data).difference(known_risk)
            if unknown_risk:
                raise ValueError(f"risk state содержит неизвестные поля {sorted(unknown_risk)}")
            positive_risk_fields = {
                "current_equity", "realized_equity", "peak_equity", "day_start_equity",
            }
            numeric_risk_fields = positive_risk_fields | {"unrealized_pnl", "max_drawdown_pct"}
            for field_name in numeric_risk_fields.intersection(risk_data):
                value = risk_data[field_name]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"risk.{field_name} должен быть конечным числом")
                if field_name in positive_risk_fields and value <= 0:
                    raise ValueError(f"risk.{field_name} должен быть > 0")
            if "max_drawdown_pct" in risk_data and not 0 <= risk_data["max_drawdown_pct"] <= 100:
                raise ValueError("risk.max_drawdown_pct должен быть в [0, 100]")
            expected_equity = round(risk_data["realized_equity"] + risk_data["unrealized_pnl"], 4)
            if not math.isclose(risk_data["current_equity"], expected_equity, rel_tol=0.0, abs_tol=1e-4):
                raise ValueError("risk.current_equity не совпадает с realized_equity + unrealized_pnl")
            if risk_data["peak_equity"] + 1e-9 < risk_data["current_equity"]:
                raise ValueError("risk.peak_equity не может быть ниже current_equity")
            implied_drawdown = max(
                0.0,
                (risk_data["peak_equity"] - risk_data["current_equity"])
                / risk_data["peak_equity"] * 100.0,
            )
            if risk_data["max_drawdown_pct"] + 1e-6 < implied_drawdown:
                raise ValueError("risk.max_drawdown_pct меньше просадки, следующей из peak/current equity")
            if (max(risk_data["max_drawdown_pct"], implied_drawdown)
                    >= risk_mgr.cfg.emergency_kill_switch_pct
                    and not risk_data["kill_switch_triggered"]):
                raise ValueError(
                    "risk.kill_switch_triggered=false при просадке, достигшей emergency порога"
                )
            if "current_day_str" in risk_data:
                day_value = risk_data["current_day_str"]
                if not isinstance(day_value, str):
                    raise ValueError("risk.current_day_str должен быть строкой")
                if day_value:
                    try:
                        parsed_day = datetime.strptime(day_value, "%Y-%m-%d")
                    except ValueError as exc:
                        raise ValueError("risk.current_day_str должен быть пустым или YYYY-MM-DD") from exc
                    if parsed_day.strftime("%Y-%m-%d") != day_value:
                        raise ValueError("risk.current_day_str должен быть пустым или YYYY-MM-DD")
                    daily_drawdown = (
                        (risk_data["day_start_equity"] - risk_data["current_equity"])
                        / risk_data["day_start_equity"] * 100.0
                    )
                    if (daily_drawdown >= risk_mgr.cfg.daily_stop_loss_pct
                            and not risk_data["daily_stop_triggered"]):
                        raise ValueError(
                            "risk.daily_stop_triggered=false при дневной просадке, "
                            "достигшей daily stop порога"
                        )
            for field_name in ("is_paused_manual", "daily_stop_triggered", "kill_switch_triggered"):
                if field_name in risk_data and not isinstance(risk_data[field_name], bool):
                    raise ValueError(f"risk.{field_name} должен быть bool")
            if not isinstance(positions_data, dict):
                raise ValueError("open_positions должен быть JSON-объектом")
            if not isinstance(pending, dict):
                raise ValueError("pending_orders должен быть JSON-объектом")
            if isinstance(raw_seq, bool) or not isinstance(raw_seq, int) or raw_seq < 0:
                raise ValueError("trade_seq должен быть неотрицательным целым числом")

            # Stage every component before mutating the caller's risk manager.
            candidate_risk = AdaptiveRiskManager(risk_mgr.cfg)
            candidate_risk.from_dict(risk_data)
            known = {field.name for field in dataclasses.fields(OpenPositionState)}
            required_position = {
                "trade_id", "symbol", "direction", "strategy", "entry_ts",
                "entry_price", "stop_price", "tp1_price", "tp2_price",
                "initial_stop_dist", "size_usdt", "risk_usdt", "order_type",
            }
            numeric_position_fields = {
                "entry_price", "stop_price", "tp1_price", "tp2_price",
                "initial_stop_dist", "size_usdt", "risk_usdt",
                "realized_tp1_gross_usdt", "remaining_fraction",
                "max_favorable_px", "max_adverse_px", "equity_at_entry", "leverage",
            }
            positive_position_fields = {
                "entry_price", "stop_price", "tp1_price", "tp2_price",
                "initial_stop_dist", "size_usdt", "risk_usdt", "leverage",
            }
            restored: Dict[str, OpenPositionState] = {}
            for sym, pos_dict in positions_data.items():
                if not isinstance(sym, str) or not sym or not isinstance(pos_dict, dict):
                    raise ValueError("каждая open_position должна быть объектом с непустым symbol key")
                unknown = set(pos_dict).difference(known)
                if unknown:
                    raise ValueError(f"позиция {sym}: неизвестные поля backup {sorted(unknown)}")
                missing = required_position.difference(pos_dict)
                if missing:
                    raise ValueError(f"позиция {sym}: отсутствуют поля {sorted(missing)}")
                if not all(isinstance(pos_dict[field], str) and pos_dict[field] for field in ("trade_id", "symbol", "strategy")):
                    raise ValueError(f"позиция {sym}: trade_id, symbol и strategy должны быть непустыми строками")
                if pos_dict["direction"] not in {"long", "short"}:
                    raise ValueError(f"позиция {sym}: direction должен быть long/short")
                if pos_dict["order_type"] not in {"market", "limit"}:
                    raise ValueError(f"позиция {sym}: order_type должен быть market/limit")
                if pos_dict.get("breakout_level") is not None:
                    value = pos_dict["breakout_level"]
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                        raise ValueError(f"позиция {sym}: breakout_level должен быть конечным числом > 0 или None")
                entry_ts = pos_dict["entry_ts"]
                if isinstance(entry_ts, bool) or not isinstance(entry_ts, int) or entry_ts <= 0:
                    raise ValueError(f"позиция {sym}: entry_ts должен быть положительным целым числом")
                if entry_ts > saved_at_ms:
                    raise ValueError(f"позиция {sym}: entry_ts не может быть позже saved_at_utc")
                signal_ts_ms = pos_dict.get("signal_ts_ms")
                if signal_ts_ms is not None:
                    if (isinstance(signal_ts_ms, bool) or not isinstance(signal_ts_ms, int)
                            or signal_ts_ms <= 0 or signal_ts_ms > entry_ts):
                        raise ValueError(
                            f"позиция {sym}: signal_ts_ms должен быть положительным целым числом "
                            "не позже entry_ts"
                        )
                for field_name in numeric_position_fields.intersection(pos_dict):
                    value = pos_dict[field_name]
                    # Leverage was added after legacy Plan B backups already existed.
                    # Preserve those positions; liquidation-aware paths separately fail closed without it.
                    if field_name == "leverage" and value is None:
                        continue
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        raise ValueError(f"позиция {sym}: {field_name} должен быть конечным числом")
                    if field_name in positive_position_fields and value <= 0:
                        raise ValueError(f"позиция {sym}: {field_name} должен быть > 0")
                if pos_dict.get("realized_tp1_gross_usdt", 0.0) < 0:
                    raise ValueError(f"позиция {sym}: realized_tp1_gross_usdt не может быть отрицательным")
                fraction = pos_dict.get("remaining_fraction", 1.0)
                if fraction < 0 or fraction > 1:
                    raise ValueError(f"позиция {sym}: remaining_fraction должен быть в [0, 1]")
                entry = pos_dict["entry_price"]
                tp1 = pos_dict["tp1_price"]
                tp2 = pos_dict["tp2_price"]
                if pos_dict["direction"] == "long" and not entry < tp1 < tp2:
                    raise ValueError(f"позиция {sym}: long targets должны удовлетворять entry < TP1 < TP2")
                if pos_dict["direction"] == "short" and not entry > tp1 > tp2:
                    raise ValueError(f"позиция {sym}: short targets должны удовлетворять entry > TP1 > TP2")
                tp1_hit = pos_dict.get("tp1_hit", False)
                realized_tp1 = pos_dict.get("realized_tp1_gross_usdt", 0.0)
                if not tp1_hit and not math.isclose(realized_tp1, 0.0, rel_tol=0.0, abs_tol=1e-9):
                    raise ValueError(f"позиция {sym}: realized TP1 PnL задан при tp1_hit=false")
                for field_name in ("max_favorable_px", "max_adverse_px"):
                    if field_name in pos_dict and pos_dict[field_name] <= 0:
                        raise ValueError(f"позиция {sym}: {field_name} должен быть > 0")
                if pos_dict.get("direction") == "long":
                    if ("max_favorable_px" in pos_dict
                            and pos_dict["max_favorable_px"] < entry):
                        raise ValueError(f"позиция {sym}: long max_favorable_px не может быть ниже entry")
                    if ("max_adverse_px" in pos_dict
                            and pos_dict["max_adverse_px"] > entry):
                        raise ValueError(f"позиция {sym}: long max_adverse_px не может быть выше entry")
                else:
                    if ("max_favorable_px" in pos_dict
                            and pos_dict["max_favorable_px"] > entry):
                        raise ValueError(f"позиция {sym}: short max_favorable_px не может быть выше entry")
                    if ("max_adverse_px" in pos_dict
                            and pos_dict["max_adverse_px"] < entry):
                        raise ValueError(f"позиция {sym}: short max_adverse_px не может быть ниже entry")
                for field_name in ("tp1_hit",):
                    if field_name in pos_dict and not isinstance(pos_dict[field_name], bool):
                        raise ValueError(f"позиция {sym}: {field_name} должен быть bool")
                if "maker_exits" in pos_dict and pos_dict["maker_exits"] is not None and not isinstance(pos_dict["maker_exits"], bool):
                    raise ValueError(f"позиция {sym}: maker_exits должен быть bool или null")
                if "tp1_maker" in pos_dict and pos_dict["tp1_maker"] is not None and not isinstance(pos_dict["tp1_maker"], bool):
                    raise ValueError(f"позиция {sym}: tp1_maker должен быть bool или null")
                if "risk_tier_id" in pos_dict and pos_dict["risk_tier_id"] is not None:
                    value = pos_dict["risk_tier_id"]
                    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                        raise ValueError(f"позиция {sym}: risk_tier_id должен быть положительным целым числом")
                for field_name in ("risk_limit_value", "maintenance_margin_rate", "maintenance_margin_deduction",
                                   "risk_tier_max_leverage", "initial_margin_usdt", "maintenance_margin_usdt"):
                    if field_name in pos_dict and pos_dict[field_name] is not None:
                        try:
                            value = Decimal(str(pos_dict[field_name]))
                        except Exception as exc:
                            raise ValueError(f"позиция {sym}: {field_name} должен быть Decimal-строкой") from exc
                        if not value.is_finite() or value < 0:
                            raise ValueError(f"позиция {sym}: {field_name} должен быть конечным числом >= 0")
                if "exchange_sized" in pos_dict and not isinstance(pos_dict["exchange_sized"], bool):
                    raise ValueError(f"позиция {sym}: exchange_sized должен быть bool")
                qty_fields = ("contract_qty", "tp1_contract_qty", "remaining_contract_qty",
                              "qty_step", "min_order_qty", "min_notional_value")
                parsed_qty = {}
                for field_name in qty_fields:
                    raw = pos_dict.get(field_name)
                    if raw is not None:
                        if not isinstance(raw, str) or not raw:
                            raise ValueError(f"позиция {sym}: {field_name} должен быть Decimal-строкой")
                        try:
                            value = Decimal(raw)
                        except InvalidOperation as exc:
                            raise ValueError(f"позиция {sym}: {field_name} некорректен") from exc
                        if not value.is_finite() or value <= 0:
                            raise ValueError(f"позиция {sym}: {field_name} должен быть конечным числом > 0")
                        parsed_qty[field_name] = value
                if pos_dict.get("exchange_sized", False):
                    if pos_dict.get("leverage") is None:
                        raise ValueError(f"позиция {sym}: exchange_sized требует подтверждённое leverage")
                    required_qty = ("contract_qty", "remaining_contract_qty", "qty_step",
                                    "min_order_qty", "min_notional_value")
                    missing_qty = [name for name in required_qty if name not in parsed_qty]
                    if missing_qty:
                        raise ValueError(f"позиция {sym}: exchange_sized требует quantity/spec поля: {missing_qty}")
                    initial_qty = parsed_qty["contract_qty"]
                    remaining_qty = parsed_qty["remaining_contract_qty"]
                    step = parsed_qty["qty_step"]
                    if initial_qty % step != 0 or remaining_qty % step != 0:
                        raise ValueError(f"позиция {sym}: contract quantities не выровнены по qtyStep")
                    tp1_qty = parsed_qty.get("tp1_contract_qty", Decimal("0"))
                    if tp1_hit:
                        if tp1_qty <= 0 or tp1_qty + remaining_qty != initial_qty:
                            raise ValueError(f"позиция {sym}: TP1/remaining contract quantities не сходятся")
                    elif tp1_qty != 0 or remaining_qty != initial_qty:
                        raise ValueError(f"позиция {sym}: до TP1 весь contract_qty должен оставаться открытым")
                    min_qty = parsed_qty["min_order_qty"]
                    min_notional = parsed_qty["min_notional_value"]
                    if initial_qty < min_qty or remaining_qty < min_qty:
                        raise ValueError(f"позиция {sym}: открытая contract quantity ниже minOrderQty")
                    lowest_planned_exit = min(
                        Decimal(str(pos_dict["stop_price"])),
                        Decimal(str(pos_dict["tp2_price"])),
                    )
                    if remaining_qty * lowest_planned_exit < min_notional:
                        raise ValueError(
                            f"позиция {sym}: remaining contract quantity нарушает minNotionalValue "
                            "на минимальной плановой цене выхода"
                        )
                    if tp1_hit and (
                        tp1_qty < min_qty
                        or tp1_qty * Decimal(str(pos_dict["tp1_price"])) < min_notional
                    ):
                        raise ValueError(
                            f"позиция {sym}: TP1 contract quantity нарушает minOrderQty/minNotionalValue"
                        )
                expected_remaining = 1.0 - TP1_FRACTION if tp1_hit else 1.0
                if pos_dict.get("exchange_sized", False):
                    expected_remaining = float(
                        parsed_qty["remaining_contract_qty"] / parsed_qty["contract_qty"]
                    )
                if not math.isclose(fraction, expected_remaining, rel_tol=0.0, abs_tol=1e-9):
                    raise ValueError(f"позиция {sym}: tp1_hit и remaining_fraction противоречат друг другу")
                if tp1_hit:
                    if pos_dict.get("exchange_sized", False):
                        tp1_qty_for_pnl = parsed_qty["tp1_contract_qty"]
                        expected_tp1_gross = round(
                            float(tp1_qty_for_pnl * abs(Decimal(str(tp1)) - Decimal(str(entry)))),
                            4,
                        )
                    else:
                        closed_fraction = 1.0 - fraction
                        expected_tp1_gross = round(
                            pos_dict["size_usdt"] * closed_fraction
                            * abs(tp1 - entry) / entry,
                            4,
                        )
                    if not math.isclose(
                        realized_tp1, expected_tp1_gross, rel_tol=0.0, abs_tol=1e-4
                    ):
                        raise ValueError(
                            f"позиция {sym}: realized_tp1_gross_usdt не соответствует "
                            "TP1 price и закрытому количеству"
                        )
                tp1_ts = pos_dict.get("tp1_ts_ms")
                if tp1_ts is not None:
                    if isinstance(tp1_ts, bool) or not isinstance(tp1_ts, int) or tp1_ts <= 0:
                        raise ValueError(f"позиция {sym}: tp1_ts_ms должен быть положительным целым числом или null")
                if tp1_hit:
                    if tp1_ts is None:
                        raise ValueError(f"позиция {sym}: tp1_hit=true требует tp1_ts_ms")
                    if tp1_ts < entry_ts:
                        raise ValueError(f"позиция {sym}: tp1_ts_ms не может быть раньше entry_ts")
                    if tp1_ts > saved_at_ms:
                        raise ValueError(f"позиция {sym}: tp1_ts_ms не может быть позже saved_at_utc")
                elif tp1_ts is not None:
                    raise ValueError(f"позиция {sym}: tp1_ts_ms задан при tp1_hit=false")
                if "bars_held" in pos_dict:
                    value = pos_dict["bars_held"]
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        raise ValueError(f"позиция {sym}: bars_held должен быть неотрицательным целым числом")
                pos = OpenPositionState(**pos_dict)
                if (
                    getattr(risk_mgr.cfg, "enable_post_break_invalidation", False)
                    and pos.strategy in {"H1-momentum-breakout"}
                    and pos.bars_held <= POST_BREAK_INVALIDATION_BARS
                    and pos.breakout_level is None
                ):
                    raise ValueError(
                        f"позиция {sym}: H-C включён, но отсутствует signal-time breakout_level"
                    )
                if pos.symbol != sym:
                    raise ValueError(f"ключ позиции {sym!r} не совпадает с pos.symbol {pos.symbol!r}")
                restored[sym] = pos

            if set(raw_marks) != set(restored):
                missing_marks = sorted(set(restored).difference(raw_marks))
                extra_marks = sorted(set(raw_marks).difference(restored))
                raise ValueError(
                    f"last_mark_prices должен точно покрывать open_positions; "
                    f"отсутствуют={missing_marks}, лишние={extra_marks}"
                )
            candidate_marks: Dict[str, float] = {}
            for symbol, value in raw_marks.items():
                if not isinstance(symbol, str) or not symbol:
                    raise ValueError("last_mark_prices содержит некорректный symbol")
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                    raise ValueError(f"last_mark_prices[{symbol}] должен быть конечным числом > 0")
                candidate_marks[symbol] = float(value)

            required_pending = {
                "symbol", "direction", "strategy", "signal_ts", "entry_price",
                "stop_dist", "order_type",
            }
            allowed_pending = {
                "symbol", "direction", "strategy", "signal_ts", "entry_price",
                "stop_price", "tp1_price", "tp2_price", "stop_dist", "atr",
                "vol_ratio", "session", "order_type", "breakout_level",
            }
            for sym, signal in pending.items():
                if not isinstance(sym, str) or not sym or not isinstance(signal, dict):
                    raise ValueError("каждый pending signal должен быть объектом с непустым symbol key")
                unknown = set(signal).difference(allowed_pending)
                if unknown:
                    raise ValueError(f"pending signal {sym}: неизвестные поля backup {sorted(unknown)}")
                missing = required_pending.difference(signal)
                if missing:
                    raise ValueError(f"pending signal {sym}: отсутствуют поля {sorted(missing)}")
                if signal.get("breakout_level") is not None:
                    value = signal["breakout_level"]
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                        raise ValueError(f"pending signal {sym}: breakout_level должен быть конечным числом > 0 или None")
                signal_ts = signal["signal_ts"]
                if isinstance(signal_ts, bool) or not isinstance(signal_ts, int) or signal_ts <= 0:
                    raise ValueError(f"pending signal {sym}: signal_ts должен быть положительным целым числом")
                if signal_ts > saved_at_ms:
                    raise ValueError(f"pending signal {sym}: signal_ts не может быть позже saved_at_utc")
                if signal["symbol"] != sym:
                    raise ValueError(f"ключ pending {sym!r} не совпадает с signal.symbol {signal['symbol']!r}")
                if signal["direction"] not in {"long", "short"}:
                    raise ValueError(f"pending signal {sym}: direction должен быть long/short")
                if signal["order_type"] not in {"market", "limit"}:
                    raise ValueError(f"pending signal {sym}: order_type должен быть market/limit")
                if not isinstance(signal["strategy"], str) or not signal["strategy"]:
                    raise ValueError(f"pending signal {sym}: strategy должен быть непустой строкой")
                if (
                    getattr(risk_mgr.cfg, "enable_post_break_invalidation", False)
                    and signal["strategy"] in {"H1-momentum-breakout"}
                    and signal.get("breakout_level") is None
                ):
                    raise ValueError(
                        f"pending signal {sym}: H-C включён, но отсутствует signal-time breakout_level"
                    )
                for field_name in ("entry_price", "stop_dist"):
                    value = signal[field_name]
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                        raise ValueError(f"pending signal {sym}: {field_name} должен быть конечным числом > 0")
                if "vol_ratio" in signal:
                    value = signal["vol_ratio"]
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                        raise ValueError(f"pending signal {sym}: vol_ratio должен быть конечным числом >= 0")

            overlapping_symbols = set(restored).intersection(pending)
            if overlapping_symbols:
                raise ValueError(f"символы одновременно в open_positions и pending_orders: {sorted(overlapping_symbols)}")
            trade_ids = [position.trade_id for position in restored.values()]
            if len(trade_ids) != len(set(trade_ids)):
                raise ValueError("backup содержит повторяющиеся trade_id в open_positions")

            seq = raw_seq
            # не даём новым ID совпасть с восстановленными
            for p in restored.values():
                m = re.search(r"(\d+)$", p.trade_id)
                if m:
                    seq = max(seq, int(m.group(1)))

            # Commit the validated risk state only after all backup components parsed.
            risk_mgr.from_dict(candidate_risk.to_dict())
            self.last_mark_prices = candidate_marks
            if restored and log_restore:
                logger.info("🛡️ План Б: восстановлено %d позиций, kill_switch=%s, daily_stop=%s",
                            len(restored), risk_mgr.kill_switch_triggered, risk_mgr.daily_stop_triggered)
            return restored, pending, seq
        except Exception as e:
            # A missing file is a clean cold start; an existing but unreadable
            # backup is not. Never silently discard possibly-open exchange state.
            logger.critical("Критическая ошибка загрузки состояния План Б; запуск запрещён: %s", e)
            raise RuntimeError(
                f"Не удалось безопасно восстановить состояние из {self.backup_filepath!r}; "
                "пустое состояние не будет подставлено вместо повреждённого backup"
            ) from e


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
                "total_trades": 0, "net_pnl": 0.0, "total_costs": 0.0, "funding_cost_usdt": 0.0,
                "ret_pct": 0.0, "win_rate": 0.0,
                "pf": 0.0, "expectancy_r": 0.0,
                "max_dd_pct": max(0.0, float(mark_to_market_max_dd_pct or 0.0)), "avg_risk_pct": 0.0,
                "cost_drag_pct": 0.0, "passed_count": 0, "all_ok": False, "checks": {},
                "top_bottleneck_title": "Нет сделок", "top_bottleneck_patch": "Ожидание сигналов"
            }

        net_pnl = sum(t.pnl_usdt for t in trades)
        gross_pnl = sum(t.gross_pnl for t in trades)
        total_costs = sum(t.exchange_fees_usdt + t.slippage_cost_usdt + t.funding_cost_usdt for t in trades)
        total_funding_cost = sum(t.funding_cost_usdt for t in trades)
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

        # Closed trades sharing one exit timestamp are a single portfolio
        # equity event. Iterating them individually makes max drawdown depend
        # on symbol/list order (e.g. a same-bar win before a stop loss).
        pnl_by_exit_ts: Dict[datetime, float] = {}
        for trade in trades:
            try:
                exit_dt = datetime.fromisoformat(trade.exit_date.replace("Z", "+00:00"))
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid trade exit_date for drawdown calculation: {trade.exit_date!r}") from exc
            if exit_dt.tzinfo is None or exit_dt.utcoffset() is None:
                raise ValueError(f"trade exit_date must include timezone: {trade.exit_date!r}")
            exit_dt = exit_dt.astimezone(timezone.utc)
            pnl_by_exit_ts[exit_dt] = pnl_by_exit_ts.get(exit_dt, 0.0) + trade.pnl_usdt

        eq = peak = cfg.capital_usdt
        max_dd_pct = 0.0
        for exit_dt in sorted(pnl_by_exit_ts):
            eq += pnl_by_exit_ts[exit_dt]
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
            "total_costs": round(total_costs, 2), "funding_cost_usdt": round(total_funding_cost, 2),
            "ret_pct": round(ret_pct, 2),
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
        funding_dir: Optional[str] = None,
        mark_price_dir: Optional[str] = None,
        instrument_specs_dir: Optional[str] = None,
        max_instrument_spec_age_ms: Optional[int] = 30 * 24 * 60 * 60 * 1000,
        risk_tiers_dir: Optional[str] = None,
        max_risk_tier_age_ms: Optional[int] = 30 * 24 * 60 * 60 * 1000,
        max_market_state_skew_ms: Optional[int] = None,
    ):
        self._explicit_config = config_path
        self.funding_dir = funding_dir
        self.mark_price_dir = mark_price_dir
        self.instrument_spec_history = (
            InstrumentSpecHistory.from_directory(instrument_specs_dir)
            if instrument_specs_dir else None
        )
        if max_instrument_spec_age_ms is not None and max_instrument_spec_age_ms < 0:
            raise ValueError("max_instrument_spec_age_ms cannot be negative")
        self.max_instrument_spec_age_ms = max_instrument_spec_age_ms
        self.risk_tier_history = (
            RiskTierHistory.from_directory(risk_tiers_dir) if risk_tiers_dir else None
        )
        if max_risk_tier_age_ms is not None and max_risk_tier_age_ms < 0:
            raise ValueError("max_risk_tier_age_ms cannot be negative")
        self.max_risk_tier_age_ms = max_risk_tier_age_ms
        if max_market_state_skew_ms is not None and (
                isinstance(max_market_state_skew_ms, bool)
                or not isinstance(max_market_state_skew_ms, int)
                or max_market_state_skew_ms < 0):
            raise ValueError("max_market_state_skew_ms must be a non-negative integer or None")
        self.max_market_state_skew_ms = max_market_state_skew_ms
        self.liquidation_model_enabled = bool(self.risk_tier_history is not None and mark_price_dir)
        self._mark_price_candles: Dict[str, Dict[int, MarkPriceCandle]] = {}
        if bool(funding_dir) != bool(mark_price_dir):
            raise ValueError("--funding-dir and --mark-price-dir must be provided together")
        self.funding_by_symbol: Dict[str, List[Dict[str, Any]]] = {}
        self._funding_mark_prices: Dict[str, Dict[int, Decimal]] = {}
        if funding_dir:
            self._load_funding_history(funding_dir)
        if mark_price_dir:
            self._load_mark_price_history(mark_price_dir)
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
        self._intrabar_mtm_marks: Dict[str, float] = {}
        self._intrabar_mtm_marks_ts: Optional[int] = None
        self._intrabar_liquidation_exits: Dict[str, float] = {}
        self._bar_entry_risk_budgets: Dict[str, float] = {}
        self._bar_entry_equity: Optional[float] = None
        self._state_restored = False

        if restore_plan_b:
            self.open_positions, self.pending, self.trade_seq = self.plan_b.load_state(self.risk_mgr)
            self._last_mark_prices = dict(self.plan_b.last_mark_prices)
            self._validate_restored_positions_market_state()
            # Даже если файл содержит только risk state, это не свежий backtest.
            self._state_restored = True

    def _load_funding_history(self, directory: str) -> None:
        """Load <SYMBOL>.csv with funding_timestamp_ms and funding_rate columns."""
        if not os.path.isdir(directory):
            raise ValueError(f"Funding directory does not exist: {directory}")
        for path in glob.glob(os.path.join(directory, "*.csv")):
            symbol = os.path.splitext(os.path.basename(path))[0].upper()
            rows = []
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                required = {"funding_timestamp_ms", "funding_rate"}
                if not reader.fieldnames or not required.issubset(reader.fieldnames):
                    raise ValueError(f"{path}: required columns funding_timestamp_ms,funding_rate")
                for line_no, row in enumerate(reader, start=2):
                    try:
                        row_symbol = str(row.get("symbol") or symbol).upper()
                        ts = int(row["funding_timestamp_ms"])
                        rate = Decimal(str(row["funding_rate"]))
                    except (TypeError, ValueError, KeyError, InvalidOperation) as exc:
                        raise ValueError(f"{path}:{line_no}: invalid funding row") from exc
                    if row_symbol != symbol or ts <= 0 or not rate.is_finite():
                        raise ValueError(f"{path}:{line_no}: invalid symbol/timestamp/rate")
                    rows.append({"ts": ts, "rate": rate})
            if not rows:
                raise ValueError(f"{path}: no funding rows found")
            rows.sort(key=lambda row: row["ts"])
            if len({row["ts"] for row in rows}) != len(rows):
                raise ValueError(f"{path}: duplicate funding timestamps")
            self.funding_by_symbol[symbol] = rows
        if not self.funding_by_symbol:
            raise ValueError(f"No funding CSV files found in {directory}")

    def _load_mark_price_history(self, directory: str) -> None:
        """Load exact-timestamp Mark OHLC; retain open-only legacy files for funding."""
        if not hasattr(self, "_mark_price_candles"):
            self._mark_price_candles = {}
        if not os.path.isdir(directory):
            raise ValueError(f"Mark-price directory does not exist: {directory}")
        for path in glob.glob(os.path.join(directory, "*.csv")):
            symbol = os.path.splitext(os.path.basename(path))[0].upper()
            marks: Dict[int, Decimal] = {}
            candles: Dict[int, MarkPriceCandle] = {}
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                required = {"timestamp_ms", "open"}
                full_ohlc = {"high", "low", "close"}.issubset(set(reader.fieldnames or []))
                if not reader.fieldnames or not required.issubset(reader.fieldnames):
                    raise ValueError(f"{path}: required columns timestamp_ms,open")
                if getattr(self, "liquidation_model_enabled", False) and not full_ohlc:
                    raise ValueError(f"{path}: liquidation model requires timestamp_ms,open,high,low,close")
                for line_no, row in enumerate(reader, start=2):
                    try:
                        row_symbol = str(row.get("symbol") or symbol).upper()
                        ts = int(row["timestamp_ms"])
                        mark_open = Decimal(str(row["open"]))
                        if full_ohlc:
                            mark_high = Decimal(str(row["high"]))
                            mark_low = Decimal(str(row["low"]))
                            mark_close = Decimal(str(row["close"]))
                    except (TypeError, ValueError, KeyError, InvalidOperation) as exc:
                        raise ValueError(f"{path}:{line_no}: invalid mark-price row") from exc
                    if row_symbol != symbol or ts <= 0 or not mark_open.is_finite() or mark_open <= 0:
                        raise ValueError(f"{path}:{line_no}: invalid symbol/timestamp/mark price")
                    if ts in marks:
                        raise ValueError(f"{path}:{line_no}: duplicate mark-price timestamp {ts}")
                    marks[ts] = mark_open
                    if full_ohlc:
                        values = (mark_open, mark_high, mark_low, mark_close)
                        if any(not value.is_finite() or value <= 0 for value in values):
                            raise ValueError(f"{path}:{line_no}: Mark OHLC values must be finite and positive")
                        if mark_high < max(mark_open, mark_low, mark_close) or mark_low > min(mark_open, mark_high, mark_close):
                            raise ValueError(f"{path}:{line_no}: invalid Mark OHLC ordering")
                        candles[ts] = MarkPriceCandle(ts, mark_open, mark_high, mark_low, mark_close)
            if not marks:
                raise ValueError(f"{path}: no mark-price rows found")
            self._funding_mark_prices[symbol] = marks
            if candles:
                self._mark_price_candles[symbol] = candles
        if not self._funding_mark_prices:
            raise ValueError(f"No mark-price CSV files found in {directory}")
        if getattr(self, "liquidation_model_enabled", False):
            missing = sorted(set(self.funding_by_symbol) - set(self._mark_price_candles))
            if missing:
                raise ValueError(f"Liquidation model requires full Mark OHLC for symbols: {missing}")

    def reset_state_for_new_run(self) -> None:
        self.risk_mgr.reset_for_backtest(self.cfg)
        self.open_positions.clear()
        self.pending.clear()
        self.closed_trades.clear()
        self.trade_seq = 0
        self._last_mark_prices.clear()
        self._intrabar_risk_marks.clear()
        self._intrabar_risk_marks_ts = None
        self._intrabar_mtm_marks.clear()
        self._intrabar_mtm_marks_ts = None
        self._intrabar_liquidation_exits.clear()
        self._defer_close_risk_evaluation = False
        self._bar_entry_risk_budgets.clear()
        self._bar_entry_equity = None
        self._state_restored = False

    @staticmethod
    def _risk_mark_for_position(pos, candle: Candle) -> float:
        """Adverse intrabar mark, using stop fill rather than later wick after stop."""
        is_long = pos.direction == "long"
        stop_crossed = candle.low <= pos.stop_price if is_long else candle.high >= pos.stop_price
        if stop_crossed:
            return min(pos.stop_price, candle.open) if is_long else max(pos.stop_price, candle.open)
        return candle.low if is_long else candle.high

    def _mark_candle_for_symbol(self, symbol: str, candle_ts: int, *, required: bool = False):
        mark = getattr(self, "_mark_price_candles", {}).get(symbol, {}).get(int(candle_ts))
        if mark is None and required:
            raise RuntimeError(
                f"{symbol}: missing exact-timestamp Mark OHLC candle at {candle_ts}; "
                "refusing liquidation-aware replay"
            )
        return mark

    def _liquidation_exit_price(self, pos: OpenPositionState, trade_candle: Candle,
                                as_of_ts: int) -> Optional[float]:
        """Conservative full-takeover estimate; ignores Bybit's partial-liquidation ladder."""
        if not getattr(self, "liquidation_model_enabled", False):
            return None
        mark_candle = self._mark_candle_for_symbol(pos.symbol, trade_candle.ts, required=True)
        if getattr(self, "instrument_spec_history", None) is not None:
            market_state = get_linear_market_state(
                self.instrument_spec_history, self.risk_tier_history,
                pos.symbol, as_of_ts,
                max_snapshot_skew_ms=getattr(self, "max_market_state_skew_ms", None),
                max_instrument_age_ms=getattr(self, "max_instrument_spec_age_ms", None),
                max_risk_tier_age_ms=getattr(self, "max_risk_tier_age_ms", None),
            )
            tiers = market_state.risk_tiers
        else:
            tiers = self.risk_tier_history.get_tiers(
                pos.symbol, as_of_ts,
                max_age_ms=getattr(self, "max_risk_tier_age_ms", 30 * 24 * 60 * 60 * 1000),
            )
        if pos.leverage is None or not math.isfinite(float(pos.leverage)) or pos.leverage <= 0:
            raise RuntimeError(f"{pos.symbol}: missing valid entry leverage; refusing liquidation-aware replay")
        quantity = (
            Decimal(str(pos.remaining_contract_qty)) if pos.exchange_sized
            else Decimal(str(pos.size_usdt)) / Decimal(str(pos.entry_price))
                 * Decimal(str(pos.remaining_fraction))
        )
        funding_cost = Decimal("0")
        if getattr(self, "funding_dir", None):
            if pos.symbol not in self.funding_by_symbol:
                raise RuntimeError(f"Funding enabled but no CSV for liquidation position {pos.symbol}")
            funding_cost = accrued_funding_cost_for_remaining_margin(
                pos, self.funding_by_symbol[pos.symbol],
                self._funding_mark_prices.get(pos.symbol, {}), as_of_ts,
                defer_boundary_receipts=True,
            )
        adverse_mark = mark_candle.low if pos.direction == "long" else mark_candle.high
        health = evaluate_isolated_margin_health(
            symbol=pos.symbol, direction=pos.direction,
            entry_price=pos.entry_price, mark_price=adverse_mark,
            quantity=quantity, leverage=pos.leverage, tiers=tiers,
            taker_fee_rate=TAKER_FEE, funding_net_cost=funding_cost,
        )
        if not health.liquidation_triggered:
            return None
        bankruptcy = calculate_isolated_usdt_bankruptcy_price(
            direction=pos.direction, entry_price=pos.entry_price,
            leverage=pos.leverage, quantity=quantity,
            funding_net_cost=funding_cost,
        )
        return float(bankruptcy)

    def _prepare_portfolio_intrabar_marks(self, bar_candles: Dict[str, Candle]) -> None:
        """Pre-mark all positions with Mark Price for MTM and Last Price for stop execution."""
        if not bar_candles:
            return
        # Support deterministic __new__ fixtures and legacy state objects.
        if not hasattr(self, "_intrabar_risk_marks"):
            self._intrabar_risk_marks = {}
        if not hasattr(self, "_intrabar_mtm_marks"):
            self._intrabar_mtm_marks = {}
        if not hasattr(self, "_intrabar_liquidation_exits"):
            self._intrabar_liquidation_exits = {}
        timeframe_ms = {
            "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
            "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
            "4h": 14_400_000, "6h": 21_600_000, "12h": 43_200_000,
            "1d": 86_400_000,
        }
        timeframe = str(self.cfg.timeframe).strip().lower()
        if timeframe not in timeframe_ms:
            raise ValueError(f"Unsupported timeframe for intrabar marks: {self.cfg.timeframe!r}")
        first_candle = next(iter(bar_candles.values()))
        bar_close_ts = first_candle.ts + timeframe_ms[timeframe]
        if any(c.ts != first_candle.ts for c in bar_candles.values()):
            raise ValueError("Cannot aggregate portfolio marks: trade candles are not synchronized")
        self._intrabar_risk_marks.clear()
        self._intrabar_mtm_marks.clear()
        self._intrabar_liquidation_exits.clear()
        self._intrabar_risk_marks_ts = bar_close_ts
        self._intrabar_mtm_marks_ts = bar_close_ts
        for sym, candle in bar_candles.items():
            pos = self.open_positions.get(sym)
            trade_risk_mark = self._risk_mark_for_position(pos, candle) if pos is not None else candle.close
            self._intrabar_risk_marks[sym] = trade_risk_mark
            mark_candle = self._mark_candle_for_symbol(
                sym, candle.ts, required=bool(pos is not None and getattr(self, "liquidation_model_enabled", False))
            )
            if mark_candle is None:
                self._last_mark_prices[sym] = candle.close
                self._intrabar_mtm_marks[sym] = trade_risk_mark
                continue
            self._last_mark_prices[sym] = float(mark_candle.close)
            if pos is None:
                self._intrabar_mtm_marks[sym] = float(mark_candle.close)
                continue
            liquidation_exit = self._liquidation_exit_price(pos, candle, bar_close_ts)
            if liquidation_exit is not None:
                self._intrabar_liquidation_exits[sym] = liquidation_exit
                self._intrabar_mtm_marks[sym] = liquidation_exit
            else:
                stop_crossed = (
                    candle.low <= pos.stop_price if pos.direction == "long"
                    else candle.high >= pos.stop_price
                )
                if stop_crossed:
                    # Once a Last Price stop is touched, later Mark wicks in the
                    # same OHLC candle cannot be charged to a position already exited.
                    self._intrabar_mtm_marks[sym] = trade_risk_mark
                else:
                    adverse_mark = mark_candle.low if pos.direction == "long" else mark_candle.high
                    self._intrabar_mtm_marks[sym] = float(adverse_mark)

    def _unrealized_pnl_at_marks(self, as_of_ts: Optional[int] = None) -> float:
        """Conservative unrealized PnL, including cumulative funding through as_of_ts."""
        total = 0.0
        # __new__-based deterministic fixtures and legacy restored objects may
        # predate the intrabar Mark-to-Market cache; fall back to last Mark/entry.
        intrabar_mtm_marks = getattr(self, "_intrabar_mtm_marks", {})
        for sym, pos in self.open_positions.items():
            mark = intrabar_mtm_marks.get(sym, self._last_mark_prices.get(sym, pos.entry_price))
            sign = 1.0 if pos.direction == "long" else -1.0
            position_qty = (Decimal(str(pos.contract_qty)) if pos.exchange_sized
                            else Decimal(str(pos.size_usdt)) / Decimal(str(pos.entry_price)))
            remaining_qty = (Decimal(str(pos.remaining_contract_qty)) if pos.exchange_sized
                             else position_qty * Decimal(str(pos.remaining_fraction)))
            remaining_gross = float(remaining_qty) * sign * (mark - pos.entry_price)
            gross = pos.realized_tp1_gross_usdt + remaining_gross
            entry_notional = float(position_qty * Decimal(str(pos.entry_price)))
            entry_cost = entry_notional * (MAKER_FEE if pos.order_type == "limit" else TAKER_FEE)
            entry_slip = 0.0 if pos.order_type == "limit" else entry_notional * TAKER_SLIP
            tp1_qty = (Decimal(str(pos.tp1_contract_qty)) if pos.exchange_sized and pos.tp1_contract_qty
                       else position_qty * Decimal(str(TP1_FRACTION)))
            tp1_notional = float(tp1_qty * Decimal(str(pos.tp1_price)))
            remaining_exit_notional = float(remaining_qty * Decimal(str(mark)))
            # Match _close_position(): legacy/restored positions may not carry
            # maker_exits, so resolve the same order-type fallback before MTM.
            maker_exits = (pos.order_type == "limit") if pos.maker_exits is None else pos.maker_exits
            tp1_maker = maker_exits if pos.tp1_maker is None else pos.tp1_maker
            tp1_cost = (tp1_notional * (MAKER_FEE if tp1_maker else TAKER_FEE)) if pos.tp1_hit else 0.0
            tp1_slip = (tp1_notional * TAKER_SLIP
                        if pos.tp1_hit and not tp1_maker else 0.0)
            exit_cost = remaining_exit_notional * (TAKER_FEE + TAKER_SLIP)
            funding_cost = 0.0
            if getattr(self, "funding_dir", None):
                if sym not in self.funding_by_symbol:
                    raise RuntimeError(f"Funding enabled but no CSV for traded symbol {sym}")
                funding_ts = as_of_ts if as_of_ts is not None else self._intrabar_risk_marks_ts
                if funding_ts is None:
                    raise RuntimeError("Funding mark-to-market requires an explicit as_of timestamp")
                funding_cost = float(accrued_funding_cost(
                    pos, self.funding_by_symbol[sym],
                    self._funding_mark_prices.get(sym, {}), funding_ts,
                    defer_boundary_receipts=True,
                ))
            total += gross - entry_cost - entry_slip - tp1_cost - tp1_slip - exit_cost - funding_cost
        return total

    def _update_mark_to_market(self, ts_ms: int) -> None:
        unrealized = self._unrealized_pnl_at_marks(ts_ms)
        if getattr(self, "_defer_close_risk_evaluation", False):
            # A synchronized replay bar has no known intra-bar ordering between
            # symbols. Refresh the ledger/equity snapshot, but evaluate portfolio
            # stops only after every symbol's same-timestamp execution is applied.
            self.risk_mgr.unrealized_pnl = float(unrealized)
            self.risk_mgr.current_equity = round(
                self.risk_mgr.realized_equity + self.risk_mgr.unrealized_pnl, 4
            )
            return {"daily_stop_hit": False, "kill_switch_hit": False}
        alerts = self.risk_mgr.mark_to_market(unrealized, ts_ms)
        # Protective latches must survive a process restart even when this MTM
        # update does not close the currently stepped symbol. Persist only on the
        # false->true transition, not on every candle.
        if alerts.get("kill_switch_hit") or alerts.get("daily_stop_hit"):
            self._persist()
        if alerts.get("kill_switch_hit"):
            self.tg.send_message(
                f"🚨 KILL-SWITCH [{self.cfg.bot_version}]: mark-to-market drawdown достиг лимита "
                f"-{self.cfg.emergency_kill_switch_pct}%. Новые входы заблокированы.")
        elif alerts.get("daily_stop_hit"):
            self.tg.send_message(
                f"⏸ ДНЕВНОЙ СТОП [{self.cfg.bot_version}]: mark-to-market дневная просадка достигла "
                f"-{self.cfg.daily_stop_loss_pct}%. Новые входы заблокированы до 00:00 UTC.")

    def _persist(self) -> None:
        self.plan_b.save_state(
            self.cfg, self.risk_mgr, self.open_positions, self.pending,
            self.trade_seq, last_mark_prices=self._last_mark_prices,
        )

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
    def step_candle(
        self, symbol: str, candles_history: List[Candle], *,
        evaluate_new_signal: bool = True,
    ) -> bool:
        """Process this symbol's existing position/order.

        When evaluate_new_signal=False, return True only when this symbol is
        eligible for the later portfolio-wide signal-discovery phase.
        """
        if not candles_history:
            return False
        # Backward-compatible defaults for restored/fixture instances created
        # without running __init__; normal engine construction already sets these.
        if not hasattr(self, "_intrabar_risk_marks"):
            self._intrabar_risk_marks = {}
        if not hasattr(self, "_intrabar_risk_marks_ts"):
            self._intrabar_risk_marks_ts = None
        if not hasattr(self, "_intrabar_mtm_marks"):
            self._intrabar_mtm_marks = {}
        if not hasattr(self, "_intrabar_mtm_marks_ts"):
            self._intrabar_mtm_marks_ts = None
        if not hasattr(self, "_intrabar_liquidation_exits"):
            self._intrabar_liquidation_exits = {}
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
        pos_for_risk = self.open_positions.get(symbol)
        mark_candle = self._mark_candle_for_symbol(
            symbol, curr.ts, required=bool(pos_for_risk is not None and getattr(self, "liquidation_model_enabled", False))
        )
        self._last_mark_prices[symbol] = float(mark_candle.close) if mark_candle is not None else curr.close
        # Last Price continues to drive stop execution; Mark Price drives MTM and liquidation.
        risk_mark = self._risk_mark_for_position(pos_for_risk, curr) if pos_for_risk is not None else curr.close
        if self._intrabar_risk_marks_ts != bar_close_ts:
            self._intrabar_risk_marks.clear()
            self._intrabar_risk_marks_ts = bar_close_ts
        self._intrabar_risk_marks[symbol] = risk_mark
        if self._intrabar_mtm_marks_ts != bar_close_ts:
            self._intrabar_mtm_marks.clear()
            self._intrabar_liquidation_exits.clear()
            self._intrabar_mtm_marks_ts = bar_close_ts
        if mark_candle is None:
            self._intrabar_mtm_marks[symbol] = risk_mark
        elif pos_for_risk is None:
            self._intrabar_mtm_marks[symbol] = float(mark_candle.close)
        else:
            liquidation_exit = self._intrabar_liquidation_exits.get(symbol)
            if liquidation_exit is None:
                liquidation_exit = self._liquidation_exit_price(pos_for_risk, curr, bar_close_ts)
            if liquidation_exit is not None:
                self._intrabar_liquidation_exits[symbol] = liquidation_exit
                self._intrabar_mtm_marks[symbol] = liquidation_exit
            else:
                stop_crossed = curr.low <= pos_for_risk.stop_price if pos_for_risk.direction == "long" else curr.high >= pos_for_risk.stop_price
                self._intrabar_mtm_marks[symbol] = (
                    risk_mark if stop_crossed else
                    float(mark_candle.low if pos_for_risk.direction == "long" else mark_candle.high)
                )
        # Let mark_to_market refresh the boundary equity before it rolls the UTC day.
        # Calling on_new_timestamp here first would lock in the previous bar's stale equity.
        self._update_mark_to_market(bar_close_ts)

        if symbol in self.open_positions:
            self._manage_position(symbol, candles_history, fill_bar=False, exit_ts=bar_close_ts)
            return False

        if symbol in self.pending:
            if self._try_fill_pending(symbol, curr):
                # The position did not exist during the portfolio pre-mark. Recompute
                # both Last-Price stop risk and Mark-Price MTM/liquidation for this fill bar.
                new_pos = self.open_positions[symbol]
                self._intrabar_risk_marks[symbol] = self._risk_mark_for_position(new_pos, curr)
                mark_candle = self._mark_candle_for_symbol(
                    symbol, curr.ts, required=getattr(self, "liquidation_model_enabled", False)
                )
                if mark_candle is None:
                    self._intrabar_mtm_marks[symbol] = self._intrabar_risk_marks[symbol]
                else:
                    liquidation_exit = self._liquidation_exit_price(new_pos, curr, bar_close_ts)
                    if liquidation_exit is not None:
                        self._intrabar_liquidation_exits[symbol] = liquidation_exit
                        self._intrabar_mtm_marks[symbol] = liquidation_exit
                    else:
                        stop_crossed = curr.low <= new_pos.stop_price if new_pos.direction == "long" else curr.high >= new_pos.stop_price
                        self._intrabar_mtm_marks[symbol] = (
                            self._intrabar_risk_marks[symbol] if stop_crossed else
                            float(mark_candle.low if new_pos.direction == "long" else mark_candle.high)
                        )
                self._update_mark_to_market(bar_close_ts)
                self._manage_position(symbol, candles_history, fill_bar=True, exit_ts=bar_close_ts)
                return False
            # A multi-bar execution policy may retain an unfilled order in
            # self.pending. Do not evaluate a fresh signal for this symbol and
            # overwrite that order on the same candle.
            if symbol in self.pending:
                return False

        if not evaluate_new_signal:
            return True

        can_open, _ = self.risk_mgr.can_open_new_trade(len(self.open_positions) + len(self.pending))
        if not can_open:
            return False
        sig = QuantStrategyCore.evaluate_signal(symbol, candles_history, self.cfg)
        if not sig:
            return False
        self.pending[symbol] = sig        # исполнение — на СЛЕДУЮЩЕЙ свече
        self._persist()
        return False

    def _open_portfolio_risk_usdt(self) -> float:
        """Conservative sum of estimated stop risk on remaining open position sizes."""
        return sum(max(0.0, pos.risk_usdt) * max(0.0, min(1.0, pos.remaining_fraction))
                   for pos in self.open_positions.values())

    def _prepare_pending_entry_risk_budgets(self) -> Dict[str, float]:
        """Allocate this bar's remaining risk budget as a deterministic batch.

        Higher volume-ratio signals receive scarce position slots first; symbol
        name is only a stable tie-breaker. Eligible pending signals share the
        available portfolio risk equally, so iteration order cannot consume it.
        """
        self._bar_entry_risk_budgets = {}
        self._bar_entry_equity = self.risk_mgr.current_equity
        pending_symbols = list(self.pending)
        if not pending_symbols:
            return self._bar_entry_risk_budgets

        available_slots = max(0, self.cfg.max_concurrent_positions - len(self.open_positions))
        ranked = sorted(
            pending_symbols,
            key=lambda sym: (-float(
                self.pending[sym].get("priority_score", self.pending[sym].get("vol_ratio", 0.0))
            ), sym),
        )
        eligible = ranked[:available_slots]
        portfolio_cap = self.risk_mgr.current_equity * (self.cfg.max_portfolio_risk_pct / 100.0)
        available_risk = max(0.0, portfolio_cap - self._open_portfolio_risk_usdt())
        per_signal_budget = available_risk / len(eligible) if eligible else 0.0
        for symbol in pending_symbols:
            self._bar_entry_risk_budgets[symbol] = per_signal_budget if symbol in eligible else 0.0
        return self._bar_entry_risk_budgets

    def _try_fill_pending(self, symbol: str, curr: Candle) -> bool:
        """Fill only on the immediately following candle; stale signals are discarded."""
        sig = self.pending[symbol]
        timeframe_ms = {
            "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
            "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
            "4h": 14_400_000, "6h": 21_600_000, "12h": 43_200_000,
            "1d": 86_400_000,
        }
        timeframe = str(self.cfg.timeframe).strip().lower()
        signal_ts = sig.get("signal_ts")
        expected_entry_bar_ts = (
            signal_ts + timeframe_ms[timeframe]
            if timeframe in timeframe_ms
            and isinstance(signal_ts, int) and not isinstance(signal_ts, bool)
            else None
        )
        if expected_entry_bar_ts is None or curr.ts != expected_entry_bar_ts:
            self.pending.pop(symbol, None)
            getattr(self, "_bar_entry_risk_budgets", {}).pop(symbol, None)
            self._persist()
            logger.warning(
                "Discard stale pending signal %s: signal_ts=%r current_bar_ts=%r timeframe=%s",
                symbol, signal_ts, curr.ts, timeframe,
            )
            return False
        sig = self.pending.pop(symbol)
        signal_origin_ts = sig.get("signal_origin_ts", signal_ts)
        if (isinstance(signal_origin_ts, bool) or not isinstance(signal_origin_ts, int)
                or signal_origin_ts <= 0 or signal_origin_ts > signal_ts):
            logger.error("Reject pending %s: invalid original signal timestamp %r", symbol, signal_origin_ts)
            self._persist()
            return False
        strategy_name = str(sig.get("strategy", ""))
        if (
            self.cfg.enable_post_break_invalidation
            and strategy_name in {"H1-momentum-breakout"}
            and sig.get("breakout_level") is None
        ):
            logger.error("H-C: отклонён pending %s — отсутствует signal-time breakout_level", symbol)
            self._persist()
            return False
        ok, _ = self.risk_mgr.can_open_new_trade(len(self.open_positions))
        if not ok:
            self._persist()
            return False

        direction = sig["direction"]
        ref = sig["entry_price"]
        is_long = direction == "long"

        effective_order_type = sig["order_type"]
        if sig["order_type"] == "limit":
            touched = curr.low <= ref if is_long else curr.high >= ref
            if not touched:
                self._persist()
                return False                       # лимитка не исполнилась — сделка пропущена
            fill = min(ref, curr.open) if is_long else max(ref, curr.open)
            # A limit order crossed by the opening gap is marketable and takes
            # liquidity. OHLC cannot prove maker status for later intrabar
            # touches, which remain an explicitly optimistic maker proxy.
            marketable_at_open = curr.open < ref if is_long else curr.open > ref
            if marketable_at_open:
                effective_order_type = "market"
        else:
            if ref > 0 and abs(curr.open - ref) / ref * 100.0 > self.cfg.max_chase_limit_pct:
                self._persist()
                return False                       # гэп/погоня за ценой — отмена
            fill = curr.open

        stop_price, tp1, tp2 = QuantStrategyCore.build_levels(direction, fill, sig["stop_dist"], self.cfg)
        allocated_budget = getattr(self, "_bar_entry_risk_budgets", {}).pop(symbol, None)
        if allocated_budget is None:
            sizing_equity = self.risk_mgr.current_equity
            portfolio_risk_cap = sizing_equity * (self.cfg.max_portfolio_risk_pct / 100.0)
            remaining_portfolio_risk = max(
                0.0, portfolio_risk_cap - self._open_portfolio_risk_usdt(),
            )
            equity_override = None
        else:
            # Every entry in this synchronized batch uses the same pre-fill equity
            # and its preallocated risk share; earlier fills must not resize later ones.
            sizing_equity = getattr(self, "_bar_entry_equity", None)
            if sizing_equity is None:
                sizing_equity = self.risk_mgr.current_equity
            remaining_portfolio_risk = allocated_budget
            equity_override = sizing_equity
        if equity_override is None:
            size_usdt, risk_usdt = self.risk_mgr.calculate_position_size(
                fill, stop_price, order_type=effective_order_type,
                risk_budget_usdt=remaining_portfolio_risk,
            )
        else:
            size_usdt, risk_usdt = self.risk_mgr.calculate_position_size(
                fill, stop_price, order_type=effective_order_type,
                risk_budget_usdt=remaining_portfolio_risk,
                equity_override=equity_override,
            )
        if size_usdt <= 0 or risk_usdt <= 0:
            self._persist()
            return False

        exchange_order = None
        instrument_spec = None
        # Optional strict execution path. When a dated Bybit snapshot directory
        # is supplied, missing/stale symbols, leverage mismatches and exchange
        # lot constraints reject the entry; there is deliberately no proxy fallback.
        instrument_spec_history = getattr(self, "instrument_spec_history", None)
        market_state = None
        if instrument_spec_history is not None:
            try:
                risk_tier_history = getattr(self, "risk_tier_history", None)
                if risk_tier_history is not None:
                    market_state = get_linear_market_state(
                        instrument_spec_history, risk_tier_history,
                        symbol, curr.ts,
                        max_snapshot_skew_ms=getattr(self, "max_market_state_skew_ms", None),
                        max_instrument_age_ms=getattr(
                            self, "max_instrument_spec_age_ms",
                            30 * 24 * 60 * 60 * 1000,
                        ),
                        max_risk_tier_age_ms=getattr(
                            self, "max_risk_tier_age_ms",
                            30 * 24 * 60 * 60 * 1000,
                        ),
                    )
                    instrument_spec = market_state.instrument_spec
                else:
                    instrument_spec = instrument_spec_history.get_spec(
                        symbol, curr.ts,
                        max_age_ms=getattr(
                            self, "max_instrument_spec_age_ms",
                            30 * 24 * 60 * 60 * 1000,
                        ),
                    )
                instrument_spec.validate_leverage(Decimal(str(self.cfg.leverage_val)))
                exchange_order = size_to_exchange_constraints(
                    instrument_spec, size_usdt, fill, risk_usdt,
                    order_type=effective_order_type,
                    side="buy" if is_long else "sell",
                    price_is_execution=True,
                )
            except ValueError as exc:
                logger.warning(
                    "Reject entry %s: dated Bybit execution constraints unavailable: %s",
                    symbol, exc,
                )
                self._persist()
                return False
            size_usdt = float(exchange_order.notional_usdt)
            risk_usdt = float(exchange_order.risk_usdt)

        risk_margin = None
        risk_tier_history = getattr(self, "risk_tier_history", None)
        if risk_tier_history is not None:
            try:
                position_value = Decimal(str(size_usdt))
                if market_state is not None:
                    risk_margin = calculate_margin_requirements_from_tiers(
                        symbol, position_value,
                        leverage=Decimal(str(self.cfg.leverage_val)),
                        tiers=market_state.risk_tiers,
                    )
                else:
                    risk_margin = risk_tier_history.calculate_margin_requirements(
                        symbol, curr.ts, position_value,
                        leverage=Decimal(str(self.cfg.leverage_val)),
                        max_age_ms=getattr(self, "max_risk_tier_age_ms", 30 * 24 * 60 * 60 * 1000),
                    )
            except ValueError as exc:
                logger.warning(
                    "Reject entry %s: dated Bybit risk tier unavailable or exceeded: %s",
                    symbol, exc,
                )
                self._persist()
                return False

        self.trade_seq += 1
        self.open_positions[symbol] = OpenPositionState(
            trade_id=f"T-{self.trade_seq:04d}", symbol=symbol, direction=direction,
            strategy=sig["strategy"], entry_ts=curr.ts, entry_price=fill,
            stop_price=stop_price, tp1_price=tp1, tp2_price=tp2,
            initial_stop_dist=sig["stop_dist"], size_usdt=size_usdt, risk_usdt=risk_usdt,
            order_type=effective_order_type,
            breakout_level=sig.get("breakout_level"),
            signal_ts_ms=signal_origin_ts,
            maker_exits=(self.cfg.maker_entry_and_tp1 if self.cfg.maker_tp1_and_target is None else self.cfg.maker_tp1_and_target),
            max_favorable_px=fill, max_adverse_px=fill,
            equity_at_entry=sizing_equity,
            leverage=float(self.cfg.leverage_val),
            risk_tier_id=risk_margin.tier_id if risk_margin else None,
            risk_limit_value=str(risk_margin.risk_limit_value) if risk_margin else None,
            maintenance_margin_rate=str(risk_margin.maintenance_margin_rate) if risk_margin else None,
            maintenance_margin_deduction=str(risk_margin.mm_deduction) if risk_margin else None,
            risk_tier_max_leverage=str(risk_margin.max_leverage) if risk_margin else None,
            initial_margin_usdt=str(risk_margin.initial_margin) if risk_margin else None,
            maintenance_margin_usdt=str(risk_margin.maintenance_margin) if risk_margin else None,
            contract_qty=str(exchange_order.qty) if exchange_order else None,
            remaining_contract_qty=str(exchange_order.qty) if exchange_order else None,
            qty_step=str(instrument_spec.qty_step) if instrument_spec else None,
            min_order_qty=str(instrument_spec.min_order_qty) if instrument_spec else None,
            min_notional_value=str(instrument_spec.min_notional_value) if instrument_spec else None,
            exchange_sized=exchange_order is not None,
        )
        self._persist()
        return True

    @staticmethod
    def _apply_tp1(pos: OpenPositionState, tp1_ts_ms: Optional[int] = None) -> bool:
        tp1_move = abs(pos.tp1_price - pos.entry_price) / pos.entry_price
        if pos.exchange_sized:
            initial_qty = Decimal(str(pos.contract_qty))
            step = Decimal(str(pos.qty_step))
            tp1_qty = (initial_qty * Decimal(str(TP1_FRACTION)) / step).to_integral_value(
                rounding=ROUND_FLOOR
            ) * step
            remaining_qty = initial_qty - tp1_qty
            min_qty = Decimal(str(pos.min_order_qty))
            min_notional = Decimal(str(pos.min_notional_value))
            # The remaining reduce order must still satisfy minNotional at
            # every planned exit level. For shorts, TP2 can be below entry
            # while the initial stop is above it; checking only min(stop, entry)
            # would miss that lower-notional target exit.
            lowest_planned_exit = min(
                Decimal(str(pos.stop_price)),
                Decimal(str(pos.tp2_price)),
            )
            if (tp1_qty < min_qty or remaining_qty < min_qty
                    or tp1_qty * Decimal(str(pos.tp1_price)) < min_notional
                    or remaining_qty * lowest_planned_exit < min_notional):
                return False
            pos.tp1_contract_qty = str(tp1_qty)
            pos.remaining_contract_qty = str(remaining_qty)
            pos.realized_tp1_gross_usdt = round(float(tp1_qty) * abs(pos.tp1_price - pos.entry_price), 4)
            pos.remaining_fraction = float(remaining_qty / initial_qty)
        else:
            pos.realized_tp1_gross_usdt = round(pos.size_usdt * TP1_FRACTION * tp1_move, 4)
            pos.remaining_fraction = 1.0 - TP1_FRACTION
        pos.tp1_hit = True
        pos.tp1_ts_ms = tp1_ts_ms
        return True

    def _manage_position(self, symbol: str, hist: List[Candle], fill_bar: bool, exit_ts: int) -> None:
        pos = self.open_positions[symbol]
        tp1_was_hit = pos.tp1_hit
        curr = hist[-1]
        cfg = self.cfg
        is_long = pos.direction == "long"
        pos.bars_held += 1
        atr = QuantStrategyCore.compute_atr(hist[:-1], cfg.atr_period)
        stop_dist = max(1e-8, pos.initial_stop_dist)

        exit_price: Optional[float] = None
        exit_reason: Optional[str] = None
        maker_exits = (pos.order_type == "limit") if pos.maker_exits is None else pos.maker_exits
        final_exit_maker = False
        liquidation_exit = getattr(self, "_intrabar_liquidation_exits", {}).get(symbol)
        if liquidation_exit is None:
            liquidation_exit = self._liquidation_exit_price(pos, curr, exit_ts)
        if liquidation_exit is not None:
            self._intrabar_liquidation_exits[symbol] = liquidation_exit

        # 1) Liquidation on Mark Price precedes Last Price stops if both are
        # touched in the same OHLC interval; intrabar event order is unknowable.
        # Если стоп пересечён, OHLC не показывает порядок high/low: не засчитываем
        # благоприятный экстремум этой свечи и ограничиваем MAE фактической модельной
        # ценой стоп-исполнения, а не более глубоким последующим wick.
        stop_hit = (curr.low <= pos.stop_price) if is_long else (curr.high >= pos.stop_price)
        kill_switch_hit = bool(self.risk_mgr.kill_switch_triggered)
        if liquidation_exit is not None:
            exit_price, exit_reason = liquidation_exit, "liquidation"
            if is_long:
                pos.max_adverse_px = min(pos.max_adverse_px, exit_price)
            else:
                pos.max_adverse_px = max(pos.max_adverse_px, exit_price)
        elif kill_switch_hit:
            # The portfolio kill-switch may have been triggered by this bar's
            # adverse mark before position management. OHLC cannot establish
            # whether a simultaneous TP touch happened before or after it, so
            # forced flattening takes priority over every discretionary exit.
            exit_price = self._intrabar_risk_marks.get(symbol, curr.close)
            exit_reason = "kill_switch"
            if is_long:
                pos.max_adverse_px = min(pos.max_adverse_px, exit_price)
            else:
                pos.max_adverse_px = max(pos.max_adverse_px, exit_price)
        elif stop_hit:
            if fill_bar:
                exit_price = pos.stop_price
            elif is_long:
                exit_price = min(pos.stop_price, curr.open)    # гэп вниз -> худшая цена
            else:
                exit_price = max(pos.stop_price, curr.open)    # гэп вверх -> худшая цена
            if is_long:
                pos.max_adverse_px = min(pos.max_adverse_px, exit_price)
            else:
                pos.max_adverse_px = max(pos.max_adverse_px, exit_price)
            exit_reason = "trailing_stop" if pos.tp1_hit else "stop_loss"
        else:
            # На свече исполнения благоприятный экстремум не обновляем: он мог быть
            # до фактического входа. Неблагоприятный экстремум сохраняем консервативно.
            if is_long:
                if not fill_bar:
                    pos.max_favorable_px = max(pos.max_favorable_px, curr.high)
                pos.max_adverse_px = min(pos.max_adverse_px, curr.low)
            else:
                if not fill_bar:
                    pos.max_favorable_px = min(pos.max_favorable_px, curr.low)
                pos.max_adverse_px = max(pos.max_adverse_px, curr.high)

        if is_long:
            mfe_r = (pos.max_favorable_px - pos.entry_price) / stop_dist
            mae_r = (pos.entry_price - pos.max_adverse_px) / stop_dist
        else:
            mfe_r = (pos.entry_price - pos.max_favorable_px) / stop_dist
            mae_r = (pos.max_adverse_px - pos.entry_price) / stop_dist

        if not stop_hit and not fill_bar and not kill_switch_hit and liquidation_exit is None:
            tp2_hit = (curr.high >= pos.tp2_price) if is_long else (curr.low <= pos.tp2_price)
            if tp2_hit:
                if not pos.tp1_hit:
                    tp1_applied = self._apply_tp1(pos, exit_ts)  # TP1 lies between entry and TP2; both are filled
                    if tp1_applied:
                        tp1_marketable_at_open = (
                            curr.open > pos.tp1_price if is_long
                            else curr.open < pos.tp1_price
                        )
                        pos.tp1_maker = bool(maker_exits and not tp1_marketable_at_open)
                tp2_marketable_at_open = (
                    curr.open > pos.tp2_price if is_long
                    else curr.open < pos.tp2_price
                )
                final_exit_maker = bool(maker_exits and not tp2_marketable_at_open)
                exit_price, exit_reason = pos.tp2_price, "take_profit"
            else:
                if not pos.tp1_hit:
                    tp1_hit = (curr.high >= pos.tp1_price) if is_long else (curr.low <= pos.tp1_price)
                    if tp1_hit:
                        tp1_applied = self._apply_tp1(pos, exit_ts)
                        if tp1_applied:
                            tp1_marketable_at_open = (
                                curr.open > pos.tp1_price if is_long
                                else curr.open < pos.tp1_price
                            )
                            pos.tp1_maker = bool(maker_exits and not tp1_marketable_at_open)

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

        if exit_price is None and symbol in self.open_positions:
            # TP1 changes realized/unrealized decomposition and the modeled exit
            # legs. Re-mark only after that state transition; otherwise the MTM
            # snapshot would still describe the pre-TP1 position.
            if pos.tp1_hit and not tp1_was_hit:
                self._update_mark_to_market(exit_ts)
            if self.risk_mgr.kill_switch_triggered:
                exit_price, exit_reason = self._intrabar_risk_marks.get(symbol, curr.close), "kill_switch"
            elif (
                self.cfg.enable_post_break_invalidation
                and pos.strategy in {"H1-momentum-breakout"}
                and pos.bars_held <= POST_BREAK_INVALIDATION_BARS
            ):
                if pos.breakout_level is None:
                    raise RuntimeError(
                        f"H-C: open position {symbol} has no persisted signal-time breakout_level"
                    )
                retested_inside = (
                    curr.close <= pos.breakout_level if pos.direction == "long"
                    else curr.close >= pos.breakout_level
                )
                if retested_inside:
                    exit_price, exit_reason = float(curr.close), "breakout_retest_invalidation"
                else:
                    self._persist()
            else:
                # Persist per-candle position evolution (bars held, MFE/MAE,
                # trailing stop and TP1 state) so a restart cannot restore an
                # obsolete protective stop or stale position lifecycle.
                self._persist()

        if exit_price is not None and exit_reason is not None:
            self._close_position(
                pos, exit_price, exit_reason, exit_ts, mae_r, mfe_r,
                final_exit_maker if exit_reason == "take_profit" else False,
            )

    @staticmethod
    def _leg_cost(notional: float, maker: bool) -> Tuple[float, float]:
        return (notional * (MAKER_FEE if maker else TAKER_FEE),
                0.0 if maker else notional * TAKER_SLIP)

    def _close_position(self, pos: OpenPositionState, exit_price: float, exit_reason: str,
                        exit_ts: int, mae_r: float, mfe_r: float,
                        final_exit_maker: Optional[bool] = None) -> None:
        sign = 1.0 if pos.direction == "long" else -1.0
        if pos.exchange_sized:
            remaining_qty = Decimal(str(pos.remaining_contract_qty))
            if exit_reason != "liquidation":
                step = Decimal(str(pos.qty_step))
                min_qty = Decimal(str(pos.min_order_qty))
                min_notional = Decimal(str(pos.min_notional_value))
                if remaining_qty <= 0 or remaining_qty % step != 0:
                    raise RuntimeError(f"{pos.symbol}: final reduce quantity is not positive/aligned to qtyStep")
                if remaining_qty < min_qty or remaining_qty * Decimal(str(exit_price)) < min_notional:
                    raise RuntimeError(
                        f"{pos.symbol}: final reduce quantity violates archived minOrderQty/minNotionalValue; "
                        "cannot claim exchange-valid close"
                    )
            rem_gross = float(remaining_qty) * sign * (exit_price - pos.entry_price)
        else:
            remaining_qty = (Decimal(str(pos.size_usdt)) / Decimal(str(pos.entry_price))
                             * Decimal(str(pos.remaining_fraction)))
            rem_chg = sign * (exit_price - pos.entry_price) / pos.entry_price
            rem_gross = pos.size_usdt * pos.remaining_fraction * rem_chg
        gross_pnl = _money_round(pos.realized_tp1_gross_usdt + rem_gross)
        funding_cost = 0.0
        if getattr(self, "funding_dir", None):
            if pos.symbol not in self.funding_by_symbol:
                raise RuntimeError(f"Funding enabled but no CSV for traded symbol {pos.symbol}")
            funding_cost = float(accrued_funding_cost(
                pos, self.funding_by_symbol[pos.symbol],
                self._funding_mark_prices.get(pos.symbol, {}), exit_ts,
                closed_ts_ms=exit_ts,
            ))

        # Издержки по ногам. Сначала суммируем точные значения всех ног,
        # затем округляем итог в денежном формате (half-up), а не каждую ногу отдельно.
        entry_maker = pos.order_type == "limit"
        fees = slip = 0.0
        position_qty = (Decimal(str(pos.contract_qty)) if pos.exchange_sized
                        else Decimal(str(pos.size_usdt)) / Decimal(str(pos.entry_price)))
        entry_notional = float(position_qty * Decimal(str(pos.entry_price)))
        f, s = self._leg_cost(entry_notional, entry_maker)
        fees += f; slip += s
        maker_exits = (pos.order_type == "limit") if pos.maker_exits is None else pos.maker_exits
        tp1_maker = maker_exits if pos.tp1_maker is None else pos.tp1_maker
        if pos.tp1_hit:
            tp1_qty = (Decimal(str(pos.tp1_contract_qty)) if pos.exchange_sized
                       else position_qty * Decimal(str(TP1_FRACTION)))
            tp1_notional = float(tp1_qty * Decimal(str(pos.tp1_price)))
            f, s = self._leg_cost(tp1_notional, tp1_maker)
            fees += f; slip += s
        final_maker = (
            maker_exits and exit_reason == "take_profit"
            if final_exit_maker is None
            else bool(final_exit_maker) and exit_reason == "take_profit"
        )
        final_notional = float(remaining_qty * Decimal(str(exit_price)))
        if exit_reason == "liquidation":
            # Bybit documents no liquidation fee for perpetual/futures; takeover
            # settles at bankruptcy price outside the ordinary matching engine.
            f, s = 0.0, 0.0
        else:
            f, s = self._leg_cost(final_notional, final_maker)
        fees += f; slip += s
        fees, slip = _money_round(fees), _money_round(slip)

        net_pnl = _money_round(gross_pnl - fees - slip - funding_cost)
        risk = max(1e-6, pos.risk_usdt)
        eq0 = pos.equity_at_entry if pos.equity_at_entry > 0 else self.cfg.capital_usdt

        record = TradeRecord(
            id=pos.trade_id, token=pos.symbol, direction=pos.direction,
            entry_date=datetime.fromtimestamp(pos.entry_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            exit_date=datetime.fromtimestamp(exit_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            entry_price=round(pos.entry_price, 12), exit_price=round(exit_price, 12),
            size_usdt=pos.size_usdt, strategy=pos.strategy,
            pnl_usdt=net_pnl, gross_pnl=gross_pnl,
            r_multiple=net_pnl / risk,
            exchange_fees_usdt=fees, slippage_cost_usdt=slip,
            mae=round(max(0.0, mae_r), 2), mfe=round(max(0.0, mfe_r), 2),
            exit_reason=exit_reason, order_type=pos.order_type,
            bot_version=self.cfg.bot_version,
            signal_ts_ms=pos.signal_ts_ms,
            session=QuantStrategyCore.get_utc_session(pos.entry_ts),
            gross_r_multiple=gross_pnl / risk,
            risk_usdt=round(pos.risk_usdt, 4),
            risk_pct=round(pos.risk_usdt / eq0 * 100.0, 3),
            funding_cost_usdt=funding_cost,
            exchange_sized=bool(pos.exchange_sized),
            contract_qty=str(pos.contract_qty) if pos.exchange_sized else None,
            tp1_contract_qty=str(pos.tp1_contract_qty) if pos.exchange_sized and pos.tp1_contract_qty is not None else None,
            final_contract_qty=str(remaining_qty) if pos.exchange_sized else None,
            qty_step=str(pos.qty_step) if pos.exchange_sized else None,
            leverage=float(pos.leverage) if pos.leverage is not None else None,
            risk_tier_id=pos.risk_tier_id,
            risk_limit_value=pos.risk_limit_value,
            maintenance_margin_rate=pos.maintenance_margin_rate,
            maintenance_margin_deduction=pos.maintenance_margin_deduction,
            initial_margin_usdt=pos.initial_margin_usdt,
            maintenance_margin_usdt=pos.maintenance_margin_usdt,
            initial_stop_dist=round(pos.initial_stop_dist, 12),
            initial_stop_price=round(
                pos.entry_price - pos.initial_stop_dist if pos.direction == "long"
                else pos.entry_price + pos.initial_stop_dist, 12,
            ),
            tp1_price=round(pos.tp1_price, 12),
            tp2_price=round(pos.tp2_price, 12),
            tp1_hit=bool(pos.tp1_hit),
            tp1_ts_ms=pos.tp1_ts_ms,
            realized_tp1_gross_usdt=round(pos.realized_tp1_gross_usdt, 8),
            remaining_fraction_at_exit=round(pos.remaining_fraction, 8),
            final_stop_price=round(pos.stop_price, 12),
            breakout_level=round(pos.breakout_level, 12) if pos.breakout_level is not None else None,
            tp1_maker=tp1_maker if pos.tp1_hit else None,
            final_exit_maker=final_maker,
        )
        self.closed_trades.append(record)
        del self.open_positions[pos.symbol]

        # Учитываем закрытый PnL и переоцениваем оставшиеся позиции без двойного счёта закрываемой.
        self.risk_mgr.unrealized_pnl = self._unrealized_pnl_at_marks(exit_ts)
        if getattr(self, "_defer_close_risk_evaluation", False):
            self.risk_mgr.on_new_timestamp(exit_ts)
            self.risk_mgr.realized_equity = round(
                self.risk_mgr.realized_equity + net_pnl, 4
            )
            self.risk_mgr.current_equity = round(
                self.risk_mgr.realized_equity + self.risk_mgr.unrealized_pnl, 4
            )
            alerts = {"daily_stop_hit": False, "kill_switch_hit": False}
        else:
            alerts = self.risk_mgr.register_closed_trade_pnl(net_pnl, exit_ts)
        if alerts.get("kill_switch_hit"):
            self.tg.send_message(
                f"🚨 KILL-SWITCH [{self.cfg.bot_version}]: просадка от пика достигла -{self.cfg.emergency_kill_switch_pct}%. "
                f"Новые входы заблокированы, открытые позиции закрываются по рынку.")
        elif alerts.get("daily_stop_hit"):
            self.tg.send_message(
                f"⏸ ДНЕВНОЙ СТОП [{self.cfg.bot_version}]: дневная просадка превысила -{self.cfg.daily_stop_loss_pct}%. "
                f"Новые входы заблокированы до 00:00 UTC (открытые позиции ведутся по плану).")
        if not getattr(self, "_defer_close_risk_evaluation", False):
            self._persist()

    def _force_flatten_open_positions_after_kill_switch(self, exit_ts: int) -> None:
        """Flatten residual positions after a post-execution, portfolio-wide risk check."""
        if not self.risk_mgr.kill_switch_triggered or not self.open_positions:
            return
        previous_defer = getattr(self, "_defer_close_risk_evaluation", False)
        self._defer_close_risk_evaluation = True
        try:
            for symbol, pos in list(self.open_positions.items()):
                liquidation_exit = getattr(self, "_intrabar_liquidation_exits", {}).get(symbol)
                if liquidation_exit is not None:
                    exit_price, reason = liquidation_exit, "liquidation"
                else:
                    exit_price = getattr(self, "_intrabar_risk_marks", {}).get(
                        symbol, self._last_mark_prices.get(symbol, pos.entry_price)
                    )
                    reason = "kill_switch"
                stop_dist = max(1e-8, pos.initial_stop_dist)
                if pos.direction == "long":
                    pos.max_adverse_px = min(pos.max_adverse_px, exit_price)
                    mae_r = max(0.0, (pos.entry_price - pos.max_adverse_px) / stop_dist)
                    mfe_r = max(0.0, (pos.max_favorable_px - pos.entry_price) / stop_dist)
                else:
                    pos.max_adverse_px = max(pos.max_adverse_px, exit_price)
                    mae_r = max(0.0, (pos.max_adverse_px - pos.entry_price) / stop_dist)
                    mfe_r = max(0.0, (pos.entry_price - pos.max_favorable_px) / stop_dist)
                self._close_position(
                    pos, float(exit_price), reason, exit_ts, mae_r, mfe_r,
                    final_exit_maker=False,
                )
        finally:
            self._defer_close_risk_evaluation = previous_defer
        self._update_mark_to_market(exit_ts)
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
        missing_symbols = sorted(set(self.open_positions) - set(marks))
        if missing_symbols:
            raise ValueError(
                "Для финализации отсутствуют последние свечи открытых позиций: "
                + ", ".join(missing_symbols)
            )
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
        self._update_mark_to_market(final_ts)

        # End-of-test exits share one timestamp. As in the synchronized replay
        # loop, do not let the arbitrary dictionary order create transient peaks
        # or drawdown latches between otherwise simultaneous final closes.
        previous_defer = getattr(self, "_defer_close_risk_evaluation", False)
        self._defer_close_risk_evaluation = True
        try:
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
        finally:
            self._defer_close_risk_evaluation = previous_defer
        self._update_mark_to_market(final_ts)
        self._persist()

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



_TIMEFRAME_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "12h": 43_200_000,
    "1d": 86_400_000,
}


def validate_candle_timeframe(candles: Dict[str, List[Candle]], timeframe: str) -> None:
    """Reject CSV/replay candles whose timestamp step disagrees with cfg.timeframe."""
    tf = str(timeframe).strip().lower()
    expected_ms = _TIMEFRAME_MS.get(tf)
    if expected_ms is None:
        raise ValueError(f"Неподдерживаемый timeframe для проверки свечей: {timeframe!r}")
    if not candles:
        raise ValueError("Нет свечных данных для проверки timeframe")
    for symbol, rows in candles.items():
        if len(rows) < 2:
            raise ValueError(f"{symbol}: для проверки timeframe нужно минимум 2 свечи")
        deltas = [b.ts - a.ts for a, b in zip(rows, rows[1:])]
        bad = sorted({delta for delta in deltas if delta != expected_ms})
        if bad:
            actual = sorted(set(deltas))
            raise ValueError(
                f"{symbol}: интервал CSV не соответствует cfg.timeframe={tf!r}; "
                f"ожидается {expected_ms} ms, обнаружено {actual[:8]}"
            )


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


def run_sparse_simulation_pass(
    engine: UnifiedQuantEngine, candles: Dict[str, List[Candle]],
    symbols: List[str], data_label: str = "СИНТЕТИКА",
    signal_evaluator: Optional[Callable] = None,
    signal_context_provider: Optional[Callable] = None,
    bar_complete_callback: Optional[Callable] = None,
) -> Dict:
    """Shared-capital replay over a dynamic universe with per-symbol availability.

    Each symbol must have a continuous timeframe grid. Symbols may start at
    different timestamps; the replay walks the union grid and processes only
    symbols with a real candle at each timestamp. All selected series are
    truncated to their earliest common terminal candle for safe finalization.
    """
    if engine._state_restored:
        raise RuntimeError("Нельзя запускать backtest поверх восстановленного состояния.")
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("Sparse replay requires a non-empty unique symbol list")
    missing = sorted(set(symbols) - set(candles))
    if missing:
        raise ValueError(f"Нет свечных данных для символов: {', '.join(missing)}")

    selected = {sym: candles[sym] for sym in symbols}
    validate_candle_timeframe(selected, engine.cfg.timeframe)
    timeframe = str(engine.cfg.timeframe).strip().lower()
    timeframe_ms = _TIMEFRAME_MS[timeframe]
    for sym, rows in selected.items():
        if any(c.ts <= 0 or c.ts % timeframe_ms for c in rows):
            raise ValueError(f"{sym}: timestamps are not aligned to {timeframe} boundaries")

    common_end_ts = min(rows[-1].ts for rows in selected.values())
    trimmed = {}
    events = {}
    for sym, rows in selected.items():
        kept = [c for c in rows if c.ts <= common_end_ts]
        if len(kept) < 2 or kept[-1].ts != common_end_ts:
            raise ValueError(
                f"{sym}: no candle at common sparse replay end {common_end_ts}; "
                "refusing inconsistent terminal coverage"
            )
        trimmed[sym] = kept
        for index, candle in enumerate(kept):
            events.setdefault(candle.ts, {})[sym] = (index, candle)

    engine.reset_state_for_new_run()
    for ts in sorted(events):
        event = events[ts]
        active_symbols = set(event)
        missing_open = sorted(set(engine.open_positions) - active_symbols)
        missing_pending = sorted(set(engine.pending) - active_symbols)
        if missing_open or missing_pending:
            raise ValueError(
                f"Sparse replay has no candle at {ts} for open positions "
                f"{missing_open} or pending entries {missing_pending}"
            )
        if not any(index >= 25 for index, _ in event.values()) and not engine.open_positions:
            continue

        active_candles = {sym: candle for sym, (_, candle) in event.items()}
        engine._prepare_portfolio_intrabar_marks(active_candles)
        bar_close_ts = ts + timeframe_ms
        engine._update_mark_to_market(bar_close_ts)
        engine._prepare_pending_entry_risk_budgets()

        signal_candidates = []
        histories = {}
        engine._defer_close_risk_evaluation = True
        try:
            for sym in symbols:
                item = event.get(sym)
                if item is None:
                    continue
                index, _ = item
                if index < 25:
                    continue
                lo = max(0, index + 1 - CALC_WINDOW)
                history = trimmed[sym][lo:index + 1]
                histories[sym] = history
                if engine.step_candle(sym, history, evaluate_new_signal=False):
                    signal_candidates.append(sym)
        finally:
            engine._defer_close_risk_evaluation = False
        engine._bar_entry_risk_budgets.clear()
        # Evaluate drawdown once against the complete synchronized post-execution
        # portfolio. If this new snapshot trips the emergency latch, flatten the
        # remaining positions as one same-timestamp batch.
        engine._update_mark_to_market(bar_close_ts)
        force_flatten = getattr(
            engine, "_force_flatten_open_positions_after_kill_switch", None
        )
        if force_flatten is not None:
            force_flatten(bar_close_ts)
        persist = getattr(engine, "_persist", None)
        if persist is not None:
            persist()

        signal_context = (
            signal_context_provider(bar_close_ts, histories, engine.cfg)
            if signal_context_provider is not None else None
        )
        for sym in signal_candidates:
            can_open, _ = engine.risk_mgr.can_open_new_trade(len(engine.open_positions))
            if not can_open:
                break
            if signal_evaluator is None:
                sig = QuantStrategyCore.evaluate_signal(sym, histories[sym], engine.cfg)
            else:
                sig = signal_evaluator(sym, histories[sym], engine.cfg, signal_context)
            if sig:
                engine.pending[sym] = sig
                engine._persist()
        if bar_complete_callback is not None:
            bar_complete_callback(bar_close_ts, engine)

    final_marks = {sym: trimmed[sym][-1] for sym in engine.open_positions}
    engine.finalize_open_positions(final_marks, exit_reason="end_of_test")
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


def run_simulation_pass(engine: UnifiedQuantEngine, candles: Dict[str, List[Candle]],
                        symbols: List[str], data_label: str = "СИНТЕТИКА",
                        allow_sparse_data: bool = False,
                        signal_evaluator: Optional[Callable] = None,
                        signal_context_provider: Optional[Callable] = None,
                        bar_complete_callback: Optional[Callable] = None) -> Dict:
    # Это именно новый независимый бэктест, не восстановление live-сессии.
    if engine._state_restored:
        raise RuntimeError("Нельзя запускать backtest поверх восстановленного состояния. "
                           "Для live-resume нужен отдельный цикл с reconciliation по бирже.")
    if not symbols:
        raise ValueError("Список символов для симуляции пуст")
    missing = sorted(set(symbols) - set(candles))
    if missing:
        raise ValueError(f"Нет свечных данных для символов: {', '.join(missing)}")
    selected_candles = {sym: candles[sym] for sym in symbols}
    if allow_sparse_data:
        return run_sparse_simulation_pass(
            engine, selected_candles, symbols, data_label=data_label,
            signal_evaluator=signal_evaluator,
            signal_context_provider=signal_context_provider,
            bar_complete_callback=bar_complete_callback,
        )
    if (signal_evaluator is not None or signal_context_provider is not None
            or bar_complete_callback is not None):
        raise ValueError("Custom replay callbacks currently require allow_sparse_data=True")
    validate_candle_timeframe(selected_candles, engine.cfg.timeframe)
    check_alignment(selected_candles)
    engine.reset_state_for_new_run()
    bars_total = len(candles[symbols[0]])
    for bar in range(25, bars_total):
        lo = max(0, bar + 1 - CALC_WINDOW)
        # Evaluate portfolio drawdown against all symbols' adverse marks for this
        # synchronized bar before any single symbol can trigger a risk decision.
        engine._prepare_portfolio_intrabar_marks({sym: candles[sym][bar] for sym in symbols})
        timeframe_ms = _TIMEFRAME_MS[str(engine.cfg.timeframe).strip().lower()]
        bar_close_ts = candles[symbols[0]][bar].ts + timeframe_ms
        engine._update_mark_to_market(bar_close_ts)
        engine._prepare_pending_entry_risk_budgets()
        signal_candidates = []
        engine._defer_close_risk_evaluation = True
        try:
            for sym in symbols:
                if engine.step_candle(
                    sym, candles[sym][lo:bar + 1], evaluate_new_signal=False,
                ):
                    signal_candidates.append(sym)
        finally:
            engine._defer_close_risk_evaluation = False
        engine._bar_entry_risk_budgets.clear()
        # Do not let the order of simultaneous symbol closes create a transient
        # peak/drawdown. Reconcile the full bar, then force-flat if the final
        # post-execution portfolio snapshot trips the emergency kill-switch.
        engine._update_mark_to_market(bar_close_ts)
        engine._force_flatten_open_positions_after_kill_switch(bar_close_ts)
        engine._persist()

        # Discover every eligible signal from the same post-execution portfolio
        # state. Position-slot priority is applied to the complete pending batch
        # on the next bar, never to whichever symbols happen to be iterated first.
        for sym in signal_candidates:
            can_open, _ = engine.risk_mgr.can_open_new_trade(len(engine.open_positions))
            if not can_open:
                break
            sig = QuantStrategyCore.evaluate_signal(
                sym, candles[sym][lo:bar + 1], engine.cfg,
            )
            if sig:
                engine.pending[sym] = sig
                engine._persist()

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
    parser.add_argument("--funding-dir", type=str, default=None, help="Папка с <SYMBOL>.csv funding history")
    parser.add_argument("--mark-price-dir", type=str, default=None, help="Папка с <SYMBOL>.csv Mark Price OHLC klines")
    parser.add_argument("--risk-tiers-dir", type=str, default=None, help="Папка с dated Bybit linear risk-tier snapshots; together with Mark OHLC enables liquidation model")
    args = parser.parse_args()

    engine = UnifiedQuantEngine(config_path=args.config, journal_output_path=args.journal,
                                persist_state=args.persist_state, state_path=args.state_path,
                                funding_dir=args.funding_dir, mark_price_dir=args.mark_price_dir,
                                risk_tiers_dir=args.risk_tiers_dir)
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