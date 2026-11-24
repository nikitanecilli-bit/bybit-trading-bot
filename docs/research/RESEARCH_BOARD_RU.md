# Research Board — текущее состояние лаборатории

> Последняя сверка: 2026-11-24. Рабочая ветка: `research/market-regime-v1-main`. Это короткая управленческая панель; детали, доказательства и исторические значения остаются в Experiment Ledger и первичных отчётах.

## 1. Главный вопрос

Есть ли на конкретном рынке и горизонте воспроизводимая закономерность, которая после реалистичных издержек остаётся прибыльной, выдерживает независимую проверку и может быть исполнена?

**На сегодня ответ не установлен. Доказанного устойчивого edge нет.** Количество кода, зелёный CI и прохождение synthetic tests не меняют этот статус.

## 2. Текущий режим работы

**Разрешено:**
- read-only аудит кода, GitHub history, уже сохранённых данных и результатов;
- deterministic synthetic tests и проверки временной причинности;
- исправления, которые предотвращают искажение исследовательских результатов;
- точечное улучшение документации и воспроизводимости.

**Не является текущей задачей и запрещено действующими gates:**
- подключение Bybit, private/account API, API keys или live-режима;
- настройка self-hosted runner и обход сетевых ограничений;
- новые биржевые архивы/collectors;
- новые market-PnL backtests, parameter sweeps или event studies на текущем пакете;
- paper/live trading и реальные ордера.

Запрет на Bybit/runner/новые архивы действует до последовательного прохождения исторической проверки и paper/forward validation. Это не отменяет отдельного разрешения, которое потребуется для любых реальных ордеров.

## 3. Доска гипотез

| Направление | Статус | Что подтверждено | Следующее решение |
|---|---|---|---|
| Базовая H1 breakout / E01–E13 | **DEFERRED / NO EDGE** | Ряд shared-capital proxy результатов отрицателен; выборка не PIT Bybit; старые результаты имеют ограничения исполнения и provenance | Не тюнить прежние folds. Возвращаться только при новом независимом основании и закрытых data/method gates |
| H-A relative-strength breakout | **REJECTED — tested configuration** | В preregistered proxy comparison хуже baseline и отрицательна по folds | Не подбирать параметры и символы на тех же folds |
| H-C post-break invalidation | **REJECTED AS PROFITABILITY CANDIDATE / MECHANICS ONLY** | Проверенная proxy-конфигурация не показала превосходства; реализация находится за default-OFF флагом; synthetic tests не доказывают edge | Не продолжать tuning на использованном окне |
| H-B mean reversion | **SIGNAL + CLASSIFIER + ENTRY MECHANICS PASS / LIFECYCLE BLOCKED** | Frozen default RegimeConfig candidate, causal adapter, predicate и next-open entry contract прошли Research CI #45465175545; 21 H-B signal/entry tests и 6 regime-adapter tests; нет engine integration, exit/persistence lifecycle и market PnL | Решить, нужен ли synthetic-only exit/persistence contract; не подключать engine и не запускать PnL |
| Новые стратегии/фильтры | **DEFERRED** | Ни один новый кандидат не обоснован достаточно, чтобы оправдать расширение | Не добавлять до закрытия текущего H-B mechanical question |

Статусы REJECTED относятся к конкретным проверенным конфигурациям/окнам, а не к утверждению, что любой вариант семейства стратегий математически невозможен.

## 4. Данные: что реально есть

В рабочем дереве на момент аудита обнаружены шесть ZIP в `data/archives/cryptofetch/`. Аудит архива сообщает 67 CSV entries: 64 непустых/пригодных для legacy loader, три пустых; перекрывающиеся дубликаты прошли сравнение без обнаруженных конфликтов.

Это Binance-style OHLCV proxy. В репозитории нет подтверждённого Bybit-native пакета trade OHLCV + mark + funding + dated instrument/risk-tier snapshots и нет полного point-in-time universe. Наличие collector-кода и его mocked/offline tests не означает, что реальные архивы были получены.

Следствие: текущий data package не открывает путь к достоверному Bybit execution replay. Не маскировать этот пробел новыми расчётами на той же выборке.

## 5. Ближайшая последовательность

