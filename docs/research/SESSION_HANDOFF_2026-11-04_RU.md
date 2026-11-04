# Стартовая точка новой сессии — 2026-11-04

> Назначение: компактный handoff для нового чата. Это не замена Experiment Ledger и полному аудиту. Перед любыми действиями перепроверять live-состояние GitHub.

## 1. Текущая точка GitHub

- Репозиторий: `nikitanecilli-bit/bybit-trading-bot` (private).
- Рабочая ветка: `research/market-regime-v1-main`.
- Последний code/test commit: `948c7a161682d677fe6c284bf1877fbac5fe6964` — standalone inspector now reconstructs bid/ask state and rejects crossed books in snapshots and deltas.
- Последний завершённый Research CI SUCCESS: [Research engine checks #41885051272](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41885051272), commit `948c7a1`, job `tests` SUCCESS, 57/57 workflow steps. Actual logs confirm aggregate-L2 83/83, runner/inspector 19/19 and PASS for crossed snapshot/delta rejection. Prior CI #41884668466 on `94daea1` also passed with 83/83 aggregate-L2 and 18/18 runner/inspector tests, including malformed normalized-trade validation.
- В предыдущем CI #41875905360 до новой regression: aggregate-L2 primitive tests 81/81; runner/inspector suite 9/9; portfolio accounting 54/54; state persistence 84/84. В новом CI #41881215008 эти L2 suites расширились до 82/82 и 13/13 соответственно.
- Предыдущая неудачная попытка #41872989853 была вызвана устаревшим тестом после перехода trade inspector на общий `parse_trade_timestamp_ms`; тест синхронизирован в `ec28763`, после чего полные CI #41873039139, #41873425668, #41874277483, #41875093214 и #41875905360 прошли.
- PR #4: открыт, Draft, base `main`, head = текущая research-ветка; последний ответ GitHub по `mergeable` был `null` (не вычислено), не трактовать это как false/true. Не сливать автоматически.
- Последнее сравнение с `main` на snapshot `d9f6d6a`: diverged, 2225 commits ahead / 36 behind. Main HEAD на момент сверки: `c87612207d145af433394f0ea992f2d29eba28d5`; merge-base: `ae599a2f3279e15fe27360662f94f0e7ef8db5be`. После snapshot добавлены code/test commits `b54e5cb`, `63458f9`, `af667d2`, `2255e0f`, `6ee892a`, `3733f7c`, `94daea1`, `948c7a1`, а также обновления handoff/ledger; точный текущий branch HEAD всегда перепроверять через GitHub перед следующей работой.
- `main` не менять. Не делать wholesale merge/rebase research branch. Использовать только reviewed selective PR/cherry-pick при отдельном обосновании.
- В репозитории есть отдельная ветка `Audit` и `chore/main-repository-organization`; не предполагать, что они слиты или актуальны без проверки.

## 2. Обязательные правила проекта

Прочитать перед работой:
1. `AGENTS.md`
2. `PROJECT_WORKING_RULES_RU.md`
3. `docs/README_RU.md`
4. `docs/research/EXPERIMENT_LEDGER_RU.md`
5. Этот handoff и полный `docs/research/CONTINUATION_CHECKPOINT_2026-11-04_RU.md`.

Режим пользователя: максимальная автономность, вычислительный бюджет balanced. Самостоятельно проводить безопасный статический аудит, исправлять подтверждённые дефекты, добавлять focused regression tests, проверять завершённые CI и обновлять документы. Не спрашивать подтверждение на обычные обратимые исследовательские действия. Не обещать работу в фоне после окончания сессии.

### Жёсткие ограничения до отдельного изменения решения пользователя

- Не скачивать новые Bybit market archives и не запускать collectors.
- Не запускать market/PnL backtests, parameter sweeps или новые strategy replay до убедительного подтверждения maker execution realism и открытия data/PnL gate.
- Не подключать private/account API, не запрашивать API keys/secrets, не настраивать live trading.
- Не размещать paper/live orders.
- Не регистрировать self-hosted runner.
- Не менять production и не трогать `main`.
- Не удалять и не перезаписывать исходные датасеты, holdout, результаты и исторические эксперименты.
- Статический аудит, provenance review, deterministic unit/regression tests и точечные исправления подтверждённых дефектов разрешены.
- Не объявлять тесты пройденными по наличию тестовых функций или по запуску workflow: проверять terminal conclusion, job steps и фактическое число тестов.
- Не считать OHLCV limit-touch / maker limit fill доказательством исполнения: это optimistic proxy без подтверждённой очереди, задержек и adverse selection.

## 3. Цель и исследовательская стратегия

- Цель проекта — найти устойчивую чистую прибыльную стратегию; ранее пользователь обозначал ориентир 20% net/month, но это не доказанная достижимая доходность.
- Предпочтение H1 вместо HFT/15m из-за комиссий.
- Будущий отбор: 5 лучших инструментов + 5 резервных, а не широкая одновременная торговля 50 инструментами.
- Исследовательские направления: трендовый режим, market regime, истинный/ложный breakout, качество post-break impulse, maker micro-pullback и снижение частоты/издержек.
- Исторические 15m Donchian20 + volume результаты были отрицательны после costs; gross expectancy около +0.011R/trade против costs около 0.17R/trade (по предоставленным пользователем результатам).
- H1 gross улучшился, но ранее оставался ниже costs. Старые H-C/H-A/E11/E13 и Gemini Donchian48/EMA50/200 варианты не считать доказанно прибыльными.
- Любой кандидат должен иметь net PnL после fees/slippage/funding и реалистичного исполнения, независимые хронологические периоды, walk-forward/holdout без подбора на holdout и shared-capital portfolio validation.

## 4. L2 aggregate queue replay — текущая инженерная база

Ключевые файлы:
- `bybit_l2_queue_replay.py`
- `scripts/run_bybit_l2_queue_replay.py`
- `tests/test_bybit_l2_queue_replay.py`
- `tests/test_run_bybit_l2_queue_replay.py`
- `bybit_instrument_specs.py`
- `instrument_spec_history.py)
- `docs/research/CONTINUATION_CHECKPOINT_2026-11-04_RU.md)

Подтверждённые проверки/защитные механизмы:
- Строгая integer-валидация `u`, `seq`, `cts`; bool/float/string coercion отклоняются; все поля положительные.
- `u=1` допустим только для snapshot; snapshot полностью заменяет уровни; `seq` ordering не сбрасывается вместе с update ID.
- Первое book event обязано быть snapshot; delta до snapshot отклоняется.
- Atomic candidate-state update: malformed snapshot/delta не оставляет частично изменённый стакан.
- JSON duplicate keys отклоняются; archive event/data/symbol/cts валидируются до boundary filtering.
- Arrival book state берётся строго по `cts < arrival_ts`; markout state — до первого события с `cts >= target`; same-ms events исключаются консервативно.
- Проверяется non-decreasing `seq` и `cts`; поздние malformed/out-of-order archive tails не игнорируются.
- Public trades требуют `trdMatchID`, точные integer-ms timestamps, валидные side/price/size и обязательные BT/RPI flags; block trades и RPI prints не расходуют обычную displayed queue.
- Duplicate trade IDs внутри replay отклоняются; overlapping replay idempotent через сохранённые processed IDs; replay transactional.
- Canonical `bybit_instrument_specs.InstrumentSpec` используется для проверки limit order constraints; off-tick/off-step/min-notional/status и symbol mismatch fail closed.
- Частичные fills сохраняются отдельно; есть filled VWAP/notional; fee ledger принимает только явно переданные per-fill rates; per-fill markouts считаются отдельно.
- Runner capture helpers покрыты dedicated chronology tests; CI #41840361238 подтвердил 4/4 runner tests и 80/80 primitive tests.

### Что это НЕ доказывает

