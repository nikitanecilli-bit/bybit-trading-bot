# ENG-KS-001 — приоритет kill-switch над TP при внутрисвечной неоднозначности

Статус до исправления: HYPOTHESIS REGISTERED / дефект подтверждён чтением кода.  
Дата: 2026-11-02.  
Тип: deterministic engine correctness regression; не рыночный эксперимент.

## Наблюдаемая проблема

В `Bybit_Trading_Engine_v14_research.py`, `UnifiedQuantEngine._manage_position()`:
- kill-switch уже может быть установлен вызовом `_update_mark_to_market()` в `step_candle()`;
- затем код сначала обрабатывает stop и TP2;
- резервная ветка `if exit_price is None and self.risk_mgr.kill_switch_triggered` выполняется только если позиция ещё не закрывается по stop/TP/time-stop.

Следовательно, если одна OHLC-свеча одновременно содержит неблагоприятный экстремум, который вызвал portfolio kill-switch, и касание TP2, движок может записать `take_profit`, хотя защитный выключатель уже сработал. Порядок high/low по OHLC неизвестен.

## Предварительная гипотеза

Если kill-switch активен до управления позицией на текущем баре, принудительное закрытие должно иметь приоритет над TP1/TP2/time-stop. Цена выхода — уже рассчитанная консервативная `_intrabar_risk_marks[symbol]` (включая stop/gap fill, если stop пересечён); fallback — close текущей свечи только если mark отсутствует.

На свече kill-switch не учитывать новый благоприятный экстремум в MFE: внутрисвечной путь неизвестен, а позиция принудительно ликвидируется по adverse risk mark.

## Критерии проверки (до исправления)

- Новый regression test запускает полный `step_candle()`, где adverse low вызывает kill-switch, stop не пересечён, но high касается TP2.
- Ожидается `exit_reason == "kill_switch"`, цена равна adverse intrabar mark, а не TP2.
- Не должно быть TP1 partial realization на этом баре.
- Существующие kill-switch, stop-gap, TP collision, fill-bar и дневной stop tests остаются зелёными.
- Изменение не меняет обычную обработку TP/SL, когда kill-switch не активен.
- Только deterministic tests; никаких рыночных backtests и параметрических оптимизаций.

## Риски и границы

- OHLC не раскрывает реальную последовательность исполнения; adverse mark остаётся консервативной proxy, а не реальным гарантированным fill.
- Это исправление корректности симулятора, не доказательство улучшения edge или доходности.
- Не менять live/production execution, параметры стратегии, комиссии или данные.

## Решение

Оставить OPEN до завершения regression tests и проверки CI. ACCEPT только если все критерии выполнены; иначе REJECT/INCONCLUSIVE с логами.
