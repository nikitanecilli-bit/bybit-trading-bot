# ENG-EXEC-036 — L2 inspector/replay compatibility boundary

Дата: 2026-11-04

## Находка

Статическое сравнение `scripts/inspect_bybit_orderbook_sample.py` и `bybit_l2_queue_replay.py` выявило различия, которые могут быть неверно поняты при чтении отчётов:

- L2 inspector допускает отсутствующий `cts` у отдельного события, учитывая его в `missing_cts_count`; верхний `status: success` означает, что сканирование завершилось, а не что архив пригоден для queue replay.
- Queue replay требует целочисленный `cts` у каждого события, так как без него нельзя построить pre-arrival snapshot или проверить временную последовательность.
- Inspector отклоняет регрессии `cts` и `seq`, но не применяет archive-wide monotonicity rule к `u`; replay через `OrderBook.apply()` отклоняет уменьшение `u`, кроме полного snapshot с reset marker `u=1`.
- Документ ENG-EXEC-031 намеренно не вводит универсальное правило `u+1` или archive-wide monotonicity для inspector, поскольку контракт глубины-200 и семантика всех reset/update последовательностей не подтверждены.

## Вывод и решение

Это не доказательство ошибки реконструкции книги: inspector — диагностический сканер, replay — более строгий потребитель данных. Однако их результаты нельзя считать взаимозаменяемыми. Успешный L2 inspection не является подтверждением replay compatibility. До получения подтверждённой спецификации архива не менять правила `u` и не ослаблять строгую проверку `cts` в replay.

Следующее улучшение — явно маркировать в L2 inspector различие между scan completion и replay compatibility, а также отдельно учитывать missing `cts` и update-ID regressions как compatibility dimensions. Изменение пока не внесено.

## Проверки и ограничения

- Только статический аудит исходников и тестов; market archives не скачивались.
- Network inspector workflow, collectors, queue replay, market PnL/backtests, private API, runner и paper/live orders не запускались.
- Нет нового CI run и нет нового code change.
- `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` без изменений.
- `main` не изменён; PR #4 не сливался.
