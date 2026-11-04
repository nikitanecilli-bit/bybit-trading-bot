# Стартовая точка новой сессии — 2026-11-04

> Назначение: компактный handoff для нового чата. Это не замена Experiment Ledger и полному аудиту. Перед любыми действиями перепроверять live-состояние GitHub.

## 1. Текущая точка GitHub

- Репозиторий: `nikitanecilli-bit/bybit-trading-bot` (private).
- Рабочая ветка: `research/market-regime-v1-main`.
- HEAD на момент подготовки handoff: `025cfca91ebb3a0d4419f8cdaa53be3b9c29f667`.
- Последний code commit, покрытый успешным Research CI: `d2740c6ff444c3a7302b4b04dcc04d15ebf1dcb1`.
- HEAD handoff commit — документальное дополнение поверх проверенного code commit; его diff добавляет только раздел 34 в checkpoint, production/research code не менялся.
- Последний подтверждённый CI: [Research engine checks #41840361238](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41840361238), commit `d2740c6`, conclusion SUCCESS, job `tests` SUCCESS, 57/57 workflow steps.
- В этом CI: aggregate-L2 primitive tests 80/80 passed; runner chronology/markout test step SUCCESS (4 теста в `tests/test_run_bybit_l2_queue_replay.py`).
- Предыдущая неудачная попытка #41840229312 была исправлена import-path fix в `d2740c6`; после исправления #41840361238 прошёл.
- PR #4: открыт, draft, base `main`, head = текущая research-ветка. Не сливать автоматически.
- Сравнение с `main`: diverged, 2061 commits ahead / 36 behind. Merge-base: `ae599a2f3279e15fe27360662f94f0e7ef8db5be`.
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
