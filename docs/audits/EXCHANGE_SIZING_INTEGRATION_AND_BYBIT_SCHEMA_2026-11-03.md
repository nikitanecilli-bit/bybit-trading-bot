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

## 14. Max order quantity fields are now mandatory

Ещё один fail-open путь: `maxOrderQty` и `maxMktOrderQty` ранее парсились как optional, а `validate_order()` пропускал max cap при `None`. В актуальной Bybit Linear schema оба поля присутствуют в `lotSizeFilter`; их отсутствие означает неполную спецификацию, а не отсутствие лимита. Оба поля теперь обязательны при создании `InstrumentSpec`; добавлен тест, который удаляет каждое поле по отдельности и требует fail-closed ValueError.

CI:
- #41534399745, commit `2ec1c2b22e0521e370281e1f16d4724862fb138e`: success, parser and full deterministic suite.
- #41534426284, commit `fb73773944a8dc289f84621dfb2ff88cbdb12aa4`: success, including missing-max-cap regression.

Таким образом, helper's static validation now fails closed for missing price bounds, quantity caps, min qty/notional, wrong category, and non-Trading status. This does not close the engine exact-qty integration gap.

## 15. Исправлена комиссия/проскальзывание выхода по execution notional

### Подтверждённый дефект

До исправления `_close_position()` считал комиссию и slippage TP1 и финального выхода от первоначального `pos.size_usdt` × fraction, то есть от entry notional. `_unrealized_pnl_at_marks()` делал то же самое для TP1 и оставшегося выхода. Но для USDT linear фактическая торговая комиссия считается от `executed quantity × executed price × fee rate`; на входе и выходе цены могут различаться. Официальный Bybit USDT P&L guide показывает отдельные формулы Fee to open = Qty × Entry Price × Rate и Fee to close = Qty × Exit Price × Rate.

Это давало направленную ошибку:
- прибыльный long / прибыльный short с выходом по более низкой цене: exit fee/slippage были занижены, net PnL завышен;
- убыточный long / убыточный short с выходом по более высокой цене: exit fee/slippage были завышены, net PnL занижен;
- TP1/остаток также оценивались по entry notional, а не по фактическим модельным ценам своих legs.

### Исправление

В `Bybit_Trading_Engine_v14_research.py`:
- proxy quantity = `size_usdt / entry_price`;
- TP1 execution notional = `quantity × tp1_price × TP1_FRACTION`;
- final execution notional = `quantity × exit_price × remaining_fraction`;
- MTM TP1/remaining exit costs используют соответственно `tp1_price` и текущий adverse mark;
- entry fee/slippage остаются на entry notional;
- risk sizing exit fee/slippage до стопа умножаются на `stop_price / entry_price`, поскольку stop exit notional отличается от entry notional. Нулевая/отрицательная stop price fail-closed отклоняется.

Gross PnL и funding уже используют эквивалентный qty proxy (`size_usdt / entry_price`) и price movement/mark; этот patch синхронизировал с ним fee/slippage legs. Точный биржевой qty всё ещё не используется: он остаётся отдельным integration blocker.

### Регрессионные проверки

Обновлены `tests/test_portfolio_accounting.py`, `tests/test_gap_execution.py`, `tests/test_time_model.py`:
- long stop 100→95: exit notional 950 вместо 1,000;
- short stop 100→105: exit notional 1,050;
- long gap stop 100→90: exit notional 900;
- TP1 110 на половине qty и TP2 120 на остатке: fees на notional 1,000 + 550 + 600;
- TP1 maker + trailing taker stop: отдельные maker/taker notional per leg;
- MTM fee reserve рассчитывается на текущем adverse mark и TP1 fill price;
- stop-risk estimate учитывает exit notional по stop price.

Research engine checks run `41536540759`, commit `4eb9a2e7d7fc6a198937ef028dec32a5f723e22d`: SUCCESS; все 31 job steps, включая portfolio accounting, gap execution, time model, funding, sizing, state persistence, режимные фильтры и secret scan.

