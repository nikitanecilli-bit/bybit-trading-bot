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