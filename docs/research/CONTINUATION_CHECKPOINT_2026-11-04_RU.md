# Контрольная точка исследования — 2026-11-04

Ветка: `research/market-regime-v1-main`  
Проверенная версия движка: `230b13261a05d3c6c787d4ab889e43c450c5e4f2`  
Последний успешный Research CI: [#41822512553](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41822512553), 55/55 numbered steps + cleanup.

## 1. Непересматриваемые ограничения проекта

По решению пользователя от 2026-11-03:
- не регистрировать self-hosted runner;
- не запускать collector workflows и не скачивать новые Bybit market archives;
- не подключать private/account API;
- не запускать новые рыночные PnL backtests / parameter sweeps, пока нет устойчивого положительного кандидата на уже имеющихся данных;
- разрешены статический аудит, проверка provenance, deterministic unit/regression tests и исправление подтверждённых дефектов.

Полная автономность в текущей сессии не отменяет это более конкретное ограничение. Реальные ордера не размещать.

## 2. Проверенная инженерная база

- Синхронизированные закрытия нескольких символов обрабатываются как единый timestamp batch; проверены порядок закрытий, финализация и post-batch kill-switch flatten. Последний CI #41822512553 успешен.
- H1 Top-5 selector исправлен от per-symbol train/validation leakage. Дополнительно проверяются H1 alignment, ordering, uniqueness, continuity и exact timestamp intersection. Реального Bybit selection manifest нет; selector не запускался.
- Funding arithmetic unit tests не равны доказательству полноты архива. Manifest фиксирует query/page provenance и CSV hash, но расписание settlements не может быть независимо восстановлено только из точечных snapshots. Funding gate остаётся CLOSED.
- EMA50/EMA200 интегрирован только как opt-in paired comparison; PnL-эффект не измерен. 1,000 H1 bars pre-roll — текущая замороженная burn-in политика.
- Delayed-fill regime attribution исправлен: используется исходный `signal_ts_ms`, а не вычисленная свеча перед entry.
- Multi-bar limit wait freshness исправлен в runners; исторические E11/E13 запускались в market mode, поэтому этот дефект их опубликованные результаты не затрагивает.
- OHLC maker fills остаются optimistic proxy. Очередь, частичные fills, spread, latency и adverse selection нельзя вывести из OHLC.

## 3. Bybit L2 sample — уже существующее доказательство, не стратегия

В workflow #41814167058 сохранён report artifact для одного полного дня AAVEUSDT (2025-09-02):
- L2 archive: 88,252,368 bytes, SHA-256 `e3646429c600f4917c021e240497e8f3d46fd44ba57168100633181916c761f6`, 816,684 events, 24h, ZIP CRC проверен;
- public trades: 13,095,906 bytes, SHA-256 `cf11d05f6053acfeb22b1112df666ff328034963f04c6e6159f35cae63de1bc1`, 346,131 уникальных trade IDs;
- 66 trades предшествуют первому matching-engine book timestamp и должны быть исключены из replay;
- четыре hand-scheduled hypothetical orders: fill fractions 58%, 100%, 100%, 33%; это mechanics smoke test, не fill-rate estimate и не maker profitability evidence;
- mean signed midpoint markout: 1s −2.73 bps; 5s −0.58 bps; 30s +3.11 bps; 60s +4.09 bps. n=4 — статистически бессмысленно для выводов об устойчивом adverse selection.

Queue prototype прошёл 14 synthetic tests и CI #41812777279; same-millisecond exclusion regressions прошли CI #41814166935. Прототип не подключён к strategy PnL.

## 4. Что не считать доказанным

- Bybit-native H1/funding/mark completeness и dated execution specs/risk tiers.
- Исторический полный universe без survivorship bias.
- Реальный maker fill rate / queue priority / partial-fill fee lifecycle.
- Точная settlement Mark цена и account-specific fee tier.
- Положительная чистая доходность любой текущей стратегии.
- Цель 20% net/month.

Старые CryptoFetch/Binance proxy результаты сохраняются как exploratory. H-C, H-A, E11 и E13 не являются готовыми кандидатами; E11/E13 архивные прогоны были market-mode. Исторические net-PnL результаты, полученные до исправления execution-notional fee/slippage, остаются provisional по соответствующей записи Experiment Ledger.

## 5. Следующий разрешённый порядок работы

1. Продолжить статический аудит queue replay: timestamp ordering, book reset semantics, queue-ahead assumptions, fee treatment and order-spec validation.
2. Проверить все старые PnL results against engine/code provenance and Experiment Ledger; не пересчитывать без конкретного основания.
3. Проверить режимную атрибуцию и причинность существующих отчётов; не менять стратегию по результатам одного среза.
4. Добавлять только детерминированные тесты, которые закрывают воспроизводимый дефект или неоднозначный контракт.
5. Не запускать PnL replay, пока не будет явно пересмотрен data/execution gate в соответствии с решением пользователя.

Документ фиксирует состояние и ограничения; торговую логику и параметры стратегии не меняет.

## 6. Исправление fail-closed в aggregate-L2 trade parser (2026-11-04, продолжение)

Подтверждённый дефект в `apply_public_trade()`:
- неизвестная сторона aggressor trade проверялась только после сравнения цены с лимитом; malformed row на другой цене молча игнорировалась;
- любое неизвестное значение RPI, кроме нескольких false-подобных строк, автоматически считалось RPI и исключалось из очереди;
- неположительные price/size не всегда отклонялись как ошибка данных.

Исправление:
- side валидируется строго как Buy/Sell до проверки цены;
- RPI принимается только из явно допустимых true/false значений; неизвестные значения вызывают ValueError;
- price и size должны быть положительными;
- malformed rows fail closed, а не исчезают из статистики.

Добавлены 3 regression tests; aggregate-L2 tests теперь **19/19 passed** в Research CI [#41828681722](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41828681722). Предыдущий Research CI после исправления parser также прошёл [#41828545268](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41828545268). Это parser/data-integrity verification, не strategy PnL.

## 7. Снижение ненужных сетевых запусков CI

Обнаружено, что push изменений queue parser/tests автоматически запускал отдельный Bybit sample workflow, который заново скачивал уже проверенный AAVEUSDT L2 и public-trade день. Два последовательных коммита вызвали два повторных sample runs; оба завершились SUCCESS:
- [#41828512197](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41828512197)
- [#41828545237](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41828545237)

Чтобы не повторять это при каждом изменении кода:
- `.github/workflows/bybit-orderbook-sample-inspection.yml` переведён на `workflow_dispatch` only;
- bounded Bybit order-book archive probe удалён из обычного `research-checks.yml`; теперь обычный CI не делает сетевой запрос за Bybit archive probe;
- deterministic parser tests остаются в обычном Research CI.

Изменение workflow проверено успешным Research CI [#41828681722](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41828681722). Полный sample-inspection запуск оставлен ручным, чтобы сетевой сбор/повторное скачивание происходили только при осознанном отдельном запуске.

## 8. Текущие ограничения без изменений

- Queue replay остаётся aggregate-L2 approximation, не L3 и не exchange-confirmed execution.
- Нет tick/qty step validation, latency/cancel model, per-fill VWAP markout/fee lifecycle, broad-symbol/regime sample.
- Четыре hypothetical orders остаются только smoke test.
- Maker execution gate остаётся CLOSED для strategy PnL.
- Не запускались новые рыночные PnL backtests, parameter sweeps, private API, paper/live orders.

## 9. Final CI/network-trigger state after hardening

- `bybit-orderbook-archive-probe.yml` also switched to manual dispatch only (commit `83d10f9c9f6c2f707afb6f2bfaaa4063d2fd729e`).
- Research CI after removing the bounded network probe: [#41828681722](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41828681722) SUCCESS.
- Both sample-inspection runs caused by the two parser commits completed SUCCESS; they re-read only the same existing AAVEUSDT 2025-09-02 sample, not a new date or symbol.
- All data-collection / sample-download workflows now require explicit manual dispatch; default deterministic CI no longer runs Bybit network probes or full L2 downloads.

## 10. Bybit L2 update-ID restart semantics — hardening внесён, CI не подтверждён

Официальная Bybit V5 orderbook документация определяет u как update ID и указывает, что u=1 означает snapshot после service restart; локальный стакан должен быть заменён новым snapshot. seq — отдельный cross sequence; меньший seq означает более раннее состояние. Источник: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook.

В прежнем OrderBook.apply() поле data.u не проверялось. Поэтому parser не мог fail-closed остановиться, если в архиве встречался u=1 вместе с type=delta: такой event мог быть применён как обычное изменение, хотя полное состояние стакана не подтверждено.

Изменения в research branch:
- u обязателен, положителен и не может быть bool;
- u=1 разрешён только вместе с type=snapshot; u=1 delta отклоняется fail-closed;
- snapshot по-прежнему полностью заменяет уровни книги;
- seq ordering не сбрасывается автоматически вместе с u: сохраняется проверка non-decreasing seq, поскольку это отдельный cross-sequence сигнал;
- cts остаётся монотонным.

Regression coverage: reset snapshot заменяет старые уровни; u=1 delta отклоняется без мутации; отсутствующий u отклоняется; u=1 не обходит seq ordering. Queue test file содержит 23 теста.
- Source commits: 46d264d40a567438c0311bd227f76b0b753700ef, 3b6b71b43776f79b4ec19d3e801ac6fa52b356a2.
- Test commits: 5687cd39ff869b9bcabc2f12a55f51596b899e63, ed03e42bbba772d2e0b9c55a3282f05b3df4fdf9, 7d8f54318552d8d8aa3b9d7ae08d0feb61bb0ebb, 5113865fb1accd38b202cb67ca5d6c541c2113cc.
- Research CI is configured to run on pushes touching these paths. The new push-run terminal result is not exposed by the available PR-only workflow-run lookup; do not mark this patch CI-passed until a terminal run is checked.

The previously inspected AAVEUSDT 2025-09-02 sample had zero u=1 resets, so this is a parser-integrity guard, not a correction to the four-order sample metrics. No archive was re-downloaded, no strategy signal was replayed, no PnL was run, and no Bybit account/API/order operation occurred.

Next static audit items remain: order-spec/tick/qty validation, per-fill fee and VWAP markout lifecycle, latency/cancel assumptions, and duplicate public-trade ID handling. Keep MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL.
## 11. L2 parser follow-up audit: test-fixture correction and atomic state application

Во время повторной проверки предыдущей серии автоправок обнаружены дефекты в самих regression fixtures: повторяющиеся ключи u в двух Python dict literals (последний ключ молча перезаписывал первый), а также неконсистентное имя/ожидание теста restart snapshot. Исправлено до использования тестов как доказательства.

Дополнительно выявлен настоящий robustness-дефект: OrderBook.apply() очищал/менял live book до полной проверки всех уровней. Некорректный snapshot/delta мог оставить частично изменённое состояние после исключения. Исправлено транзакционным применением: строится candidate book, проверяются уровни и crossed state, затем одним шагом заменяются bids/asks и sequence metadata.

Изменения:
- `bybit_l2_queue_replay.py`: atomic candidate-state apply; malformed decimal values нормализуются в ValueError.
- `tests/test_bybit_l2_queue_replay.py`: restart fixture очищен от duplicate dict keys; restart snapshot использует seq=3 после seq=2 и проверяет сохранение cross-sequence ordering; добавлены два regression tests на atomic failure для malformed delta и snapshot.
- Queue replay test file сейчас содержит 25 test functions; duplicate `u` keys отсутствуют.

Последние commits: atomic source `38b17dcc50f59d17f746cc38ebf61ed68b429eb5`; test repair/atomic regressions `6207866ea5ec6deff952cd42b0c90dac8154842e`; decimal validation `b1922c98b194b1c45501c59b0df9d1bc426e6404`; strict ValueError assertion `afb1e090b00fc45f9329cea5ce02e744764995a7`.

CI state: combined commit status and available commit-workflow lookup returned no runs/statuses for these push commits. The available wrapper only exposes PR-triggered runs. Therefore tests are committed but execution is NOT independently verified in this session; do not claim 25/25 passed. No local runner was available in this tool context.

Next: obtain a terminal Research CI result through Actions UI/API with push-run visibility; then continue order-spec validation and duplicate trade-ID audit. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` remains unchanged. No strategy PnL, data re-download, private API or live order was used.
## 12. Public-trade identity and replay atomicity

Дополнительный audit показал, что CSV reader сохранял `trdMatchID`, но queue replay никак не проверял его уникальность. Повтор одной и той же public trade строки мог дважды уменьшить очередь и создать завышенный fill.

Исправлено:
- `trdMatchID` теперь обязательная колонка trade archive schema.
- Replay отклоняет пустой/missing trade ID и повтор ID в пределах используемого интервала ордера.
- Replay выполняется на копии PassiveOrder и коммитит её состояние только после успешного прохода; при duplicate/missing ID или timestamp error исходный order state не меняется.
- Добавлены два regression tests: duplicate ID и missing ID; оба проверяют отсутствие частичной мутации исходной заявки при отказе.

Последние commits: source `624b78dd470b8d3910af67952a66add4ad74cb17`, test `59f5664a6842e6e7515025a255fd83b2945af138`, atomic replay source `0ed49682d5f049bd231606db6ed11e2e5b5c416a`, test `ef20e9e2af27f8e2f3bd16f03e2c40264fe78094`.

Queue test file содержит 27 test functions; duplicate `u` fixture keys отсутствуют. Как и для предыдущих правок, test execution в текущей сессии не подтвержден: доступный GitHub workflow-run wrapper фильтрует PR-triggered runs и не показывает push runs. Не заявлять 27/27 passed до проверки terminal CI.

Следующий engineering gate: order-spec validation (tickSize, qtyStep, minOrderQty, minNotional) и measured latency/cancel assumptions. Per-fill VWAP/fee/markout accounting остаётся не реализованным. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`; никаких новых PnL, архивных загрузок, private API или ордеров.
## 13. Exchange order constraints integrated into aggregate-L2 queue replay

Первоначально при добавлении проверки tick/qty был создан локальный упрощённый InstrumentSpec. При повторном аудите обнаружен уже существующий canonical `bybit_instrument_specs.InstrumentSpec`, который дополнительно проверяет status, min/max price, maxOrderQty/maxMktOrderQty и minNotionalValue. Дублирующую структуру удалили; queue replay теперь использует canonical validator.

Изменения:
- `place_passive_order(..., instrument_spec=..., symbol=...)` при переданной спецификации вызывает canonical `InstrumentSpec.validate_order(..., order_type='limit')`.
- Off-step quantity отклоняется, если canonical validator округлил бы его вниз: queue replay не должен менять заявленный размер незаметно.
- При переданной спецификации symbol обязателен и должен совпадать с `spec.symbol`; cross-symbol spec reuse отклоняется.
- Проверки покрывают валидную заявку, off-tick, off-step, minOrderQty, minNotionalValue, отсутствующий symbol и mismatch symbol.
- Queue test file содержит 34 test functions; duplicate `u` dict keys отсутствуют.

Commits: source `4ae1b4446bf7daf4f2e84d77f315b3d03b68ecf1` (первоначальная реализация), canonical refactor `8f9ccec5087aa87e1e81bb4ce18eb98c38fa9159`, final symbol binding `bdda745b27c08dc61bf4d3030947cbd3f91c8e12`; tests `2ebcf94fada4920d0fbb91377e199a8807157028`, `55987001d72892e25ac1b4d27cdd8ce16efad9f9`, `768b6eca52fe3c79f6f4294cf4dedee2a69c8ba3`.

Critical limitation: this repository has an as-of snapshot loader (`instrument_spec_history.py`) and manual public snapshot collector, but no verified 2025-09-02 full-universe instrument snapshot was found in the inspected project files. Therefore the existing AAVEUSDT 2025 sample cannot be retroactively certified against the exact historical tick/qty/min-notional/status filters. Do not substitute a current snapshot or infer historical constraints. The sample runner does not yet pass a dated spec; this patch adds the validation hook and deterministic tests only.

CI: `research-checks.yml` already runs `tests/test_bybit_l2_queue_replay.py` on pushes to this branch and includes source/tests in compile step. Combined statuses for latest source/test commits are empty in the available GitHub wrapper; no terminal push-run result is visible. 34 test functions are authored, not claimed passed.

Branch comparison at this checkpoint: `research/market-regime-v1-main` is diverged from `main` (1962 ahead, 36 behind). Do not merge this research branch wholesale or infer that it is safe to fast-forward; preserve main and use a reviewed selective PR/cherry-pick strategy later.

Next audit: inspect existing queue replay against canonical dated spec history integration and identify whether a valid historical snapshot exists in prior artifacts; if not, keep historical order-validity unknown. Then continue per-fill execution accounting and latency/cancel modeling. No new archive/API call, PnL run, private API, or live order was made.
## 14. Per-fill lifecycle: partial fills, VWAP, explicit fee rates and per-fill markout

Расширен execution trace прототипа без запуска нового рыночного replay:
- `PassiveOrder` сохраняет отдельный immutable `PassiveFill` для каждого частичного исполнения: timestamp, side, price, quantity.
- Добавлены `filled_notional` и `filled_vwap` по фактическим fill records.
- `replay_public_trades()` копирует также список fills перед replay; при ошибке валидации после уже смоделированного частичного fill исходный order остаётся неизменным.
- `per_fill_fee_ledger()` принимает только явно переданные ставки комиссии для каждого fill; не подставляет account tier и допускает отрицательную ставку только как явно заданный rebate. Количество ставок обязано совпадать с числом fills.
- Runner сохраняет каждый fill в report и рассчитывает 1s/5s/30s/60s markout отдельно от цены/времени каждого fill, а не только от первого fill.
- Report явно помечает `order_spec_validation=not_performed_no_verified_historical_snapshot` и `fee_accounting=not_calculated_requires_account_fee_tier_per_fill`.

Добавлены regression tests на partial-fill VWAP, per-fill rate matching, разные fee rates/rebate, markout каждого partial fill и rollback после duplicate trade ID, который возникает уже после потенциального первого fill. Queue test file содержит 39 test functions.

Commits: fill records/fee ledger source `e9af629e1fe9ecf9748c508f57c45e9cca48fc6b`; fee/VWAP tests `6511bc0064be70a45bbc188e2c15dfe947c3515d`; per-fill markout runner `4db0454c121b3f198fcdade736af4fb58346a3ae`; tests `89f1f0f249338c15c4e744a4fc791f6bc33722fe`; report gate labels `d8371ddacc6b6df9fc91c454c0e902cbb17543f4`; rollback regression `5c83a3c370ade99b65112a0a78b1faf6b087902f`.

Verification status: 39 test functions are present and source/runner/test files were re-fetched from branch; duplicate `u` fixture keys absent. GitHub combined statuses are empty for latest commits and the available workflow-run wrapper does not expose push runs. Do not state that tests passed until terminal Research CI is inspected.

Research branch comparison now reports 1969 commits ahead and 36 behind `main` (diverged). Keep changes isolated; no merge/rebase to main.

Remaining execution gaps: no verified historical instrument spec for the 2025-09-02 sample; no historical/account-specific per-fill fee rates; no measured order-entry/cancel latency or cancel queue model; no L3 priority. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`. No data downloads, PnL tests, private API or live orders.
## 15. Strict integer validation for L2 order-book metadata

Повторный статический аудит `OrderBook.apply()` выявил тихое приведение malformed JSON metadata через `int(...)`: например, `u=2.9` превращалось в `2`, а `seq=True` — в `1`. Это могло скрывать повреждение архива и применять неверный ordering metadata.

Исправление: введён strict integer parser для `cts`, `seq`, `u`; принимаются только JSON integer values (bool/float/string coercion отклоняются), все три поля обязаны быть положительными. Ошибка возникает до candidate book mutation.

Добавлены regression tests: fractional `u` (плюс проверка отсутствия мутации), boolean `seq`, fractional `cts`. Queue test file теперь содержит 42 test functions; duplicate `u` keys отсутствуют.

Commits: source `c08336161c73a071cd440c50fc12f2aa7b5091f5`; tests `14d979ab8efef6100a9b8a678e94bc21ec050be3`.

Bybit public orderbook docs define `u` and `seq` as integer fields, `cts` as matching-engine timestamp in ms, and `u=1` as restart snapshot marker. Source: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook. The separate full-orderbook synchronization page documents consecutive `u` for that specific full-depth stream; do not transfer that stronger continuity contract to the current depth-200 archive without confirming its feed format.

CI remains unverified for these new push commits: combined status is empty and the available commit-workflow wrapper only returns PR-triggered runs; `research-checks.yml` has push/workflow_dispatch triggers but no `pull_request` trigger. No test-pass claim. Research branch compare: 1973 ahead / 36 behind `main`, diverged. Do not merge PR #4 or retarget it.

External-data hold remains in force: do not dispatch collectors, configure self-hosted runner, download new Bybit archives, connect account/private API, or place paper/live orders until user-defined profitability condition is met. Current static work only. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`.
## 16. Idempotent overlapping public-trade replay

Статический аудит выявил риск повторного применения одного и того же trade archive к уже частично обработанному PassiveOrder: прежняя реализация хранила duplicate IDs только в локальном set одного вызова. Повторный вызов мог повторно уменьшить `queue_ahead_remaining` и завысить fill.

Исправление:
- `PassiveOrder` теперь хранит `processed_trade_ids` как пары `(SYMBOL, trade_id)`.
- Replay работает на копии order и копии persistent ID set; новые ID фиксируются только после успешного прохода.
- Повторное чтение уже обработанных trade IDs из overlapping archive пропускается, поэтому повторный replay идемпотентен.
- Повтор ID внутри одного текущего архива по-прежнему вызывает ValueError; транзакционность не допускает частичного commit.
- IDs до `arrival_ts` не сохраняются, чтобы не раздувать память полным префиксом дневного CSV; timestamps при этом продолжают проверяться на монотонность.

Добавлен regression test: первый replay расходует только часть queue-ahead без fill; повторный replay того же архива не уменьшает очередь повторно и не увеличивает eligible trade count. Всего 43 test functions в `tests/test_bybit_l2_queue_replay.py`.

Commits: initial idempotency source `f318a21d0d13676ce79390decaaea24aa6951b91`; test `c5b2e036b3af98f7a4d5d203acf671ab3ee6feb1`; duplicate-vs-prior-ID correction `539adee9722887aec4c26a30de4f413aa597ad93`; active-window ID retention `4852ebb7ed4fc32e0cd622b89301db1c60119129`.

Bybit trade archive runner remains a one-pass per-order probe. Persistent ID state makes the primitive safe for overlapping/restarted replay use; it does not improve the underlying aggregate-L2 queue approximation or prove fills. CI is still not terminally verified for latest push commits; no tests-pass claim. No new data, private API, PnL or orders.
## 17. Trade-time precision, block-trade/RPI filtering, and initial snapshot guard

Следующий статический audit нашёл три существенных источника ложного queue consumption:

1. Public trade timestamp parser использовал `float()` + `round()`, а `apply_public_trade()` — `int()`. Fractional ms могли округляться/усекаться и перемещать print через arrival boundary. Теперь archive timestamp разбирается через Decimal без float; секунды преобразуются в ms точно; sub-ms значения отклоняются; replay/apply и hypothetical order arrival/expiry требуют strict integer timestamps.
2. Bybit public trade stream имеет `BT` (block trade) и `RPI` flags. Стандартный orderbook feed не включает RPI orders. Block-trade prints не должны уменьшать displayed L2 queue, а RPI prints также не сопоставимы с обычным displayed book. Ранее queue replay игнорировал BT и допускал отсутствие RPI flag. Теперь replay исключает BT/RPI, считает их отдельно и fail-closed отклоняет архив, если отсутствует любой из этих классификаторов (`isBlockTrade`/`BT` и `RPI`/`isRPITrade`).
3. `OrderBook.apply()` принимал delta как первое событие и мог инициализировать reconstructed book без полного snapshot. Теперь первый event обязан быть snapshot.

Добавлены regression tests на точный timestamp parser (seconds/ms), запрет sub-ms округления, invalid timestamp values, direct apply/replay rollback, integer arrival timestamp, исключение block trades, сохранение normal prints, invalid flags, обязательные BT/RPI columns и parser aliases. Исправлены newline escapes в gzip CSV test fixtures. Queue test file содержит 56 test functions.

Commits: exact trade timestamp source `8911feb143ce8160e7fb897aba284c1be6c6df6a`; source integration `f392f7c3c81b2a4ed7da3e1e2209e70e9d0aeae9`; initial-snapshot source `b09de7d3bfebf5f41d630c983eb0d08cd9fb51bf`; block-trade source `efbb20ca4110ea70cb2c269d8dd8c7801b7a5360`; RPI-required source `012ae49d29fbdcfc4da1a2261ed32568eccc3410`; order timestamp source `ad9c8145a3ebde52e3928428b42ac82809858fca`; timestamp tests `57a4ca71fdb3a5cf9742d6bfb6ee4cfc7c91390c`; newline fixture repair `9f244a82dc80544d96335aa88f9efad7411465c3`; block-trade tests `e63497bacf6cdfca18c58dfaddf09f693906a169`; RPI tests `cf22d6927bdca97c78544c29592cebaa97b5dc77`; final order timestamp tests `4c78ad78c4c6d149cfc83e1c883253a68103e215`.

Official Bybit docs: public trade stream defines `T` as fill timestamp, `S` as taker side, `BT` as block-trade flag, and `RPI` as RPI flag: https://bybit-exchange.github.io/docs/v5/websocket/public/trade. Standard orderbook docs state RPI orders are not included and `cts` can be correlated with public-trade `T`: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook.

Latest validation is static only: source/test/runner files re-fetched and reviewed; 56 test functions present. CI execution is not confirmed. GitHub combined statuses remain empty for these push commits, and available workflow-run wrapper only surfaces PR-triggered runs; no workflow_dispatch action is available through current connector. No tests-pass claim.

Runner report now declares mandatory BT/RPI metadata and counts excluded block trades. No historical archives downloaded or replayed, no new network collector invoked, no private API/live/paper orders. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` remains.


## 12. Дополнительный аудит временной точности instrument-spec history

При статической проверке `instrument_spec_history.py` найдено тихое преобразование `as_of_ts = int(as_of_ts)`: дробная миллисекунда отбрасывалась, а bool/строковое значение могло быть неявно принято. Это создавало риск выбора неверного исторического снимка при ошибочном типе входа. Также преобразование ISO-времени через float `datetime.timestamp() * 1000` не давало строгой гарантии точной миллисекундной границы.

Исправлено в research branch:
- `get_spec()` теперь принимает только настоящий Python integer timestamp в миллисекундах; bool, float и string отклоняются;
- ISO `fetched_at` переводится в UTC через целочисленную арифметику timedelta, без float;
- ISO timestamp с точностью меньше миллисекунды отклоняется, а не усекается;
- добавлены regression tests на fractional/bool/string as-of и sub-millisecond snapshot timestamp.

Изменения:
- source commit: `64d6e2640a926e9bc0cc08f338a2667ff990e14e`
- test commit: `ee0b173f707c53af25f0f892a37357c5a8a90cc1`
- source blob: `dd5c44ee1af39e8b9be2f776744ef8a393d774ed`
- test blob: `a458dd69875bba1ad4cbc40aece0166389fa44ce`

Проверка на данный момент статическая: изменения записаны в GitHub, но локальный Python test runner недоступен, а доступный workflow-run lookup показывает только PR-triggered runs. Поэтому тесты добавлены, но не объявляются пройденными; CI status требует отдельного подтверждения. `main` не затронут. Новые рыночные архивы, PnL, private API и ордера не запускались.


## 13. L2 / public-trade event-time alignment audit

Сверены временные поля в replay с актуальной официальной документацией Bybit:
- orderbook `cts` — matching-engine timestamp, на который создано состояние стакана;
- public trade `T` — timestamp исполнения сделки;
- Bybit описывает `cts` как поле, которое можно коррелировать с `T`, но не предоставляет в этих публичных payloads общий sequence number, который однозначно упорядочивает гипотетическую заявку относительно событий с одинаковой миллисекундой.

Текущая реализация:
- для состояния стакана на момент прихода заявки берёт только book events с `cts < arrival_ts`;
- для markout на горизонте берёт только состояние до первого события с `cts >= target`;
- public trades с `T <= arrival_ts` не засчитываются в fill;
- таким образом, события на той же миллисекунде исключаются, а не упорядочиваются предположительно.

Это правильная консервативная граница для имеющейся точности timestamp, но не доказывает точную очередность событий и не заменяет exchange sequence/L3. Отдельно остаётся подтвердить на уже имеющемся архивном файле, что CSV поле `timestamp` соответствует документированному времени исполнения `T` и что единицы/формат распознаны корректно. Новые архивы для этой проверки не скачивались.

Официальные источники: Bybit Orderbook docs указывают matching-engine смысл `cts` и корреляцию с `T`; Public Trade docs определяют `T` как время исполнения, а `i` как trade ID и `BT`/`RPI` как специальные признаки. См. https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook и https://bybit-exchange.github.io/docs/v5/websocket/public/trade.

Итог: timestamp boundary реализована консервативно; временная модель остаётся proxy, пока не будет проверен формат конкретного сохранённого CSV и пока не будет измерена реальная задержка доставки/постановки заявки. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` без изменений.


## 14. Проверка совместимости публичного trade archive с обязательными BT/RPI флагами

Проверен контракт источника, который зашит в runner: `https://public.bybit.com/trading/AAVEUSDT/AAVEUSDT2025-09-02.csv.gz`. По опубликованным описаниям структуры futures CSV у `public.bybit.com` содержит стандартные поля сделки и `RPI`, но `BT/isBlockTrade` в перечисленной схеме отсутствует. При этом официальный V5 recent-trade API явно предоставляет оба флага — `isBlockTrade` и `isRPITrade` — но это другой формат/endpoint, не доказательство наличия этих полей в историческом CSV.

Следствие для текущей реализации:
- `iter_public_trades()` намеренно требует оба признака и завершает обработку ошибкой, если один отсутствует;
- поэтому текущий runner, вероятно, остановится на проверке заголовка CSV, не дойдя до replay, если исторический CSV соответствует опубликованной стандартной схеме;
- это не дефект fail-closed логики, а несовместимость выбранного источника с требованиями модели: нельзя безопасно приравнивать отсутствие BT к `False`;
- не ослаблять проверку и не считать все строки обычными сделками. Нужен источник исторических принтов с достоверными BT и RPI, либо доказательство, что конкретная версия архива содержит дополнительные колонки.

Источники для проверки: Bybit V5 Recent Public Trades документирует оба флага; описание публичной futures CSV схемы перечисляет `RPI`, но не `BT`. Это schema-level warning; реальный заголовок файла не проверялся, потому что действует запрет на новые скачивания. См. https://bybit-exchange.github.io/docs/v5/market/recent-trade и https://github.com/Anton495/bybit-data-downloader.

Никаких новых архивов не скачивал. Не менял парсер, так как fail-closed поведение здесь корректно. Это отдельный блокер для L2 replay: `TRADE_ARCHIVE_FLAGS = UNVERIFIED_COMPATIBILITY`. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` сохраняется.


## 15. Повторный audit нормализованных trade events и границ L2 archive

В ходе повторной статической проверки найдены два обхода fail-closed гарантий:

1. apply_public_trade() использовал trade.get("block_trade", False) и trade.get("rpi", False). Поэтому прямой вызов функции с неполным normalized event мог засчитать неизвестный print как обычную сделку, хотя CSV parser требовал оба флага. Теперь отсутствие любого флага приводит к ValueError до изменения очереди/объёма. parse_exchange_bool() также больше не принимает float 0.0/1.0 через неявное равенство с integer.
2. capture_book_at() делал int(event["cts"]) до проверки события. Дробный cts на границе arrival мог быть усечён и привести к тому, что malformed event был пропущен без вызова OrderBook.apply(). Теперь iter_book_events() валидирует тип события, data object, symbol и строгий integer cts на каждой строке до передачи вызывающему коду.

Добавлены regression tests:
- отсутствующий block_trade отклоняется;
- отсутствующий rpi отклоняется;
- float bool flags отклоняются;
- fractional cts отклоняется даже если прежнее boundary сравнение могло пропустить событие.

Изменения в research/market-regime-v1-main:
- trade flag source: 1fe177b36b4564e3aefcfb79b445b2108840c54e
- trade flag tests: 0e5a8d9fa5af9cd715e3cc574b20c1f57871fbde
- archive cts source: 6f493dd914783d825ed916bd1f7bb930d594485b
- archive cts test: fe2c706f237bee563deb6101ca9cc03f566263b8

Статическая проверка изменений выполнена повторным чтением файлов из GitHub. В tests/test_bybit_l2_queue_replay.py добавлены четыре regression tests; тесты не объявляются пройденными до terminal CI. Для последних двух commits запущены Research engine checks через push; на момент checkpoint runs ещё выполнялись. main не менялся.

Не запускались новые архивные загрузки, market/PnL replay, private API, paper/live orders. Сохраняются TRADE_ARCHIVE_FLAGS = UNVERIFIED_COMPATIBILITY и MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL.


## 16. Terminal CI verification for queue replay hardening

После последовательного устранения несоответствий в legacy regression tests полный Research engine checks завершился SUCCESS:
- workflow run: 41835268896
- URL: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41835268896
- tested commit: e7f4174fbf99e1b311980a106c9bf4ee66d60630
- job: tests — SUCCESS
- conservative Bybit aggregate-L2 queue replay primitives: 60/60 tests passed
- compile step и остальные включённые Research CI steps завершились успешно.

Предыдущие CI failures были вызваны несовпадающими с текущим строгим контрактом тестовыми ожиданиями, которые последовательно исправлены:
- четыре order-spec rejection tests не передавали обязательный symbol;
- markout test сравнивал текстовое форматирование Decimal вместо численного значения;
- missing-u test ожидал старое сообщение, а не strict integer validation;
- restart-sequence test использовал seq=0, который корректно отклоняется раньше как неположительный; сценарий изменён на seq=2 → seq=1;
- RPI validation test ожидал прежний текст ошибки.

Test-only repair commits: e1bd0e6acf5ddc534cb1531f168483bb4abd2a0e, 2f9fb8fff4f09ceb4ef8f7f04adfef065f0e5b94, 76e964b6455a2cf188ac37e89e987f4664d78915, b2c1aa69a0c4de015f48fc6fcd8c0876a0d617ac, e7f4174fbf99e1b311980a106c9bf4ee66d60630.

Это подтверждает корректность текущих deterministic parser/queue primitive tests в GitHub CI, но не подтверждает реальную maker execution: aggregate L2 без L3, latency/cancel model, verified historical instrument spec и подтверждённого historical BT/RPI trade archive остаётся proxy. Не запускались новые Bybit archive downloads, strategy PnL, private API, paper/live orders. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` остаётся без изменений.

Branch compare после изменений: research/market-regime-v1-main diverged from main, 2009 ahead / 36 behind. `main` не менялся; wholesale merge/rebase не выполнять.


## 17. Depth-200 event continuity and historical replay completeness

Повторно проверены `capture_scenarios()`, `capture_book_states_at()`, `capture_book_at()` и `iter_book_events()`.

Подтверждено статическим анализом:
- Arrival snapshots исключают все book events с `cts >= arrival_ts`; несколько событий с одной миллисекундой не упорядочиваются предположительно.
- Markout snapshots также используют состояние до первого события с `cts >= target`; если архив не содержит состояния на горизонте, runner помечает `no_book_state`, а не подставляет будущие данные.
- `iter_book_events()` проверяет JSON object/data, symbol и строгий integer `cts`; `OrderBook.apply()` проверяет положительные `u`/`seq`/`cts`, non-decreasing `seq`/`cts`, snapshot initialization и корректность reconstructed book.
- Runner не проверяет непрерывность `u` через `u+1`. Это намеренно: официальная стандартная orderbook документация описывает `u` как Update ID, `seq` как cross sequence и restart marker `u=1`, но не публикует явное правило непрерывности для depth-200 historical archive. Отдельная документация Full Orderbook задаёт consecutive `u` для другого потока и не может без подтверждения использоваться как контракт depth-200.

Оставшийся существенный риск: если исторический depth-200 архив потерял промежуточные delta records, текущие проверки могут не обнаружить пропуск и восстановленный book может стать неполным/неверным. `seq` в стандартной документации предназначен для сравнения/упорядочивания, но не объявлен consecutive для этого потока. По этой причине отсутствие `u+1` validation не является подтверждением непрерывности архива. Требуется официальный контракт именно для исторического depth-200 файла либо независимый integrity manifest/sequence proof. Не добавлять произвольное continuity правило без такого контракта.

Временные и markout проверки подтверждают только корректность обработки имеющихся записей, но не полноту самого архива. Следовательно, aggregate-L2 queue replay остаётся research proxy и не получает допуска к strategy PnL. Новые архивы не скачивались; runner не запускался; private API, orders и PnL не использовались. Предыдущий terminal CI run 41835268896 подтвердил 60/60 deterministic queue primitive tests на commit e7f4174; этот checkpoint update не меняет тестовый код.

Источники документации (проверены 2026-11-04): стандартный public orderbook https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook; отдельный Full Orderbook https://bybit-exchange.github.io/docs/v5/websocket/public/full-ob.


## 18. Дополнительное свидетельство по depth-200 update continuity (неофициальное)

Найдено вторичное описание формата quote-saver historical orderbook archive в README стороннего downloader (не Bybit): для futures/spot orderbook JSONL snapshots + deltas, файлы `*_ob200.data.zip`, а `update_id` для deltas описан как monotonically +1. Это потенциально относится к тому же семейству исторических файлов, что runner URL `quote-saver.bycsi.com/orderbook/linear/..._ob200.data.zip`.

Ограничения доказательства:
- источник не официальный Bybit и не подтверждает контракт именно текущего файла/даты;
- описание не устанавливает, что `u` в сырых JSONL runner archive идентичен `update_id` в нормализованном Parquet schema во всех версиях;
- фактический архив не скачивался/не проверялся из-за external-data hold.

Поэтому пока не включать `u+1` enforcement и не считать continuity доказанной. При будущем разрешённом аудите уже имеющегося локального файла можно проверить фактический raw JSONL: event types, snapshot/restart behavior, repeated IDs, gaps in u, seq semantics, cts monotonicity, and archive integrity. До этого остаётся блокер completeness для queue replay. Источник: https://github.com/Anton495/bybit-data-downloader (вторичный, неофициальный; проверен 2026-11-04).


## 19. Строгая проверка схемы historical trade CSV и идентификаторов сделок

В статическом аудите iter_public_trades() выявлены два дефекта валидации входного CSV:
- csv.DictReader при повторяющихся заголовках может молча перезаписать одно из полей, что делает интерпретацию схемы неоднозначной;
- пустой или whitespace-only trdMatchID принимался парсером и мог попасть в обработку как ID сделки.

Исправлено в bybit_l2_queue_replay.py:
- duplicate column names отклоняются до чтения строк;
- trdMatchID должен быть непустой строкой после проверки .strip(); исходное значение ID сохраняется без модификации;
- fail-closed проверки обязательных BT/isBlockTrade и RPI/isRPITrade не ослаблялись.

Добавлены regression tests:
- duplicate CSV headers отклоняются;
- пустой и whitespace-only trade ID отклоняются;
- тестовая фикстура содержит обязательные BT и RPI колонки и корректные newline-разделители.

Изменения в research/market-regime-v1-main:
- source commit: 8fa6e0d0ef23bda6d1f628f3673692640164eb2e;
- regression tests: d122abbd3f7f00d05279993bd43801e7fb4a92ab;
- fixture correction: e188a785df0a865afcee69dec295a4209f3b804f (текущая голова на момент обновления).

CI:
- source-only run 41836144914 завершился SUCCESS;
- первый test run 41836151013 завершился FAILURE из-за некорректной CSV test fixture: в ней использовались двойные escape-последовательности для newline, поэтому парсер закономерно не видел заголовки и останавливался раньше проверки ID;
- fixture исправлена отдельным commit e188a785df0a865afcee69dec295a4209f3b804f;
- повторный run 41836302327: job tests завершился SUCCESS; 56/56 шагов job завершены успешно, включая Test conservative Bybit aggregate-L2 queue replay primitives.

Это подтверждает deterministic parser/queue regression tests, но не доказывает полноту depth-200 архива, реальную maker очередь/L3 priority, delivery latency, cancel behavior, historical fee tier или совместимость BT/RPI конкретного публичного historical CSV. Не запускались новые Bybit archive downloads, strategy PnL, private API, paper/live orders. TRADE_ARCHIVE_FLAGS = UNVERIFIED_COMPATIBILITY и MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL остаются без изменений.


## 20. Запрет queue placement на same-ms/future order-book state

Статический audit показал, что place_passive_order() проверял пассивность цены и брал displayed queue из переданного OrderBook, но сам по себе не проверял timestamp этого состояния относительно arrival_ts. Поэтому прямой вызов primitive мог использовать состояние книги с cts == arrival_ts (неопределённый same-ms порядок) или cts > arrival_ts (будущая информация) и получить некорректную начальную очередь.

Исправлено fail-closed:
- timestamped order-book state обязателен (last_cts не None);
- last_cts должен быть строго меньше arrival_ts; same-ms и future book states отклоняются;
- runner уже строит arrival snapshots только из событий cts < arrival_ts, поэтому его корректные сценарии сохраняются.

Добавлены regression tests для same-ms, future и untimestamped book state. Существующие тесты queue placement приведены к строгому pre-arrival контракту (arrival=1001 при snapshot cts=1000); тесты проверки spec constraints теперь достигают именно соответствующей проверки, а не падают раньше на timestamp guard.

Изменения в research/market-regime-v1-main:
- source commit: de899eaa18aac3d3d8256ff92f6ceea729e9217b;
- new regression tests: 3a3e5676ba79d6c47990d63de4c3cc2c88730b3b;
- test fixture alignment: f8f7b922e176ca5842c899760e3ef7b38a4a2a9a (текущая голова на момент обновления).

CI:
- source-only run 41836500038 завершился failure на старых тестовых ожиданиях, которые использовали book cts == arrival; это ожидаемое следствие нового строгого контракта и было исправлено в тестах;
- run 41836504786 также предшествовал test fixture alignment;
- полный run 41836556302 на commit f8f7b922e176ca5842c899760e3ef7b38a4a2a9a: job tests SUCCESS, 56/56 steps completed successfully; queue replay primitive test step SUCCESS.

Это закрывает конкретную временную утечку на API уровне place_passive_order(), но не решает неизвестную непрерывность depth-200 update stream, отсутствие L3 priority, measured delivery/cancel latency и несовместимость/непроверенность historical BT/RPI CSV. Не запускались новые архивные загрузки, strategy PnL, private API, paper/live orders. MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL остаётся без изменений.


## 21. Дополнительная строгая валидация строк historical trade CSV

В iter_public_trades() выявлено, что csv.DictReader может помещать значения сверх числа заголовков в специальный ключ None. Ранее такие лишние поля не отклонялись и могли быть молча проигнорированы. Также идентификатор trdMatchID проверялся на пустоту через strip(), но исходное значение с внешними пробелами оставалось неизменным; это позволяло одному и тому же биржевому ID иметь разные строковые представления.

Исправлено:
- любая CSV-строка с дополнительными полями отклоняется;
- отсутствие значения любого обязательного поля строки (включая выбранные BT/RPI флаги) отклоняется;
- trdMatchID должен быть непустым и не содержать внешних пробелов; значение не нормализуется молча;
- прежние проверки дублирующихся заголовков, обязательных классификационных флагов и уникальности ID сохранены.

Добавлены regression tests на лишние CSV поля и пробелы вокруг trade ID.

Изменения в research/market-regime-v1-main:
- source commit: 08d6c302c795fe58e7ace603560de9c585b9e57a;
- regression tests: 6c71ff31275e6107f6b6a533c3f0c89cf0e3d9cb;
- исправление newline в test fixtures: fe86247bec1c723a55a9daab2e3c977053089b50 (текущая голова на момент обновления).

CI:
- source run 41836837057: SUCCESS;
- test run 41836847048: FAILURE из-за дефекта новой fixture (newline escape был некорректным, поэтому тест лишних полей не создавал ожидаемую строку);
- после исправления fixture run 41836868306 на commit fe86247bec1c723a55a9daab2e3c977053089b50: SUCCESS, job tests 56/56 steps completed successfully, включая Test conservative Bybit aggregate-L2 queue replay primitives.

Эти изменения укрепляют проверку структуры trade CSV, но не подтверждают, что фактический исторический архив Bybit содержит совместимые BT/RPI поля, и не доказывают полноту архивных записей. Новые архивы не загружались, strategy PnL не запускался, private API и ордера не использовались. MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL остаётся без изменений.


## 22. Полная проверка trade archive после expiry / completion заявки

В replay_public_trades() ранее использовался break при первом trade timestamp >= order.expiry_ts, а также break после полного fill. Это могло скрыть повреждённый порядок строк в оставшейся части CSV: если после первой post-expiry записи встречалась более ранняя запись внутри active window, replay прекращался до её обнаружения. Аналогично дубли tradeMatchID за пределами active window или после completion не обнаруживались.

Исправлено:
- весь public-trade CSV теперь читается до конца для проверки монотонности timestamp и уникальности trade ID;
- строки вне интервала (arrival_ts, expiry_ts) не применяются к очереди;
- после полного fill оставшиеся строки продолжают валидироваться, но не добавляются в processed_trade_ids и не влияют на исполнение;
- повтор ID обнаруживается по всему архиву, включая записи вне active window;
- отсутствующий/пустой/пробельный/обрамлённый пробелами ID отклоняется; текст ошибки согласован с существующим regression test.

Добавлены regression tests:
- out-of-order print после первой post-expiry строки отклоняется и транзакционно откатывает order;
- duplicate trade ID вне active window отклоняется и не мутирует order.

Изменения в research/market-regime-v1-main:
- source logic commit: 49334bb35d1157bec7a4db6aeaeaaf577c17703d;
- tests commit: 8e13d5600139cda2eedef74bb218422704c50c4d;
- error-message compatibility commit: 26d5a46d6760fbede7c6ab88c16ffab48e05f04d (current code head before checkpoint update).

CI:
- run 41837173560 failed only because a pre-existing test asserted the previous error wording ("missing public trade ID"); the new validation correctly raised a broader malformed-ID message;
- message was changed to preserve the expected phrase while still identifying surrounding whitespace;
- final run 41837303070 on commit 26d5a46d6760fbede7c6ab88c16ffab48e05f04d: SUCCESS, job tests 56/56 steps completed successfully, including Test conservative Bybit aggregate-L2 queue replay primitives.

Trade-off: each replay now scans the full CSV instead of stopping at expiry/completion. This is more CPU/I/O per hypothetical order, but avoids silently treating a malformed, out-of-order archive as a valid no-fill result. This remains deterministic input validation, not proof that the source archive itself is complete or semantically compatible. No new archive downloads, strategy PnL, private API, paper/live orders. MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL remains unchanged.


## 23. Конфликтующие алиасы block-trade и RPI

В iter_public_trades() ранее выбирался один из синонимичных столбцов (isBlockTrade при наличии, иначе BT; RPI при наличии, иначе isRPITrade). Если CSV содержит оба алиаса, но значения противоречат друг другу, второй столбец игнорировался. Это могло классифицировать block/RPI print как обычную сделку и завысить модельное исполнение.

Исправлено:
- все доступные алиасы block-trade (isBlockTrade и BT) парсятся строгим boolean parser; если присутствуют оба, их значения обязаны совпадать;
- все доступные алиасы RPI (RPI и isRPITrade) также парсятся и должны совпадать;
- отсутствующее значение любого присутствующего алиаса или конфликт значений приводит к fail-closed ValueError;
- при одном присутствующем алиасе поведение сохраняется.

Добавлены два regression tests: конфликт isBlockTrade vs BT и конфликт RPI vs isRPITrade.

Изменения в research/market-regime-v1-main:
- source commit: 06e4ebfda9583aec9e6641276801dc94c11cf8c1;
- regression tests: 1f518ad55433323b7af73d28074f9d8054074161;
- fixture newline correction: 50fb0b6585104996ed3b2bf279f08c7266e36612 (текущая голова кода/тестов на момент обновления).

CI:
- source run 41837502894: SUCCESS;
- initial test run 41837508481: FAILURE из-за неправильного newline escaping в новых CSV fixtures, в результате тест доходил до проверки отсутствующего RPI столбца, а не до проверки конфликта;
- после fixture correction run 41837526701 на commit 50fb0b6585104996ed3b2bf279f08c7266e36612: SUCCESS, job tests 56/56 steps completed successfully, including Test conservative Bybit aggregate-L2 queue replay primitives.

Это устраняет неоднозначную классификацию при наличии двух aliases, но фактическая схема исторического CSV по-прежнему не подтверждена на raw archive. Не запускались новые загрузки архивов, strategy PnL, private API, paper/live orders. MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL остаётся без изменений.


## 24. Дубликаты ценовых уровней внутри одного L2 события

OrderBook.apply() ранее обрабатывал уровни через dict. Если один и тот же price встречался несколько раз в одном snapshot/delta side, более поздняя запись молча перезаписывала предыдущую. Это делало malformed event неоднозначным и могло исказить displayed queue size.

Исправлено:
- внутри каждого side одного event цена может встречаться только один раз;
- duplicate bid или ask price level отклоняется до commit;
- candidate-state модель сохраняет атомарность: при ошибке текущая книга и last_cts/last_seq/last_u остаются неизменными.

Добавлены regression tests: duplicate price levels в snapshot отклоняются без инициализации книги; duplicate levels в delta отклоняются без изменения ранее восстановленной книги.

Изменения в research/market-regime-v1-main:
- source commit: de84dc284e34d86a47324d45d3412390aaa9f307;
- regression tests: 663595ad478d8eb81b9b365ecdd53ceaabb7d921.

CI:
- source run 41837688799: SUCCESS;
- full test run 41837696571 на commit 663595ad478d8eb81b9b365ecdd53ceaabb7d921: SUCCESS, job tests 56/56 steps completed successfully; queue replay primitive test step SUCCESS.

Это устраняет неоднозначность повторных ценовых уровней в пределах одного event, но не доказывает, что сам исторический depth-200 stream полный или соответствует контракту, который сейчас предполагает replay. Не выполнялись новые archive downloads, strategy PnL, private API, paper/live orders. MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL остаётся без изменений.


## 25. Повторяющиеся JSON object keys в L2 archive

iter_book_events() ранее использовал стандартный json.loads(), который принимает повторяющиеся ключи JSON object и молча оставляет последнее значение. Например, event с двумя полями u/seq/cts или повторным data/b/a мог быть интерпретирован иначе, чем исходная строка архива.

Исправлено:
- добавлен object_pairs_hook _unique_json_object();
- duplicate keys отклоняются на любом уровне вложенности JSON, до проверки и yield event;
- остальные проверки event/data/symbol/strict integer cts сохраняются.

Добавлен regression test с повторным вложенным data.u; archive iterator должен завершиться ValueError.

Изменения в research/market-regime-v1-main:
- source commit: 398d234ff4a0bece192780939914eb25f516f9ae;
- test commit: caf17b5ef566d03963fa0ae4ebb6305d97f6a784;
- исправление вызова теста на l2_module.iter_book_events: e7b60c224d77b3a8fe4bbbacb621f80e069a4294 (текущая голова кода/тестов на момент обновления).

CI:
- source run 41837887140: SUCCESS;
- run 41837896308: FAILURE только из-за NameError в тесте (использовалось неимпортированное имя iter_book_events);
- после module-qualified test fix run 41838006400 на commit e7b60c224d77b3a8fe4bbbacb621f80e069a4294: SUCCESS, job tests 56/56 steps completed successfully, queue replay primitive test step SUCCESS.

Это устраняет неоднозначность повторных JSON ключей, но не подтверждает семантическую непрерывность update IDs depth-200 или отсутствие пропущенных архивных событий. Новые archive downloads и PnL не запускались; private API и paper/live orders не использовались. MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL остаётся без изменений.


## 26. Валидация всех полей каждой historical trade CSV строки

После перехода replay_public_trades() на полное чтение архива для проверки timestamp order/ID uniqueness выяснилось, что iter_public_trades() всё ещё валидировал side, price и size только косвенно через apply_public_trade(). Поэтому malformed side/price/size в строках вне active window заявки могли остаться незамеченными.

Исправлено в iter_public_trades():
- каждая строка архива должна содержать side строго Buy или Sell;
- price и size каждой строки разбираются как конечные Decimal и должны быть строго положительными;
- проверки выполняются до yield, независимо от того, попадает строка в срок конкретной гипотетической заявки или нет;
- исходные price/size значения сохраняются в нормализованной записи после валидации.

Добавлен regression test на неизвестную сторону, нулевую цену и нулевой размер.

Изменения в research/market-regime-v1-main:
- source commit: 54c418a8c840808bcf9be16059994ef7546acb04;
- regression tests: aae78ae30df5ff84582f3ce00c39819267fddb19.

CI:
- source run 41838205603: SUCCESS, 56/56 steps;
- full test run 41838211515 на commit aae78ae30df5ff84582f3ce00c39819267fddb19: SUCCESS, 56/56 steps; queue replay primitive test step SUCCESS.

Таким образом, replay теперь валидирует всю последовательность строк по timestamp, ID, block/RPI flags, side, price и size, включая строки вне active window и после completion. Это повышает строгость структурной валидации, но не доказывает полноту/истинность исходного архива и maker execution realism. Не запускались новые архивные загрузки, strategy PnL, private API, paper/live orders. MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL остаётся без изменений.


## 27. Queue placement за границами видимой L2 глубины

place_passive_order() ранее возвращал queue_ahead=0 для любой цены, отсутствующей в snapshot. Для цены за пределами худшего видимого уровня это некорректно: отсутствие уровня в top-200 не означает отсутствие очереди, поскольку глубже границы снимка ликвидность неизвестна. Такая ситуация могла искусственно завысить fill rate.

Исправлено:
- Buy limit ниже минимальной видимой bid price, если точного уровня нет, отклоняется как outside visible bid depth;
- Sell limit выше максимальной видимой ask price, если точного уровня нет, отклоняется как outside visible ask depth;
- цена без отображённого уровня внутри известного ценового диапазона остаётся допустимой с queue_ahead=0;
- существующие проверки пассивности, timestamp, spec и точного displayed queue сохранены.

Добавлены regression tests на отказ за границами видимой глубины и допустимость пустого уровня внутри известного диапазона.

Изменения в research/market-regime-v1-main:
- source commit: e262ce63c903f7665392b41df4099a3ea38b74b5;
- regression tests: 5ab0b56138bd7cc039f18c0df641a6fda8cec32a.

CI:
- full run 41838431510 на commit 5ab0b56138bd7cc039f18c0df641a6fda8cec32a: SUCCESS, job tests 56/56 steps completed successfully, queue replay primitive test step SUCCESS.

Это предотвращает трактовку неизвестной очереди за границей top-200 как нулевой, но не решает stale-book age/latency и неизвестную полноту архива. Не запускались новые archive downloads, strategy PnL, private API, paper/live orders. MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL остаётся без изменений.


## 28. Граница применимости update ID continuity contract

Повторно сверена официальная документация Bybit по двум различным каналам:
- Standard public orderbook (включая level 200): описывает snapshot/delta, u как Update ID, seq как Cross sequence и occasional u=1 как restart snapshot; отдельное правило u+1 для depth-200 standard stream в описании не установлено.
- Full Orderbook: отдельный delta-only channel; его документация явно требует consecutive u+1 в пределах session и отдельную процедуру синхронизации с REST snapshot.

Вывод: u+1 continuity нельзя переносить с Full Orderbook на исторический depth-200 archive без доказательства, что архив действительно использует тот же stream contract. Текущий replay сохраняет строгую проверку positive integer u, u=1 только snapshot, монотонность seq/cts и атомарность, но не делает неподтверждённое u+1 предположение. Для окончательного решения нужны raw historical archive samples и подтверждённая спецификация формата; новые архивы не загружались из-за действующего external-data hold.



## 29. capture_book_at: проверка хронологии после arrival boundary

В capture_book_at() был ранний break на первом событии с cts >= arrival_ts. Это корректно исключало same-ms/future updates из книги, но одновременно прекращало чтение архива. Если позже в файле находилось событие с cts < arrival_ts (нарушение порядка архива), оно не обнаруживалось; функция могла вернуть устаревшее состояние, считая архив корректным.

Исправлено:
- arrival_ts проходит strict integer validation и должен быть положительным;
- функция продолжает сканировать весь archive после arrival boundary;
- все cts проверяются как strict positive integer и globally non-decreasing;
- в OrderBook.apply() попадают только события с cts < arrival_ts; same-ms/future updates не применяются;
- out-of-order event после arrival теперь fail-closed вместо незаметного возврата неполной книги.

Добавлены regression tests: out-of-order cts после arrival boundary и fractional arrival_ts.

Изменения в research/market-regime-v1-main:
- source commit: 4362daa0b6bd9941e5ac32109389d23eb7b42eee;
- regression tests: 892ca5bcf09a8c7bda7b2d677b66b6dc9f6f4baf.

CI:
- full run 41838847266 на commit 4362daa0b6bd9941e5ac32109389d23eb7b42eee: SUCCESS, 56/56 steps; queue replay primitive test SUCCESS; no failed steps.

Исправление гарантирует, что point-in-time capture не принимает архив с нарушенной хронологией после точки отсечения. Оно не подтверждает непрерывность update IDs depth-200 и не заменяет доказательство полноты архива. Новые архивы не скачивались, strategy PnL не запускался, private API и paper/live orders не использовались. MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL остаётся без изменений.


## 30. Строгая валидация target timestamps в markout state capture

scripts/run_bybit_l2_queue_replay.py:capture_book_states_at() принимал targets напрямую через sorted(set(targets)); float/bool/string значения могли попасть в расчёт возраста состояния книги и markout target без строгой проверки. Также после основного capture loop находился недостижимый второй цикл для ordered[next_index] == cts: первый цикл уже обрабатывал все targets <= cts.

Исправлено:
- каждый markout target проходит общий strict_int parser (bool/float/string coercion запрещены);
- все target timestamps должны быть положительными;
- удалён недостижимый дублирующий цикл, не меняя правило исключения same-ms updates: capture выполняется до применения события с cts >= target.

Добавлен regression test для fractional, bool, string и нулевого target.

Изменения в research/market-regime-v1-main:
- runner commit: 75ff12884210356fcc58d78999befa2ec90857ba;
- regression tests: c9722e0a3998bccb061a65bc7c0a1e1c33075a12.

CI:
- full run 41839020044 на commit 75ff12884210356fcc58d78999befa2ec90857ba: SUCCESS, 56/56 steps; queue replay primitive test SUCCESS; no failed steps.

Это закрывает нестрогую валидацию внутренних временных целей markout. Оно не меняет ограничения stale-book age, delivery latency, L3 queue priority и неизвестной полноты depth-200 archive. Новые архивы не скачивались, strategy PnL не запускался, private API и paper/live orders не использовались. MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL остаётся без изменений.


## 31. Freshness of captured book state: age is observable, validity is not inferable from age alone

Static audit of scripts/run_bybit_l2_queue_replay.py confirms:
- arrival scenarios already report book_state_age_ms = arrival_ts - last_book_cts;
- post-fill markouts already report book_state_age_ms = target_ts - last_book_cts;
- there is no max-age cutoff or stale/fresh classification.

Decision: do NOT add an arbitrary age threshold or reject an otherwise quiet book solely because its last update is old. The archive is an event stream; a long gap can mean no book changes, a capture outage, or missing archived messages. Without verified heartbeat/sequence continuity and the exact historical archive contract, timestamp age alone cannot distinguish these cases. Current output exposes the age but must not be interpreted as proof of freshness.

Before using queue-fill estimates, future archive-level audit must establish whether heartbeat records, connection/session markers, or a documented continuity signal exist. If they do not, report age distributions and flag long gaps as ambiguous, not as confirmed data loss. A future report should stratify queue outcomes by observed age rather than silently treating all ages as equally reliable.

## 32. CI side effects reviewed

Inspected full GitHub Actions log for run 41839020044 and its workflow `.github/workflows/research-checks.yml`.

- The CI job did run `scripts/audit_cryptofetch_archives.py` against the already checked-out local directory `data/archives/cryptofetch`; no network downloader or Bybit archive collector was invoked.
- It also ran `scripts/run_h_a_relative_strength_replay.py` without `--execute`; log explicitly says `PREPARE ONLY: no market PnL replay was run`.
- Existing local CryptoFetch audit output: 67 valid files, 64 backtest-eligible, 3 empty/too short, 0 rejected, 0 conflicting overlapping bars, 6 duplicate symbol/timeframe groups, 0 longest-file-not-superset pairs.
- H-A preparation output: 50 H1 symbols before terminal filter and 50 included, common terminal timestamp 1792972800000; no PnL replay.

Thus this CI run did not download new market archives, run the H-A PnL replay, access private Bybit API, or place orders. It did inspect existing repository OHLCV files and create/upload audit/preparation artifacts. This distinction is recorded so future workflow changes can be checked against the external-data hold.

Maker execution remains blocked for strategy PnL: no measured delivery latency, no exchange-confirmed historical order lifecycle, no L3 queue priority, no verified depth-200 archive continuity contract, and no historical fee tier ledger. No arbitrary stale-age threshold was introduced.


## 33. Cross-sequence validation across the complete arrival-capture archive

Official Bybit standard public orderbook documentation was rechecked (2026-11-04): the standard depth stream describes snapshot/delta handling, says `u=1` is a restart snapshot marker, and defines `seq` as cross sequence where smaller values indicate earlier data. It does not document `u+1` continuity for the standard depth-200 stream. The separate Full Orderbook stream has a distinct explicit consecutive-u contract; it must not be transplanted to standard depth-200 archives.

Accordingly, no u monotonicity/continuity enforcement was added. Existing behavior continues to treat `u=1` only as a full-snapshot reset marker, while avoiding assumptions about repeated or skipped `u` values in this archive format.

New confirmed validation: capture_book_at() previously validated cts ordering across the full archive, but seq ordering was only checked by OrderBook.apply() for events before arrival_ts. A seq regression in later rows could therefore escape the full-archive integrity scan. It now validates every event's seq as a strict positive integer and rejects a decrease anywhere in the archive, including after arrival_ts. Equal seq remains allowed because the documented rule only establishes that smaller seq is earlier; it does not state that every same-stream event must have a unique seq.

Regression test added: seq regression after arrival boundary.

Commits:
- source: 6fe9bd49a68ad79d596ad6ec59fbfeb3a11a21da
- tests: b017e3f928d8dd07161a0c1fc673e18ca17b5d14

CI:
- run 41839709345 on source commit 6fe9bd49a68ad79d596ad6ec59fbfeb3a11a21da: SUCCESS, 56/56 steps, queue replay primitive test SUCCESS, no failed steps.

Official documentation references: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook and https://bybit-exchange.github.io/docs/v5/websocket/public/full-ob. The former does not specify standard depth-200 u+1 continuity; the latter explicitly does for its separate Full Orderbook protocol.

No archives were downloaded; no PnL replay, private API, or orders were run. Maker execution realism remains BLOCKED_FOR_STRATEGY_PNL.


## 34. Runner-level deterministic tests added

Static audit found that the L2 queue replay primitives had 80 tests, but the orchestration helpers in scripts/run_bybit_l2_queue_replay.py had no dedicated test module. Added tests/test_run_bybit_l2_queue_replay.py and wired it into the Research CI compile/test steps.

Coverage added:
- capture_scenarios() captures the last book state strictly before each scheduled arrival boundary, including when an event has exactly the same cts as the arrival;
- insufficient archive duration fails rather than fabricating missing scenarios;
- capture_book_states_at() excludes the event at the exact markout target, uses the preceding book state, and does not extrapolate beyond the archive end;
- malformed/out-of-order archive tails are rejected even when the target timestamp occurred earlier.

The first CI attempt exposed a test-only import-path issue (the repository root was not on sys.path when executing the test file directly). This was fixed; no production behavior change was needed for that failure.

Final CI:
- run 41840361238 on commit d2740c6ff444c3a7302b4b04dcc04d15ebf1dcb1: SUCCESS, 57/57 steps;
- L2 primitive suite: 80/80 tests passed;
- new runner chronology/markout test step: SUCCESS.

Commits:
- initial runner tests: be036969543fa05b7bfaced2ad25fb17fefd738e;
- fixture newline correction: ee12b38811e8537fb4817ea123a2a52cf3485da3;
- CI wiring: a969acf7e4307be299d82812d3de9331ce671339;
- import-path correction: d2740c6ff444c3a7302b4b04dcc04d15ebf1dcb1.

This adds regression coverage only; no strategy PnL, archive downloads, private API, or orders were run. Maker execution realism remains BLOCKED_FOR_STRATEGY_PNL.


## 35. Empty L2 arrival archive fails with an explicit validation error — 2026-11-04

Static audit of `scripts/run_bybit_l2_queue_replay.py:capture_scenarios()` found that a valid ZIP container with one empty `.data` member left `first_cts=None`; the scheduled-arrival tail then attempted arithmetic on `None`, producing an incidental TypeError rather than a controlled input-validation failure.

Correction:
- Explicitly reject a stream with no book events using `ValueError("order-book archive contains no events")`.
- Added `test_capture_scenarios_rejects_empty_order_book_archive` using an empty `.data` archive.

Commits:
- source: `067109a14312c39ebd95ecf2eaede8d19375426c`
- regression: `54f30eeb095fb01998bf9d03b69c4ff2a1b40687`

Verification status:
- Both modified files were fetched again from `research/market-regime-v1-main`; the guard and regression are present.
- The last confirmed CI remains #41840361238 on `d2740c6ff444c3a7302b4b04dcc04d15ebf1dcb1`, SUCCESS (57/57 steps; L2 primitives 80/80; runner chronology step SUCCESS).
- CI outcome for the new source/test commits has not been retrieved. This regression is **not yet claimed as passed**.
- No market PnL, data download/collector, private API/account access, paper/live orders, or main-branch changes.


## 36. Validate complete L2 archive payload after the arrival boundary — 2026-11-04

Static audit found that `capture_book_at()` checked `cts` and `seq` for the full archive but skipped applying events at/after `arrival_ts` to an order book. That correctly prevented future/same-ms events from contaminating the returned pre-arrival snapshot, but it also meant malformed post-boundary payloads (for example, non-integer `u` or a crossed reconstructed book) could escape validation.

Correction:
- Keep the returned `book` frozen at the last state strictly before arrival.
- At the first event at/after arrival, seed a separate validation-only `OrderBook` from the pre-arrival state and apply the remaining events to it. This validates update IDs, levels, snapshot/delta semantics and reconstructed-book integrity without introducing look-ahead into the returned snapshot.
- Added `test_capture_book_at_rejects_malformed_book_events_after_arrival_boundary`, covering malformed update ID and crossed book in the tail.

Commits:
- source: `b79d827d7c6feadb7f4bf9f306fede7b5bd53f25`
- regression: `57f5263c7bbd5f123e19cd2be2f23c2a31765446`

Verification:
- Source and test were re-fetched from the working branch; both changes are present.
- The available commit-associated workflow lookup returned no runs for the test commit. CI is **unverified**; no claim that the new test passed.
- The immediately preceding empty-arrival-archive guard is recorded in section 35; its CI status is also unverified.
- No market PnL, archive collection/download, private API/account access, paper/live order, or main-branch change.


## 37. Final L2 archive-tail validation update — 2026-11-04

- Added a validation-only reconstructed book after the arrival boundary in `capture_book_at()`. This catches malformed update IDs and invalid reconstructed states in the archive tail while keeping the returned snapshot strictly pre-arrival.
- Regression: `test_capture_book_at_rejects_malformed_book_events_after_arrival_boundary` covers a non-integer update ID and a crossed book.
- Commits: source `b79d827d7c6feadb7f4bf9f306fede7b5bd53f25`; test `57f5263c7bbd5f123e19cd2be2f23c2a31765446`.
- This follows section 35's empty-archive handling fix (`067109a14312c39ebd95ecf2eaede8d19375426c`; regression `54f30eeb095fb01998bf9d03b69c4ff2a1b40687`).
- Both code/test pairs were re-fetched from the research branch and their changes confirmed. The available commit-associated workflow lookup returned no runs for the latest test commit; new tests remain **CI-unverified**. The last verified Research CI is still #41840361238 on `d2740c6`, SUCCESS, 57/57 steps.
- No market PnL, archive download/collector, API/account access, runner registration, paper/live orders, or main-branch changes.


## 38. Runner test file was not executing its plain test functions; fixed and verified — 2026-11-04

A direct audit of the actual CI log for run #41842036275 revealed that the step `python tests/test_run_bybit_l2_queue_replay.py` emitted no test output. The file contained plain `test_*` functions but no `unittest`/pytest discovery or `__main__` invocation. Therefore that earlier successful CI step had not executed the runner tests. Previous checkpoint statements describing the runner test step as executed evidence are superseded by this finding.

Correction and validation:
- Commit `60d9202b0f93fccd1938c99137cbeefd3094f9d5` added a `__main__` runner that calls each `test_*` function and reports individual PASS lines and the count.
- The first real execution (CI #41842455791) correctly failed on an existing incorrect test expectation: it expected a book state after the final archive event, despite the function's deliberate no-extrapolation rule. This was a test-fixture defect, not a production-code defect.
- Commit `19ca8bcfe407cecea18a2bfc6ad5c86cf54085af` fixed the fixture by adding a later archive event to bracket the intermediate target, while preserving the assertion that a target after the final event is not extrapolated.

Final verification:
- Research CI #41842592947 on `19ca8bcfe407cecea18a2bfc6ad5c86cf54085af`: run conclusion SUCCESS; job `tests` SUCCESS; all 56 workflow steps completed successfully.
- Actual log output: runner chronology/markout file **5/5 tests passed**; aggregate L2 primitive suite **81/81 tests passed**, including `test_capture_book_at_rejects_malformed_book_events_after_arrival_boundary`.
- The empty archive regression `test_capture_scenarios_rejects_empty_order_book_archive` also appears in the 5/5 executed runner suite.
- CI #41842036275 succeeded but did not execute the runner test functions; do not use it as evidence for those tests.

No market PnL, market archive download/collector, Bybit private/account API, self-hosted runner, paper/live order, or main-branch change. PR #4 remains Draft/open. Continue with independent static review only unless a new reproducible defect is found.


## 39. Exact millisecond timestamp cutoff fixed and verified — 2026-11-04

Static CSV parser review found that `parse_trade_timestamp_ms()` classified values as milliseconds only when strictly greater than `1_000_000_000_000`. Therefore the exact valid millisecond timestamp `1000000000000` was incorrectly treated as seconds and multiplied by 1,000.

Correction:
- Changed the cutoff to `>= Decimal("1000000000000")`.
- Added an exact-boundary regression assertion in `test_trade_timestamp_parser_preserves_exact_seconds_and_milliseconds`.

Commits:
- source: `e972a4466ed8053b0471eead932144a18ee91790`
- test: `a9443b1c9ee81d63ab80150ffe3650af78aff560`

Verification:
- Research CI #41842908843 on `a9443b1c9ee81d63ab80150ffe3650af78aff560`: SUCCESS; job `tests` SUCCESS; all 56 workflow steps completed.
- Actual log: aggregate L2 primitives **81/81 passed**; L2 runner chronology/markout suite **5/5 passed**.
- Read-only audit of report serialization and CSV schema found no additional reproducible issue. No networked runner `main()` or market-data download was executed.
- No PnL, archive collection/download, private API/account access, runner registration, paper/live order, or main-branch change.


## 40. Dated Bybit specs, risk tiers and account fee provenance remain absent — 2026-11-04

Read-only GitHub inventory:
- `data/archives/` contains only the existing `cryptofetch/` directory.
- `data/archives/bybit/`, `data/instrument_specs/`, and `data/risk_tiers/` are absent (GitHub Contents API returned 404).
- No new archives or collector workflows were run.

Interpretation:
- `InstrumentSpecHistory` and `RiskTierHistory` implement strict dated/as-of loading, but there are no committed historical Bybit snapshots to supply those loaders. Current specs cannot be substituted for historical snapshots.
- L2 report explicitly records `order_spec_validation=not_performed_no_verified_historical_snapshot` and `fee_accounting=not_calculated_requires_account_fee_tier_per_fill`.
- Existing maker/taker/slippage constants are modeled assumptions, not account-specific historical fee evidence. No private API/account access was used.
- Execution-realism audit continues to block maker PnL because spread, queue, partial-fill latency, cancel latency/adverse-selection and dated account fee evidence remain incomplete.
- PR #4 is still open + Draft. No main-branch changes, merge/rebase/retarget, PnL, market data downloads, API, runner registration or orders.

No code change was justified by the artifact inventory. Continue read-only review only until the required dated public data/snapshots and execution evidence can be acquired within the project's approved gates.


## 41. Risk-tier as-of timestamps now enforce exact millisecond semantics — 2026-11-04

Static review of `bybit_risk_tiers.py` found that `get_tiers()` and `get_tier()` coerced `as_of_ts` with `int()`. This silently accepted booleans, numeric strings and fractional values, unlike `InstrumentSpecHistory`'s strict integer-ms contract. The snapshot parser also used floating-point `datetime.timestamp() * 1000` and accepted sub-millisecond `fetched_at` values.

Correction:
- Added a shared strict `_as_of_ms()` guard: only integer milliseconds are accepted; bool, float and string inputs fail closed.
- Snapshot timestamps now require millisecond precision, normalize explicitly to UTC, and convert using integer timedelta arithmetic rather than float.
- Added regressions for invalid as-of types, sub-millisecond timestamps and exact timezone-offset conversion.

Commits:
- initial source: `7f16b39da23a8b6fbe1b80b05c51d53aa2318fdd`;
- UTC normalization: `aa35e028dac3a6ba478e93cee36b693138708dfe`;
- initial tests (one incorrect expected epoch, caught by CI): `5f6001e7620222738e8bac2b28a1078d4242d2a3`;
- corrected tests: `ae64222055c794584ee2b4207e940762b12fb130`.

Verification:
- Final Research CI #41844132573 on `ae64222055c794584ee2b4207e940762b12fb130`: SUCCESS; job `tests` SUCCESS; all 54 workflow steps completed.
- Actual job log confirms `tests/test_bybit_risk_tiers.py` ran **13/13 tests**, including all new timestamp regressions. The full deterministic suite and compile step also passed.
- Intermediate CI #41844055151 failed only because the newly added timezone test contained an incorrect expected epoch; the UTC-normalization implementation was retained and the fixture corrected before the final green run.

No Bybit data collection, market PnL, private API/account access, runner registration, paper/live orders, or main-branch changes. PR #4 remains Draft/open. Continue with read-only point-in-time contract audit; strategy PnL remains blocked by missing dated snapshots and execution evidence.


## 42. Bybit snapshot collectors now emit timestamps accepted by as-of loaders — 2026-11-04

Static audit found that both Bybit snapshot collectors used `datetime.now(timezone.utc).isoformat()` by default, which emits arbitrary microsecond precision. The corresponding `InstrumentSpecHistory` and `RiskTierHistory` loaders deliberately reject timestamps not aligned to milliseconds. Thus a collector could create a snapshot that its own history loader would reject.

Correction:
- Both `scripts/snapshot_bybit_instruments.py` and `scripts/snapshot_bybit_risk_limits.py` now emit canonical UTC timestamps with exactly millisecond precision.
- Explicit timestamps must be valid timezone-aware ISO-8601 values aligned to milliseconds; they are normalized to UTC.
- Added offline tests for default precision, naive/sub-millisecond rejection, offset normalization and full collector-to-history round-trip (build, write, load, as-of lookup).

Commits:
- instrument collector source: `36686cb65a5dfc7d9adf6ec63e04c3a2fc1ae272`;
- risk-limit collector source: `5c99ecb47f734406ed6e8c925093f60e688990d8`;
- instrument collector tests: `3277c7c038a295bea6a6123decc3426d63d1a7d6`;
- risk-limit collector tests: `729bc1a18d676e5c4dee81e3e29db37bbb21949f`.

Verification:
- Intermediate runs exposed only test-fixture expectation mistakes (canonical `.000Z` formatting and using an as-of timestamp earlier than the generated snapshot). Both fixtures were corrected; no collector network call occurred.
- Final Research CI #41845297286 on `729bc1a18d676e5c4dee81e3e29db37bbb21949f`: SUCCESS; job `tests` SUCCESS; 57 completed workflow steps, no failed steps.
- Actual logs confirm `tests/test_snapshot_bybit_instruments.py` **17/17 passed** and `tests/test_snapshot_bybit_risk_limits.py` **16/16 passed**, including both generated-snapshot round-trip tests.

No Bybit collectors or downloads, market PnL, private API/account access, runner registration, paper/live orders, or main-branch changes. PR #4 remains Draft/open. Continue read-only data-contract review; strategy PnL remains blocked by missing dated exchange snapshots and execution evidence.


## 43. Risk-tier history rejects missing higher-tier mmDeduction and boolean numerics — 2026-11-04

Static comparison of the history loader with the snapshot collector found a fail-open mismatch: RiskTierHistory.from_directory() defaulted a missing/empty mmDeduction to zero for every tier, while the collector requires this field on every tier above the lowest. A malformed archive could therefore load with incorrect maintenance-margin deduction. The shared Decimal parser also accepted bool values as numeric 0/1 in some fields.

Correction:
- Only the lowest tier may omit mmDeduction; missing/empty deduction on a higher tier now fails closed.
- _d() explicitly rejects booleans.
- Added regressions for missing higher-tier deduction and boolean maintenance-margin input.

Commits:
- source: 6a668cf70c26680a751ed62fd8b1d9a24799fa76;
- tests: 625b84cc3c6eb6354a6801262ee77d77ad9efe5b.

Verification:
- Research CI #41845762278 on 625b84cc3c6eb6354a6801262ee77d77ad9efe5b: SUCCESS; job tests SUCCESS; all 57 workflow steps completed without failure.
- Actual log confirms risk-tier history 15/15 tests passed, including both new regressions; mark-price liquidation and engine integration suites also passed.

No collector execution, Bybit data download, PnL, private API/account access, runner registration, paper/live orders or main-branch change. PR #4 remains Draft/open. Continue read-only schema and execution-consumer review; strategy PnL remains blocked pending verified historical snapshots and execution evidence.


## 44. RiskTierHistory is explicitly restricted to linear contracts — 2026-11-04

Static review found that RiskTierHistory and calculate_margin_requirements() implement Bybit linear/USDT risk-tier semantics, but the loader and direct constructor could accept category=inverse. That would permit inverse tiers to be evaluated with linear IM/MM formulas.

Correction:
- RiskTierHistory now rejects every snapshot category except linear.
- The separate snapshot collector may still archive inverse category data, but this linear margin model cannot consume it.
- Added a regression for constructing RiskTierHistory from an inverse-category snapshot.

Commits:
- source: 2959547ab8c5150ebb9648e54c2792965ea1d06e;
- tests: 6a257b205aef1b8724845c7f6b83fbe0b7aed1b4.

Verification:
- Research CI #41846247554 on 6a257b205aef1b8724845c7f6b83fbe0b7aed1b4: SUCCESS; job tests SUCCESS; all 57 workflow steps completed without failure.
- Actual logs confirm the new inverse-category regression and risk-tier history suite **16/16 passed**.

No Bybit data collection/download, PnL, private API/account access, runner registration, paper/live orders or main-branch changes. PR #4 remains Draft/open. Continue read-only metadata and type-guard review; the PnL gate remains closed.


## 45. Snapshot history loaders enforce integer metadata types — 2026-11-04

Static review found that Python considers bool values equal to integers: schema_version=true passed a comparison with 1, and count/tier_count=true could pass for a one-row snapshot.

Correction:
- InstrumentSpecHistory and RiskTierHistory now require schema_version to be a non-bool int equal to 1.
- Instrument snapshot count and risk-tier tier_count must be non-bool integers equal to the actual row count.
- Added regressions for boolean schema_version and count/tier_count in both history loaders.

Commits:
- instrument history source: 43765d20a61a56c0ce165f6e20c7eb163ae38987;
- risk-tier history source: b2d284529ceeddab617d4d2ba95c7974b2d0098a;
- instrument history tests: 7fd2d8623ef2ba70248b457504f868e1877afa63;
- risk-tier history tests: 3b7442b32383f5c41043ea7bf74430e1acbcd7b2.

Verification:
- Research CI #41846644399 on 3b7442b32383f5c41043ea7bf74430e1acbcd7b2: SUCCESS; job tests SUCCESS; all 57 workflow steps completed without failure.
- Actual logs confirm InstrumentSpecHistory **12/12 passed** and RiskTierHistory **17/17 passed**, including the new metadata type regressions.

No Bybit collector/download, market PnL, private API/account access, runner registration, paper/live orders or main-branch changes. PR #4 remains Draft/open. Next: verify final branch/PR/CI state, then continue independent static execution-consumer review.


## 46. Risk-tier isLowestRisk metadata must be an integer — 2026-11-04

The risk-tier snapshot collector and history loader rejected booleans but accepted JSON floating-point values 1.0 and 0.0, because Python compares them equal to integers. The Bybit schema field is an integer flag.

Correction:
- Both collector and history loader now require isLowestRisk to be a non-bool integer exactly 0 or 1.
- Added offline regression coverage in both collector and history-loader suites.

Commits:
- history loader source: a14f21c35bfe77674d3a7a3850396a6ecc2d781f;
- history regression: 3e7047ddc19cff0543ab72fd1b42ce65df72236b;
- collector source: 57796a8ecca249a482604a7e9b67dfa968cb9ff1;
- collector regression: 715a7fe71350ff5ffd58b7bb7b1a232e6b7d57c6.

Verification:
- Research CI #41847652788 on 715a7fe71350ff5ffd58b7bb7b1a232e6b7d57c6: SUCCESS; job tests SUCCESS; all 57 workflow steps completed without failure.
- Actual logs confirm both new float-flag regressions passed; collector suite 17/17, history suite 18/18.

Read-only execution consumer review also traced optional exchange sizing, dated tier selection, exact contract quantity through partial exits/fees/funding/MTM. Documented limits remain: OHLC/L2 execution proxies, account-level tier aggregation, settlement-mark approximation, static/account-unspecific fees and no dated historical Bybit snapshots.

No Bybit collection/download, PnL/backtest, private API/account access, runner registration, paper/live orders or main-branch changes. Continue static audit only; PnL gate remains closed.


## 47. Funding timestamps must remain integer milliseconds — 2026-11-04

Static audit found that the Funding accounting helpers and active Bybit Funding API parser converted timestamps with int() without checking the original type. A numeric float such as 2000.5 could therefore be silently truncated, potentially moving a settlement to a different millisecond boundary.

Correction:
- Added a positive, non-bool integer-millisecond validator for entry, as-of, TP1, final-close and event timestamps in both funding accounting helpers.
- The active Funding parser accepts only a non-bool integer or an ASCII digit string; floats, booleans and decimal strings fail closed.
- Added offline regressions for fractional/boolean timestamps in both accounting and API parsing.

Verification:
- Intermediate CI attempts exposed only an assertion-regex mismatch in the new test because malformed events are wrapped in a contextual ValueError. The test was corrected; no code behavior defect remained.
- Final Research CI #41848927029 on 39af6fa583ef2074b33905e89c8b78c9b58d83a1: SUCCESS; 57/57 workflow steps, zero failures.
- Actual logs: funding accounting 23/23; Bybit market-history parser 26/26; both new regression methods passed.

No market PnL/backtest, Bybit collection/download, private API/account access, runner registration, paper/live orders or main changes. Funding archive completeness and execution-realism gates remain closed.

### Current branch topology snapshot — 2026-11-04
- main: c87612207d145af433394f0ea992f2d29eba28d5
- research/market-regime-v1-main: 39af6fa583ef2074b33905e89c8b78c9b58d83a1
- merge base: ae599a2f3279e15fe27360662f94f0e7ef8db5be
- GitHub compare: diverged, 2125 commits ahead / 36 behind
- PR #4: open, Draft, mergeable=false
- Do not merge, rebase, reset, force-push or delete this research branch. Preserve both histories; future integration must use reviewed small patches/cherry-picks or a fresh integration branch.


## 48. TP1 must preserve minNotional at the planned short TP2 exit — 2026-11-04

Static audit found that _apply_tp1() checked the remaining exchange-sized quantity against min(stop_price, entry_price), but did not include TP2. For a short, TP2 can be below both entry and initial stop. The remainder could therefore pass TP1 validation while a planned TP2 reduce order would be below minNotionalValue and later fail final-close validation.

Correction: remaining quantity is now checked against the lowest of stop, entry and TP2 prices. The TP1 leg continues to be checked at TP1 price. Added a regression where TP1 leg notional is exactly 45, remaining TP2 notional is 40, and minNotionalValue is 45; TP1 must be rejected with state unchanged.

Verification:
- Final Research CI #41850162961 on e01a53868885f5ac79f2ad3d3cfa3179e7207b1a: SUCCESS, 57/57 workflow steps, no failed steps.
- Actual log: test_tp1_rejects_short_remainder_below_min_notional_at_tp2 passed; MarkPriceEngineIntegrationTests 9/9.
- Source-only CI #41850143419 on 7238076b271bf25010d01ce2df0c1321e3652722: SUCCESS, 57/57 steps.

Classification: exchange-order validity guardrail; not strategy/PnL evidence. No market replay, data download, collector, private API, runner, paper/live orders or main-branch changes.


## 49. Current Git topology after ENG-EXEC-015 documentation — 2026-11-04

- main: c87612207d145af433394f0ea992f2d29eba28d5.
- research/market-regime-v1-main before this checkpoint-only commit: 0c30a0c32a2dc4d8347568c30b21d4d208a3c097.
- merge base: ae599a2f3279e15fe27360662f94f0e7ef8db5be.
- GitHub compare: diverged, 2,134 ahead / 36 behind.
- PR #4: open, Draft, mergeable=false; head is research/market-regime-v1-main.
- The prior topology section (2125 ahead) is superseded by this fresh snapshot. Preserve both histories; do not merge/rebase/reset/force-push. main unchanged.


## 50. Exchange-sized restore constraints and TP1 funding-state consistency — 2026-11-04

Restore path now rejects exchange-sized positions whose initial/remaining quantity is below minOrderQty, whose remaining notional at the lowest planned exit (stop/entry/TP2) is below minNotionalValue, or whose TP1 leg violates minOrderQty/minNotionalValue. Two regression cases added. CI #41851236490 (d50c923b2e158e951d9ca979708d093e54ae3983) SUCCESS, 57/57 steps. A first run exposed only an assertion mismatch against the persistence loader's intentionally wrapped RuntimeError; test now asserts fail-closed behavior rather than inner message text.

Funding audit found accrued_funding_cost() and accrued_funding_cost_for_remaining_margin() accepted a TP1 timestamp while tp1_hit=false, and accepted non-bool tp1_hit values through truthiness. Both now require a bool and enforce timestamp iff TP1 is hit. Two regressions added. Final CI #41851768270 (3170738a78eac92b0a93eda66510c038660f0864) SUCCESS, 57/57 steps; actual log confirms both tests passed; funding suite 76 tests. Source-only CI #41851738950 (568f5ed2552d27dadfeb82c4d1e9610cfac3cd13) SUCCESS, 57/57.

Classification: execution/persistence/accounting correctness; no evidence of strategy profitability. No market PnL, archive downloads, private API, runner, paper/live orders, or main changes.


## 51. MinNotional must use actual planned exit prices, not entry — 2026-11-04

Refined exchange-sized TP1/restore checks: entry price is not a planned exit order. The minimum notional price is now min(stop_price, tp2_price), with TP1 leg separately validated at TP1 price. This avoids false rejection after a long trailing stop rises above entry while both actual exit prices still meet minNotionalValue.

Regression: exchange-sized long entry 100, trailing stop 110, TP2 112, qty 1, minNotional 105. Restore succeeds although entry notional is 100, because stop and TP2 notionals are valid. CI #41852293859 on c88e587d01739eb7c0ee6fe94e0369b28aff664c: SUCCESS 57/57; actual log confirms new test passed; state persistence suite 77/77.


## 52. Git topology after execution/accounting guardrail updates — 2026-11-04

- main: c87612207d145af433394f0ea992f2d29eba28d5.
- research/market-regime-v1-main before this checkpoint-only commit: 3bdce827c02767e93b43eb5c9e7d88fea58b8a3d.
- merge base: ae599a2f3279e15fe27360662f94f0e7ef8db5be.
- GitHub compare: diverged, 2,148 ahead / 36 behind.
- PR #4: open, Draft, mergeable=false; preserve both histories. No merge/rebase/reset/force-push; main unchanged.
- Latest tested code/test head: c88e587d01739eb7c0ee6fe94e0369b28aff664c; CI #41852293859 SUCCESS, 57/57. Subsequent commits were documentation-only.


## 53. Funding helpers enforce TP1 flag vs actual remaining quantity — 2026-11-04

Both cumulative funding helpers now reject inconsistent lifecycle state: TP1 false with a partial remaining quantity, and TP1 true with no quantity reduction. The remaining-margin helper also validates remaining_fraction in [0,1]. Exact contract quantity is authoritative over stale/rounded display fraction.

The funding test fixture's default was corrected from a half-size remainder to full quantity when TP1 is false. Added three regressions (partial quantity without TP1, TP1 true without reduction, exact partial contract quantity without TP1). Final CI #41853410298 on 0cf45d16809a04e2653325934b37723b009097d0: SUCCESS 57/57; log confirms all three tests and funding suite 28/28. An intermediate source-only run failed because it checked out the previous fixture, which contradicted the new invariant; corrected fixture and rerun passed.

Classification: accounting/state-integrity guardrail only; not strategy/PnL evidence. No market-data, PnL, API, runner, paper/live or main changes.


## 54. Restore must verify realized TP1 gross against closed leg — 2026-11-04

Restore previously trusted any finite, nonnegative `realized_tp1_gross_usdt` once TP1 was marked hit. Since this field is directly included in MTM/final PnL, a stale or modified backup could inject arbitrary realized gross.

Now `load_state()` recomputes expected TP1 gross from actual closed quantity and TP1 price: exact `tp1_contract_qty * abs(tp1-entry)` for exchange-sized positions; legacy `size_usdt * (1-remaining_fraction) * abs(tp1-entry)/entry` otherwise. Comparison follows 4-decimal engine rounding (1e-4 tolerance).

Added corrupted legacy backup regression (stored 31 vs expected 30). Updated exchange-sized fixtures to exact contract gross 3 (0.5 contract * 6 price delta), and legacy TP1 liquidity fixture to its valid 30 gross. Final CI #41854119883 on f42979860d97090120ee3a8aed79d59695d441ee SUCCESS 57/57; persistence suite 78 tests; log confirms both valid round-trips and corrupted-gross rejection. Earlier two runs failed only on stale fixtures; final full workflow green.

Classification: persisted PnL integrity, not profitability evidence. No market PnL/backtest/API/runner/paper/live or main changes.


## 55. Git topology after TP1 funding/PnL integrity checks — 2026-11-04

- main: c87612207d145af433394f0ea992f2d29eba28d5.
- Research branch HEAD before this checkpoint-only commit: 1f8283e6e41c1da9e084ce386a5d1b04edcabc36.
- Merge base: ae599a2f3279e15fe27360662f94f0e7ef8db5be; compare main...research: diverged, 2,160 ahead / 36 behind.
- PR #4 remains open, Draft, mergeable=false. Preserve both histories; no merge/rebase/reset/force-push; main unchanged.
- Latest code/test commit with successful full CI: f42979860d97090120ee3a8aed79d59695d441ee; workflow #41854119883 SUCCESS, 57/57; persistence suite 78 tests.
- Commits after that successful code/test head are documentation-only updates to handoff/checkpoint/ledger.


## 56. Restore validates directional MFE/MAE extrema — 2026-11-04

Restore now rejects non-positive persisted max_favorable_px/max_adverse_px (which `__post_init__` would otherwise silently replace with entry), and enforces directional consistency: long favorable >= entry/adverse <= entry; short favorable <= entry/adverse >= entry. Missing legacy fields still default to entry.

Three regressions added: zero favorable extreme, long favorable below entry, short adverse below entry. Source CI #41854906684 SUCCESS 57/57; final test CI #41854947672 on 4c7744c22180a97fa868547eac034cdf91b69491 SUCCESS 57/57; state persistence suite 81 tests, actual logs confirm all three tests.

Classification: restored excursion-metric integrity only; no strategy PnL/backtest/API/runner/paper/live or main changes.


## 57. Git topology after restored MFE/MAE validation — 2026-11-04

- main: c87612207d145af433394f0ea992f2d29eba28d5.
- Research HEAD before this checkpoint-only commit: 249e0d11596fcf8efadd572027b71fe0b55d4c52.
- Merge base: ae599a2f3279e15fe27360662f94f0e7ef8db5be; compare main...research: diverged, 2,166 ahead / 36 behind.
- PR #4: open, Draft, mergeable=false. No merge/rebase/reset/force-push; main unchanged.
- Latest tested source/test commit: 4c7744c22180a97fa868547eac034cdf91b69491; CI #41854947672 SUCCESS, 57/57; state persistence 81 tests. Commits after this code/test head are documentation-only.


## 57. Restore validates stop latches against drawdown thresholds — 2026-11-04

A backup with current drawdown above emergency threshold but `kill_switch_triggered=false`, or current-day drawdown above daily stop but `daily_stop_triggered=false`, could pass restore and re-enable entries because `can_open_new_trade()` trusts those flags.

Restore now requires kill switch true if max(current implied DD, historical max_drawdown_pct) reaches `emergency_kill_switch_pct`; historical max is included so recovery in equity cannot clear the latched emergency stop. For non-empty `current_day_str`, daily stop must be true if current daily DD reaches `daily_stop_loss_pct`.

Three regressions: current emergency breach, historical emergency breach followed by recovery, current daily breach. Source CI #41861236015 SUCCESS 57/57; final CI #41861273155 on 669a7d66c50df5426e63c5490580b2d8bbc92f22 SUCCESS 57/57; persistence suite 84 tests.

Known schema limit: an intraday daily-stop breach followed by recovery before backup cannot be independently reconstructed if the latch is corrupted, because no daily minimum-equity watermark is persisted. Runtime still persists latch transitions. Classification: risk-state integrity only; no strategy PnL/backtest/API/runner/paper/live or main changes.



## 58. UTC rollover CI regression was a stale test double — 2026-11-04

Fresh branch inspection found Research CI #41861996487 and #41862040810 failing in `tests/test_time_model.py::test_mtm_uses_close_timestamp_for_15m_bar`. Production code had intentionally moved UTC-day rollover into `AdaptiveRiskManager.mark_to_market()`, so the equity mark is refreshed before the new-day baseline is captured. The test fixture still replaced `_update_mark_to_market` with a bare timestamp recorder and expected the old direct `on_new_timestamp()` call from `step_candle()`.

Corrected the test double to model the actual production call path (`_update_mark_to_market -> risk_mgr.mark_to_market -> on_new_timestamp`). No production logic was changed for this fix. CI #41866503614 on 8816659b3a81dda7afd920203a2c84ef0839b525: SUCCESS, all 54 numbered test steps. The integrated UTC rollover regression in `tests/test_portfolio_accounting.py` remains in place and verifies the boundary equity is refreshed before daily baseline reset.

Classification: stale test fixture, not a newly confirmed production defect. The earlier failing runs are retained as history; latest tested code state is green.

## 59. Maker markout decomposed into spread capture and post-fill price movement — 2026-11-04

Static audit found that the runner's historical `signed_mid_markout_bps` measures fill-price-to-future-mid return. This is a valid execution-return measure, but it includes the spread captured at entry and therefore does not isolate post-fill adverse selection.

Runner now also captures the last valid L2 BBO strictly before each fill timestamp (same-millisecond events remain excluded; quote age is recorded), then reports two explicit measures at each 1s/5s/30s/60s horizon:
- `signed_fill_to_future_mid_bps`: signed return from actual fill price to future midpoint; includes spread capture.
- `signed_mid_move_from_pre_fill_bps`: signed movement from the pre-fill midpoint to future midpoint; isolates post-fill price movement from spread capture, subject to the recorded pre-fill quote age.

The prior `signed_mid_markout_bps` field is retained as a compatibility alias for fill-to-future-mid. Added a deterministic runner regression proving the two measures differ when the fill captures spread but the midpoint subsequently moves. This is a measurement clarification, not a real-market result; no Bybit sample runner was invoked and no archives were downloaded.

CI #41867866581 on 794342bbd00342d0b7f1af660362794408da0345: SUCCESS. Primitive L2 suite 81/81; runner chronology/markout suite 6/6; all 54 numbered workflow steps successful.

## 60. Git topology and current execution gate — 2026-11-04

- `main`: c87612207d145af433394f0ea992f2d29eba28d5 (unchanged).
- Research branch latest tested code/test head before this checkpoint update: 794342bbd00342d0b7f1af660362794408da0345.
- Merge base: ae599a2f3279e15fe27360662f94f0e7ef8db5be; compare main...research: diverged, 2,180 ahead / 36 behind.
- PR #4 remains Draft and not mergeable; do not merge/rebase/reset/force-push.
- Latest full Research CI: #41867866581 SUCCESS, 54/54 numbered steps; L2 primitive tests 81/81 and runner tests 6/6.
- `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` remains unchanged. Aggregate L2 still lacks verified historical instrument-spec snapshots for every scenario, latency/cancel modeling, L3 priority, and a broad multi-symbol/regime validation sample. Per-fill fee rates must be explicitly supplied; none are guessed.
- No new market archives/downloads, collectors, private Bybit API, PnL backtests, parameter sweeps, paper/live orders, or changes to `main`.



## 61. Проверка временной семантики Bybit L2 и public trades — 2026-11-04

Проверены официальные V5 docs:
- Public trades: `T` — время исполнения сделки в миллисекундах; `side` — сторона taker; `seq` — cross sequence: https://bybit-exchange.github.io/docs/v5/websocket/public/trade
- Standard public orderbook: `cts` — время matching engine, когда создано состояние книги; документация говорит, что оно может коррелироваться с `T` public trade: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook

Вывод:
- Использование trade timestamp `T` и orderbook `cts` в общей временной шкале обосновано официальной документацией как коррелируемых matching-engine timestamps.
- Документация не даёт гарантии, что все события в одной миллисекунде имеют однозначный порядок только по timestamp. Поэтому текущая политика строгого исключения book events с `cts == target` остаётся консервативной и не должна заменяться сортировкой по порядку строк архива.
- У обоих потоков есть `seq` cross-sequence. Runner пока не использует trade `seq` для разрешения same-ms порядка. Это потенциальное улучшение точности, но сначала нужно подтвердить наличие и семантику `seq` в фактическом историческом CSV-архиве; не делать предположений о формате.
- Это подтверждение временной семантики, а не доказательство точного event ordering или maker fills.

Статус execution gate не меняется: `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`. No archive download, collector, strategy PnL, API, paper/live orders, or main changes.


## 62. Повторно использован сохранённый CI artifact: реальная схема AAVE trade CSV — 2026-11-04

Без новой загрузки рыночных архивов извлечён ранее созданный GitHub Actions artifact из run `41814167058` (artifact `13314017303`, дата исходного исследования 2026-11-04 10:26 UTC). Внутри сохранён полный результат сканирования уже тогда загруженного AAVEUSDT 2025-09-02 CSV:

- 346,131 trade rows; уникальных `trdMatchID` — 346,131; повторов ID — 0.
- Фактические колонки: `timestamp,symbol,side,size,price,tickDirection,trdMatchID,grossValue,homeNotional,foreignNotional,RPI`.
- `RPI` присутствует, все 346,131 значений равны `0`.
- `isBlockTrade` и `BT` отсутствуют.
- Архивный report показывает 66 trades до начала L2 `cts` и 346,065 внутри временного диапазона книги; timestamp trades начинается на 1,276 ms раньше минимального book `cts`, последний trade — на 5,177 ms раньше максимального `cts`.

Критическая интерпретация:
- Текущий строгий parser корректно отклонит этот CSV из-за отсутствия block-trade классификатора. Это ожидаемое fail-closed поведение, не поломка parser.
- Нельзя трактовать отсутствие BT как `False`, даже несмотря на нулевой RPI в этом конкретном файле.
- Старый сохранённый `bybit_l2_queue_replay_report.json` был создан до обязательной проверки BT/RPI. Его четыре гипотетических сценария (0.58 partial, 1.00 filled, 1.00 filled, 0.33 partial) нельзя считать валидированными maker fills: block-trade принты не были надёжно отделены. Эти fill/markout числа — только исторический exploratory artifact, не evidence для PnL или fill-rate.
- Этот артефакт не доказывает, что все Bybit historical CSV версии имеют ту же схему; он доказывает именно схему сохранённого AAVE файла.

Следующий реальный блокер: нужен источник исторических trades с достоверным block-trade flag либо независимая проверка, позволяющая безопасно классифицировать BT. Пока такого источника нет, L2 queue replay не должен проходить в strategy PnL. Не ослаблять fail-closed parser и не повторять старый replay как будто его fills подтверждены.

Artifact был получен из уже существующего CI run; никаких новых Bybit market archives не скачивалось. Main не менялся.


## 63. Trade archive inspector: поддержка BT alias — 2026-11-04

При статическом сравнении инструментов обнаружено расхождение схемы: строгий queue replay parser принимал оба официальных имени block-trade флага (isBlockTrade и BT), но вспомогательный scripts/inspect_bybit_trade_sample.py проверял только isBlockTrade. При CSV с колонкой BT инспектор мог ошибочно сообщить, что block-trade flag отсутствует.

Исправлено в commit 5f9f24aa32a2ccca34407abc6a05a21a3be0160e:
- добавлен helper block_trade_flag_columns(), распознающий оба поддерживаемых имени;
- отчёт инспектора теперь содержит has_block_trade_flag и список фактически найденных колонок block_trade_flag_columns;
- добавлен regression test для BT, isBlockTrade, обоих aliases и отсутствия флага.

Research CI run #41870649976 завершился SUCCESS: job completed, все 57 шагов завершены без failure; шаг runner chronology/markout test также SUCCESS. Это подтверждает кодовую проверку alias helper, но не меняет вывод по сохранённому AAVE CSV: в нём по-прежнему отсутствуют оба block-trade aliases. Никакие архивы не скачивались и инспектор с сетевой загрузкой не запускался.

Статус execution gate остаётся MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL: нет исторического источника с надёжным BT classification. Main не менялся (HEAD c87612207d145af433394f0ea992f2d29eba28d5).


## 64. Проверка доступных официальных каналов для исторического BT — 2026-11-04

Проверены актуальные публичные контракты Bybit:
- REST Get Recent Public Trades (/v5/market/recent-trade) возвращает isBlockTrade, isRPITrade и seq, но параметры запроса включают category/symbol/baseCoin/optionType/limit; startTime/endTime для выборки произвольного исторического интервала в этом endpoint отсутствуют. Максимальный limit для linear — 1,000. Документация: https://bybit-exchange.github.io/docs/v5/market/recent-trade.
- Public Trade WebSocket содержит BT, RPI и seq в real time: https://bybit-exchange.github.io/docs/v5/websocket/public/trade.
- Bybit Get Trade History (/v5/execution/list) относится к пользовательским исполнениям и не является market-wide public print tape: https://bybit-exchange.github.io/docs/v5/order/execution.
- Сохранённый исторический AAVE CSV действительно не имеет BT/isBlockTrade. Внешняя схема публичного daily CSV, найденная в независимой документации downloader, также перечисляет 11 колонок без BT; это вспомогательное corroboration, не официальный контракт: https://github.com/Anton495/bybit-data-downloader.

Вывод:
- Нельзя восстановить историческую BT-классификацию за произвольный старый период из documented public REST recent-trade endpoint.
- Private execution history не может классифицировать все публичные сделки рынка.
- Для достоверного historical BT нужен уже существующий WS capture/архив с BT или внешний источник с документированной и проверенной семантикой этого поля. Ничего из этого в проверенных сохранённых артефактах пока не найдено.
- Не запускать collector и не загружать новые архивы в обход текущего ограничения. Возможный будущий WS capture — только после отдельного решения пользователя; до этого исторический maker replay остаётся заблокированным.

Статус: MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL. Никакие REST/WS запросы к Bybit не выполнялись; проверялась только публичная документация. Main не менялся.

## 65. Trade archive inspector использует общий строгий timestamp parser — 2026-11-04

Статический аудит вспомогательного `scripts/inspect_bybit_trade_sample.py` выявил расхождение с основным queue replay parser: инспектор применял `float(timestamp)` и `round()`, поэтому sub-millisecond timestamp мог быть округлён до миллисекунды и попасть в отчёт как валидный. Основной `bybit_l2_queue_replay.iter_public_trades()` уже использовал Decimal parser с отказом при sub-millisecond precision.

Исправление:
- Инспектор импортирует и использует общий `parse_trade_timestamp_ms()` из `bybit_l2_queue_replay.py`; отдельная реализация преобразования timestamp удалена.
- Добавлена регрессия для точного преобразования seconds и milliseconds, а также отказа для sub-millisecond, non-finite и non-positive значений.
- Итоговая реализация едина для inspector и queue replay; CSV timestamp больше не проходит через binary float/rounding.

CI:
- Source-only #41872780436 на `96c3b6aecd56d734cc660541ff848ff0ef4cc954`: SUCCESS, все 57 workflow steps.
- Тестовый run #41872788110 на `63ecbba28e040bc26953a3da611d7144fd52b3b1`: SUCCESS, все 57 workflow steps.
- После refactor на общий parser промежуточный #41872989853 завершился failure: test по-прежнему обращался к локальному `parse_archive_timestamp_ms`, уже удалённому из inspector. Это был устаревший тестовый интерфейс, а не отказ parser; тест синхронизирован.
- Финальный Research CI #41873039139 на `ec28763da6ade2635c31cd0111ae8c612625f23d`: SUCCESS, job `tests` SUCCESS, 57/57 workflow steps без failure. Фактический лог подтверждает runner/inspector suite 7/7 и aggregate-L2 primitive suite 81/81.

Классификация: timestamp/provenance integrity для диагностического инструмента; не execution evidence и не PnL. Inspector не запускался с сетевой загрузкой; архивы не скачивались. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` остаётся неизменным из-за отсутствия достоверного historical BT flag в доступном AAVE CSV. Нет PnL/backtest, collectors, private API, runner, paper/live orders или изменений `main`.


## 66. Trade archive inspector: fail-closed диагностика trade IDs — 2026-11-04

Статический аудит `scripts/inspect_bybit_trade_sample.py` выявил, что inspector пропускал пустые/отсутствующие `trdMatchID` и ID с окружающими пробелами: счётчики дубликатов/уникальных ID не отражали эти строки. Основной replay parser такие строки отклоняет, поэтому диагностический отчёт должен явно показывать этот дефект данных.

Исправлено:
- Добавлен `classify_trade_id(value, seen_ids)`: `missing` для None/пустого/whitespace-only; `malformed` для surrounding whitespace; `duplicate` для повторного ID; `unique` для нового корректного ID.
- Inspector теперь считает `missing_trade_id_count`, `malformed_trade_id_count`, `duplicate_trade_id_count`; сообщает `has_trade_id_column` и `trade_id_validation_status`.
- Статус `valid` выставляется только если колонка существует и все три проблемных счётчика равны нулю.
- Регрессия покрывает отсутствующее значение, пустую строку, whitespace-only, ID с окружающими пробелами, корректный уникальный ID и повтор.

Коммиты:
- Source: `bd2c0f9bc9fe2ad64044a4b9fe672ceb148950b3`.
- Test: `6dcb9d8bc000778c09975dbd462c36545e23682c`.

Проверка:
- Source-only CI #41873380445: SUCCESS.
- Final Research CI #41873425668 на test commit `6dcb9d8`: SUCCESS, job `tests` SUCCESS, 57/57 workflow steps.
- Фактический лог: runner/inspector suite 9/9; aggregate-L2 primitive suite 81/81; portfolio accounting 54/54; state persistence 84/84. Новый test `test_trade_sample_inspector_classifies_missing_malformed_and_duplicate_ids` явно отмечен PASS.

Классификация: улучшение качества диагностики historical CSV; не доказательство maker execution, fill rate или PnL. Inspector с сетевой загрузкой не запускался; новые архивы не скачивались. Исторический AAVE CSV по-прежнему не имеет BT/isBlockTrade, поэтому `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`. Никаких PnL/backtests, collectors, API, runner, paper/live orders или main changes.


## 67. Разделение spread capture и post-fill mid-price movement — 2026-11-04

Аудит markout accounting показал, что прежний `signed_mid_markout_bps` сравнивал цену fill с будущим midpoint. Для maker fill этот показатель включает как захваченный spread, так и последующее движение midpoint; трактовать его целиком как adverse selection нельзя.

Исправление в `scripts/run_bybit_l2_queue_replay.py:add_post_fill_markouts()`:
- Для каждого partial fill дополнительно фиксируется pre-fill BBO/midpoint из последнего book state строго до fill timestamp; события с тем же millisecond исключаются.
- `signed_fill_to_future_mid_bps` сохраняет полную доходность от fill до future mid; старое поле `signed_mid_markout_bps` оставлено как compatibility alias.
- `signed_mid_move_from_pre_fill_bps` измеряет изменение midpoint от pre-fill mid до будущего mid, отделяя движение рынка от spread capture.
- Fill timestamp проходит `strict_int`, без усечения float/string значений.

Regression:
- Synthetic Buy fill 99 при pre-fill mid 100 и future mid 101: fill-to-future-mid около 202.02 bps; pre-fill-to-future-mid ровно 100 bps. Это подтверждает разложение, а не смешение двух компонентов.
- Проверка также подтверждает сохранение pre-fill mid и строгое исключение same-ms book events.

CI:
- Final Research CI #41867866581 на `794342bbd00342d0b7f1af660362794408da0345`: SUCCESS, 57/57 workflow steps; runner chronology/markout suite 6/6, aggregate-L2 primitive suite 81/81.
- Последующие #41873039139 и #41873425668 также повторно прошли markout/runner suite (7/7 и 9/9 соответственно) на более поздних code/test commits.

Интерпретация:
- Старый сохранённый AAVE report был создан до decomposition и не содержит pre-fill midpoint; его прежние markout числа нельзя ретроспективно трактовать как чистый adverse-selection measure.
- Повторный replay не выполнялся: тот же сохранённый AAVE trade CSV не имеет BT/isBlockTrade и потому не проходит строгий parser. Новые архивы не скачивались.
- Это улучшение измерения execution diagnostics, не доказательство maker fill realism или PnL. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` остаётся закрытым.

## 68. Inspector validates every BT/RPI flag value and alias — 2026-11-04

Сверка диагностического inspector с `iter_public_trades()` выявила ещё один разрыв: inspector сообщал только о наличии колонок BT/RPI и считал значения первого RPI alias, но не проверял каждую строку и не выявлял конфликт между одновременно присутствующими aliases. Основной replay parser уже fail-closed отклоняет missing/malformed flags и conflicting aliases.

Исправление:
- Inspector использует общий `parse_exchange_bool()` из replay parser.
- Добавлен `classify_boolean_flag_aliases()`: `true`, `false`, `missing`, `malformed`, `conflict`.
- Для BT/isBlockTrade и RPI/isRPITrade отдельно собираются row-status counters; отчёт выставляет `*_flag_validation_status=valid` только при наличии хотя бы одного поддерживаемого alias и отсутствии missing/malformed/conflicting строк.
- Regression покрывает отсутствие колонок/значений, пустое значение, malformed flag, true/false, согласованные aliases и конфликтующие aliases.

Коммиты:
- Source: `83bca2b14a5cbb613e0ab849a45a2fbf4750aa71`.
- Test: `5f315bdd048f8abefa07a992aa667010d0ea1f5b`.

Проверка:
- Source-only CI #41874223792: SUCCESS, 57/57 workflow steps.
- Финальный Research CI #41874277483 на `5f315bdd048f8abefa07a992aa667010d0ea1f5b`: SUCCESS, job `tests` SUCCESS, 57/57 workflow steps, zero failures. Фактический лог подтверждает новую flag-alias regression; inspector/runner suite 9/9; aggregate-L2 primitives 81/81.

Классификация: улучшение диагностики полноты и согласованности trade classification metadata; не execution evidence и не PnL. Сохранённый AAVE CSV не содержит BT/isBlockTrade, поэтому его нельзя переклассифицировать этим исправлением. Inspector с сетевой загрузкой не запускался; новые архивы не скачивались. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` остаётся. Нет PnL/backtest, collectors, private API, runner, paper/live orders или изменений `main`.

## 68. Inspector отклоняет некорректную структуру trade CSV — 2026-11-04

Сравнение `scripts/inspect_bybit_trade_sample.py` с `iter_public_trades()` выявило, что основной replay parser отклоняет duplicate column names и malformed row widths, а диагностический inspector не выполнял эти структурные проверки. Из-за поведения `csv.DictReader` повторяющиеся заголовки могут перезаписывать значения в словаре, а лишние поля попадают под ключ `None`; без явной проверки отчёт мог быть неполным или вводить в заблуждение.

Исправление:
- Добавлены `validate_trade_csv_header()` и `validate_trade_csv_row()`.
- Duplicate header columns и отсутствующие обязательные header columns отклоняются до чтения строк.
- Каждая строка проверяется на лишние CSV fields и отсутствующие core values (`timestamp`, `symbol`, `side`, `size`, `price`) до агрегации.
- Поведение согласовано с fail-closed структурными проверками основного replay parser; optional classification flags и trade IDs продолжают учитываться отдельными диагностическими counters.

Коммиты:
- Source: `ab27c80413c23f4d0689441cff6f131a91a0ab5d`.
- Test: `846279119545a7036d65b57a156c8ea38b7ae895`.

Проверка:
- Source-only CI #41875043047: SUCCESS, 57/57 workflow steps.
- Финальный Research CI #41875093214 на `846279119545a7036d65b57a156c8ea38b7ae895`: SUCCESS, job `tests` SUCCESS, 57/57 workflow steps, zero failures. Фактический лог подтверждает новые header/row-shape regressions; inspector/runner suite 9/9; aggregate-L2 primitives 81/81.

Классификация: structural data-integrity guardrail диагностического инструмента, не execution evidence и не PnL. Архивы не скачивались; inspector с сетевой загрузкой не запускался. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` остаётся. Нет PnL/backtest, collectors, private API, runner, paper/live orders или изменений `main`.

## 69. Orderbook inspector использует strict integer contract replay parser — 2026-11-04

Read-only comparison `scripts/inspect_bybit_orderbook_sample.py` с `OrderBook.apply()` выявил coercion через `int()` для `ts`, `cts`, `seq` и `u`. Это принимало bool, floats (с truncation) и numeric strings, хотя основной replay parser через `strict_int()` требует именно JSON integer и отдельно проверяет положительность.

Исправление:
- Inspector теперь импортирует общий `strict_int()` и использует `parse_event_integer_fields()`.
- `ts`, `seq`, `u` обязательны, должны быть положительными non-bool integers; `cts` также strict integer, если присутствует.
- Отсутствующий или null `cts` по-прежнему учитывается как missing; null теперь считается так же, как отсутствующее поле.

Коммиты:
- Source: `d6078d4f0e56c1d398b427b8c7640b1f09021b89`.
- Test: `1b50c9da41b99ea23d04e009e7ba6e6424d73e01`.

Проверка:
- Source-only CI #41875836674: SUCCESS, 57/57 workflow steps.
- Финальный Research CI #41875905360 на `1b50c9da41b99ea23d04e009e7ba6e6424d73e01`: SUCCESS, job `tests` SUCCESS, 57/57 workflow steps, zero failures. Фактический лог подтверждает strict orderbook inspector regression; inspector/runner suite 9/9, aggregate-L2 primitives 81/81.

Классификация: strict timestamp/sequence provenance guardrail диагностического инструмента; не execution evidence и не PnL. Inspector не запускался с сетевой загрузкой, новые архивы не скачивались. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` остаётся. Нет PnL/backtest, collectors, private API, runner, paper/live orders или изменений `main`.

## 34. No-overwrite JSON report serialization (ENG-EXEC-032)

Три исследовательских скрипта ранее записывали JSON в фиксированные имена через `Path.write_text()`, поэтому повторный запуск мог перезаписать прежний отчёт.

Исправлено:
- общий `report_io.py` открывает отчёт в exclusive-create режиме `x`; существующий файл остаётся неизменным и вызывает `FileExistsError`;
- сериализация выполняется до создания файла; частично записанный новый файл удаляется при ошибке записи;
- обновлены queue replay runner, trade inspector и orderbook inspector;
- добавлены два deterministic tests: no-overwrite/byte preservation и отсутствие файла при serialization failure.

Commits: helper `0a58d10f`; runner `ddc3defd` + import correction `a70d7596`; trade inspector `e2f484a7`; orderbook inspector `6bdedbeb`; tests `ed089a1c`; note `118acb07`.

CI для HEAD `118acb07` не подтверждён: combined commit status не вернул check records. Не считать тесты выполненными. Не запускать network inspection workflow: он скачивает новые архивы и выполняет bounded queue probe. Новые архивы, collectors, market PnL, private API, runner, paper/live orders не использовались. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`; `main` не изменён, PR #4 не слит.

## 35. Explicit public-trade timestamp ordering status (ENG-EXEC-033)

Trade inspector ранее считал timestamp regressions, но не публиковал явный статус совместимости с replay. Replay path отклоняет уменьшение timestamp. Добавлено поле `timestamp_order_validation_status`: `valid` только при нулевом `nonmonotonic_timestamp_count`, иначе `invalid`. Добавлен строгий classifier и deterministic regression на valid/invalid и malformed inputs.

Source `0c4cf2e2`; tests `6fc17e4d`. CI не подтверждён (combined status пуст). Новые архивы и network workflows не запускались; collectors, PnL/backtest, private API, runner и paper/live orders не запускались. Maker gate закрыт.

## 36. Strict CSV quoting for public trade archives (ENG-EXEC-034)

В обоих trade parser paths `csv.DictReader` переведён в `strict=True`. Причина: стандартный `strict=False` принимал некоторые незакрытые quoted fields, включая malformed optional RPI value, которое могло пройти дальнейший boolean parsing. Добавлены deterministic tests для core replay и standalone inspector. Локальная проверка stdlib parser подтверждает отказ `csv.Error: unexpected end of data`.

Core `81f58d0b`, inspector `d7872099`; tests `13f32dbc` + fixture correction `5f6c245d`, inspector test `06544878` + correction `9302114d`. CI не подтверждён. Новые архивы/network workflows не запускались; collectors, PnL, private API, runner и paper/live orders не использовались.

## 37. Aggregate queue-replay compatibility and empty trade archive (ENG-EXEC-035)

Trade inspector теперь отдельно публикует `queue_replay_compatibility_status`: `valid` только при валидных timestamp order, trade IDs, RPI и block-trade flags, а также при числе строк > 0. Пустой/header-only архив получает `duration_hours: null` и `invalid_or_incomplete`, не аварийный расчёт с None.

Source `86a0590f`, `68ee303e`; tests `8311daa4`, `82852d6f`. Research CI run `41888048946` на `82852d6` завершился success. Никаких архивов, collectors, PnL/backtest, API, runner или orders.

## 38. L2 inspector/replay compatibility boundary (ENG-EXEC-036)

Статический аудит выявил, что L2 inspector может завершить сканирование с `status: success`, одновременно указав `missing_cts_count > 0`; replay требует `cts` для каждого события. Также inspector не вводит archive-wide monotonicity rule для `u`, тогда как replay `OrderBook.apply()` отклоняет non-reset regressions `u`. Это различие не следует считать автоматически дефектом: ENG-EXEC-031 намеренно не закрепляет неподтверждённую универсальную семантику `u`.

Код не менялся. Не трактовать scan success как replay readiness; не ослаблять replay и не ужесточать inspector без подтверждения формата архива. Следующий шаг — определить explicit L2 replay compatibility dimensions после проверки источника/контракта. Note: `ENG_EXEC_036_L2_INSPECTOR_REPLAY_COMPATIBILITY_RU.md`. Архивы/network workflow/PnL/API/runner/orders не запускались; maker gate закрыт.

## 39. Price-through trades and passive replay boundary (ENG-EXEC-037)

Текущий aggregate-L2 replay уменьшает очередь и создаёт fill только по opposing-aggressor trade с ценой, строго равной лимиту. Prints по более выгодной цене игнорируются. Постановка заявки фиксирует начальную очередь; последующие L2 deletions, проход цены через лимит и повторное появление уровня не меняют состояние заявки. Существующие тесты явно закрепляют эти ограничения.

Это ограниченная механическая модель, а не maker execution evidence. Возможен недосчёт price-through исполнений, но объём отмен впереди/позади заявки неизвестен; автоматически засчитывать better-price prints было бы необоснованно. Код/тесты не менялись. Нужна синхронная реконструкция L2+trades с подтверждённой семантикой порядка событий и fail-closed обработкой неоднозначностей. Note: `ENG_EXEC_037_PRICE_THROUGH_PASSIVE_REPLAY_BOUNDARY_RU.md`.

Только статический аудит. Тесты, архивы, queue replay, PnL/backtests, collectors/network workflows, API, runner и orders не запускались. Maker gate закрыт; `main` не изменён; PR #4 не слит.