- Это aggregate L2 approximation, не L3 и не exchange-confirmed fills.
- Нет реальной очереди отдельных заявок, подтверждённого exchange priority, измеренной delivery/order latency, cancel latency и cancel queue model.
- Cancel credit не моделируется (консервативно), но latency отмены не измерена.
- Нет проверенной полной исторической instrument-spec snapshot для sample date 2025-09-02; текущий snapshot нельзя подставлять вместо dated spec.
- Нет подтверждённых account-specific maker fee rates для каждого fill.
- Не доказан исторический формат trade CSV с обязательными BT и RPI flags; стандартная опубликованная схема archive может не содержать BT. Не ослаблять fail-closed validation.
- Не подтверждена непрерывность исторического depth-200 delta archive: стандартная документация не даёт явного u+1 continuity contract для этого конкретного archive. Не переносить Full Orderbook continuity rule на depth-200 без доказательства.
- Один сохранённый sample AAVEUSDT 2025-09-02 и четыре hand-scheduled hypothetical orders — только mechanics smoke test, не статистика fill rate и не profitability.
- Поэтому `TRADE_ARCHIVE_FLAGS = UNVERIFIED_COMPATIBILITY` и `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`.

## 5. Данные и уже существующее evidence

- В workflow #41814167058 уже был сохранён однодневный AAVEUSDT L2 + public-trade sample; не скачивать его повторно.
- Sample: L2 archive 88,252,368 bytes, SHA-256 `e3646429c600f4917c021e240497e8f3d46fd44ba57168100633181916c761f6`, 816,684 events; public trades 13,095,906 bytes, SHA-256 `cf11d05f6053acfeb22b1112df666ff328034963f04c6e6159f35cae63de1bc1`, 346,131 unique IDs.
- В sample 66 public trades предшествовали первому matching-engine book timestamp и должны исключаться.
- Четыре заранее назначенные hypothetical orders имели fill fractions 58%, 100%, 100%, 33%; это не random sample.
- Mean signed midpoint markouts при n=4: 1s −2.73 bps; 5s −0.58 bps; 30s +3.11 bps; 60s +4.09 bps. Не делать выводов о стабильном adverse selection на n=4.
- В текущей работе не повторять sample inspection и не скачивать новые архивы.

## 6. Следующие безопасные задачи

1. Продолжить статический audit queue replay: очередь при отсутствующем price level, crossed/stale book, expiry, partial fills, timestamp sorting, CSV schema/ID edge cases, runner report correctness.
2. Проверить исторические instrument-spec artifacts и fee provenance без новых загрузок; если доказательства отсутствуют — сохранять unknown/blocker.
3. Проверить Experiment Ledger и provenance прежних H1/PnL результатов; не пересчитывать старые эксперименты без конкретной причины.
4. Сверить causal regime attribution / signal timestamps / market-regime reports и выявлять только воспроизводимые дефекты.
5. Любую новую правку — отдельный focused commit + regression test + проверка завершённого CI; обновить этот handoff/checkpoint и Experiment Ledger при необходимости.
6. Не запускать PnL, пока maker execution realism и data gates закрыты.

## 7. Правило для нового чата

Начать с перепроверки текущего branch HEAD, PR #4, последних Actions runs и содержимого этого документа. Затем прочитать обязательные файлы из раздела 2. Не считать SHA выше актуальными после начала новой сессии: это снимок состояния на момент handoff.

**Пользовательская инструкция:** продолжать автономно; не ждать одобрения на безопасные исследовательские действия; не прекращать работу только потому, что workflow ещё выполняется; спрашивать только при реальном внешнем блокере. При этом все ограничения data/PnL/API/live из раздела 2 остаются обязательными.


## Session update — 2026-11-04 (L2 empty-archive guard)

- Re-read the current working rules and handoff before continuing. The branch's documented starting HEAD was `025cfca91ebb3a0d4419f8cdaa53be3b9c29f667`; the previous verified Research CI remains #41840361238 on code commit `d2740c6ff444c3a7302b4b04dcc04d15ebf1dcb1` (SUCCESS, 57/57 steps; L2 primitives 80/80; runner chronology step SUCCESS).
- Static audit found one malformed-input edge case in `scripts/run_bybit_l2_queue_replay.py:capture_scenarios()`: an empty .data event stream left `first_cts=None` and later failed with an incidental TypeError instead of a clear validation error.
- Fixed by explicitly raising `ValueError("order-book archive contains no events")`; added `test_capture_scenarios_rejects_empty_order_book_archive` in `tests/test_run_bybit_l2_queue_replay.py`.
- Commits: source `067109a14312c39ebd95ecf2eaede8d19375426c`; regression `54f30eeb095fb01998bf9d03b69c4ff2a1b40687`.
- The two files were re-fetched from the working branch and the guard/test presence confirmed. CI result for these commits has not yet been retrieved; do not report the new regression as passed until the actual job/test output is inspected.
- No market PnL, archive download, collector, API/account access, runner registration, paper/live order, or main-branch change.
- Next safe task: continue static L2 queue-replay audit on report generation and CSV edge cases, avoiding reinspection of already-covered chronology, sequence ordering, trade-ID uniqueness, and same-ms boundaries. Then retrieve/verify the CI result for the two commits if available.


## Session update — 2026-11-04 (full L2 archive-tail validation)

- Continued the permitted static audit of `capture_book_at()`. Found that chronology and `seq` were checked after the arrival boundary, but malformed book payloads (`u`, levels, crossed reconstructed state, etc.) were skipped because future/same-ms events were not applied to the returned snapshot.
- Added a separate validation-only OrderBook state seeded from the pre-arrival snapshot. Events at/after arrival are applied to that validator, while the returned book remains strictly pre-arrival. This preserves the no-look-ahead capture rule and validates the complete event stream.
- Regression `test_capture_book_at_rejects_malformed_book_events_after_arrival_boundary` covers a non-integer update ID and a crossed reconstructed book in the post-arrival tail.
- Commits: source `b79d827d7c6feadb7f4bf9f306fede7b5bd53f25`; regression `57f5263c7bbd5f123e19cd2be2f23c2a31765446`.
- Both files were fetched again from the working branch; the validator and regression are present. No commit-associated workflow runs were returned by the available commit-runs lookup; CI outcome is therefore **unverified**, not passed.
- Previous empty-archive correction remains: source `067109a14312c39ebd95ecf2eaede8d19375426c`; regression `54f30eeb095fb01998bf9d03b69c4ff2a1b40687`. CI for it is also unverified.
- No PnL, archive downloads/collectors, API/account access, runner registration, paper/live orders, or main changes.
- Next: inspect report serialization and public-trade CSV boundary cases; avoid duplicating existing chronology, duplicate-ID, flag, same-ms, and archive-tail checks. Retrieve actual CI job results before calling either new regression passed.


## Session update — 2026-11-04 (complete post-arrival L2 validation)

- Further static audit found that `capture_book_at()` previously validated chronology/`seq` beyond arrival but did not validate the full order-book payload there. Added a validation-only book seeded from the pre-arrival snapshot; future/same-ms events are validated without altering the returned pre-arrival state.
- Regression covers a non-integer post-arrival update ID and a crossed post-arrival book.
- Commits: `b79d827d7c6feadb7f4bf9f306fede7b5bd53f25` (source), `57f5263c7bbd5f123e19cd2be2f23c2a31765446` (test).
- This follows the empty-stream TypeError correction: `067109a14312c39ebd95ecf2eaede8d19375426c` (source), `54f30eeb095fb01998bf9d03b69c4ff2a1b40687` (test).
- The changed files were re-fetched and both corrections are present. The available commit-associated workflow lookup returned no runs for the latest test commit; both changes remain CI-unverified. Do not call tests passed.
- No PnL, archive downloads/collectors, Bybit API/account access, runner registration, paper/live orders, or main-branch changes.
- Next safe action: retrieve actual CI results if an Actions run becomes available. Until then, avoid stacking further queue-replay changes on top of unverified edits; continue only independent read-only review.


