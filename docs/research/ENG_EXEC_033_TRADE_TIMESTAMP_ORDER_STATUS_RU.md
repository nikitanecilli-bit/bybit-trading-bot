# ENG-EXEC-033 — Explicit trade timestamp ordering validity

Дата: 2026-11-04

## Наблюдение

Статический аудит сопоставил `scripts/inspect_bybit_trade_sample.py` с replay path. Inspector считал уменьшения timestamp в `nonmonotonic_timestamp_count`, но не давал отдельного machine-readable статуса пригодности порядка. При этом `replay_public_trades()` отклоняет регрессию времени. Поэтому downstream consumer мог увидеть общий `status: success` и не заметить, что архив несовместим с replay по хронологии.

## Исправление

- Добавлено `timestamp_order_validation_status` в validation report: `valid` только при нулевом числе регрессий, иначе `invalid`.
- Добавлен строгий classifier `trade_timestamp_order_status()`, отклоняющий bool/float/string/negative counts.
- Добавлен deterministic regression для valid/invalid и malformed classifier inputs.
- Сохраняется диагностический отчёт и счётчик нарушений; сканирование не прекращается на первом нарушении. Это не подменяет replay validation.

## Коммиты

- Source: `0c4cf2e2504d69d31d3113b0f408f2b236c3db09`.
- Tests: `6fc17e4d7f3274a8d4a609b845d658fd8010df15`.
- Branch: `research/market-regime-v1-main`.

## CI и gates

- Combined commit status пока пуст; тесты и CI для изменения не подтверждены.
- Никаких trade/L2 архивов не загружали; network inspector workflow не запускали.
- Нет PnL/backtest, collectors, private API, runner, paper/live orders.
- `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`; `main` не менялся; PR #4 не сливался.
