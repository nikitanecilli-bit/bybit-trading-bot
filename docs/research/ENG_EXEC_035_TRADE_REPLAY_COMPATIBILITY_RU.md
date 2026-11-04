# ENG-EXEC-035 — Explicit queue-replay compatibility and empty-archive handling

Дата: 2026-11-04

## Наблюдение

Trade inspector возвращал общий `status: success` после полного сканирования даже когда отдельные validation blocks показывали отсутствие trade IDs или BT/RPI flags либо timestamp regression. Это могло быть неверно истолковано как готовность архива к queue replay. Также header-only CSV давал нулевое число сделок, но расчёт duration пытался вычесть пустые timestamp bounds.

## Исправление

- Добавлен агрегированный `queue_replay_compatibility_status`. Он равен `valid` только когда timestamp ordering, trade ID, RPI flag и block-trade flag имеют статус `valid` и число строк больше нуля.
- Для нулевого числа строк агрегированный статус — `invalid_or_incomplete`.
- `duration_hours` теперь равен null для архива без строк, вместо арифметической ошибки.
- Общий `status: success` оставлен как статус завершения сканирования, не как подтверждение replay-совместимости.
- Добавлены регрессии на aggregate status и пустой архив.

## Коммиты и CI

- Inspector logic: `86a0590f6c9978675426523ba8d86ddc3fdc8b85`, `68ee303ea44744950881033f9c4660912ee8ae9e`.
- Tests: `8311daa4c4f63cebaf00d1b9bc3f5dbfe91ca381`, `82852d6f82f4a619a8838db50dcc9431e04560cb`.
- CI: Research engine checks run `41888048946`, commit `82852d6`, completed successfully. The job log confirms the compatibility regression and the strict CSV/report-writer tests passed.
- Intermediate run `41888039132` failed because the code signature gained a row_count argument before its test call was updated; the immediately following test commit fixed the call, and run `41888048946` passed.

## Gates

No archive downloads, collectors, network inspector workflow, market PnL/backtests, private API, runner, paper/live orders. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`. `main` unchanged; PR #4 remains Draft/unmerged.