1. Довести PR #16 до актуальной базы рабочей ветки без потери изменений.
2. Включить H-B signal-only module/tests в технический Research CI так, чтобы CI выполнял только compile и deterministic tests — без market-PnL workflows. **Выполнено.**
3. Получить фактический запуск точных H-B tests и релевантных legacy regression tests; прочитать логи и убедиться, что выполнялись именно нужные тесты. **Выполнено:** Research CI #45463406898 подтвердил 10/10 signal tests; #45464653488 подтвердил 13 market-regime tests, 13 H-B signal tests и 6 H-B regime-adapter tests.
4. Провести независимый code review временной семантики и входных контрактов. Исправлять только подтверждённые дефекты. **Выполнено для signal/regime layer.**
5. Зафиксировать результат как **SIGNAL + REGIME MECHANICS PASS**, не как strategy/edge pass. Engine integration не выполнять.
6. Pure next-open fill geometry выполнен: наличие t+2 бара, exact timestamp, actual open строго между frozen stop и target. Не продолжать к sizing/persistence/manager без отдельного решения о необходимости и без допустимого пути к market validation.
7. Сейчас H-B остановлена на границе механической готовности. Не строить полный engine lifecycle ради гипотезы без возможности проверить её на независимых рыночных данных.

## 6. Критерии остановки и доказательности

- Если signal contract требует будущих данных, неоднозначного timestamp или скрытого подбора параметров — остановить/переформулировать гипотезу.
- Если тесты не запускаются в репозитории, не объявлять их пройденными по ручному копированию функции.
- Synthetic pass подтверждает только механику заданного контракта.
- Технический CI подтверждает только выполненные проверки.
- Market edge требует отдельного preregistration, подходящих данных, независимой выборки, общего капитала, полной cost-модели и проверки исполнимости.
- Holdout не используется для выбора параметров. Отрицательные результаты сохраняются.
- Расширение engine/infra заморожено, кроме исправлений, доказанно необходимых для корректности исследования.

## 7. Источники истины

- Цели, разрешения и ограничения: `PROJECT_COMPASS_RU.md` и `../../PROJECT_WORKING_RULES_RU.md`.
- Исторические эксперименты: `EXPERIMENT_LEDGER_RU.md`.
- Доказательства и ограничения данных: `../audits/POINT_IN_TIME_UNIVERSE_AND_ARCHIVE_AUDIT_2026-11-03.md`, funding completeness audit и первичные experiment reports.
- Текущая реализация и тесты: только актуальные файлы/commits рабочей ветки; старые сообщения чата не заменяют GitHub-проверку.

Обновлять эту доску после каждого решения ACCEPT/REJECT/BLOCKED или существенного изменения разрешений/данных. Не превращать её в подробный журнал событий.


## 2026-11-24 — CI dependency correction

- Первый Research CI после добавления H-B tests: run [45463120336](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45463120336) — FAILURE только на команде `python -m pytest`: runner не содержит pytest (`No module named pytest`). H-B assertions не исполнялись; это не провал логики сигнала.
- Не добавлять внешнюю зависимость только ради одного набора синтетических тестов. Тесты переведены на стандартный `unittest`; workflow теперь запускает `python tests/test_h_b_signal.py`.
- Повторный Research CI run [45463406898](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45463406898) для SHA `582ccedf943ed7d4a5a60db0436bbb63d4f5741c` находится в работе. До его завершения статус H-B mechanics остаётся UNVERIFIED.


## 2026-11-24 — H-B signal mechanics CI passed

- PR #16 объединён в рабочую ветку. Исследовательский commit с H-B pure predicate, tests и CI wiring: `5bd43a32bd3955684924b0bddc93356afa2de10c`; последующая замена pytest на стандартный unittest и финальный workflow: `582ccedf943ed7d4a5a60db0436bbb63d4f5741c`.
- Research CI [45463406898](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45463406898) — SUCCESS. В логах: `Ran 10 tests`, `OK`; compile и все предыдущие regression steps также прошли.
- Первый запуск [45463120336](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45463120336) провалился из-за отсутствующего pytest; после перевода тестов на stdlib unittest проблема закрыта. Это была инфраструктурная ошибка запуска, не ошибка assertions.
- Решение: **H-B SIGNAL MECHANICS PASS** только для изолированного контракта. Не означает market validation, profitability, edge, engine integration или readiness.
- Следующий шаг: статически проверить существующий causal regime classifier/RegimeConfig, timestamp convention и границы следующего бара. Не выполнять market-PnL, parameter tuning, data collection или lifecycle integration.


## 2026-11-24 — independent H-B / regime code review

