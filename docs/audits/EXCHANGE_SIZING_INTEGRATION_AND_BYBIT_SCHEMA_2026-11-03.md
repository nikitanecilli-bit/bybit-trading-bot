# Аудит интеграции exchange sizing и официальных Bybit V5 спецификаций

> **Актуальный статус на 2026-11-03:** этот документ фиксирует более ранний этап до ENG-EXEC-009–014. Exchange-valid sizing и dated risk-tier lookup теперь подключены в `UnifiedQuantEngine._try_fill_pending()`; H1 runner требует Bybit-native candles, funding/Mark OHLC и исторически покрывающие instrument/risk-tier snapshots. Поэтому утверждения ниже о том, что sizing не подключён к engine, следует читать как исторические и superseded. Текущая реализация и оставшиеся ограничения описаны в [Execution integration re-audit](EXECUTION_INTEGRATION_REAUDIT_2026-11-03.md). Снимки и полноценные Bybit market archives пока отсутствуют; это не снимает P0 data gate.


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


## 16. Optional strict integration into research engine

The research engine now accepts `instrument_specs_dir` and loads `InstrumentSpecHistory` only when this explicit argument is supplied. In that mode, each entry:
1. selects the newest complete linear snapshot at or before the entry candle timestamp, with a default maximum age of 30 days;
2. rejects missing/stale symbols and non-Trading instruments;
3. validates configured leverage against dated min/max/step;
4. converts the risk-sized notional to Decimal quantity, floors to qtyStep, and applies the correct market/limit maximum, minOrderQty and minNotionalValue;
5. uses the actual modeled fill price (not a newly rounded quote) and still enforces tick alignment for limit fills;
6. reduces stored position notional and risk in proportion to the floored quantity, so downstream linear PnL/funding calculations derive the same contract quantity from notional / entry price.

There is intentionally no silent fallback: if the directory is supplied but the dated spec is absent, stale, non-trading, leverage-invalid, or violates exchange constraints, the entry is rejected. If no directory is supplied, legacy notional-proxy mode remains for backwards-compatible research and is explicitly **not contract-accurate**.

The H1 runner has not yet been switched to strict mode because the repository currently contains no archived `data/instrument_specs/linear/*.json` snapshots and the Bybit snapshot workflow has repeatedly received HTTP 403. Therefore no existing H1 PnL or experiment result is retroactively upgraded by this integration. Synthetic regression tests exercise the strict path; an actual market replay remains blocked on dated official snapshots.


## 17. Strict engine integration CI verification

