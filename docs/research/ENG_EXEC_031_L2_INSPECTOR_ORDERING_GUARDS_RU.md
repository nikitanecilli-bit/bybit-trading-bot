# ENG-EXEC-031 — Fail-closed ordering checks in the standalone L2 inspector

Дата: 2026-11-04

## Контекст

Статическое сравнение `scripts/inspect_bybit_orderbook_sample.py` с уже принятыми правилами replay показало, что inspector считал нарушения `seq` диагностическим счётчиком, но продолжал реконструировать книгу; для matching-engine `cts` отдельной проверки порядка не было. Это позволяло получить успешный inspection report при нарушенной хронологии.

## Изменение

- Если `cts` присутствует, inspector отклоняет уменьшение относительно предыдущего присутствующего `cts`; отсутствующий/null `cts` по-прежнему учитывается отдельным счётчиком.
- Inspector отклоняет уменьшение `seq` по всему архиву, включая события после иных временных границ; равные значения разрешены.
- Сохраняется правило `u=1` только для полного snapshot.
- Не вводится неподтверждённое требование `u+1` и не добавляется новое archive-wide monotonicity правило для `u`; это соответствует ранее зафиксированному ограничению применимости depth-200 archive contract в checkpoint §33.
- Добавлены deterministic regressions для cts/seq regressions и корректного `u=1` snapshot reset.

## Коммиты

- Source: `614b80d29db6a7d9f25f27691268a69d62ad0d06`.
- Tests: `0a0b51d39ebd107749cb8c7ebc9f81d88ca96504`.
- Рабочая ветка: `research/market-regime-v1-main`.

## Проверка и ограничения

- GitHub commit и файлы проверены после записи.
- Combined commit statuses на test commit не вернули checks; доступный workflow-runs connector фильтрует PR-triggered runs, а Research CI workflow настроен на push в рабочую ветку. Поэтому завершение нового CI и фактическое число тестов пока НЕ подтверждены. Последний ранее подтверждённый Research CI остаётся #41885051272 на commit `948c7a1` (57/57 steps); он не покрывает эти новые изменения.
- Это data-integrity guardrail, не execution evidence и не PnL.
- Новые архивы не скачивались; network inspector, collectors, market/PnL replay, private API, runner и paper/live orders не запускались.
- `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` без изменений.
- `main` не изменялся; PR #4 остаётся Draft и не сливался.
