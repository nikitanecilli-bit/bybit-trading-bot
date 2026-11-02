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

## 7. Исправлено расписание instrument snapshots

Официальная документация предупреждает, что `maxLimitOrderQty`, `maxMarketOrderQty` и `postOnlyMaxLimitOrderSize` пересматриваются 3-го и 17-го числа месяца. Исходный weekly Monday cron мог не снять snapshot непосредственно после этих изменений. Расписание `.github/workflows/bybit-instrument-snapshots.yml` изменено на 3-е и 17-е число в 02:17 UTC (10:17 UTC+8), после указанного Bybit времени обновления 08:00 UTC+8. Workflow dispatch сохранён. Это только изменение расписания; API workflow не запускался и snapshot не получен.

## 8. Дополнительные fail-closed дефекты InstrumentSpec закрыты

При повторной проверке обнаружены ещё три ограничения текущего sizing helper:

1. Parser не читал `priceFilter.minPrice/maxPrice`, хотя Linear V5 их публикует. Лимитная цена могла быть tick-aligned, но находиться за биржевым диапазоном.
2. Parser принимал явно указанный category, отличный от `linear`, хотя helper рассчитывает USDT linear notional как qty × price. Это могло ошибочно применить linear semantics к другому контрактному типу.
3. `validate_order()` не блокировал инструменты со статусом `PendingOpen`/unknown; V5 возвращает PendingOpen в общем наборе, но размещать ордер до Trading нельзя.

Минимальное fail-closed исправление внесено в `bybit_instrument_specs.py`:
- явно отвергать category != linear;
- парсить обязательные `minPrice/maxPrice`, проверять диапазон и tick-rounded limit price;
- отклонять sizing при `status != Trading`.

Регрессионные тесты добавлены в `tests/test_bybit_instrument_specs.py` и `tests/test_exchange_order_sizing.py`. GitHub Actions Research engine checks #631 (parser) и #632 (tests) были запущены автоматически на push и на момент фиксации аудита находились `in_progress`; итог пока не заявляется. Предыдущий run #630 завершился success и включал базовые тесты parser/sizing, но не новые регрессии.

Это исправление локально закрывает ограничения helper; оно не меняет подтверждённый integration gap с основным engine и не превращает notional proxy backtest в contract-accurate replay.

## 9. Доказательство недоступности Bybit API из GitHub Actions

Получены jobs и decoded logs для существующих запусков instrument snapshot workflow #7–#10. Во всех попытках API hosts возвращали HTTP 403; затем workflow завершался exit code 1, snapshot commit step пропускался. В логах также есть отказ host validation для одного из fallback hosts. Это подтверждает сетевую/API access проблему на runner, а не отсутствие endpoint или ошибку JSON schema. Не предпринимать обход географических/сетевых ограничений; получать официальный snapshot из разрешённой пользователем среды или ждать исправления доступности.

## 10. Официальные региональные API hosts и workflow triggers

По текущей Bybit Integration Guidance официальный список mainnet hosts включает `api.bybit.com`, `api.bytick.com`, `api.bybit.tr`, `api.bybit.kz`, `api.bybitgeorgia.ge`, `api.bybit.ae`, `api.bybit.eu`, `api.bybit.id`. Документация прямо говорит, что IP из США и Mainland China получают HTTP 403; для EEA API отдельно указано ограничение для API broker users. Фактическая география egress GitHub runner в проверенных логах не установлена, поэтому 403 нельзя приписывать конкретной стране без IP evidence.

Устаревший Netherlands host был удалён из Integration Guidance 2026-09-22; в workflow ошибочно использовался `api.bybit-tr.com` вместо официального `api.bybit.tr`. Исправлены allowlists обоих snapshot scripts, host lists всех трёх market-data workflows и соответствующие tests. Официальные домены проверяются unit tests; retired/invalid hosts отвергаются.

