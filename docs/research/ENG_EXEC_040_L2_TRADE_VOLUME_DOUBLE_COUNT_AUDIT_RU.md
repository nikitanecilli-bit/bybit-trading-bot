# ENG-EXEC-040 — L2 reductions vs public trades: volume double-count audit

Дата: 2026-11-04

## Вопрос

Может ли текущий passive queue replay дважды списывать один и тот же объём: один раз по L2 уменьшению размера уровня, второй раз по публичной сделке, отражающей то же исполнение?

## Проверенный код

- `place_passive_order()` берёт `queue_ahead_initial` из отображаемого размера уровня в L2-книге. Книга должна иметь timestamp строго меньше arrival time.
- `apply_public_trade()` уменьшает `queue_ahead_remaining` только по публичной сделке на точной цене заявки, с противоположной стороной aggressor, после arrival и до expiry, исключая RPI и block trades.
- После arrival последующие L2 delta не передаются в `apply_public_trade()` и не уменьшают `queue_ahead_remaining`.
- Тест `test_l2_cancellations_and_new_size_do_not_rewrite_existing_queue_ahead` закрепляет, что последующие L2 reductions и additions не меняют уже созданную очередь.
- `replay_public_trades()` валидирует уникальность `trdMatchID` в архиве и хранит обработанные ключи (symbol, trade_id), чтобы повторное воспроизведение не учитывало match повторно.
- Replay использует только trade stream для последующего потребления queue-ahead и потенциальных fills. L2 после исходного snapshot не применяется как второй источник consumption.

## Вывод по двойному учёту

**Прямого двойного списания одного и того же объёма через L2 delta и public trade в текущем коде не обнаружено.** Причина — L2 delta после arrival не списывает объём очереди вообще; trade print является единственным механизмом consumption.

Это не доказывает точность replay:
- Нет cross-stream reconciliation по event identity/sequence.
- Нельзя определить, какая часть L2 уменьшения была исполнением, отменой или иным изменением агрегированного уровня.
- Нельзя проверить, что конкретный public trade соответствует конкретному L2 update.
- Исторический daily CSV trade `seq` остаётся неподтверждённым/неиспользуемым (см. ENG-EXEC-039).
- Same-ms ordering остаётся неразрешённым; консервативный no-same-ms policy сохранён.
- RPI/block prints исключаются из consumption; их влияние на агрегированный уровень не распределяется между очередью и исполнениями.

## Риск направления смещения

Текущая политика не даёт credit за L2 cancellations, что обычно консервативно для позиции в очереди. Но без cross-stream reconciliation нельзя утверждать, что replay является точной моделью fills. Нельзя автоматически добавлять L2 reduction consumption: это создало бы риск двойного учёта execution, если тот же объём уже присутствует в public trades. Нельзя также автоматически добавлять все trade prints поверх L2 reductions, пока L2 reductions не используются в consumption path.

## Решение

- Не менять код.
- Сохранить single-source consumption rule: только валидные public trades уменьшают queue-ahead после arrival.
- Сохранить L2 как pre-arrival snapshot/диагностический поток, а не второй канал consumption.
- Не заявлять maker execution realism или точную fill probability.
- Для более точной модели потребуется единая event timeline, проверенная cross-stream sequence/schema, явная классификация executions vs cancellations и правила level deletion/reappearance; даже это не устранит неопределённость aggregate L2 allocation между участниками очереди.

## Ограничения

- Статически проверены `bybit_l2_queue_replay.py`, связанные regression tests и ENG-EXEC-037.
- Архивы и API не запрашивались; тесты, replay, PnL/backtests, collectors, private API, runner и orders не запускались.
- Код/тесты не менялись. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`.
- `main` не изменён; PR #4 остаётся Draft/unmerged.
