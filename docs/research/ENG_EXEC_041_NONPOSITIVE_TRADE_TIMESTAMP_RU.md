# ENG-EXEC-041 — positive timestamps for normalized public trades

Дата: 2026-11-04

## Вопрос

Может ли прямой вызов `apply_public_trade()` принять некорректный normalized event с нулевым или отрицательным `timestamp_ms`, хотя CSV parser такие timestamps отклоняет?

## Подтверждённая причина

До исправления primitive выполнял строгую проверку integer-типа, затем проверял side/price/size/flags, но не проверял `timestamp_ms > 0`. Временная фильтрация после этого возвращала управление для `ts <= order.arrival_ts`. Поэтому нулевой/отрицательный timestamp не менял очередь, но и не вызывал ошибку. Это нарушало единый fail-closed контракт: `parse_trade_timestamp_ms()` уже отклоняет non-finite и non-positive timestamps.

## Исправление

В `bybit_l2_queue_replay.py:apply_public_trade()` добавлена проверка `ts <= 0` до остальных полей и до active-window filtering.

Regression `test_apply_public_trade_rejects_non_positive_timestamp_without_mutation` проверяет timestamp 0 и -1, а также неизменность `queue_ahead_remaining` и `filled`.

## Проверка

- Code/test commit: [ed2d355](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/ed2d35551496eb56e1298420507fbaed735e6b29).
- Research CI: [#41891208250](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41891208250) — SUCCESS; job `tests` SUCCESS.
- Фактические логи: aggregate-L2 primitive suite 85/85; L2 runner/inspector step 26/26; новый regression явно PASS.

## Решение и границы

Принять как deterministic input-validation guardrail. Это не подтверждает исторический trade CSV schema, archive completeness, maker fill probability или profitability. Никакие рыночные PnL-прогоны, загрузки архивов, collectors, private API, runner registration, paper/live orders не выполнялись. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` остаётся закрытым. `main` не изменён.
