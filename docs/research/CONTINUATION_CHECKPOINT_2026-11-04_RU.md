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

## 10. Bybit L2 update-ID restart semantics — исправление внесено, CI не подтверждён

Официальная Bybit V5 orderbook документация определяет u как update ID и указывает, что u=1 означает snapshot после service restart; локальный стакан должен быть заменён новым snapshot. seq — cross sequence; для full-depth документации он монотонный, но не обязан быть consecutive. Источник: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook.

Подтверждённый дефект в прежнем OrderBook.apply():
- код очищал стакан только при type=snapshot, но не читал data.u;
- проверка seq < last_seq выполнялась до очистки snapshot, поэтому корректный restart snapshot с новой sequence epoch мог быть отвергнут;
- u=1 на delta мог быть применён как обычный incremental update, хотя без полного snapshot такой state нельзя считать синхронизированным.

Исправление в research branch:
- u обязателен, положителен и не может быть bool;
- u=1 принимается только вместе с type=snapshot; такой snapshot сбрасывает старые уровни и разрешает новую seq epoch;
- u=1 на delta отклоняется fail-closed;
- обычная монотонная проверка cts сохраняется, а для non-reset событий сохраняется проверка non-decreasing seq.

Regression coverage:
- restart snapshot с уменьшившимся seq очищает старые уровни и загружает новые;
- u=1 delta отклоняется без изменения предыдущего стакана;
- отсутствие u отклоняется;
- существующие synthetic fixtures дополнены update IDs.
- Source commit: 46d264d40a567438c0311bd227f76b0b753700ef.
- Test commits: 5687cd39ff869b9bcabc2f12a55f51596b899e63, ed03e42bbba772d2e0b9c55a3282f05b3df4fdf9, 7d8f54318552d8d8aa3b9d7ae08d0feb61bb0ebb; current queue test file contains 22 tests.
- The Research CI workflow is configured to run on pushes touching these paths. Its new run is not visible through the available PR-only workflow-run lookup; do not mark this patch CI-passed until a terminal push-run result is checked.

The previously inspected AAVEUSDT 2025-09-02 sample had zero u=1 resets, so this is a future-data integrity guard, not a correction to the four-order sample metrics. No archive was re-downloaded, no strategy signal was replayed, no PnL was run, and no Bybit account/API/order operation occurred.

Next static audit items remain: order-spec/tick/qty validation, per-fill fee and VWAP markout lifecycle, latency/cancel assumptions, and duplicate public-trade ID handling. Keep MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL.