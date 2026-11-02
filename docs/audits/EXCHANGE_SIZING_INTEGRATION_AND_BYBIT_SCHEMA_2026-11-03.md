# Аудит интеграции exchange sizing и официальных Bybit V5 спецификаций

Дата: 2026-11-03
Статус: CONFIRMED INTEGRATION GAP; instrument field parser matches current Linear schema.
Ветка: `research/market-regime-v1-main`.

## 1. Уточнение по полям instruments-info

Первоначальная гипотеза о несовпадении полей была отклонена после проверки раздела Linear/Inverse официальной документации Bybit V5.

Для Linear/Inverse Bybit документирует:
- `priceFilter.tickSize`
- `lotSizeFilter.minNotionalValue`
- `lotSizeFilter.maxOrderQty` — limit/post-only
- `lotSizeFilter.maxMktOrderQty` — market
- `lotSizeFilter.minOrderQty`
- `lotSizeFilter.qtyStep`
- `leverageFilter.minLeverage/maxLeverage/leverageStep`

Это соответствует `InstrumentSpec.from_snapshot()` и `InstrumentSpec.validate_order()`. Поля `minOrderAmt/maxLimitOrderQty/maxMarketOrderQty` относятся к Spot-подсекции документации и не должны переноситься в Linear parser.

Источник: Bybit V5 Get Instruments Info, раздел Linear/Inverse, https://bybit-exchange.github.io/docs/v5/market/instrument

## 2. Подтверждённый разрыв интеграции

Модули `bybit_instrument_specs.py` и `exchange_order_sizing.py` реализуют Decimal parsing, tick/qty rounding, min/max quantity and min-notional checks, а также risk scaling после округления.

Однако основной `UnifiedQuantEngine._try_fill_pending()`:
1. вызывает `risk_mgr.calculate_position_size()`, который возвращает `size_usdt` notional proxy и `risk_usdt`;
2. создаёт `OpenPositionState` только с `size_usdt` и `risk_usdt`;
3. не загружает `InstrumentSpec`;
4. не вызывает `size_to_exchange_constraints()`;
5. не сохраняет точный contract quantity.

Далее TP1 реализуется как доля `size_usdt`, funding/MTM и PnL тоже используют notional proxy. Поэтому qtyStep rounding, minNotional, отдельные market/limit max qty и реальное количество контрактов не влияют на сделки основного движка.

Это подтверждённый пробел в integration/execution realism, не ошибка самого Decimal helper и не утверждение, что backtest arithmetic внутри текущей proxy-модели неверен.

## 3. Официальный источник risk tiers существует

Bybit V5 предоставляет публичный GET `/v5/market/risk-limit`:
- для `linear` ответ пагинируется, по 15 символов на страницу;
- поля включают `id`, `symbol`, `riskLimitValue`, `maintenanceMargin`, `initialMargin`, `maxLeverage`, `mmDeduction`.

Источник: https://bybit-exchange.github.io/docs/v5/market/risk-limit

Следовательно, risk-tier таблицу не требуется выдумывать. Но в этой сессии нет подтверждённого свежего API payload, пригодного для архивирования: прежние запросы к Bybit API из GitHub Actions завершались HTTP 403 на сетевом edge. Документация подтверждает структуру endpoint, но не подменяет датированный snapshot значений.

## 4. Формулы и ограничения

Для USDT isolated Bybit публикует формулы liquidation price long/short, использующие entry price, quantity, leverage, extra margin, taker fee, MMR и MM deduction. Для cross/UTA liquidation trigger определяется account-level MMR; единственная позиционная формула isolated не является корректной заменой cross account engine.

Источники:
- https://www.bybit.kz/en-KAZ/help-center/article/Liquidation-Price-Calculation-under-Isolated-Margin-Unified-Trading-Account
- https://www.bybit.com/en/help-center/article/Maintenance-Margin-USDT-Contract
- https://www.fbybit.com/en/help-center/article/FAQ-Order-Execution-and-Liquidation

Позиционные risk tiers могут изменяться с mark price. Поэтому нельзя выбрать tier один раз по entry notional и считать полученную liquidation price точной без проверки piecewise tier consistency. Cross margin также требует общего collateral/equity/MMR портфеля и учета других позиций/ордеров.

## 5. Решение / следующий безопасный шаг

- Не переписывать Linear parser: поля соответствуют официальной схеме.
- Не считать текущий backtest Bybit contract-accurate: sizing helper не подключён к engine lifecycle.
- Перед подключением exact qty необходимо расширить OpenPositionState/TradeRecord с qty, qty_step snapshot id, contract value semantics и actual filled quantity; TP1/remaining qty/funding/PnL должны использовать qty, а не долю notional proxy.
- Ввести versioned archived instrument snapshots и risk-tier snapshots с fetched_at, category, symbol, schema version, raw payload hash.
- Реализовать isolated liquidation calculator только после появления реальных risk-tier fixtures; обязательно решать piecewise tier transitions и проверять mark-price trigger.
- Cross mode оставить BLOCKED до явной account-mode specification и account-level collateral/MMR model.
- Любой новый margin calculator сначала покрыть deterministic tests, затем подтвердить CI. Не заявлять execution realism или live readiness на основании одного isolated formula.

## Вывод

`LINEAR INSTRUMENT FIELD PARSER: PASS (static schema review)`.
`EXCHANGE SIZING HELPER: PASS (unit-test inventory present; not rerun in this session)`.
`ENGINE INTEGRATION: FAIL / NOT WIRED`.
`RISK-TIER SNAPSHOT: NOT ACQUIRED`.
`ISOLATED LIQUIDATION: NOT IMPLEMENTED`.
`CROSS/UTA PORTFOLIO LIQUIDATION: NOT IMPLEMENTED`.

## 6. Snapshot automation already exists; data still unverified

The branch already contains:
- `.github/workflows/bybit-instrument-snapshots.yml` (weekly schedule + workflow_dispatch; retries a list of official regional API hosts);
- `.github/workflows/bybit-risk-limit-snapshots.yml` (same pattern for risk tiers);
- `scripts/snapshot_bybit_instruments.py`;
- `scripts/snapshot_bybit_risk_limits.py`.

These workflows check out `research/market-regime-v1-main` and commit snapshots under `data/instrument_specs/linear` and `data/instrument_specs/risk_limits`. However, direct repository-content checks for both expected output directories returned 404 at audit time. Thus workflow definitions and snapshot code exist, but a committed dated dataset was not verified. No workflow dispatch action is exposed through the connected GitHub tools in this session, so neither workflow was triggered and no run result is claimed.

This changes the next action: first inspect the next scheduled/manual workflow result and validate the raw snapshots; do not create a duplicate downloader or duplicate scheduled workflow.
