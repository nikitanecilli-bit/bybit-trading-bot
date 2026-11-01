# Execution realism readiness audit — 2026-11-02

Статус: статический аудит и проверка доступности источников; **новый market backtest не запускался**. Реальные ордера не размещались.

## Краткий вывод

Сейчас преждевременно делать выводы о реальной прибыльности E13/E11. Основные причины — Bybit-спецификации не удалось получить из GitHub Actions, sizing helper не подключён к движку, funding quantity пока proxy, а execution costs заданы константами и не измерены на реальном стакане.

Это не дефект, который надо «лечить» ещё одним стратегическим backtest. Это execution-data gate перед следующим сравнением.

## Подтверждённые факты

### 1. Нет сохранённого датированного Bybit instrument snapshot

- Каталог `data/instrument_specs/linear/` отсутствует в текущем дереве ветки; `data/` содержит только архивы CryptoFetch.
- Workflow [41358634175](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41358634175) и более поздний [41362639497](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362639497) завершились failure на получении данных.
- В последнем запуске последовательно проверялись `api.bybit.com`, `api.bytick.com`, `api.bybit.kz`, `api.bybit.nl`, `api.bybit.ae`, `api.bybit-tr.com`; каждый endpoint вернул HTTP 403. Сбой сетевого доступа, а не schema/parser.
- Я добавил параметр `--base-url` и fallback по региональным хостам. Исправление не помогло из-за блокировки всех шести хостов из GitHub runner.
- Workflow schedule будет исполняться только когда файл workflow находится в default branch; в research branch сейчас работают push/manual triggers, но не ежедневный cron.

Файлы: `scripts/snapshot_bybit_instruments.py`, `.github/workflows/bybit-instrument-snapshots.yml`.

### 2. Exchange sizing пока не участвует в расчёте сделок движка

- `bybit_instrument_specs.py` корректно описывает Decimal tick/qty/min/max ограничения.
- `instrument_spec_history.py` умеет выбирать последний snapshot не позже as-of и отклонять отсутствующий/неактивный символ.
- `exchange_order_sizing.py` умеет округлять qty вниз, применять tickSize, minNotional и maxMarketOrderQty/maxOrderQty.
- Но исследовательский движок импортирует `funding_accounting`, а не эти три модуля. `calculate_position_size()` в `Bybit_Trading_Engine_v14_research.py` возвращает notional в USDT и risk, а позиция не хранит фактическое количество контрактов. Сайзинг на основе реального `qtyStep` не включён в E11/E13.

Следствие: результаты текущего движка нельзя считать точным воспроизведением допустимых Bybit quantity/price increments, min-notional и market-order caps. На малых размерах позиции это может привести к существенным расхождениям или отклонению заявки.

### 3. Funding accounting улучшен, но quantity и settlement mark остаются proxy

- `funding_accounting.py` считает cumulative funding с правильным long/short sign, границей settlement и TP1 fraction.
- Количество рассчитывается как `size_usdt / entry_price`, а не из фактического exchange qty после qtyStep.
- Mark берётся из open mark-price candle с совпадающим timestamp; это timestamp-aligned proxy, не доказанная settlement mark цена Bybit.
- `validate_funding_coverage.py` проверяет совпадение timestamps и валидность значений, но не идентичность цены фактической settlement mark.
- В E13 funding вообще не включён; отчёт E13 прямо указывает это ограничение.

### 4. Execution cost assumptions не являются наблюдаемой Bybit microstructure

В движке зафиксированы:
- taker fee 0.055% на одну ногу;
- maker fee 0.020% на одну ногу;
- taker slippage 0.0225% на одну ногу.

E13 умножает fee/slippage константы на 2. Это полезный stress multiplier, но не оценка фактического spread/slippage по символу, времени и размеру заявки. В E13 нет order-book spread, queue priority, partial fills, cancellation latency, adverse selection и market impact. Поэтому maker fill или taker cost не подтверждены реальным исполнением.

Файлы: `Bybit_Trading_Engine_v14_research.py`, `scripts/run_e13_h1_compression_gate_replay.py`.

### 5. Bybit recent-data validation пока не дала независимого результата

Workflow `.github/workflows/bybit-recent-validation.yml` существует, manual-only, и пытается скачать H1 candles, mark и funding с нескольких региональных endpoint. В доступной истории Actions нет завершённого успешного run этого workflow. E11/E13 используют Binance OHLCV proxy, а не Bybit H1 candles.

## Приоритеты

| Priority | Пробел | Почему важен | Следующее безопасное действие |
|---|---|---|---|
| P0 research gate | Нет официального Bybit data/snapshot capture | Нельзя проверить execution assumptions на Bybit | Получить публичный snapshot/data через доступный network route и сохранить timestamp + SHA-256 |
| P1 | Exchange sizing не подключён к позиции | QtyStep/minNotional/maxQty не влияют на позиции | Интегрировать exact qty в research engine после получения snapshot; gross PnL, funding и risk считать от одного qty |
| P1 | Funding qty/mark proxy | Funding PnL не exact | Перейти на exact qty и источник settlement mark; coverage + reconciliation |
| P1 | Fee/slippage модель статична | Может перевернуть малый gross edge | Снять bid/ask или order-book snapshots для фиксированного списка символов и оценить spread/impact |
| P2 | Нет queue/partial-fill model | Maker result может быть завышен | Не тестировать maker edge до наличия L2/trade data; OHLC limit-touch считать верхней границей |

## Что не следует делать

- Не запускать новый PnL threshold sweep: текущая неопределённость execution выше возможного выигрыша от подбора сигнальных параметров.
- Не считать удвоенные fee/slippage заменой Bybit spread/order-book measurement.
- Не интегрировать текущие instrument helpers с выдуманными или недатированными specs.
- Не переносить E13 compression gate в production.

## Следующий план

1. Добиться одного успешно сохранённого полного linear instrument snapshot и сохранить источник, UTC timestamp, category, count, raw JSON и SHA-256.
2. Получить Bybit H1 + mark + funding для фиксированного universe без открытия/использования торговых ключей.
3. Сверить symbol coverage и timestamps, затем проверить exchange sizing на реальных спецификациях.
4. Только после этого — один execution-aware replay на уже замороженной стратегии/параметрах, без повторного выбора порогов.
5. Отдельно оставить maker execution как upper-bound, пока не появятся bid/ask/L2 данные.

## CI

- Research engine checks run [41362633014](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362633014): success; compile, instrument specs, snapshot collector, as-of history, exchange sizing, funding accounting/MTM/coverage, regime, gap/time, portfolio tests и secret scan.
- Это подтверждает тестируемую корректность вспомогательных функций, но **не** наличие Bybit snapshot и не корректность реального исполнения.

## Изменения в этой проверке

- Добавлен `--base-url` в snapshot collector.
- Workflow пробует шесть региональных Bybit API hosts, аналогично recent-data downloader.
- Fallback проверен в GitHub Actions; все шесть hosts вернули 403. Никакие данные не записаны и исходные архивы не затронуты.

**Решение:** execution realism gate пока не пройден. Следующий стратегический backtest отложить до появления проверяемого Bybit data + dated instrument snapshot.
