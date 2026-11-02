# ENG-STATE-003 — fail-closed restore при повреждённом backup

Статус: ACCEPT — fail-closed restore regression и CI прошли.  
Дата: 2026-11-02.  
Тип: state persistence integrity; deterministic tests only.

## Наблюдаемая проблема

`PlanBStatePersistence.load_state()` оборачивает чтение JSON, восстановление risk manager, open positions и pending orders в общий `except Exception`, логирует ошибку и возвращает пустые `({}, {}, 0)`.

При включённом `restore_plan_b` конструктор движка после этого устанавливает `_state_restored=True`, но вызывающий код не получает исключение и не может отличить отсутствие файла от повреждённого backup. Пустое восстановленное состояние опасно: открытые позиции и pending orders могут существовать на бирже, а локальная копия будет выглядеть пустой.

Отсутствие файла — штатный cold start. Наличие файла, который не удаётся прочитать/валидировать, — не cold start.

## Предварительное решение

- Сохранить текущий штатный возврат пустого состояния, если файла нет.
- Если файл существует, но JSON/структура/состояние не восстанавливаются, выбросить явный `RuntimeError` с исходной причиной.
- Не возвращать пустые позиции после ошибки.
- Не менять формат backup, торговые параметры или live execution.

## Критерии проверки

1. Нет файла → пустое состояние без ошибки.
2. Корректный backup → точное восстановление risk flags, позиции, pending, trade_seq.
3. Повреждённый JSON → явная ошибка, не пустой state.
4. Неверная структура/позиция → явная ошибка.
5. Существующие deterministic tests и CI проходят.

## Границы

Это защищает от тихого сброса локального состояния, но не заменяет reconciliation с Bybit: backup может быть валидным и при этом устаревшим относительно реальных позиций/ордеров. До отдельной reconciliation-процедуры восстановленное состояние нельзя считать подтверждённым состоянием биржи.

## Решение

Решение: ACCEPT для исследовательского движка.

- Исправление: commit `ce6f3a1b3ba7b3277c9e8180fee799bf7dc67a9f`.
- Тесты и CI workflow: commits `1706cd3cf9f8e8022361b02c8e62516932f50dfc`, `d6f6d2374f93979e1253f6bf22fe5192f18ae471`, import-path correction `3bff014673d77ae7b6eddaa63aa010f6b89f08a0`.
- CI: [Research engine checks #41432693641](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41432693641), SUCCESS.
- `tests/test_state_persistence.py`: 4/4 — missing file cold start, valid round-trip, corrupt JSON rejection, invalid position shape rejection.
- Compile, all configured deterministic tests, secret scan passed.

Критерии выполнены. Market backtests не запускались.

ACCEPT означает только то, что существующий повреждённый backup больше не маскируется под пустое состояние. Восстановление всё ещё не доказывает соответствие локального backup фактическим позициям и ордерам Bybit; exchange reconciliation остаётся обязательной отдельной задачей перед live-resume.