Same-bar order-invariance test допускает максимум (2×10^{-6}) процентного пункта расхождения max-DD из-за 4-decimal equity rounding; realized PnL, final equity и MTM остаются проверены отдельно и инвариантны.

### Последствия для старых результатов

Результаты 50-symbol H1 screen (включая 14/50 net-positive кандидатов) и прежние 15m/H1 сравнения теперь считаются PROVISIONAL до повторного расчёта на исправленном engine. Старый fee formula занижал costs прибыльных exits и завышал costs убыточных exits. Совокупное влияние на старые PnL и ранжирование ещё не пересчитано. Новые market backtests остаются заблокированы до закрытия remaining execution/data realism gate; этот patch сам по себе не разрешает новый strategy sweep.

### Оставшиеся fee assumptions

Rates `TAKER_FEE=0.00055`, `MAKER_FEE=0.00020`, `TAKER_SLIP=0.000225` остаются фиксированными research assumptions. Фактический VIP tier и региональные account fee rates не подключены. Maker fill still assumes touch/fill and lacks queue/partial-fill/adverse-selection model.

Источник формулы: https://www.bybit.com/en/help-center/article/Profit-Loss-calculations-USDT-Contract

## 16. Точный qty: implementation map and migration requirements

Static call-site mapping for the next implementation (not yet coded):

1. **Spec resolution / entry:** `UnifiedQuantEngine._try_fill_pending()` currently receives `size_usdt, risk_usdt` from `calculate_position_size()` and stores notional proxy. Resolve an immutable point-in-time Linear `InstrumentSpec` for symbol and entry timestamp; call `size_to_exchange_constraints()` after choosing modeled fill price; reject if min/max/qtyStep/minNotional fails. Recompute risk from final rounded qty and actual entry/stop prices, not from pre-round target notional.
2. **Position state:** extend `OpenPositionState` with requested qty, actual modeled filled qty, remaining qty, and spec snapshot identifier/hash/fetched_at. Do not reconstruct actual qty from rounded notional after entry.
3. **Partial TP1:** `_apply_tp1()` currently uses fixed `TP1_FRACTION` and `remaining_fraction`. Replace with step-rounded `tp1_qty` and exact `remaining_qty = entry_qty - tp1_qty`; verify both legs meet minQty/qtyStep/minNotional. If no valid split exists, define an explicit policy (skip partial TP1 or close full position); never send an invalid half-qty.
4. **PnL and costs:** unrealized/realized linear PnL = signed `qty × (mark/exit_price - entry_price)`; fee/slippage per leg = actual leg qty × modeled execution price × rate. TP1 and final exit quantities must sum to entry filled qty exactly.
5. **Funding:** `funding_accounting.accrued_funding_cost()` currently derives qty as `size_usdt / entry_price`. Use stored actual qty and remaining qty; settlement quantity at TP1/close boundaries must follow the existing conservative event-order policy.
6. **Journal:** extend `TradeRecord` with entry/TP1/final executed qty and spec snapshot reference; keep `size_usdt` only as descriptive entry notional, not as canonical position size.
7. **Persistence:** `PlanBStatePersistence` serializes `asdict(pos)`, checks strict `known`/required/numeric field sets and constructs `OpenPositionState(**pos_dict)`. Adding qty requires a schema version bump and explicit migration/rejection policy for old backups. Never infer live open-order qty from an old notional-only backup.
8. **Margin/liquidation:** only after qty is canonical and dated risk tiers exist; isolated calculator first. Cross/UTA remains a separate account-level project.

Required tests before market PnL sweeps: arbitrary qtyStep (including odd step counts), minQty/minNotional boundary, market-vs-limit max caps, long/short entry sizing after qty rounding, TP1 split valid/invalid, TP1+final quantity conservation, gap exit, mark-to-market, funding at entry/TP1/close boundary, save/restore schema migration, and portfolio multi-symbol order invariance.

Current blocker: no committed dated Bybit instrument/risk-limit snapshots; both snapshot workflows fail HTTP 403 on the configured default host. Therefore this section is a design checklist only; do not substitute invented instrument specs or risk tiers.