GitHub Actions trigger semantics: scheduled workflows run only on default branch, and `workflow_dispatch` only receives events when workflow file exists on default branch. Три snapshot/archive workflow существуют только в research branch (проверка main вернула 404). Чтобы instrument/risk snapshots можно было валидировать без изменения main, добавлен branch-scoped `push` trigger с paths filter к обоим snapshot workflows. Schedule и workflow_dispatch оставлены как future-ready, но до появления этих файлов в default branch не являются действующими триггерами. Market-history archive остаётся manual-only и не может быть dispatch-нут из branch-only workflow через GitHub UI/API.

CI evidence:
- Research engine checks run #41533273830, commit `e55aa6b46b7ab2ab0a06060fa12da70a49c20082`: success; full deterministic suite including updated InstrumentSpec parser, as-of history, and exchange sizing.
- Research engine checks #41533575723, commit `e5256757dc088d27b0081302639392de9a3255a3`: success; official/retired host allowlist tests for instrument collector.
- Research engine checks #41533598553, commit `032a97bc18ad7eb28f750f565c0dd86f3a90db6c`: success; full deterministic suite including risk-limit host allowlist tests.
- Instrument snapshot workflow #41533728951 was triggered by the new branch-scoped push trigger; result is being checked separately. No risk-limit snapshot success or real data archive is claimed.

Sources:
- Bybit Integration Guidance: https://bybit-exchange.github.io/docs/v5/guide
- Bybit V5 changelog (2026-09-22 removed Netherlands domain): https://bybit-exchange.github.io/docs/changelog/v5
- GitHub workflow syntax / events: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax and https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

## 11. Проверка новых branch-scoped API runs завершена

- Instrument snapshot workflow run `41533728951` failed at download step. После исправления host list логи показывают HTTP 403 для каждого официального host, включённого в workflow: api.bybit.com, api.bytick.com, api.bybit.kz, api.bybit.tr, api.bybitgeorgia.ge, api.bybit.ae, api.bybit.id. Snapshot commit step skipped.
- Risk-limit snapshot workflow run `41533743884` также failed at download step; все перечисленные host attempts returned HTTP 403. Никаких risk-tier rows или dated archive не получено.
- Это окончательно подтверждает текущий runner-level API access blocker. Повторять те же GET-запросы или добавлять случайные домены бессмысленно. Следующее получение snapshot должно происходить из разрешённой среды/канала с доступом к официальному API; никаких geo/network bypass действий.
- Latest deterministic Research CI at this point: #41533598553 success after the official-host allowlist tests. Snapshot workflow failures are data-access failures, not deterministic code test failures.

## 12. В репозитории не обнаружен live order adapter

Проверены root tree, `Bybit_Trading_Engine_v14_research.py`, `bybit_downloader.py`, `bybit_reconciliation.py`, `README.md` и список `scripts/`. В исследовательском движке нет `/v5/order/create`, `order/create`, `place_order`, `create_order` или вызова pybit; единственный `urllib.request.Request` в engine не является order submission. Скрипты содержат downloader, read-only credential/API check, read-only reconciliation, backtests, reports и snapshot collectors.

Следовательно, точнее говорить: в текущем исследовательском репозитории не обнаружен production/live execution adapter. Предыдущий integration gap относится к контрактно-точному sizing внутри research engine; интеграция в live adapter — отдельная будущая задача после создания/аудита этого adapter. Никаких ордеров не отправлялось.

## 13. API workflows no longer iterate across regional domains

После подтверждения 403 на каждом официальном host удалён fallback-loop по разным юрисдикциям. Instrument, risk-limit и market-history workflows теперь используют один явно настроенный `BYBIT_API_BASE_URL` из repository variable; default — `https://api.bybit.com`. Сам downloader всё равно проверяет host по allowlist официальных доменов. Это исключает случайное переключение регионов в попытке обойти 403 и позволяет владельцу репозитория выбрать только домен своего разрешённого сайта/API.

Проверка нового поведения:
- instrument workflow run `41534141800`: использовал только default `https://api.bybit.com`, получил HTTP 403, snapshot не создан;
- risk-limit workflow run `41534156659`: использовал только default `https://api.bybit.com`, получил HTTP 403, snapshot не создан.

Для изменения домена владелец может задать repository variable `BYBIT_API_BASE_URL` на официальное значение своего региона. Это не API secret. Никакие приватные credentials не нужны для этих public GET endpoints.