Research engine checks [#41543597235](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41543597235) completed with **SUCCESS** on commit `550d0c03b830aad99203bca078c078ed204583c5`. The run passed:
- Python compilation;
- dated InstrumentSpec parser and as-of history tests;
- Decimal exchange sizing and leverage-filter tests;
- strict engine entry integration tests (qtyStep/minNotional and missing-snapshot fail-closed);
- existing gap execution, portfolio accounting, funding, state-persistence and all other deterministic suites.

Two intermediate CI failures were corrected before this successful run: first the sizing fixture lacked leverageFilter fields; then older unit-test harnesses constructed the engine with `__new__` and therefore lacked the new optional attributes. The engine now uses a backward-compatible `getattr` guard while retaining strict behavior whenever an instrument-spec history is explicitly supplied.

This is code-path verification with synthetic specs only. It does not establish that dated Bybit snapshots exist for the historical E11/E13 periods, nor does it validate actual Bybit fills, funding, margin tiers or liquidation.


## 18. Remaining lifecycle limitation after entry-side integration

The strict path currently validates and floors the **opening order quantity** only. It does not yet validate the modeled TP1 partial close, final close, or any future reduce-only order quantity against qtyStep/minOrderQty/minNotionalValue. The engine still models TP1 as a 50% fractional reduction and reconstructs linear quantity downstream from `size_usdt / entry_price` (stored as float notional), rather than persisting the Decimal contract quantity as first-class position state.

Therefore this change closes the entry sizing integration gap, but **does not make the entire position lifecycle exchange-quantity exact**. Before claiming contract-accurate replay, add persisted contract quantity and dated lot constraints to position state; quantize partial and final reduce-only quantities; reconcile any residual dust; and test minimum-close behavior. Liquidation/margin remains a separate open gate.


## 19. Retired Bybit API host allowlist defect

A cross-repository allowlist scan found that `scripts/archive_bybit_market_history.py` still accepted the retired/unofficial hosts `api.bybit.nl` and `api.bybit-tr.com`, despite the instrument and risk-limit collectors already using the current official host set. Both hosts have been removed. The market-history collector tests now positively enumerate current official hosts and reject both retired hosts.

Research CI run [#41544092796](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41544092796), on code commit `2a0e0b958148f1bd69d43e4386c0487166eaa6d6`, shows compilation and every functional test step completed successfully, including the revised market-history host allowlist tests. At the last status check, GitHub was still executing the `Post Check out repository` cleanup step; no functional test remained pending. The subsequent documentation-only commit does not alter tested code.

No request was sent to either retired host.


## 20. Confirmed remaining lifecycle and risk-tier blockers

A source-level follow-up after the successful entry-sizing CI confirms three distinct limits:

1. **Partial-close quantity is still fractional, not exchange-quantized.** `OpenPositionState` persists `size_usdt` and `remaining_fraction`, but no first-class contract quantity, TP1 quantity, or remaining contract quantity. `_apply_tp1()` uses the fixed `TP1_FRACTION` and `_close_position()` reconstructs quantity as `size_usdt / entry_price`. Example: with `qtyStep=0.1` and an entry quantity of `0.1`, the modeled 50% TP1 close is `0.05`, which is not a valid quantity step. The engine therefore cannot claim that TP1/final reduce-only legs are exchange-valid. This must be fixed with persisted Decimal-compatible quantity state, quantized TP1/remainder allocation, min-close handling, and dust reconciliation before any contract-accurate replay.

2. **Risk-limit tiers are collected and validated, but not consumed by sizing.** `InstrumentSpec.validate_leverage()` checks the instrument-level leverageFilter only. It does not select a risk tier by position value, enforce the tier-specific `maxLeverage`, or calculate initial/maintenance margin and liquidation. The existing risk-tier snapshot collector validates tier data integrity and mmDeduction recurrence, but no engine path loads those tier snapshots. Instrument-level leverage acceptance is therefore not proof that a given notional is allowed at that leverage.

3. **The H1 runner remains in legacy proxy mode.** `scripts/run_h1_shared_capital_portfolio_validation.py` instantiates `UnifiedQuantEngine` without `instrument_specs_dir`; it does not activate the optional strict entry sizing path. The strict entry integration is currently covered only by synthetic unit fixtures. Existing H1 and E11/E13 results remain notional-proxy research results and are not upgraded by the new tests.

**Execution gate remains BLOCKED.** Do not run or publish market PnL backtests as contract-accurate until official dated instrument snapshots and risk-tier snapshots are available, the H1 runner explicitly enables point-in-time specs, entry and all reduce-only legs use persisted exchange quantities, and margin/liquidation assumptions are account-mode-specific. No actual order was placed.


## 21. Official risk-tier semantics and optional as-of enforcement

The official Bybit V5 `GET /v5/market/risk-limit` response defines per-symbol `riskLimitValue`, `maintenanceMargin`, `initialMargin`, `maxLeverage`, and `mmDeduction`; linear responses are paginated (15 symbols per response). See [Bybit API: Get Risk Limit](https://bybit-exchange.github.io/docs/v5/market/risk-limit).

A new `bybit_risk_tiers.py` reader loads only dated snapshots, selects the first tier whose `riskLimitValue` covers the position notional, and rejects missing/stale symbols, notional above the highest tier, or leverage above that selected tier's `maxLeverage`. The engine can opt into this gate with `risk_tiers_dir`; selected tier ID, limit, MMR and MM deduction are stored with the open position for auditability. Synthetic tests cover tier selection, leverage rejection and persistence fields.

The reader deliberately does **not** yet calculate account margin or liquidation. Bybit's official isolated USDT perpetual liquidation formula depends on tier MMR and MM deduction, position quantity, leverage, extra margin and taker close-fee assumptions. Bybit also states that isolated liquidation is triggered by Mark Price, while cross/UTA liquidation is account-level and depends on account MMR. See [Bybit UTA liquidation rules](https://www.bybit.com/en/help-center/article/UTA-Trading-Rules-Liquidation-Process) and [USDT maintenance margin](https://www.bybit.com/en/help-center/article/Maintenance-Margin-USDT-Contract). Consequently, selecting a tier is not a liquidation simulation. Account mode and margin allocation remain explicit unresolved requirements.

The H1 runner still does not pass either `instrument_specs_dir` or `risk_tiers_dir`; no existing backtest result is upgraded. Live API snapshot retrieval remains blocked by HTTP 403 on the GitHub-hosted runner. No synthetic tier fixture is represented as actual Bybit historical data.


Risk-tier file loading is independently fail-closed: the as-of reader now revalidates `tier_count`, the unique lowest-tier marker, monotonic risk limits/MMR/IMR/maxLeverage, and the official `mmDeduction` recurrence rather than trusting that archived JSON was produced by the local collector. Regression tests include a forged lowest-tier marker and a one-unit deduction mismatch.


## 22. Risk-tier selection gate CI and remaining dynamic-mark limitation

Research CI [#41615561285](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41615561285) passed the first risk-tier engine integration on commit `ede5f46709d613405b27b66fbbd000505087a30c`. After independently hardening snapshot-file validation and adding a state-persistence round-trip for selected tier metadata, Research CI [#41615868813](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41615868813) completed **SUCCESS** on commit `b784559f8ca224a893ca6fb074f8376bbeeb6837`. The passing suite includes as-of risk-tier selection, boundary selection, maxLeverage rejection, malformed lowest-tier/mmDeduction rejection, engine entry gate, position metadata persistence, and the existing complete deterministic test suite.

The official Bybit docs confirm that position value is quantity × Mark Price, maintenance margin is `position value × MMR − MM deduction`, and the risk tier can change in real time as Mark Price moves. The engine currently selects and stores a tier at entry only. It does not reselect tiers on every mark update, does not use a full historical Mark Price series for liquidation checks, and does not model the exchange's tier-deleveraging IOC partial-close sequence. The current candle-close proxy used by portfolio risk controls is not equivalent to Bybit Mark Price. See [Bybit maintenance margin](https://www.bybit.com/en/help-center/article/Maintenance-Margin-USDT-Contract) and [Bybit liquidation rules](https://www.bybit.com/en/help-center/article/UTA-Trading-Rules-Liquidation-Process).

Thus the new gate prevents an entry that exceeds the dated tier's maximum leverage or risk limit at its modeled entry value, but it is **not** a dynamic margin or liquidation engine. Before contract-accurate H1 replay, the remaining work includes dynamic tier transitions from timestamp-aligned Mark Price, correct maintenance-margin recalculation, isolated-vs-cross-vs-portfolio account semantics, liquidation/partial-deleveraging behavior, and exchange-quantized TP1/final close quantities. The H1 runner remains on legacy proxy mode and no market PnL tests were started.


## 23. Exact exchange contract quantity through TP1, funding and final close

Commit 916cbd036e3b397773682fcbce3e212f3b1e816c adds persisted Decimal-string fields to exchange-sized positions: initial contract_qty, tp1_contract_qty, remaining_contract_qty, qty_step, min_order_qty, and min_notional_value. The fields are populated from the dated instrument spec and actual floored entry order. Legacy positions retain exchange_sized=false and the historical notional proxy; they are not silently assigned fabricated exact quantities.

For strict positions, TP1 quantity is floored to qtyStep and the residual is computed as initial minus TP1, not as a floating fraction. If either leg fails the archived quantity/notional minimum checks, TP1 is skipped and the full position remains open. Final close validates the persisted residual quantity against qtyStep, minOrderQty and minNotionalValue at the modeled exit price; a violation raises instead of recording an invalid close. PnL and entry/TP1/final execution-cost legs use exact contract quantities. Funding accounting now uses exact remaining/initial quantity ratio after TP1, including ambiguous TP1 settlement boundaries. State restoration validates quantity strings, step alignment, TP1+residual conservation and consistency with remaining_fraction.

Regression coverage: exchange entry quantity survives into position state; TP1 splits a 1.0 contract position into 0.5/0.5 with 0.1 step; a 0.1 position skips an invalid 0.05 TP1 split; final PnL uses actual residual contracts; malformed final quantity is rejected; state round-trip preserves quantity/spec fields; funding uses exact residual quantity even when legacy remaining_fraction differs. Full Research CI #41617395285 — SUCCESS on 916cbd036e3b397773682fcbce3e212f3b1e816c.

Limitations: the archived minNotionalValue is conservatively applied to reduce legs, but actual Bybit reduce-only close exceptions/semantics have not been verified against authenticated order acceptance or official historical exchange responses. A gap can move the final close notional below the persisted minimum; strict replay fails loudly in that case. This is not proof of a real exchange-valid close. H1 runner still does not enable instrument_specs_dir or risk_tiers_dir; no market PnL backtests were run.


Official reduce-only semantics reviewed against Bybit V5 Place Order documentation (https://bybit-exchange.github.io/docs/v5/order/create-order): linear/perpetual order qty is contract quantity; reduceOnly=true is required for a closing/reducing order; if reduceOnly quantity exceeds max order quantity, Bybit automatically splits it. The endpoint documentation does not state a general exemption from minOrderQty/minNotionalValue for arbitrary partial reduce-only orders. Therefore this research implementation conservatively applies archived minima and explicitly labels the rule as unverified rather than assuming a bypass. No order was submitted.


## 24. Position-level risk-tier margin requirements

Added RiskTierHistory.calculate_margin_requirements() and RiskMarginRequirement. For a dated linear risk tier and configured leverage, it returns position-level initial margin = position value / leverage and maintenance margin = position value * tier maintenanceMargin - tier mmDeduction. The tier selection still enforces the dated riskLimitValue and tier maxLeverage. Regression tests cover tier 2, a 250,000 USDT position at 10x (25,000 USDT IM; 2,000 USDT MM under the synthetic fixture), and position values beyond the highest tier. Research CI #41618208413 — SUCCESS on 7775b0358d975715273185cb80a3fa76bdccb1f9.

This helper deliberately does not calculate liquidation price, account solvency, or portfolio-margin requirements. Bybit's current help documentation distinguishes cross, isolated and portfolio margin; cross margin also depends on account-level available balance and aggregate positions/orders. The engine does not yet know the user's margin mode, account configuration, other positions/orders, extra isolated margin or fee reserve. The H1 runner also still uses legacy sizing and does not pass dated instrument/risk-tier snapshot directories. No market PnL replay was run.


## 25. Confirmed cause of Bybit snapshot HTTP 403

A diagnostic step in GitHub Actions resolved the geography question. The hosted runner egress was reported by ipinfo as country US, region California, organization AS8075 Microsoft Corporation. Bybit's official V5 integration guidance explicitly states that IP addresses located in the US or Mainland China are restricted and return HTTP 403; it lists api.bybit.com and api.bytick.com as mainnet endpoints and country-specific hosts including api.bybit.kz for Kazakhstan accounts. Therefore the 403 from both instruments-info and risk-limit snapshot jobs is explained by the hosted runner's US egress, not by the snapshot parsers or missing credentials.

Both snapshot workflows now fail fast before calling Bybit when egress is US/CN or cannot be verified. Manual workflow dispatch exposes runner choice: ubuntu-latest or self-hosted. To collect official snapshots, a self-hosted GitHub Actions runner must be configured outside US/Mainland China; then select self-hosted on manual dispatch. For Kazakhstan-registered Bybit accounts, configure BYBIT_API_BASE_URL=https://api.bybit.kz (the correct host is determined by the account registration site, not merely the runner location). No API keys are needed for these public market-data endpoints. The hosted-runner diagnostic runs #41618754916 and #41618755021 confirmed the guard path; no Bybit API call was made after the guard was added.


## 26. Persist position-level margin requirements

The engine now calls RiskTierHistory.calculate_margin_requirements() on strict entries and persists the selected tier's maxLeverage plus position-level initial_margin_usdt and maintenance_margin_usdt in OpenPositionState. State restoration validates these values as finite non-negative Decimal strings. This makes the tier/entry margin estimate auditable across restart and preserves the configured leverage separately from the tier's max leverage. The estimate is entry-time only: it is not dynamically re-tiered at each mark, does not include estimated closing fees, does not enforce aggregate available margin, and does not produce a liquidation price. Research CI #41619268625 — SUCCESS on 889ae9ebdf3fbd06e81e14bed394612a5be050f6.


## 27. H1 market-PnL runner now fails closed without dated Bybit snapshots

The H1 shared-capital validation runner now requires both archived Bybit linear instrument-spec snapshots and risk-tier snapshots before loading data or launching any parameter/fold replay. It passes both directories into UnifiedQuantEngine, enabling strict as-of exchange sizing and risk-tier validation; no legacy notional-proxy fallback is used by this runner. The workflow has a matching preflight step. Added tests cover missing directories, empty snapshot directories, and valid directory configuration. Research CI #41619800964 — SUCCESS on 1e25c1cc00e69dd515e29c4515437c026a654f0a.

No dated snapshots are currently present because the hosted GitHub runner is in a Bybit-blocked US region. Therefore manual H1 market-PnL workflow dispatch will stop at the preflight until official snapshots are collected from a non-US/non-China runner. This is intentional; no market PnL backtest was run.


## 28. Historical snapshot coverage is now checked per H1 fold

A non-empty snapshot directory is not sufficient. Both Bybit public endpoints expose current instrument/risk-limit data; their documented query parameters contain no historical as-of timestamp. The instruments-info page describes online trading-pair specifications and notes that max limit/market quantity fields are adjusted twice monthly (3rd and 17th, 08:00 UTC+8). The risk-limit endpoint accepts category, symbol and cursor, but no historical time selector. Sources: https://bybit-exchange.github.io/docs/v5/market/instrument and https://bybit-exchange.github.io/docs/v5/market/risk-limit.

The H1 runner now validates snapshot time coverage for each scored fold before constructing the engine:
- at least one instrument and risk-tier snapshot must exist at or before the fold start;
- the first eligible snapshot cannot be older than the configured 30-day maximum age;
- gaps between eligible snapshots cannot exceed 30 days;
- the latest eligible snapshot cannot be more than 30 days older than fold end;
- a current-only snapshot is rejected for an older historical fold.

Six H1 runner gate tests pass, including current-only/historical mismatch, stale start, >30-day gaps and valid continuous coverage. Research CI #41622415461 — SUCCESS on e7164073a2292ed51f01b45d131ff65b3c958612.

Operational implication: snapshots must be accumulated prospectively and periodically. A one-time current capture cannot reconstruct historical Bybit contract limits or historical risk tiers. Until sufficient dated coverage exists for the requested fold, the H1 runner intentionally refuses market PnL replay. This remains separate from Binance-vs-Bybit OHLCV, funding, spread, queue position and mark-price fidelity.


## 29. H1 runner now uses official Bybit trade candles, funding and mark prices

The H1 shared-capital runner no longer reads CryptoFetch/Binance ZIP candles. It now requires an explicit BYBIT_KLINE_DIR containing official Bybit V5 H1 trade-kline CSVs and loads those candles directly. The loader rejects malformed OHLCV, duplicate timestamps, and any non-hourly gap/irregular interval; the selected symbols must share a sufficiently large synchronized overlap.

The runner also requires explicit BYBIT_FUNDING_DIR and BYBIT_MARK_PRICE_DIR. Before each scored fold it validates:
- every selected symbol has funding and mark CSVs;
- every funding settlement timestamp has a corresponding mark candle;
- official Bybit trade-kline and mark-kline timestamp grids match;
- every scored H1 candle has a mark-price candle;
- each symbol has at least one funding settlement inside the scored fold.

The engine receives funding_dir and mark_price_dir, so accrued funding is included in MTM and final trade PnL. The result's costs field now includes exchange fees, slippage and net funding cost; funding_costs is reported separately. Cost stress multipliers continue to scale trading fees/slippage only, not the historical funding cashflows.

The H1 workflow requires three explicit repository paths: kline_dir, funding_dir, mark_price_dir. The Bybit market-history archive workflow now defaults to a self-hosted runner and allows a manual choice of runner; a preflight rejects US/Mainland China egress. This is needed because the hosted runner was previously confirmed to egress from the US and Bybit returns HTTP 403.

Research CI #41623727845 — SUCCESS on e696af2f78e8ec7724d169899566c3825a9da56e (the tested code/test commit). The subsequent workflow-path/docstring-only changes are recorded separately. No market PnL backtest has been run; there are still no dated exchange snapshots or full Bybit market-history archives in the repo.

Remaining execution limitations: OHLCV is now Bybit-native, but H1 limit fills still use OHLC penetration as a proxy, not order-book queue position; spread and partial-fill adverse selection are not modelled. The funding mark uses the exact-timestamp mark-candle open proxy, not a separately archived exchange settlement mark. Account-specific fee rates and account margin mode are still not configured.