- Статический review подтвердил: `h_b_signal.evaluate_h_b_signal()` проверяет 26 непрерывных H1 баров от t-24 до t+1, берет regime[t-1], ATR[t-1], shock close[t], stabilization close[t+1], stop=low[t], target=mean из 24 pre-shock closes; entry только планируется на timestamp open[t+2]. Функция не использует бары после t+1.
- Ограничение: функция принимает `regimes` и `atr_values` отдельными массивами. Сам интерфейс не доказывает, что метки получены из `market_regime.classify_candles()` с явной frozen `RegimeConfig`. Поэтому PASS относится к predicate contract, но не к end-to-end classifier binding и не к торговой стратегии.
- До engine integration остаются отдельные контракты: проверка фактического open[t+2] и entry-price geometry (entry > stop и target > entry), pending cancellation при gap/missing next bar, position state/exit lifecycle. Это не покрывается signal-only predicate.
- Найден integrity defect в `RegimeConfig.validate()`: slope thresholds принимали NaN/Infinity и некоторые неверные типы, что могло позволить невалидную конфигурацию classifier. Добавлена проверка finite numeric thresholds и тесты для NaN, ±Infinity, bool и string. Commit с кодом: `65da09dce517a93d089bc88fc716707891eecd59`; тесты: `e9782d15ff4f5ab226d4c89d842a544ed4cddf6a`.
- Research CI run `45463921785` на HEAD `e9782d15ff4f5ab226d4c89d842a544ed4cddf6a` завершился SUCCESS: compile, causal market-regime tests, H-B 10/10 и остальные предусмотренные deterministic checks прошли.
- Следующий узкий шаг после CI: сделать pure adapter, который требует явный `RegimeConfig`, вызывает causal classifier и передает regime/ATR в H-B predicate; закрепить точные параметры конфигурации в тестах/выходной provenance. Не выбирать пороги по market data. Если нельзя обосновать конкретную конфигурацию без tuning — H-B остаётся design-blocked.


## 2026-11-24 — explicit classifier adapter verified

- В `h_b_signal.py` добавлен `evaluate_h_b_signal_with_classifier(candles, config, shock_index)`: требует явный `RegimeConfig`, валидирует его, передает в `classify_candles()` только prefix до t+1, затем передает causal regime/ATR в чистый H-B predicate. Default config не подставляется. Конфигурация целиком возвращается в signal provenance.
- Добавлены 3 synthetic tests: explicit config is required; signal carries exact config values; rows after t+1 не входят в classifier prefix и не меняют результат.
- Research CI run `45464213667` на commit `7d27224942a7082889d8e98f3155668d18a9c5bb` завершился SUCCESS. H-B test step: **13/13 OK**; causal market-regime classifier tests и остальные deterministic checks также прошли.
- Это закрывает связь signal predicate с causal classifier и явной конфигурацией на механическом уровне. Не доказывает, что значения RegimeConfig экономически обоснованы, и не проверяет fill, pending, sizing, exits, persistence или market edge.
- Следующий допустимый вопрос: нужен ли отдельный synthetic adapter contract для pending entry на open[t+2] и геометрии entry/stop/target, без включения в engine. Не использовать CryptoFetch PnL для выбора RegimeConfig.


## 2026-11-24 — H-B regime adapter и повторный CI

- Read-only audit подтвердил: `market_regime.classify_candles()` строит causal labels, но не проверяет cadence; функция допускает любые строго возрастающие timestamps. Для H-B это недостаточно, потому что classifier использует rolling windows и recursive EMA.
- Добавлен `h_b_regime.py`: явный frozen candidate `RegimeConfig` (значения унаследованы от существующих defaults, не подбирались на market PnL), требование непрерывной H1-сетки на всей истории до t+1, применение classifier и передача regime/ATR в pure H-B predicate. Данные после t+1 отсекаются.
- Исправлена валидация `RegimeConfig`: NaN/Inf, bool и нечисловые threshold values теперь fail closed. Это исправление конфигурационной целостности, не рыночная оптимизация.
- Research CI [45464653488](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45464653488) — SUCCESS на актуальном SHA `6540e375d6d2ad7dfd321202973e60e2e0815dae`. Логи: market-regime suite passed; H-B signal `Ran 13 tests / OK`; H-B regime adapter `Ran 6 tests / OK`; все остальные шаги завершились успешно.
- Вывод: **SIGNAL + REGIME MECHANICS PASS** на synthetic inputs. Frozen config — только исследовательский кандидат; он не оптимизирован и не подтверждён на рынке. Реальный t+2 fill, fill geometry, costs, engine lifecycle и edge не проверены.
- Следующий узкий шаг: отдельный pure next-open fill-geometry check; без engine integration, market PnL, data collection или Bybit.