## Session update — 2026-11-04 (runner tests actually executed; CI verified)

- Corrected a test-infrastructure defect: `tests/test_run_bybit_l2_queue_replay.py` contained five plain test functions but no executable test entrypoint. The Research CI command invoked the file directly, so the step previously exited 0 without running those functions. Earlier statements treating that step as evidence of executed runner tests were too strong.
- Added a deterministic `__main__` entrypoint that invokes all `test_*` functions and prints each PASS plus a total.
- First real execution exposed a bad expectation in `test_markout_capture_excludes_exact_target_event_and_never_extrapolates`: the test expected a markout snapshot after the last archive event, contrary to the intended fail-closed no-extrapolation behavior. Corrected fixture to include a later event that brackets the intermediate target; retained assertion that a target beyond the final archive event is omitted.
- Commits: test entrypoint `60d9202b0f93fccd1938c99137cbeefd3094f9d5` (CI #41842455791 correctly failed, revealing the assertion defect); corrected test `19ca8bcfe407cecea18a2bfc6ad5c86cf54085af`.
- Final CI #41842592947 on `19ca8bcfe407cecea18a2bfc6ad5c86cf54085af`: run SUCCESS; job `tests` SUCCESS; all 56 workflow steps completed successfully. Crucially, log confirms `tests/test_run_bybit_l2_queue_replay.py` executed **5/5 tests passed**, and aggregate L2 primitive suite executed **81/81 tests passed**, including the new post-arrival malformed-tail regression.
- CI #41842036275 on `57f5263c7bbd5f123e19cd2be2f23c2a31765446` also succeeded (all steps), but its runner test file was still a no-op at that point; do not count it as runner-test execution evidence. The empty-archive regression was exercised only by the later 5/5 runner suite.
- Current research branch code/test HEAD before this documentation update: `19ca8bcfe407cecea18a2bfc6ad5c86cf54085af`. PR #4 remains Draft/open; no merge/rebase/retarget.
- No market PnL, new market archive download/collector, private API/account access, runner registration, paper/live orders, or main-branch changes.
- Next safe task: continue independent read-only review of report serialization/CSV schema and provenance; do not add further changes to this now-green runner path without a new reproducible defect.


## Session update — 2026-11-04 (trade timestamp unit boundary)

- Independent CSV/report audit found a boundary bug in `parse_trade_timestamp_ms()`: the seconds-vs-milliseconds heuristic used `raw > 1_000_000_000_000`, so the exact valid millisecond timestamp `1000000000000` was misclassified as seconds and multiplied by 1,000.
- Changed the threshold to `>=` and added an exact-boundary regression assertion.
- Commits: source `e972a4466ed8053b0471eead932144a18ee91790`; test `a9443b1c9ee81d63ab80150ffe3650af78aff560`.
- Final Research CI #41842908843 on test commit `a9443b1c9ee81d63ab80150ffe3650af78aff560`: SUCCESS; job `tests` SUCCESS; all 56 steps completed. Actual logs: aggregate L2 primitive suite 81/81 passed; runner suite 5/5 passed, including empty-archive and markout-boundary tests.
- Static review of report serialization and CSV schema found no further reproducible defect: decimal values are serialized as strings, output is UTF-8 JSON, required CSV columns/aliases/row widths/IDs/flags and numeric fields fail closed, duplicate IDs and non-monotonic timestamps are checked across the full archive. No market data was downloaded and the runner's networked `main()` was not executed.
- Current code/test HEAD before this documentation update: `a9443b1c9ee81d63ab80150ffe3650af78aff560`. PR #4 remains Draft/open; no merge/rebase/retarget.
- No market PnL, archive downloads/collectors, Bybit private/account API, runner registration, paper/live orders, or main-branch changes.
- Next safe task: read-only audit of historical instrument-spec and fee provenance artifacts already present in the branch; do not substitute current specs/fees for missing dated evidence.


## Session update — 2026-11-04 (dated exchange-spec and fee provenance audit)

- Read-only repository inventory confirms `data/archives/` contains only `cryptofetch/`; `data/archives/bybit/`, `data/instrument_specs/`, and `data/risk_tiers/` do not exist (GitHub Contents API returned 404 for each absent path). No new archive was downloaded.
- The code supports strict as-of loading of dated Bybit instrument and risk-tier snapshots, but there are no committed snapshot artifacts to instantiate those histories. Do not substitute current specs or fabricate historical values.
- The L2 runner explicitly marks order-spec validation as `not_performed_no_verified_historical_snapshot` and fee accounting as `not_calculated_requires_account_fee_tier_per_fill`. Existing engine fee constants (maker 0.020%, taker 0.055%, taker slippage 0.0225% per leg) are model assumptions, not dated account-specific fee evidence. No account/API access was used.
- Read-only audit of `docs/audits/EXECUTION_REALISM_READINESS_RU.md` confirms maker spread/queue/partial-fill latency and account-specific fee evidence remain missing; maker execution realism stays BLOCKED_FOR_STRATEGY_PNL.
- PR #4 verified open + Draft. Its current head at the time of this check was `0f021573f4057bd046db2123c1dc0d0341a4c933` (documentation update), base merge-base `ae599a2f3279e15fe27360662f94f0e7ef8db5be`; do not merge/rebase/retarget.
- No code change was justified by the artifact inventory. No market PnL, archive download/collector, private API/account access, runner registration, paper/live order, or main-branch change.
- Next: preserve the blocker and continue only read-only provenance/code review until approved data becomes available; do not rerun known collectors or PnL.


## Session update — 2026-11-04 (точность временных меток RiskTierHistory)

- Независимый аудит `bybit_risk_tiers.py` выявил два дефекта временной строгости:
  1. `get_tiers()` и `get_tier()` применяли `int(as_of_ts)`, молча принимая bool, строки и дробные значения вместо строгого integer-ms контракта, уже реализованного в `InstrumentSpecHistory`.
  2. `_timestamp_ms()` использовал `datetime.timestamp() * 1000` через float и не отклонял субмиллисекундную точность. Это могло обрезать время получения снимка и сделать его доступным на более ранней миллисекунде.
- Исправление: добавлен строгий `_as_of_ms()`; snapshot timestamp теперь нормализуется в UTC, проверяется на миллисекундную точность и конвертируется целочисленной арифметикой (без float).
- Регрессии: строгая проверка типов для `get_tiers/get_tier`; отклонение `.000500` timestamp; точное преобразование timestamp с `+03:00` offset.
- Коммиты: source `7f16b39da23a8b6fbe1b80b05c51d53aa2318fdd` (первая версия), уточнение UTC-нормализации `aa35e028dac3a6ba478e93cee36b693138708dfe`; тесты `5f6001e7620222738e8bac2b28a1078d4242d2a3` (первый запуск выявил неверное ожидаемое значение), исправленный тест `ae64222055c794584ee2b4207e940762b12fb130`.
- CI: финальный Research CI #41844132573 на `ae64222055c794584ee2b4207e940762b12fb130` — SUCCESS; job `tests` SUCCESS; все 54 workflow steps завершились успешно. Фактический лог подтверждает 13/13 тестов `test_bybit_risk_tiers.py`, включая новые проверки; compile step и остальные deterministic suites также прошли.
- Промежуточный CI #41844055151 на тестовой фикстуре завершился FAILURE из-за неверного ожидаемого UTC epoch в новом тесте; ошибка исправлена и покрыта финальным успешным CI. Не считать промежуточный запуск успешным.
- Это исправление только временной/валидационной строгости. Нет новых Bybit snapshots/архивов, market PnL, collectors, private API/account access, runner registration, paper/live orders или изменений `main`.
- Текущий code/test HEAD: `ae64222055c794584ee2b4207e940762b12fb130`. PR #4 остаётся Draft/open.
- Следующий безопасный шаг: продолжить статический audit point-in-time контрактов и их вызывающих участков; не запускать PnL, пока execution/data gates закрыты.


## Session update — 2026-11-04 (совместимость timestamp коллекторов и as-of загрузчиков)

- Продолжая аудит, обнаружил системное несоответствие: оба collector `build_snapshot()` по умолчанию создавали `fetched_at` через `datetime.now(...).isoformat()`, то есть с произвольными микросекундами. `InstrumentSpecHistory` и `RiskTierHistory` требуют millisecond precision и отклоняют sub-ms значения. Поэтому собственный collector мог создать снимок, который его же исторический loader не сможет прочитать.
- Исправлены `scripts/snapshot_bybit_instruments.py` и `scripts/snapshot_bybit_risk_limits.py`: default timestamp теперь формируется с `timespec="milliseconds"`; явные значения проверяются на ISO-8601, timezone и миллисекундную точность; все значения нормализуются в UTC с ровно тремя цифрами миллисекунд.
- Добавлены офлайн-тесты default precision, отказа от naive/sub-ms timestamps, timezone-offset normalization и полного round-trip `build_snapshot → write_snapshot → History.from_directory → as-of lookup` для обоих типов snapshot.
- Коммиты source: instrument collector `36686cb65a5dfc7d9adf6ec63e04c3a2fc1ae272`; risk-limit collector `5c99ecb47f734406ed6e8c925093f60e688990d8`. Тесты: instrument `3277c7c038a295bea6a6123decc3426d63d1a7d6`; risk-limit `729bc1a18d676e5c4dee81e3e29db37bbb21949f`.
- Промежуточные CI завершались ошибкой на тестовых ожиданиях: сначала timestamp `Z` не учитывал канонический `.000Z`, затем один round-trip тест использовал фиксированное as-of время до сгенерированного snapshot. Оба тестовых дефекта исправлены; source behavior сохранён.
- Финальный Research CI #41845297286 на `729bc1a18d676e5c4dee81e3e29db37bbb21949f`: SUCCESS; job `tests` SUCCESS; 57 completed workflow steps, failures отсутствуют. Фактические логи подтверждают instrument collector **17/17** и risk-limit collector **16/16** тестов, включая round-trip в оба as-of loader.
- Это офлайн-коррекция формата snapshot. Сами collectors не запускались; новые Bybit данные не загружались. Нет market PnL, private API/account access, runner registration, paper/live orders или изменений `main`.
- PR #4 остаётся Draft/open. Следующий безопасный шаг — продолжить read-only аудит исторических data contracts и вызывающих участков; PnL gate остаётся закрытым из-за отсутствующих датированных снимков и execution evidence.


## Session update — 2026-11-04 (строгая валидация mmDeduction в risk-tier history)

- Дополнительная сверка RiskTierHistory с collector обнаружила fail-open несовпадение: history loader заменял отсутствующий/пустой mmDeduction на ноль для любого tier, хотя collector требует явное значение для каждого tier выше минимального. Это могло занизить/исказить maintenance margin при загрузке неполного snapshot.
- _d() также принимал bool через Decimal(str(value)) для части numeric fields; bool не является допустимым числовым значением и должен отклоняться, как это уже делает collector.
- Исправление: отсутствие mmDeduction допускается только у lowest tier (где ноль является определённым fallback); у остальных tier отсутствие/пустое значение отклоняется. _d() теперь явно запрещает bool.
- Добавлены регрессии на missing mmDeduction у higher tier и boolean maintenance margin.
- Коммиты: source 6a668cf70c26680a751ed62fd8b1d9a24799fa76; tests 625b84cc3c6eb6354a6801262ee77d77ad9efe5b.
- Финальный Research CI #41845762278 на 625b84cc3c6eb6354a6801262ee77d77ad9efe5b: SUCCESS; job tests SUCCESS; все 57 workflow steps завершились без failure. Фактический лог подтверждает test_bybit_risk_tiers.py 15/15 passed, включая обе новые регрессии; liquidation и engine integration suites также прошли.
- Никаких Bybit snapshots/архивов не скачивали; collectors не запускались. Нет PnL, private API/account access, runner registration, paper/live orders или изменений main.
- Следующий безопасный шаг: read-only аудит схемы/metadata в snapshot loaders и соседних execution consumers; сохранять PnL gate закрытым до появления подтверждённых исторических данных и execution evidence.


## Session update — 2026-11-04 (RiskTierHistory ограничен linear-контрактами)

- Статический аудит выявил, что RiskTierHistory заявлен как linear/USDT модель, а calculate_margin_requirements() применяет linear IM/MM формулы, но from_directory(category="inverse") и прямой конструктор могли принимать inverse snapshot. Это создавало возможность ошибочно рассчитать inverse risk tiers по linear формуле.
- Исправление: конструктор RiskTierHistory теперь отклоняет любую категорию, кроме linear. Это не запрещает collector архивировать inverse snapshots, но не позволяет использовать их в linear margin model.
- Добавлена регрессия на попытку создать RiskTierHistory с category="inverse".
- Коммиты: source 2959547ab8c5150ebb9648e54c2792965ea1d06e; tests 6a257b205aef1b8724845c7f6b83fbe0b7aed1b4.
- Финальный Research CI #41846247554 на 6a257b205aef1b8724845c7f6b83fbe0b7aed1b4: SUCCESS; job tests SUCCESS; все 57 workflow steps completed, failures отсутствуют. Фактический лог подтверждает новый inverse-category regression; risk-tier history suite — 16/16 passed.
- Нет Bybit data collection/download, PnL, private API/account access, runner registration, paper/live orders или изменений main. PR #4 остаётся Draft/open.
- Следующий безопасный шаг: завершить read-only review snapshot metadata/type guards и проверить итоговый branch/PR state; не открывать PnL gate без датированных данных и execution evidence.


## Session update — 2026-11-04 (строгие integer-типы metadata snapshot)

- Последний read-only проход по schema guards выявил, что Python сравнивает bool как int: schema_version=true принимался как версия 1, а count/tier_count=true мог приниматься для snapshot с одной строкой.
- Усилена проверка в InstrumentSpecHistory и RiskTierHistory: schema_version, count и tier_count теперь должны быть int, bool отклоняется отдельно, значение должно совпадать с ожидаемым.
- Добавлены регрессии для boolean schema_version и boolean count/tier_count в обоих history loaders.
- Коммиты source: instrument history 43765d20a61a56c0ce165f6e20c7eb163ae38987; risk-tier history b2d284529ceeddab617d4d2ba95c7974b2d0098a. Тесты: instrument history 7fd2d8623ef2ba70248b457504f868e1877afa63; risk-tier history 3b7442b32383f5c41043ea7bf74430e1acbcd7b2.
- Финальный Research CI #41846644399 на 3b7442b32383f5c41043ea7bf74430e1acbcd7b2: SUCCESS; job tests SUCCESS; все 57 workflow steps completed, failures отсутствуют. Фактические логи подтверждают InstrumentSpecHistory 12/12 и RiskTierHistory 17/17, включая новые metadata-type regressions.
- Никаких Bybit collectors/downloads, market PnL, private API/account access, runner registration, paper/live orders или main-branch changes. PR #4 остаётся Draft/open.
- Следующий шаг: финально сверить текущий branch HEAD, PR #4, документацию и последние CI; затем продолжить независимый статический audit execution consumers без запуска PnL.


## Session update — 2026-11-04 (strict integer metadata for isLowestRisk)

- Execution/data-contract audit continued through engine consumers, risk-tier history, funding accounting, mark-price liquidation and exchange sizing. No new market experiment or PnL run was justified.
- Found a strict-schema inconsistency: both risk-tier collector and history loader rejected boolean isLowestRisk but accepted JSON floating values 1.0/0.0 because Python equality treats them as equal to integers. Bybit schema expects integer 0/1.
- Both collector and loader now require a non-bool int exactly in {0,1}; added offline regression tests to both suites.
- Commits: history loader source a14f21c35bfe77674d3a7a3850396a6ecc2d781f; history regression 3e7047ddc19cff0543ab72fd1b42ce65df72236b; collector source 57796a8ecca249a482604a7e9b67dfa968cb9ff1; collector regression 715a7fe71350ff5ffd58b7bb7b1a232e6b7d57c6.
- Final Research CI #41847652788 on 715a7fe71350ff5ffd58b7bb7b1a232e6b7d57c6: SUCCESS; job tests SUCCESS; 57/57 workflow steps completed, no failed steps. Actual logs confirm both float regressions passed. Relevant suite counts: collector 17/17, history 18/18.
- Independent engine review confirms optional exchange sizing is fail-closed when dated instrument specs are supplied; risk tiers are selected as-of entry notional; exact contract quantity is propagated through TP1, close PnL, fees, funding and mark-to-market. Known limitations remain documented: OHLC/L2 execution proxies, account-level tier aggregation, actual funding settlement mark, account-specific fees, and absence of archived historical Bybit snapshots.
- No Bybit collectors or downloads executed; no PnL/backtest, private API/account access, runner registration, paper/live orders or changes to main. PR #4 remains research-only.
- Continue read-only review of execution consumers and provenance; do not relax the PnL gate until verified historical data and execution realism evidence exist.


## Session update — 2026-11-04 (strict funding timestamp validation)

- Static audit found silent integer coercion at two funding boundaries: the accounting helpers used int() on event/position timestamps, and the Bybit Funding parser used int() on the raw API timestamp. Numeric floats such as 2000.5 could be truncated rather than rejected.
- Added a positive non-bool integer-millisecond guard for entry/as-of/TP1/final-close and funding event timestamps in both funding accounting helpers. The active Bybit Funding parser now accepts only integer values or ASCII digit strings; booleans and floats fail closed.
- Added regressions for fractional/boolean timestamps in accounting and API parsing. Intermediate CI runs exposed an assertion-regex mismatch in the new test (the helper intentionally wraps malformed events); the test expectation was corrected. No production-code failure remained.
- Final Research CI #41848927029 on commit 39af6fa583ef2074b33905e89c8b78c9b58d83a1: SUCCESS; 57/57 workflow steps; zero failed steps. Logs confirm funding accounting 23/23 and Bybit market-history parser 26/26, including the new regressions.
- Current Git snapshot: main c87612207d145af433394f0ea992f2d29eba28d5; research HEAD 39af6fa583ef2074b33905e89c8b78c9b58d83a1; merge base ae599a2f3279e15fe27360662f94f0e7ef8db5be; compare diverged 2125 ahead / 36 behind. PR #4 remains open Draft and mergeable=false. Existing branch-divergence policy remains: do not merge/rebase/reset/force-push; integrate only reviewed small patches later. main unchanged.
- No market PnL/backtest, Bybit data collection/download, private API/account access, runner registration, paper/live orders. Data completeness and execution-realism gates remain closed.


## Session update — 2026-11-04 (TP1 remainder minNotional at TP2)

- Static review of exchange-sized TP1 handling found an under-validation for short positions. The remainder check used min(stop_price, entry_price), but a short TP2 target may be below both; a remainder could pass TP1 validation while its planned TP2 reduce order would violate archived minNotionalValue.
- Updated _apply_tp1() to validate the remaining quantity against the lowest of stop, entry and TP2 prices. Long behavior remains unchanged when TP2 is above entry; short planned target is now included.
- Added regression: 1.0 contract, 0.1 qtyStep, 0.1 minOrderQty, minNotionalValue 45; TP1 remainder 0.5 at TP1 90 passes exactly 45, but TP2 80 would be 40. Old code accepted TP1; new code rejects it and preserves full remaining quantity.
- Final Research CI #41850162961 on e01a53868885f5ac79f2ad3d3cfa3179e7207b1a: SUCCESS; 57/57 workflow steps; zero failures. Actual log confirms test_tp1_rejects_short_remainder_below_min_notional_at_tp2 passed; MarkPriceEngineIntegrationTests 9/9. Source-only CI #41850143419 on 7238076b271bf25010d01ce2df0c1321e3652722 also completed SUCCESS 57/57.
- This is an exchange-order validity guardrail, not market PnL evidence. No data downloads, collectors, private API, runner, PnL/backtest, paper/live orders or main-branch changes.


## Session update — 2026-11-04 (exchange-sized restore + TP1 funding state)

- Added fail-closed restore validation for exchange-sized positions: initial and remaining quantities must meet minOrderQty; remaining quantity must meet minNotionalValue at the lowest planned exit price among stop, entry and TP2; after TP1, the TP1 leg must also meet minOrderQty and minNotionalValue at TP1.
- Added two state-persistence regressions for restored remaining quantity below minOrderQty and below minNotionalValue. CI #41851236490 on d50c923b2e158e951d9ca979708d093e54ae3983 passed 57/57 steps; actual log confirms both tests ran. An earlier test-only run failed because tests asserted the inner error wording while loader intentionally wraps failures; assertions were corrected to verify fail-closed rejection, and rerun passed.
- Funding helper audit found a separate invariant gap: both accrued funding functions required tp1_ts_ms when tp1_hit=true, but accepted tp1_ts_ms when tp1_hit=false; they also accepted non-bool tp1_hit via truthiness. Both helpers now require tp1_hit to be bool and enforce timestamp iff TP1 is hit. Two regressions cover timestamp-without-hit and integer-as-bool.
- Final CI #41851768270 on 3170738a78eac92b0a93eda66510c038660f0864 passed 57/57 steps, zero failures. Actual log confirms both new funding regressions passed; funding accounting suite ran 76 tests. Source-only CI #41851738950 on 568f5ed2552d27dadfeb82c4d1e9610cfac3cd13 also passed 57/57.
- Scope remains technical correctness only. No PnL/backtest, market archive downloads, private API, runner, paper/live orders or main-branch changes.


## Follow-up correction — planned exit prices only (2026-11-04)

- Refined ENG-EXEC-015 / ENG-EXEC-016 minNotional guard: entry price is not itself a planned exit order. Including it in the minimum could falsely reject a valid restored long position after its trailing stop had moved above entry.
- Both TP1 and restore checks now use min(stop_price, tp2_price), i.e. the actual planned stop/target exit levels; TP1 leg remains checked separately at TP1 price.
- Added regression for an exchange-sized long with entry 100, trailing stop 110, TP2 112, qty 1, minNotional 105: restore must succeed because both planned exits satisfy the threshold even though entry notional does not.
- CI #41852293859 on c88e587d01739eb7c0ee6fe94e0369b28aff664c: SUCCESS, 57/57 steps, zero failures. Actual log confirms the new restore regression passed; state-persistence suite 77/77.


## Session update — funding TP1/quantity invariant (2026-11-04)

- Further accounting audit found both funding helpers accepted contradictory lifecycle state: `tp1_hit=false` with a partial remaining quantity, or `tp1_hit=true` while remaining quantity still equaled initial quantity. This could silently misclassify the exposure share used in cumulative funding and liquidation-margin funding.
- Both `accrued_funding_cost()` and `accrued_funding_cost_for_remaining_margin()` now fail closed on those contradictions. The margin helper also explicitly validates `remaining_fraction` in [0,1]. Exact contract quantities remain authoritative over a stale/rounded display fraction, consistent with existing behavior/tests.
- Updated funding test fixture default to a full remaining fraction when TP1 is false; previous default encoded an invalid half-sized position without a TP1 event. Added three regressions: partial quantity without TP1, TP1 flag without quantity reduction, and exact contract partial quantity without TP1.
- Final CI #41853410298 on test commit 0cf45d16809a04e2653325934b37723b009097d0: SUCCESS, 57/57 workflow steps; actual log confirms all three new tests passed and funding accounting suite ran 28 tests.
- Intermediate source-only CI #41853363357 used the prior test fixture (half remaining with TP1 false) and failed in the funding suite as expected for the newly enforced invariant. The fixture was corrected in the next commit and the full workflow rerun passed; no source rollback was needed.
- Classification: funding/accounting state-integrity guardrail, not PnL evidence. No market data downloads, PnL/backtest, private API, runner, paper/live orders, or main-branch changes.


## Session update — validate restored realized TP1 gross (2026-11-04)

- Persistence audit found restore validated that TP1 was hit and the remaining fraction/contract quantities were consistent, but trusted arbitrary nonnegative `realized_tp1_gross_usdt`. That value is added directly to final trade PnL and MTM; a modified/stale backup could therefore inject incorrect realized PnL after TP1.
- `load_state()` now recomputes expected TP1 gross from the closed leg and TP1 price: exchange-sized positions use exact `tp1_contract_qty * abs(tp1_price-entry_price)`; legacy positions use `size_usdt * (1-remaining_fraction) * abs(tp1_price-entry_price)/entry_price`. The stored value must match after the engine's 4-decimal money rounding (tolerance 1e-4).
- Added regression that corrupts a legacy TP1 realized gross from 30 to 31 and confirms restore fails closed. Corrected exchange-sized TP1 fixtures from legacy gross 30 to exact contract gross 3; corrected liquidity fixture to persist its legitimate 30 legacy TP1 gross.
- Final CI #41854119883 on f42979860d97090120ee3a8aed79d59695d441ee: SUCCESS, 57/57 workflow steps; state persistence suite 78 tests; log confirms corrupt-gross rejection and valid legacy/exchange-sized round trips.
- Earlier attempts #41853865541 and #41853997743 failed on stale test fixtures inconsistent with the new source invariant (legacy TP1 liquidity fixture omitted gross; exchange-sized fixtures used legacy-sized gross). Fixtures corrected; final full workflow green.
- Classification: persisted PnL integrity guardrail, not strategy profitability evidence. No PnL/backtest, market archive downloads, private API, runner, paper/live orders, or main changes.


## Session update — restored MFE/MAE invariants (2026-11-04)

- Backup restore previously accepted zero extrema and directionally impossible favorable/adverse prices. `OpenPositionState.__post_init__` silently replaces non-positive extrema with entry, potentially masking corrupt state and losing recorded excursion history.
- `load_state()` now rejects non-positive saved max_favorable_px/max_adverse_px and enforces directional invariants: long favorable >= entry and adverse <= entry; short favorable <= entry and adverse >= entry. Missing legacy fields still use the dataclass entry-price default.
- Added three regressions: zero favorable extreme, long favorable below entry, short adverse below entry.
- Source CI #41854906684 SUCCESS, 57/57; final source+tests CI #41854947672 on 4c7744c22180a97fa868547eac034cdf91b69491 SUCCESS, 57/57; actual log confirms all three new regressions; state persistence suite 81 tests.
- Classification: persisted trade-excursion metrics integrity; no PnL/backtest, archive downloads, API, runner, paper/live or main changes.


## Session update — risk stop latches must agree with drawdown evidence (2026-11-04)

- Found a fail-open restore case: a backup could contain current drawdown >= emergency kill-switch threshold while `kill_switch_triggered=false`, or current-day drawdown >= daily stop threshold while `daily_stop_triggered=false`. `can_open_new_trade()` trusts those latches, so restart could re-enable entries despite breached limits.
- Restore now requires `kill_switch_triggered=true` whenever either current peak-to-equity drawdown OR persisted historical `max_drawdown_pct` reaches `emergency_kill_switch_pct`. Including historical max is necessary because the emergency latch remains active after equity recovers.
- For a non-empty `current_day_str`, restore requires `daily_stop_triggered=true` whenever current equity is below `day_start_equity` by at least `daily_stop_loss_pct`.
- Regressions cover emergency threshold currently breached, historical emergency DD breached then recovered, and daily threshold currently breached. Source CI #41861236015 SUCCESS 57/57; final CI #41861273155 on 669a7d66c50df5426e63c5490580b2d8bbc92f22 SUCCESS 57/57; log confirms all three regressions; state persistence suite 84 tests.
- Residual observability limit: if an intraday daily-stop breach occurred and equity later recovered above the threshold before backup, the existing schema has no daily minimum-equity watermark; restore cannot independently reconstruct that prior breach if the latch itself is corrupted. Runtime persists the latch on false->true. A future schema-level daily watermark would be needed to validate recovered intraday breaches.
- Classification: risk-control persistence integrity, not profitability evidence. No PnL/backtest, market data downloads, API, runner, paper/live or main changes.

## Session update — строгая временная валидация trade archive inspector (2026-11-04)

- Статический аудит выявил, что `scripts/inspect_bybit_trade_sample.py` преобразовывал CSV timestamp через `float()` и `round()`. Это могло молча округлить sub-millisecond значение, хотя основной queue replay parser уже отклоняет такие значения как неоднозначные.
- Инспектор теперь использует общий `parse_trade_timestamp_ms()` из `bybit_l2_queue_replay.py`: Decimal parsing, поддержка секунд/миллисекунд, fail-closed для non-finite/non-positive и sub-millisecond значений. Это устраняет две расходящиеся реализации одного контракта.
- Regression coverage: точные секунды и миллисекунды, sub-millisecond timestamps, non-finite/non-positive values; тесты находятся в `tests/test_run_bybit_l2_queue_replay.py`.
- Финальный Research CI #41873039139 на `ec28763da6ade2635c31cd0111ae8c612625f23d`: SUCCESS; job `tests` SUCCESS; все 57 workflow steps завершились без failure. Фактический лог подтверждает inspector/runner suite 7/7 и aggregate-L2 primitives 81/81.
- Промежуточный run #41872989853 завершился failure из-за устаревшего имени helper в тесте после refactor к общему parser; тест исправлен, финальный полный workflow прошёл. Source-only и предшествующий тестовый runs #41872780436 и #41872788110 также SUCCESS на своих промежуточных commits.
- Это проверка целостности временных меток диагностического инструмента, не доказательство maker fill или PnL. Inspector с сетевой загрузкой не запускался; новые архивы не скачивались.
- Execution gate остаётся `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`: сохранённый AAVE CSV не содержит ни `BT`, ни `isBlockTrade`; documented REST recent-trade endpoint не предоставляет произвольный исторический диапазон. Нужен уже имеющийся проверенный WS capture/archive с BT либо отдельное решение о будущем сборе данных.
- Никаких PnL/backtests, market data downloads, collectors, private API, runner, paper/live orders или изменений `main` не было.


## Session update — trade ID diagnostics in historical archive inspector (2026-11-04)

- Статический аудит `scripts/inspect_bybit_trade_sample.py` выявил, что inspector считал только truthy `trdMatchID`. Пустые/отсутствующие ID и ID с окружающими пробелами пропускались без отдельного счётчика; отчёт мог выглядеть как отсутствие проблем с ID, хотя строгий queue replay такие строки отклоняет.
- Добавлен `classify_trade_id()` с теми же правилами identity, что использует replay: missing/blank → `missing`, surrounding whitespace → `malformed`, повтор → `duplicate`, иначе уникальный ID.
- JSON report теперь включает `missing_trade_id_count`, `malformed_trade_id_count`, `has_trade_id_column` и `trade_id_validation_status` (`valid` только при наличии колонки и нулевых missing/malformed/duplicate).
- Коммиты: source `bd2c0f9bc9fe2ad64044a4b9fe672ceb148950b3`; regression `6dcb9d8bc000778c09975dbd462c36545e23682c`.
- Source-only CI #41873380445 завершился SUCCESS; final Research CI #41873425668 на `6dcb9d8`: SUCCESS, job `tests` SUCCESS, 57/57 steps. Фактический лог подтверждает runner/inspector suite 9/9, включая новый ID classification regression; aggregate-L2 primitives 81/81.
- Это улучшение диагностики качества CSV, не подтверждение исторических maker fills. Сохранённый AAVE archive всё ещё не содержит BT/isBlockTrade; maker execution realism остаётся BLOCKED_FOR_STRATEGY_PNL.
- Никакие новые архивы не скачивались; inspector с сетевой загрузкой не запускался; нет PnL/backtest, collectors, private API, runner, paper/live orders или изменений main.


## Session update — maker markout decomposition (2026-11-04)

- В `scripts/run_bybit_l2_queue_replay.py:add_post_fill_markouts()` прежний fill-to-future-mid показатель включал одновременно spread capture и движение midpoint после fill. Добавлен pre-fill midpoint из последнего BBO строго до fill timestamp и отдельный `signed_mid_move_from_pre_fill_bps`; `signed_fill_to_future_mid_bps` хранит полный fill-to-future-mid результат, старое `signed_mid_markout_bps` оставлено как compatibility alias.
- Same-millisecond book events исключаются; fill timestamp проверяется строгим integer guard.
- Regression: Buy fill 99, pre-fill mid 100, future mid 101 даёт около 202.02 bps fill-to-future-mid и ровно 100 bps mid-to-mid.
- CI #41867866581 на `794342bbd00342d0b7f1af660362794408da0345`: SUCCESS, 57/57 steps; runner suite 6/6, aggregate-L2 primitives 81/81. Позднее #41873039139 и #41873425668 повторно подтвердили runner/markout suite.
- Старый сохранённый AAVE report не содержит pre-fill mid и не позволяет ретроспективно выделить adverse selection. Повторный replay не делался: CSV не содержит BT/isBlockTrade и строгий parser его отклоняет.
- Никаких новых архивов, PnL/backtest, collectors, API, runner, paper/live orders или main changes.

## Session update — BT/RPI flag alias validation in trade archive inspector (2026-11-04)

- Сверка inspector с `iter_public_trades()` показала, что инспектор фиксировал только наличие BT/RPI колонок, но не валидировал значения по строкам и не сравнивал aliases, если присутствовали оба поля. Основной replay parser уже отклонял missing/malformed flags и conflicting aliases.
- Добавлен `classify_boolean_flag_aliases()` на базе общего `parse_exchange_bool()`. Отчёт теперь содержит status counters (`true`, `false`, `missing`, `malformed`, `conflict`) и отдельный `*_flag_validation_status` для BT и RPI; `valid` возможен только при наличии alias и отсутствии проблемных строк.
- Regression покрывает отсутствие колонок/значений, пустые и malformed flags, true/false, совпадающие и конфликтующие aliases.
- Source commit `83bca2b14a5cbb613e0ab849a45a2fbf4750aa71`; test commit `5f315bdd048f8abefa07a992aa667010d0ea1f5b`.
- Source-only CI #41874223792 SUCCESS, 57/57; final CI #41874277483 на `5f315bdd`: SUCCESS, 57/57. Фактический лог подтверждает новую flag-alias regression; inspector/runner suite 9/9 и aggregate-L2 primitives 81/81.
- Это диагностика качества trade metadata, не maker execution evidence и не PnL. Сохранённый AAVE CSV по-прежнему не содержит BT/isBlockTrade. Inspector с сетевой загрузкой не запускался; архивы не скачивались.
- `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`. Нет PnL/backtests, collectors, API, runner, paper/live orders или изменений `main`.

## Session update — malformed trade CSV structure is rejected by inspector (2026-11-04)

- Сравнение `scripts/inspect_bybit_trade_sample.py` с replay parser выявило, что инспектор не отклонял duplicate CSV headers, extra row fields и missing core row values. `csv.DictReader` может перезаписать значения при повторяющихся заголовках и помещает лишние поля в ключ `None`.
- Добавлены `validate_trade_csv_header()` и `validate_trade_csv_row()`. Инспектор теперь отклоняет duplicate/missing required headers, extra CSV fields и missing core values (`timestamp`, `symbol`, `side`, `size`, `price`) до агрегации.
- Regression покрывает duplicate/missing headers, extra row fields и missing row values.
- Source commit `ab27c80413c23f4d0689441cff6f131a91a0ab5d`; test commit `846279119545a7036d65b57a156c8ea38b7ae895`.
- Source-only CI #41875043047 SUCCESS, 57/57; final CI #41875093214 на `8462791`: SUCCESS, 57/57. Фактический лог подтверждает structural regressions; inspector/runner suite 9/9 и aggregate-L2 primitives 81/81.
- Это structural data-integrity guardrail диагностического инструмента, не maker execution evidence и не PnL. Архивы не скачивались; inspector с сетевой загрузкой не запускался. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` остаётся.
- Нет PnL/backtests, collectors, API, runner, paper/live orders или изменений `main`.

## Session update — strict integer orderbook inspector fields (2026-11-04)

- Сверка `scripts/inspect_bybit_orderbook_sample.py` с `OrderBook.apply()` выявила coercion через `int()` для `ts`, `cts`, `seq`, `u`: bool, numeric strings и fractional floats принимались, хотя основной replay parser требует JSON integers и положительные значения.
- Inspector теперь использует общий `strict_int()` через `parse_event_integer_fields()`. `ts`, `seq`, `u` обязательны; `cts` проверяется строго, если присутствует. Отсутствующий/null `cts` учитывается как missing.
- Regression покрывает корректные поля, отсутствующий cts, bool, float, string и неположительные значения.
- Source commit `d6078d4f0e56c1d398b427b8c7640b1f09021b89`; test commit `1b50c9da41b99ea23d04e009e7ba6e6424d73e01`.
- Source-only CI #41875836674 SUCCESS, 57/57; final CI #41875905360 на `1b50c9d`: SUCCESS, 57/57. Фактический лог подтверждает strict orderbook inspector regression; inspector/runner suite 9/9 и aggregate-L2 primitives 81/81.
- Это timestamp/sequence integrity guardrail диагностического инструмента, не execution evidence и не PnL. Inspector не запускался с сетевой загрузкой; новые архивы не скачивались. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` остаётся.
- Нет PnL/backtests, collectors, API, runner, paper/live orders или изменений `main`.

## Session update — align standalone L2 inspector with replay invariants (2026-11-04)

- Static comparison found two integrity gaps in scripts/inspect_bybit_orderbook_sample.py: it accepted a delta before the first full snapshot, and it accepted duplicate price levels within the same bid/ask side of a snapshot or delta. The primary OrderBook replay rejects delta-before-snapshot and duplicate side/price entries.
- The inspector now rejects delta-before-initial-snapshot and duplicate price levels separately for bids/asks in both snapshots and deltas.
- Added regression coverage for delta-before-snapshot and duplicate price levels in snapshot and delta.
- Code/test commit: 63458f9108e9de65c4b167d387d8d01cc3c8a607.
- CI: run #41883538553 on prior commit b54e5cb was still in_progress when checked; it does not include this commit. No successful CI for 63458f9 yet. New regressions and full suite remain pending/unverified.
- Official Bybit docs were reviewed to avoid conflating standard depth-specific orderbook streams with orderbook.full. The standard stream docs describe snapshots/deltas, u=1 restart snapshots, and same-u repeated L1 snapshots; the full-orderbook docs specify a separate delta-only REST-sync protocol and consecutive u continuity. Do not impose full-orderbook u+1 rules on the ob200 archive absent evidence that it uses that feed format.
- Diagnostic archive integrity only; no queue-fill semantics, data archives, PnL, strategy parameters, collectors, API, runner, paper/live orders or main changes.

## Session update — duplicate JSON-key rejection in standalone orderbook inspector (2026-11-04)

- Сверка scripts/inspect_bybit_orderbook_sample.py с основным replay reader выявила несогласованность: replay использовал object_pairs_hook и отклонял duplicate JSON keys, а standalone inspector вызывал обычный json.loads, который молча оставляет последнее значение повторного ключа.
- Добавлен локальный _unique_json_object() и передан как object_pairs_hook; добавлен regression test, где повторяется ключ u в data.
- Commit: b54e5cb90393b4334e736b4e96db7b7bfdefac7d.
- На момент handoff новый workflow run для этого commit не обнаружен. Последний подтверждённый CI #41881215008 на af4ad6f предшествует изменению. Regression/full suite pending; не заявлять PASS до фактического run/log.
- Это усиление диагностического инструмента, не изменение replay/fill semantics и не PnL evidence. Никакие архивы не скачивались.

## Session update — non-reset orderbook update-ID regression guard (2026-11-04)

- Static review found that `OrderBook.apply()` accepted a lower non-`1` `u` after a higher update ID if `cts` and `seq` were still increasing. This could apply stale/out-of-order order-book state.
- Added fail-closed rejection for `update_id < last_u`, except the documented `u=1` full-snapshot reset. No contiguous-`u` requirement was added.
- Added regression coverage for atomic rejection; existing `u=1` restart snapshot coverage remains.
- Commits: code/test `2b71592a1431028a5e78af2bc166327a4a5f49b8`; explanatory comment `af4ad6f421b52cd24f864d5a71c581853cc569a8`.
- Focused isolated behavior check and test-source syntax check passed. Research CI #41881215008 on `af4ad6f` completed the `tests` job SUCCESS with 57/57 workflow steps SUCCESS; logs confirm the new regression PASS, aggregate-L2 primitives 82/82 and runner/inspector suite 13/13.
- No market data download, collector, PnL/backtest, private API, runner, paper/live orders, or `main` changes. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` remains.

## 2026-11-04 — continuation: no-overwrite report serialization (ENG-EXEC-032)

- Confirmed current research branch commit: `118acb07cec55e692cb3dd3adeeb01536426e27f`.
- Static audit found three fixed-name JSON outputs written with `Path.write_text()`, allowing a repeated run in the same working directory to silently overwrite a prior diagnostic artifact.
- Added shared `report_io.py`; report creation uses exclusive mode `x`, so existing artifacts cause `FileExistsError` and remain byte-for-byte unchanged. JSON serialization occurs before file creation; an interrupted write removes the newly created partial file.
- Updated the L2 queue replay runner, trade inspector and orderbook inspector to use the helper. Added two deterministic tests for valid JSON/no-overwrite and serialization failure/no file.
- Source commits: helper `0a58d10fd34674708623b48fee1a633ee3c8e5f3`; queue runner `ddc3defd62a623f13bc4cb0db89392aab27b783e` plus import correction `a70d75967867f609a0b1aa563591bb733a02911a`; trade inspector `e2f484a7225baf3f4138ec7d3e9ad191161dba19`; orderbook inspector `6bdedbebf9d29ca9381ebb08be35e03c9e65b736`; tests `ed089a1c9a6f0573a81357c4ee7116f709af1d53`; documentation `118acb07cec55e692cb3dd3adeeb01536426e27f`.
- Research CI workflow path filters include the modified scripts/tests and should trigger on push; combined commit status has not returned check records. Do not claim tests/CI passed until actual logs are available.
- Do not dispatch `bybit-orderbook-sample-inspection.yml`: it downloads new L2/trade archives and runs the bounded queue probe, all currently gated.
- No collectors, new archives, private API, runner, market PnL/backtests, paper/live orders. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`. `main` unchanged; PR #4 remains Draft/unmerged.

## 2026-11-04 — ENG-EXEC-033 trade timestamp order status

- Static comparison found that the public trade inspector counted timestamp regressions but did not expose an explicit validity status, while replay rejects a timestamp regression. A consumer could mistake report scan status `success` for replay-order validity.
- Added `timestamp_order_validation_status` to the trade inspector validation block (`valid` only when `nonmonotonic_timestamp_count == 0`; otherwise `invalid`) and a strict count classifier. Added deterministic valid/invalid and malformed-input coverage.
- Source commit `0c4cf2e2504d69d31d3113b0f408f2b236c3db09`; test commit `6fc17e4d7f3274a8d4a609b845d658fd8010df15`; note `1e8b9fcd63df6777296412b78fef9b21cfc3184a`.
- CI status remains unconfirmed; combined status returned no check records. No archives/network inspector, collectors, market PnL, private API, runner or orders. Maker gate remains closed.

## 2026-11-04 — ENG-EXEC-034 strict CSV quoting

- Static parser audit found that Python `csv.DictReader` defaults to `strict=False`. An unterminated quoted optional RPI field could be returned as a string and pass later boolean parsing after whitespace trimming.
- Both primary replay parser and standalone trade inspector now use `strict=True`. Inspector row iteration was factored into `validated_trade_csv_reader()` so the exact strict parser contract is covered without network access.
- Added deterministic malformed-quote regressions for both parser paths. A local standard-library reproduction confirms `csv.Error: unexpected end of data`.
- Commits: inspector `d78720991bf6a72efa05310b878505dcd5bf1123`; core `81f58d0b48705ed1e5f2db36ba80ca42c0feb50a`; tests `13f32dbc2db3e686549866a14998a0c31cf659a6` + fixture correction `5f6c245de6bbd82cd280d4db750b8e3d1434c867`; inspector test `06544878931c0daa1117980c63eb01885c8e338e` + fixture correction `9302114d0199097d834fecf112f2c6d74ec931d7`; note `69259ca59d8c653fee04e4f6ad07bb10a75d51ce`.
- CI remains unconfirmed; no combined check records. No market archive download or network workflow, collectors, PnL, private API, runner or orders.

## 2026-11-04 — ENG-EXEC-035 queue-replay compatibility summary

- Inspector's top-level `status: success` means scan completion only; it could coexist with missing trade ID/BT/RPI flags or timestamp regressions. Added `queue_replay_compatibility_status`, valid only when all four validation dimensions are valid and at least one row exists.
- Header-only/zero-row archives now return null `duration_hours` and `invalid_or_incomplete` replay compatibility rather than failing during timestamp subtraction or appearing compatible.
- Source commits `86a0590f6c9978675426523ba8d86ddc3fdc8b85`, `68ee303ea44744950881033f9c4660912ee8ae9e`; tests `8311daa4c4f63cebaf00d1b9bc3f5dbfe91ca381`, `82852d6f82f4a619a8838db50dcc9431e04560cb`.
- Research CI run `41888048946` on test commit `82852d6` completed successfully; log confirms strict CSV, report writer and replay compatibility tests passed. Intermediate run `41888039132` failed on a temporary signature/test mismatch before the following test commit corrected it.
- No market archives, collectors, PnL, private API, runner or orders. Maker gate remains closed.

## 2026-11-04 — ENG-EXEC-036 L2 inspector/replay compatibility boundary

- Static audit found a deliberate but important distinction: L2 inspector may finish with `status: success` while reporting missing `cts`; replay requires `cts` on every event. Scan completion is not replay compatibility.
- Inspector rejects `cts` and `seq` regressions but does not enforce archive-wide `u` monotonicity; replay's `OrderBook.apply()` rejects non-reset `u` regressions. ENG-EXEC-031 intentionally avoids universal `u` monotonicity until the depth-200 archive contract is confirmed.
- No code change. Do not loosen replay or add unsupported `u` assumptions. Next: define explicit L2 replay-compatibility reporting once source semantics are established.
- Note: `ENG_EXEC_036_L2_INSPECTOR_REPLAY_COMPATIBILITY_RU.md`. No archive download, network workflow, collector, PnL, API, runner or orders. Maker gate remains closed.
