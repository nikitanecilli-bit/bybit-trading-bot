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