## 2026-11-24 — H-B next-open entry contract verified

- Добавлен `prepare_h_b_entry()`: проверяет H-B long identity и policy version, точную связь `entry_ts_ms = signal_ts_ms + 1 H1`, наличие свечи t+2 с точным timestamp, свободный symbol и геометрию `entry > stop`, `target > entry`. Missing/gapped bar, occupied position и невалидная геометрия дают no-entry; невалидные числовые данные fail closed.
- Это reference open, не обещание реального fill: spread, queue, partial fills, slippage, fees и adverse selection не моделируются. Engine/pending/position state не менялись.
- Ужесточена проверка идентичности входного сигнала: принимается только H-B long и поддерживаемая policy version; сигнал с неверной временной связью отвергается.
- Research CI run `45465175545` на commit `83ebd2f644b9a1f26b2928135b3c5b0b82ac37fc` завершился SUCCESS. `tests/test_h_b_signal.py`: 21 test; `tests/test_h_b_regime.py`: 6 tests; оба workflow steps success, causal regime validation и остальные deterministic checks также прошли.
- Текущий H-B статус: synthetic signal/classifier/entry contract PASS. Это не market PnL, не edge, не execution validation. Следующий слой — только если полезен: synthetic exit/persistence invariants с заранее определённым контрактом. Не подключать engine и не запускать PnL.


## 2026-11-24 — H-B next-open geometry completed; stop before engine lifecycle

- Добавлен `h_b_fill.py`: pure offline check of actual t+2 H1 open against frozen absolute stop/target. It verifies exact timestamps and OHLC integrity; valid fill requires `stop < open[t+2] < target`. It reports per-unit geometry only.
- Added 8 deterministic synthetic tests: valid open, missing next bar, gaps at/beyond stop and target, timestamp mismatch, signal/candle mismatch, malformed OHLC and future-row isolation.
- Research CI [45465377742](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45465377742) — SUCCESS on commit `b72c15575170fc8f49691706d88a3599ed94b954`. Logs: H-B signal 19/19, regime adapter 6/6, next-open geometry 8/8; full technical workflow successful.
- This remains an OHLC next-open reference model, not an executable fill model: no spread, queue, slippage, fees, funding, partial fills or adverse selection. No sizing, persistence, position lifecycle or engine integration.
- **Decision:** H-B has passed the current narrow synthetic mechanics gates. Stop expanding it. The next meaningful proof is independent market validation with appropriate data/costs, but current provenance and user authorization gates do not permit that work. Do not build additional lifecycle infrastructure merely to keep coding.


## 2026-11-24 — экономическое ограничение H-B next-open geometry

- Синтетический accepted case в `tests/test_h_b_fill.py` имеет gross reward/risk = **0.4** (reward 2 на risk 5). Это намеренно показывает, что положительная геометрия `stop < fill < target` ещё не означает экономически приемлемую сделку.
- `h_b_fill.py` не задаёт минимальный R:R и не учитывает комиссии, spread, slippage, funding, fill probability или win rate. Не добавлять произвольный порог только ради «улучшения» тестового результата.
- До любого market validation потребуется заранее зафиксировать cost assumptions и критерии экономической приемлемости; их нельзя подбирать на уже использованных folds. Сейчас такой путь закрыт действующими data/provenance и research gates.
- Следовательно, **не переходить к engine lifecycle**. Текущий результат — механическая корректность трёх изолированных слоёв, не торговая готовность.


## 2026-11-24 — scope freeze after H-B mechanics

- Final bounded Research CI after removing the premature exit layer: run `45466778550`, commit `84d1da812d1958cbb32f3789895c7d4b56e45488`, SUCCESS (after removing the temporary exit module, tests and all workflow references). H-B signal tests (13), frozen regime adapter tests (6), next-open fill geometry tests (8) all passed; all other configured deterministic checks passed.
- A temporary standalone H-B exit evaluator was explored but deliberately removed before acceptance. It crossed the current scope boundary: H-B synthetic signal/regime/fill mechanics are enough to establish the next decision; more lifecycle code would not answer the missing economic question. No active `h_b_exit.py` or exit test remains.
- **Freeze decision:** do not add more H-B mechanics, engine integration, persistence, sizing, exit manager or new strategies. The synthetic package is complete for its narrow purpose. Current data and authorization gates do not allow market validation; adding code would create activity, not evidence.
- Resume only when an independent market-validation route is legitimately available under the existing user permissions and data/provenance gates. Until then, permitted work is read-only audits, provenance/coverage review, and documentation/decision hygiene only.
