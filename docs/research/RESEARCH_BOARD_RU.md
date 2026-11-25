# Research Board — текущее состояние лаборатории

> Последняя сверка: 2026-11-24. Рабочая ветка: `research/market-regime-v1-main`. Это короткая управленческая панель; детали, доказательства и исторические значения остаются в Experiment Ledger и первичных отчётах.

## 0. Цель компании и текущее ограничение

**Цель:** устойчивый чистый денежный результат на финансовых рынках при контролируемом риске. Лаборатория, бот, код и инфраструктура — средства.

**Метод управления:** Theory of Constraints — найти ограничение, использовать его, подчинить ему остальную работу, расширить и повторить. Любая задача должна снимать текущее ограничение или быть обязательным контролем качества/риска; активность и количество артефактов не являются результатом.

**Текущее ограничение:** ни одна гипотеза не соединяет сейчас полностью специфицированный trading lifecycle с независимым допустимым data/evidence path. H-B — только signal/entry mechanics; H1 baseline — lifecycle есть, но прежние folds уже использованы и net-PnL старых прогонов не годится для доказательства. Реальные Bybit archives и effective-time evidence также отсутствуют.

Ближайшая задача — найти один минимальный кандидат и действительно независимый период/данные. Узкий single-instrument scope может убрать cross-sectional universe requirement, но не отменяет lifecycle, D1/D3/D5 и применимые D2/D6/D8 gates. Детали: [Minimum Viable Edge Validation](MINIMUM_VIABLE_EDGE_VALIDATION_RU.md).

Канон: [Философия и операционная модель компании](../COMPANY_OPERATING_PHILOSOPHY_RU.md).

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
| Базовая H1 breakout / E01–E13 | **DEFERRED / NO EDGE** | Shared-capital proxy результаты не доказывают edge; E01–E04, E06–E11 и E13 использовали до исправления exit-fee/slippage engine, поэтому их net-PnL агрегаты не пригодны для корректного ранжирования; E12 — описательная диагностика без PnL; выборка не PIT Bybit | Не тюнить прежние folds и не пересчитывать их на запрещённом пакете. Возвращаться только при новом независимом основании и закрытых data/method gates |
| H-A relative-strength breakout | **REJECTED — tested configuration** | В preregistered proxy comparison хуже baseline и отрицательна по folds | Не подбирать параметры и символы на тех же folds |
| H-C post-break invalidation | **REJECTED AS PROFITABILITY CANDIDATE / MECHANICS ONLY** | Проверенная proxy-конфигурация не показала превосходства; реализация находится за default-OFF флагом; synthetic tests не доказывают edge | Не продолжать tuning на использованном окне |
| H-B mean reversion | **SYNTHETIC MECHANICS COMPLETE / FROZEN — NO EDGE EVIDENCE** | Signal 13 tests, frozen regime adapter 6, next-open geometry 8; final bounded Research CI #45466778550 SUCCESS; synthetic fixture gross R/R 0.4 | Не расширять H-B. Возвращаться только при появлении разрешённого независимого пути market validation; пока — read-only data/provenance audit |
| Новые стратегии/фильтры | **DEFERRED** | Доказанного edge нет; H-B mechanics завершена и заморожена без market evidence | Не расширять стратегический поиск, пока это не снимает текущее data/evidence bottleneck и нет допустимого независимого пути проверки |

Статусы REJECTED относятся к конкретным проверенным конфигурациям/окнам, а не к утверждению, что любой вариант семейства стратегий математически невозможен.

## 4. Данные: что реально есть

В рабочем дереве на момент аудита обнаружены шесть ZIP в `data/archives/cryptofetch/`. Аудит архива сообщает 67 CSV entries: 64 непустых/пригодных для legacy loader, три пустых; перекрывающиеся дубликаты прошли сравнение без обнаруженных конфликтов.

Это Binance-style OHLCV proxy. В репозитории нет подтверждённого Bybit-native пакета trade OHLCV + mark + funding + dated instrument/risk-tier snapshots и нет полного point-in-time universe. Наличие collector-кода и его mocked/offline tests не означает, что реальные архивы были получены.

Следствие: текущий data package не открывает путь к достоверному Bybit execution replay. Не маскировать этот пробел новыми расчётами на той же выборке.



**Сохранённые описательные данные (не edge):** read-only проверка артефактов E06/E11/E12 подтвердила, что можно сохранить raw signal-time OHLCV features и completed-bar market context отдельно от PnL. E12: 4,249 hourly rows, 47-symbol fixed universe; на unique selected-signal hours broad 72h breadth/return и ATR/dispersion ниже в fold 2, чем в folds 1/3. E06/E08–E11/E13 raw signal rows допустимы только для exploratory description после выбора canonical config и дедупликации; future-return columns — labels, engine fill/status/trade/PnL — исключить. Артефакты E08–E13 содержат raw candidate rows, рассчитанные до engine replay; их можно сохранить только как exploratory features, отдельно от будущих labels и engine-derived статусов. Повторяющиеся конфигурационные строки требуют canonical config и дедупликации. Это три уже просмотренных proxy folds, не независимое подтверждение и не основание для нового фильтра.

## 5. Ближайшая последовательность

1. **H-B заморожена.** Её узкая синтетическая цель выполнена; никакой engine lifecycle, sizing, persistence, exit manager или новые семейства стратегий не добавлять.
2. **Проверять только уже существующие данные и provenance.** В текущем Git tree — шесть CryptoFetch ZIP и никаких подтверждённых Bybit-native market archives. Read-only archive audit (run #41542079766, artifact #13187466159) проверил 67 CSV members: 67 структурно валидны, 64 имеют данные и проходят legacy 200-bar floor, три пусты; пропусков/нерегулярных интервалов и конфликтующих overlapping candles не обнаружено. Все шесть SHA-256 зафиксированы в артефакте.
3. **Сохранять ограничения как блокирующие.** Данные — Binance-style OHLCV proxy; отсутствуют подтверждённые Bybit trade OHLCV, mark-price, funding, dated specs/risk tiers и полноценный point-in-time tradable universe. Не запускать новые market-PnL backtests, sweeps или event studies на этом пакете.
4. **Поддерживать чистоту источников истины.** Синхронизировать верхние статусы Board/Compass с последними решениями; старые записи оставлять как историю, не удалять отрицательные результаты.
5. **Не создавать искусственный следующий этап.** Если read-only аудит не открывает разрешённого независимого пути проверки, фиксировать BLOCKED и не заменять отсутствие доказательств дополнительной инфраструктурой.
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


- Детальная запись H-B-SYNTHETIC-001 добавлена в `EXPERIMENT_LEDGER_RU.md`: точный сигнал, frozen regime candidate, состав тестов, итоговый CI, synthetic gross R/R 0.4 и ограничения. Это техническая mechanics record, не market experiment.

## 2026-11-24 — актуализация статуса и повторная сверка существующего data package

- Текущий research/market-regime-v1-main HEAD при сверке: 1e08da2cff4b07159b80664da79c70110b2f80ad. Последний принятый code/test CI — 45466778550 на 84d1da812d1958cbb32f3789895c7d4b56e45488; последующие commits в этой цепочке — документационные.
- PR #15 (PROJECT COMPASS) и PR #16 (H-B signal contract) merged в рабочую ветку. PR #13 закрыт как superseded by PR #15: его более ранний context-recovery protocol заменён обязательной связкой AGENTS.md + PROJECT_COMPASS_RU.md + RESEARCH_BOARD_RU.md.
- Git tree содержит ровно шесть файлов данных: CryptoFetch ZIP в data/archives/cryptofetch/. В текущем дереве нет подтверждённых Bybit-native OHLCV/mark/funding/spec/risk-tier snapshots.
- Сверен существующий архивный audit artifact #13187466159 из workflow #41542079766: 67/67 CSV members структурно валидны; 64 проходят legacy 200-bar floor; 3 пусты (DAIUSDT, MATICUSDT, XMRUSDT); 0 malformed; 0 irregular/missing intervals; 6 pairwise duplicate comparisons без конфликтующих OHLCV candles; longest-file winner не теряет timestamps в проверенных парах. Audit hashes совпали с E11/E13 source archives по исторической записи.
- Артефакт старый и проверяет целостность именно имеющихся Binance-style proxy archives; он не устраняет PIT universe, funding/mark, Bybit-native market, cost и execution gaps. Архивы не скачивались заново, новые данные не собирались, backtests/PnL не запускались.
- Решение не меняется: H-B synthetic mechanics complete/frozen; no demonstrated edge. Дальше разрешены только read-only provenance/coverage audits и документационная гигиена.


## 2026-11-24 — read-only аудит доказательной пригодности старых экспериментов

- **E01–E03:** ранние результаты требуют осторожности: верхнее предупреждение Ledger помечает PnL через v14 _close_position() до исправления exit fee/slippage как provisional до проверки конкретного engine commit. Положительные limit-варианты E03 нельзя считать edge: OHLC limit-touch не моделирует очередь, spread, partial fills и adverse selection.
- **E04 / E07:** положительные результаты не независимы. E04 использовал пять заранее отобранных символов, чувствителен к fold 3 и выбору chase-порога на исследованной истории. E07 перебрал 108 комбинаций на тех же трёх folds; выбор победителя подвержен multiple testing, а fold 3 дал около 68% суммы. Оба — exploratory, не доказательство.
- **E08 / E09:** E08 смешивал body filter и тип исполнения; его причинная интерпретация ограничена. E09 разделил body/gap факторы, но 2% gap gate не изменил ни одной сделки, а body-gate результат относится к пяти символам и той же proxy-истории. Limit fills остаются оптимистичными.
- **E10 / E11:** расширение body-gate на 47 символов не создало прибыльности. E10 — сумма независимых per-symbol счетов и остаётся глубоко отрицательным. Более важный shared-capital E11 также отрицателен: OFF −3,178.61 USDT, ON −2,774.00 USDT; улучшение всего +404.61 USDT, при этом fees+slippage выросли. Не трактовать фильтр как найденный edge.
- **E12 / E13:** E12 — описательная диагностика режимов, не доказательство предсказательной классификации. E13 воспроизвёл baseline E11 и дал небольшое улучшение, но итог ON остаётся −2,741.72 USDT; fold 2 остаётся существенно отрицательным, прибыль fold 3 сокращается. Три folds уже исследованы; blind holdout отсутствует.
- **H-A / H-C:** проверенные конфигурации отрицательны после моделируемых costs и хуже/не лучше baseline. H-A: −6,135.26 USDT против −5,635.98; H-C: −2,880.12 против −2,720.47 до funding. Оба используют CryptoFetch/Binance-style proxy, без funding; это отказ от конкретных конфигураций, не доказательство невозможности всего семейства.
- **E14, holdout и walk-forward:** post-break attribution — post-hoc ассоциация, не контрфактический PnL. Старый HOLDOUT_REPORT прямо указывает на пересечение с ранее исследованным периодом; walk-forward screen имеет малые holdout trade counts (около 14–16 на прошедших символах). Эти отчёты не дают независимого подтверждения edge.
- **ENG-EXEC-037–040:** статические аудиты честно фиксируют, что passive replay не моделирует price-through/cancellation allocation, cross-stream ordering остаётся неоднозначным, исторический trade CSV seq не подтверждён, а L2 reductions не используются для потребления очереди. Следовательно, L2 queue replay — ограниченный диагностический механизм, не доказанная модель maker fills.
- **Общий вывод:** старые результаты полезны для отсева проверенных конфигураций и формулирования ограничений. Ни один из них не образует надёжного положительного доказательства после реалистичных издержек и независимой проверки. Новые PnL runs, sweeps и event studies не запускались; запреты на Bybit, runner, collectors, новые архивы и paper/live остаются без изменений.


**Граница E01–E13 закрыта на уровне артефактов:** E01–E03/E07 содержат только агрегированные таблицы, не raw signal records; E04 содержит candidate-level signal CSV с признаками до симуляции; E06/E08–E11/E13 — аналогичные signal CSV; E12 — descriptive-only hourly context; E05 — неудачная загрузка данных. Сохраняются только raw signal-time features/context как exploratory data после canonicalization/deduplication. Все engine-derived fills/status/trades/PnL исключены из экономических доказательств. Статус стратегии остаётся DEFERRED / NO EDGE.


**Ключевая поправка к объёму доказательств:** E04/E06/E08/E09 — один и тот же набор 1,012 уникальных кандидатов по пяти выбранным монетам, повторённый в разных конфигурациях; E11/E13 — один и тот же набор 9,236 кандидатов по 47 монетам; E10 почти полностью совпадает с ним (9,236 общих ключей + 79 из-за временного покрытия). E12 агрегирует timestamp'ы E11, а не независимую выборку. Число строк CSV и число experiment ID нельзя трактовать как число независимых подтверждений.




## 2026-11-24 — read-only inventory внешних источников данных

- Recursive Git tree текущего research branch содержит шесть market-data ZIP, все CryptoFetch proxy; Bybit-native OHLCV/Mark/Funding/trades/L2 и датированные instrument/risk/universe snapshots в репозитории не обнаружены.
- Старый AAVEUSDT L2 run #41814167058 повторно проверен по job metadata/logs: raw L2/trades archives были временно обработаны в workflow, но в artifact сохранены только три компактных JSON-отчёта (3,725 bytes). Raw source archives не лежат в Git tree. Trade CSV не содержит block-trade flag; четыре hypothetical orders не являются fill-rate evidence.
- Найдены только внешние discovery leads: Hugging Face `rogerdehe/klines-bybit` (заявленный OHLCV/Mark/Funding, но under construction) и CryptoHFTData (L2/trades/Mark/Funding, но документированные gaps/corrections и отсутствие OHLCV family). Ни один источник не принят и не скачивался.
- Подробная классификация и ссылки: [ALT-SYSTEM-DATA-ACCEPTANCE-001, раздел 11](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#11-read-only-inventory-and-external-source-screening-2026-11-24).
- Решение: **DATA GATE BLOCKED**; D1–D6 не закрыты. Запреты на Bybit, runner, collectors, новые архивы, PnL runs, paper/live остаются без изменений.




**Дополнительная проверка совместимости (2026-11-24):** текущий H1 shared-capital runner требует frozen selection manifest, датированные instrument/risk snapshots, funding audit manifest + settlement schedule, Mark и Bybit-native H1 trade-kline; proxy candles явно блокируются. Ветка не содержит адаптеров для Hugging Face Parquet или CryptoHFTData. Внешние discovery leads нельзя подключить переименованием файлов; потребуется отдельный reviewed adapter и прохождение прежних data gates. Код не менялся, тесты и рыночные прогоны не запускались.




**D4–D6 snapshot boundary audit (2026-11-24):** universe collector queries several lifecycle statuses including Closed and records launch/delivery timestamps, but produces point-in-time observations rather than a complete suspension/resumption history. Instrument-spec and risk-tier as-of loaders select only the newest dated snapshot at or before a timestamp and fail when none exists; they cannot reconstruct pre-first-snapshot effective-time changes. No dated snapshot series is committed. D4 remains partial/unverified; D5/D6 remain missing for the historical interval. Подробнее: [ALT-SYSTEM-DATA-ACCEPTANCE-001, раздел 13](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#13-static-boundary-audit-for-d4d6-what-dated-snapshots-can-and-cannot-prove).


### 2026-11-24 — D5/D6 official API boundary re-check

- `instruments-info` / `instrument-summary`: current online specifications only; no documented historical versions. Periodic max-order-size changes make backward carry unsafe.
- `risk-limit`: current symbol tier table only. Actual account tier is dynamic from positions, active orders and mark price; account-level liquidation replay also needs account-state history.
- Official archived-trade download link does not establish historical specification/risk archives.
- **Decision:** D5/D6 remain NOT ACCEPTED; D4 remains partial/unverified. No new archives, collectors, API calls, market PnL or backtests. See [ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md, section 38](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#38-official-market-api-and-risk-limit-documentation-historical-data-boundary).


### 2026-11-24 — Official Bybit documentation Git history

- `bybit-exchange/docs` provides versioned instrument/risk-limit API documentation from 2022-12-05 onward. Instrument schema history is extensive; risk-limit history contains 34 commits.
- Recoverable: documented field/filter/response changes, pagination changes, and some published rule-change references.
- Not recoverable from this repository: complete effective-dated per-symbol numeric instrument specs or full historical risk-tier tables. Timestamped examples are partial illustrative payloads, not accepted snapshots.
- **Decision unchanged:** D5/D6 NOT ACCEPTED. Documentation history improves schema chronology only. Full evidence: [ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md, section 39](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#39-bybit-official-documentation-git-history-schema-chronology-recovered-historical-values-not-recovered).


### 2026-11-24 — external metadata snapshots found (status correction)

- **D5:** partial candidate snapshots: 9-symbol Spot+Linear fixture (2026-09-29) plus a raw BTCUSDT Linear instrument response (2026-10-21), exact BTC overlap; official BNBUSDT tick change cross-check.
- **D6:** partial candidate snapshots: 9-symbol risk-tier fixture (2026-09-29), raw BTC/ETH/SOL/XRP tier tables (2026-10-21), and a manually pasted/hand-checked BTC tier table dated 2026-10-15. All 35 tiers match exactly across the two projects for BTC/ETH/SOL/XRP; the Oct 15 BTC file is corroboration, not a direct recorder capture.
- These are external, third-party snapshots, not a full time series or full-market PIT archive. Capture provenance and universe coverage still need formal acceptance; the Oct 15 BTC file has manual-paste provenance; account-specific applied tiers are absent.
- **Updated decision:** D5 and D6 = PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED. D4 remains partial/unverified. Do not import these snapshots or start PnL/backtests without completing provenance review and the existing authorization gates.
- Details: [ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md, section 40](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#40-third-party-dated-bybit-metadata-snapshots-partial-raw-captures-and-cross-source-replication).


### 2026-11-24 — exact 47-symbol coverage measured

- Historical E11 and E13 Actions logs independently print the same 47 fold-eligible symbols (50 valid H1 symbols, 4,321 common bars). This is the Binance-style proxy archive universe, not a Bybit point-in-time universe.
- Sep 29 Linear fixture overlaps 9/47 (19.1%) for both instrument specs and risk tiers: ADA, AVAX, BNB, BTC, DOGE, ETH, LINK, SOL, XRP. Its nine Spot rows do not count toward Linear coverage.
- Oct 21 raw capture coverage: instrument specs 1/47 (2.1%), risk tiers 4/47 (8.5%).
- The 38 uncovered symbols and full interpretation are in acceptance ledger Section 41.
- D5/D6 remain PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED; D4 remains partial/unverified. Subsequent read-only download of existing E11/E13 result artifacts confirmed identical 50-row manifests, 47 included symbols, same three exclusions and identical six source-archive hashes. No market archive, collector, Bybit API request or PnL replay was performed.


### 2026-11-24 — sbt2 source lead (not yet an archive)

- Public `sbOogway/sbt2` adapter writes daily dated instrument snapshots when run, but its `/data/` outputs are git-ignored and no raw Bybit archive is present in the public tree. Snapshot stores only lowest risk tier; full D6 table is not preserved there.
- D5 potential lead only if local snapshots can be obtained with provenance; D6 insufficient as implemented. D4 partial; D5/D6 remain not accepted. No API, collectors, market data or PnL runs.
- Evidence: acceptance ledger Section 43.


### 2026-11-24 — CandleViewer Oct 25 raw risk-tier capture

- Third independent repository found: CandleViewer preserves full public Bybit REST envelopes for BTCUSDT and ETHUSDT Linear risk tiers on 2026-10-25, 35 tiers each.
- All 35 rows/fields for BTC and ETH match the Oct 21 sleeve-fund raw responses exactly and the Sep 29 crypto-dashboard fixture. This improves date/source replication for BTC/ETH but adds no new symbol breadth.
- D6 unique raw-replicated symbols remain BTC/ETH/SOL/XRP = 4/47 (8.5%); D6 remains PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED.
- CandleViewer instrument-before/after examples are generated documented-shape fixtures, not D5 live captures. D5 unchanged. Details in acceptance ledger Section 44.


### 2026-11-24 — TOC company philosophy adopted

- Пользователь утвердил цель компании: устойчивый чистый денежный результат на финансовых рынках при контролируемом риске. Принят цикл Theory of Constraints; канонический документ: [COMPANY_OPERATING_PHILOSOPHY_RU.md](../COMPANY_OPERATING_PHILOSOPHY_RU.md).
- Текущее ограничение остаётся: нет принятой доказательной базы для подтверждения/опровержения реализуемого edge на условиях Bybit. Любая задача должна снимать это ограничение или быть обязательным контролем качества/риска.
- Уточнены статусы D5 leads: Hassnain metadata не считается независимым raw snapshot; найденный 2026-10-18 capture относится к Spot и не расширяет Linear universe. D5/D6 остаются не приняты. Подробности — acceptance ledger Section 45.


### 2026-11-24 — Minimum viable validation path and funding regime update

- Добавлен [MINIMUM_VIABLE_EDGE_VALIDATION_RU.md](MINIMUM_VIABLE_EDGE_VALIDATION_RU.md): single-instrument scope, обязательные/условные data gates, conservative taker-only execution boundaries и независимость выборки. Это design only, не разрешение на сбор данных или market PnL.
- Новое подтверждённое ограничение: H-B не имеет полного lifecycle; H1 baseline имеет полный кодовый путь, но нет независимого неиспользованного периода и валидного net-PnL доказательства. Сейчас нет кандидата, готового к честной независимой проверке.
- Bybit объявил поэтапное изменение формулы funding с 2026-11-24 по 2026-12-01. В D3 нужно хранить formula regime отдельно от settlement rate и funding interval; конкретные effective dates символов пока не подтверждены. Подробности: acceptance ledger Section 46.

- Статический review текущего H1 runner подтвердил, что он не поддерживает single-symbol pilot простой конфигурацией: требует exact Top-5 selection manifest, lifecycle universe snapshot, все source directories и выполняет заранее заданный multi-arm/fold/cost loop. Новый runner не создавать, пока не выбран допустимый независимый эксперимент и не доказана необходимость такой переделки.

### Candidate readiness decision — 2026-11-24

- Ближайший существующий кандидат — H1 Donchian(48)+EMA50/200: сигнал и lifecycle есть, H-B существенно менее готова.
- Но текущий runner принудительно использует maker limit OHLC penetration (20 bps offset / 5 bps penetration / 3-bar TTL); это не доказанный maker fill. Base engine умеет market entry на next H1 open с taker accounting, но runner этот путь переопределяет.
- Наиболее дешёвый потенциальный путь — отдельная preregistered taker-only single-symbol execution profile поверх существующего H1 engine. Это новая версия execution contract, не прежний maker candidate. D1/D3/D4/D5/D8 остаются обязательны; при 5x isolated также D2/D6.
- **Решение: пока не писать runner и не запускать PnL.** Сначала доказать наличие независимого периода и accepted Bybit-native inputs для одного инструмента. Подробный read-only review — раздел 2A [Minimum Viable Edge Validation](MINIMUM_VIABLE_EDGE_VALIDATION_RU.md).

- Veldra read-only review завершён: adapter покрывает D1/D2/D3 retrieval, но не даёт D4/D5/D6 и не улучшает покрытие относительно уже имеющихся `bybit_downloader.py`, `archive_bybit_market_history.py` и funding manifests; к тому же требует Python >=3.14 против Python 3.11 в нашем CI. Решение: не внедрять и не портировать. Узкое место — реальные принятые исторические данные/разрешение на их сбор, а не downloader tooling. См. acceptance ledger Section 47.


### 2026-11-25 — BTCUSDT public GET pilot blocked by environment

- Пользователь разрешил ограниченный read-only pilot пяти публичных Bybit V5 GET endpoints для BTCUSDT. Все адресные попытки завершились недоступностью URL в web retrieval; instruments-info вернул 403 на стороне retrieval layer. Прямой HTTPS из container среды не прошёл DNS resolution. Нет валидных ответов Bybit, поэтому API reachability и все data gates остаются NOT VERIFIED/NOT ACCEPTED. Никакого обхода через прокси, архивной загрузки или PnL не выполнялось. Подробности: acceptance ledger Section 48.


### 2026-11-25 — independent holdout availability re-audited

- В репозитории нет независимого набора для замороженной H1 Donchian(48)+EMA50/200: CryptoFetch proxy заканчивается 2026-10-27 и уже использован в E01–E13/последующей разработке.
- Старый run_bybit_h1_long_only_holdout.py не подходит: Donchian(20), 11 символов отобраны на Binance train, отдельный капитал на символ, funding upper-bound, Last-price exits и явное пересечение календарного периода с прежним Binance study. Bybit data files, которых он требует, в repo отсутствуют.
- Существующий Bybit archive workflow требует self-hosted по умолчанию и предупреждает о блокировке hosted US egress. Self-hosted/collector запрещены; workflow не запускать и не менять.
- Статус: **BLOCKED BY DATA + INDEPENDENCE**. Ни старые folds, ни другой venue на том же календарном периоде не создают независимый holdout. Подробности: acceptance ledger Section 49 и Minimum Viable Validation Section 6A.

## 2026-11-25 — read-only review of Bybit announcement archive artifact

- Reviewed the already-completed separate-branch workflow [#45603180553](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45603180553) and its downloaded ZIP artifact. This review did not trigger a collector, API request, new archive, or market test.
- Artifact manifest: 66 category pages (11 delistings, 11 latest news, 19 maintenance, 25 new-crypto); 1,280 unique article records, all HTTP 200, all 1,280 body files present/non-empty and matching recorded byte counts + SHA-256. No collection or body-validation failures. Correct the earlier 1,275 figure to 1,280.
- Existing offline lifecycle output: 497 candidate symbol-events across 488 symbols (386 listing rows, 111 delisting rows); 110/111 delistings have explicit effective times; 304 listing rows confirm trading was open by publication time, not the exact start. The 47-symbol research proxy has zero matches in these 2026 listing/delisting candidates.
- **Decision: D4 remains PARTIAL / NOT ACCEPTED.** The artifact does not establish the starting tradable universe on 2026-01-01, continuous tradability, full crypto-only product classification, or all status changes. `historical_universe_complete=false` and `scope_review_required=true` are explicit in the extractor output. The 488 symbols must not be treated as an accepted universe.
- This is announcement/lifecycle evidence only, not Bybit-native market data. It does not supply trade OHLCV, Mark OHLC, complete funding settlements, or a new independent holdout. D1/D2/D3 and independence remain blocking; no market-PnL replay, tuning, or new collection is authorized by this result.
- The archive workflow and extractor live on `research/bybit-raw-response-evidence-v1`, not the active `research/market-regime-v1-main` branch. Do not merge that branch or expand collection merely because this artifact exists; preserve the active read-only / documentation-only operating mode.

## 2026-11-25 — external Bybit archive lead found; not yet accepted

- Read-only public-documentation review identified CryptoHFTData's independent Bybit Futures archive as a candidate source: hourly Parquet files since 2025-06-28, with tick trades, mark-price/funding stream, open interest and other datasets. Provider states access is free. No account/API call, sample download, data import or market test was performed.
- Source documentation: [Bybit archive overview](https://www.cryptohftdata.com/exchanges/bybit), [tick trades](https://www.cryptohftdata.com/datasets/bybit-trades-data), [mark/funding](https://www.cryptohftdata.com/datasets/bybit-funding-rate-data), [known gaps/corrections](https://www.cryptohftdata.com/docs/data-gaps-and-corrections), [pricing/licence](https://www.cryptohftdata.com/pricing).
- Candidate strengths: public Bybit execution-level trades can be aggregated into OHLCV; mark-price stream and open-interest files are available; archive begins before the previously used CryptoFetch data ends and may contain a later period. It is an independent third-party archive, not an official Bybit export.
- Blocking caveats from the provider's own documentation: Bybit trade reconnect gaps of seconds to about 3 minutes remain, with public-archive backfill listed as planned; missing full-hour ranges are listed; pre-September-2026 Bybit mark/ticker/OI rows are change-only deltas requiring careful forward-fill; funding is carried as a field in the mark-price stream and is not documented here as a complete settled-funding ledger. The provider also reports that the 2026-10 data-quality release is not yet deployed on its gaps page. No assumption of completeness is permitted.
- The archive does not provide effective-dated Bybit instrument specifications/risk tiers. It therefore does not close D4/D5/D6; D3 remains unaccepted until settlement-rate completeness and timestamps are proven. D1/D2 are candidate-only pending permitted sample-level integrity and coverage checks.
- **Decision: candidate lead only / NOT ACCEPTED.** Do not download/import data or run market PnL under the current no-new-archives restriction. If a data-access permission is later granted, first validate a single-symbol, bounded interval against exchange-origin evidence and quantify all gaps before considering any replay. The project remains **BLOCKED BY DATA + INDEPENDENCE**.
## 2026-11-25 — CryptoHFTData Bybit archive deeper documentation audit

- Read-only review of the provider's Bybit hub, REST/Parquet layout, trade, mark-price, OI and known-gaps documentation. No API calls, sample downloads, SDK installs, data imports, or market tests were performed. This preserves the current no-new-archives restriction.
- Coverage is explicitly Bybit linear derivatives (bybit), not inverse. Data families include trades, order book, ticker, mark_price (including current funding_rate and next_funding_time), open_interest and liquidations. Files are one symbol × one UTC hour, Parquet/Zstd. received_time is nanoseconds; event_time/trade_time are exchange timestamps whose unit must be interpreted per venue schema. Trade records expose trade_id, price, quantity, trade_time, and is_buyer_maker.
- Critical freshness caveat: provider's Known Gaps page says its 2026-10 data-quality release is NOT YET DEPLOYED. Therefore the documented future full-state behaviour must not be assumed present in files currently served. Before the release, Bybit ticker/mark/OI are change-only deltas with null unchanged fields; OI files exist only in hours with OI changes; per-symbol forward-fill must look back into earlier hours. Even after release, the first hour after collector state loss may contain only fields received in that hour.
- Explicit full-hour Bybit archive gaps: 2025-11-26 10 through 2025-12-26 19 UTC, and 2026-04-13 15 through 2026-04-14 21 UTC. Additional trade reconnect gaps of seconds to about 3 minutes are reported, mainly near 02:00–02:50 UTC daily. Backfill from Bybit public trade archives remains Planned, not published. Thus trade-derived OHLCV cannot be assumed complete.
- Mark/funding schema carries the current funding rate (fraction per funding period) and next_funding_time, not a separately documented ledger of settled historical funding payments. Treat this as a rate-observation stream, not proof of settlement completeness. Funding timestamps and rate changes must be causally aligned; never join using a future settlement timestamp as if it were the observation time.
- Bybit OI comes from WebSocket ticker/OI channels, not provider REST pollers. Older delta semantics and a documented issue with certain REST OI rows make OI a secondary/conditional input, not a required first pilot input.
- The provider's displayed coverage count is dynamic and differs by dataset page (e.g. funding page shows 1,592 at review time); it is not an immutable historical universe and cannot satisfy D4. Liquidation feed is not a complete ledger; no use as ground-truth fills.
- Decision: still CANDIDATE ONLY / NOT ACCEPTED. The source may be useful for a bounded, single-symbol research-data pilot only after explicit permission for sample acquisition and only with a predeclared interval outside previously used data. Current no-new-archives / read-only boundary remains in force. No PnL replay, tuning, or strategy conclusions. D1/D2/D3/D4 and independent holdout remain open.

### 2026-11-25 — CryptoHFTData Bybit wire semantics and funding boundary

- Read-only audit of the provider's detailed Bybit Futures wire-format examples and official Bybit V5 market documentation. No downloads, API calls, imports, SDK installs or market tests.
- The provider's Bybit linear collector maps ticker topic messages into mark-price rows. event_time is the exchange message timestamp (ts, milliseconds); received_time is the collector receive clock (nanoseconds). Rows are emitted when mark/index/funding fields are present or changed; unchanged fields are merged from prior state. The raw Bybit message contains fundingIntervalHour, but the normalized mark-price output does not preserve that interval or the funding cap. The interval can differ by contract.
- Therefore funding_rate is an observed current rate (fraction per funding period) carried in a ticker state, with next_funding_time; it is not itself proof of a settled payment. Official Bybit V5 funding history returns historical fundingRate with fundingRateTimestamp and is the appropriate exchange-origin reference for settlement-rate validation. Any funding cashflow replay must join on the actual settlement timestamp, preserve each symbol's interval/regime, and independently verify that the provider stream has no missing settlement observations. Do not treat every hourly mark-price row as a new funding payment.
- Important provider documentation conflict remains unresolved: the Bybit wire-format page describes merged full-state rows and shows parser replay checks recorded 2026-10-05, while the Known Gaps page says the 2026-10 data-quality release is "Not yet deployed" and says older Bybit ticker/mark/OI files have change-only deltas. Until the provider identifies the exact first deployed/corrected hour for Bybit, the release boundary and actual file semantics are NOT VERIFIED. Conservative handling must assume legacy delta/null behaviour for any uncertain period.
- Trade caveat sharpened: the provider says it backfills reconnect gaps from Bybit REST recent-trade, but that endpoint returns at most the latest 1,000 trades; on a busy symbol this recovers only part of a long disconnect. Its own known-gaps page still lists public trade archive backfill as Planned. Thus trade aggregation into OHLCV is not proven complete, even if a given hourly file exists and rows are well-formed.
- Order-book collector does document update-ID continuity checks and reconnects after a sequence gap, but only publishes the 50-level WebSocket book; REST 1,000-level snapshots cannot seed that stream. This is potentially useful later for microstructure research, not a requirement for the first H1 pilot.
- **Decision unchanged, with stricter D3 rule:** CryptoHFTData remains CANDIDATE ONLY / NOT ACCEPTED. D3 cannot be accepted from the mark-price stream alone; a bounded sample (only after explicit data-access permission) must compare provider rate observations to official funding history and quantify missing/duplicate settlements and effective interval. D1 trade completeness is also not accepted; OHLCV derived from trades needs gap measurement or exchange candle cross-check. Current no-new-archives/read-only boundary remains in force; no PnL replay, tuning or strategy conclusion.
- Sources reviewed: provider Bybit Futures wire format, Bybit funding dataset/schema, known gaps and deployment status, official Bybit funding history and mark-price kline.

### 2026-11-25 — correction: distinguish September and October provider releases

- Corrected an overbroad interpretation in the preceding CryptoHFTData audit. The provider documents Bybit ticker/mark_price/open_interest delta-to-full-state merging as part of the 2026-09 data-integrity release, not the 2026-10 data-quality release. The October release is separately marked "Not yet deployed" and its Bybit-specific listed changes concern order-book REST snapshot resets and an open-interest hour-boundary timing issue.
- Therefore it is not correct to say that Bybit mark-price full-state merging is necessarily still undeployed merely because the October release is pending. The wire-format page documents the merged-state parser behaviour and says files before the September release retain delta/null semantics. The exact first corrected Bybit hour is not identified in the reviewed public pages; the release boundary for any specific historical file still requires verification.
- Mark-price funding fields remain insufficient as a settled-funding ledger: funding_rate is the current rate per funding interval, next_funding_time is the next payment time, while fundingIntervalHour and fundingCap from the raw ticker are not preserved in the normalized output. The provider explicitly says intervals vary by contract.
- Trade completeness remains unaccepted: the wire-format page confirms REST recovery is limited to the latest 1,000 trades, and the known-gaps page still lists Bybit public-archive trade backfill as Planned.
- **Decision:** provider candidate remains NOT ACCEPTED, but for narrower, accurately stated reasons: (1) exact September release boundary/file-level state semantics not proven; (2) trade reconnect gaps and planned backfill; (3) no settled funding ledger / lost interval metadata; (4) no effective-dated specs/risk tiers or accepted PIT universe; (5) no permitted sample-level integrity validation or independent holdout. October deployment status is a separate caveat, not evidence that the September full-state change is absent.
- No downloads, API calls, imports, SDK installs, tests, PnL or strategy tuning. Read-only correction only. Sources: CryptoHFTData Bybit Futures wire format, Bybit funding dataset, and Known Gaps & Corrections.

### 2026-11-25 — repository inventory check for CryptoHFTData release evidence

- Re-read acceptance ledger Section 11.3 and the current provider Known Gaps, Bybit overview, REST ticker semantics and Bybit wire-format pages. The September release description is consistent: before release, Bybit ticker/mark/OI are change-only deltas; from the release, the provider says it publishes full carried-forward state. The provider states its current parser examples were checked against production on 2026-10-05, but does not publish an exact first Bybit hour/object key for the September transition.
- Searched the active branch's existing data tree. data/archives contains only the six already-audited CryptoFetch ZIP archives; there is no CryptoHFTData Parquet sample or local provider manifest. Therefore the repository cannot establish which release semantics apply to any actual CryptoHFTData hour, nor independently infer the exact deployment boundary from a stored file.
- Important nuance from the wire-format page: even after the September release, a collector state loss or missing prior-hour ticker state can leave the first affected hour with only fields received in that hour. Full-state carry-forward is therefore conditional on collector state continuity; it is not a blanket guarantee that every file has every field.
- **Decision:** no new evidence upgrades CryptoHFTData. Release semantics are now understood at documentation level, but file-level deployment boundary and per-hour state completeness remain unverified. Do not infer the release date from the 2026-10-05 parser-check date. Candidate remains NOT ACCEPTED; no download, API, import, test, PnL or tuning. Continue read-only work only.
- Sources: [CryptoHFTData Known Gaps & Corrections](https://www.cryptohftdata.com/docs/data-gaps-and-corrections), [Bybit archive overview](https://www.cryptohftdata.com/exchanges/bybit), [REST ticker semantics](https://www.cryptohftdata.com/docs/rest-ticker), [Bybit Futures wire format](https://www.cryptohftdata.com/docs/wire-format-bybit).

### 2026-11-25 — read-only audit of the existing Bybit funding/mark replay contract

- Inspected the existing archive_bybit_market_history.py, funding_archive_manifest.py, validate_funding_coverage.py, H1 portfolio runner, funding_accounting.py and mark_price_liquidation.py. The project already has a meaningful fail-closed D3 pipeline: official V5 funding-history pagination; page/query provenance; CSV SHA-256 and row-count checks; dated instrument snapshots; a reconstructed expected settlement grid; exact comparison of actual funding timestamps with that grid; duplicate-event rejection; and timestamp-aligned mark candles. The H1 runner refuses to treat missing funding as zero and requires mark candles across the scored fold. Do not duplicate this machinery or build another collector.
- This is not yet proof of complete historical D3. The settlement grid is inferred from dated instruments-info snapshots. The manifest explicitly acknowledges that point-in-time snapshots cannot rule out an unobserved funding-interval change and reversion between snapshots. A stable interval observed at the two ends is therefore evidence of observed stability, not proof that no intermediate change occurred.
- A second independent limitation is in the accounting price input: funding_accounting.py explicitly uses the open of the mark-price candle at the settlement timestamp as a proxy, not the exchange's actual settlement mark. Thus rate/timestamp completeness and settlement-notional price fidelity are separate questions. The hourly candle proxy is suitable only as a documented approximation until reconciled against exchange-origin settlement marks or a sufficiently precise independent mark stream.
- Liquidation modelling is also intentionally bounded: mark_price_liquidation.py is single-position isolated-margin estimation, not account-level cross/portfolio margin; the candle crossing helper detects only a fixed liquidation-price crossing and does not resolve dynamic tier upgrades or intrabar ordering against trade-price stops. This is not a newly discovered bug—the module documents these limits—but it prevents claiming exchange-exact liquidation replay.
- **Decision:** retain the current architecture; no code change is justified from this audit. D3 remains NOT ACCEPTED for exact historical cashflow proof, and liquidation output must remain labelled an estimate. Future acceptance requires (a) stronger effective-time funding-interval evidence, (b) validation of settlement mark-price input rather than silently promoting H1 candle-open proxy to exact, and (c) explicit scope for isolated versus account-level margin. No API calls, downloads, tests, PnL or tuning were run.

### 2026-11-25 — read-only audit of H1 execution, costs and same-bar exit ordering

- The H1 runner is explicit about its execution contract: signal on a completed H1 candle, entry only on a later candle; limit entry quote is offset by 20 bps, requires 5 bps OHLC penetration, and expires after 3 eligible bars. The quote is rounded to the dated Bybit tick. A limit marketable at the open is treated as taker; a later intrabar touch is modelled as maker. The runner itself warns that OHLC penetration does not model queue priority, spread, partial fills or adverse selection. This is a conditional optimistic fill proxy, not an exchange fill model.
- TP1/TP2 exits are also inferred from OHLC touches. When the stop and a target are both touched in one candle, the engine gives priority to liquidation/kill-switch/stop before discretionary targets, which is a conservative rule. A candle reaching TP2 before TP1 is handled by booking TP1 first and TP2 on the remainder. Fees/slippage are charged by leg; fixed base assumptions are 5.5 bps taker, 2 bps maker and 2.25 bps taker slippage per taker leg, with 1.0x/1.5x/2.0x stress scenarios. The runner explicitly lacks historical bid/ask, L2 queue, partial-fill adverse selection and account-specific fee tier.
- **New material ambiguity found:** after TP1 is touched on a candle, the engine updates the favorable extreme and moves the trailing stop using that candle's high/low context, but does not test the newly moved stop against the same candle's opposite extreme. If the candle first reaches TP1 and subsequently reverses through the newly calculated trail, the current replay carries the position to the next candle. OHLC cannot establish whether the TP1 touch preceded the reversal. This is an optimistic intrabar-order assumption, unlike the existing conservative stop-vs-target precedence. It can inflate results in fast reversal candles and must be resolved before treating H1 PnL as validated.
- No immediate code patch: changing the order rule without a frozen specification could silently change the strategy. Before any future PnL run, define a conservative rule (e.g. if TP1 and the post-TP1 trail are both touched in one candle, assume the trail was hit after TP1 and exit at the modelled trail price; or resolve with lower-timeframe/tick data). Apply the same rule across all arms and record it in the manifest. Then test the rule with focused synthetic cases before any market replay.
- **Decision:** execution model remains NOT ACCEPTED as exchange-realistic. Existing caveats are explicit and useful, but the TP1-to-new-trail same-bar ambiguity is an additional material research limitation. No engine changes, API calls, downloads, tests, PnL or tuning were performed.
### 2026-11-25 — follow-up: exchange order caps on simulated exits

- Rechecked the H1 configuration and order-spec enforcement. Entries are configured as passive limit orders (maker_entry_and_tp1=True), while maker_tp1_and_target=False makes TP1 and final target exits taker in the current H1 runner; stop, time-stop and forced exits are also charged as taker legs.
- bybit_instrument_specs.InstrumentSpec.validate_order() correctly distinguishes maxOrderQty for limit orders from maxMktOrderQty for market orders. Entry sizing passes its actual order type through size_to_exchange_constraints(), so the entry-side cap is enforced.
- **Conditional exchange-validity gap:** _close_position() validates that a remaining close quantity is positive, aligned to qtyStep, and above minOrderQty / minNotionalValue, but it does not validate the market-exit quantity against the dated maxMktOrderQty. The position state also does not retain that cap. Therefore, for any instrument/date where an allowed limit-entry quantity exceeds the market-order cap, the simulator can report a full taker exit that could not be submitted as one market order under the archived instrument constraints. This is not proven to occur in the current H1 symbol/fold set because no accepted instrument snapshots/data were replayed in this audit.
- This is a model-validity gap, not evidence that current PnL is wrong by a known amount. Before claiming exchange-valid exits, either cap initial position quantity to the applicable market-close cap or model deterministic reduce-only slicing with the relevant exchange constraints and execution costs; preserve the dated cap in the trade/validation manifest. Do not silently assume one market order can close every limit-sized position.
- Liquidation remains explicitly position-level isolated approximation: it checks Mark OHLC adverse extremes and current risk-tier maintenance margin, but omits Bybit's partial-liquidation ladder, account/order tier aggregation, AMR, exchange rounding and account-level cross/portfolio margin. It is not suitable for claiming exact account liquidation behavior.
- **Decision:** no code change; no tests, market replay, API calls or PnL. The sizing path is structurally conservative after quantity flooring, but taker close-cap enforcement is not yet demonstrated. Execution model remains NOT ACCEPTED as exchange-realistic.
### 2026-11-25 — read-only audit: shared equity, portfolio drawdown and kill-switch marks

- The synchronized replay correctly batches all symbols at a common candle timestamp. It precomputes portfolio marks, defers per-symbol close risk evaluation, reconciles equity after all same-timestamp executions, and only then evaluates the portfolio kill-switch. This avoids artificial transient peaks/drawdowns caused by symbol iteration order. Closed-trade PnL is moved into realized equity while remaining positions are re-marked, avoiding a direct double-count of the closed position.
- **Material drawdown measurement limitation:** `_prepare_portfolio_intrabar_marks()` deliberately selects adverse intrabar marks for open positions (Last-price stop-aware adverse trade mark and adverse Mark OHLC extreme for liquidation/MTM). `_update_mark_to_market()` feeds these adverse marks into `AdaptiveRiskManager.mark_to_market()`, which is the only path updating `peak_equity` and `max_drawdown_pct`. The replay therefore does not observe favorable intrabar portfolio equity peaks. A portfolio can rise materially during the candle and then reverse to the adverse extreme, but the high-water mark is never raised to the unseen favorable peak. Reported peak-to-trough drawdown and the emergency kill-switch trigger can consequently be understated or delayed. This is distinct from the existing conservative adverse-trough marking: conservative troughs do not compensate for missing favorable peaks.
- This finding does not mean every drawdown result is wrong by a known amount; OHLC alone cannot establish cross-symbol intrabar ordering or simultaneous favorable portfolio extremes. Before using max drawdown or kill-switch outcomes as validated, define a consistent portfolio peak/trough convention. Options include a clearly labelled close-to-close equity metric (with separately reported adverse intrabar stress) or a bounded intrabar high-water estimate with explicit simultaneity assumptions; lower-timeframe/tick portfolio marks are preferable if available. Do not mix per-symbol favorable extremes as if they occurred simultaneously without labelling that as a stress bound.
- Daily stop behavior is intentionally different from emergency kill-switch behavior: daily stop blocks new entries while existing positions continue under their position rules; emergency kill-switch triggers a same-timestamp batch flatten. Keep this distinction explicit in reporting.
- **Decision:** synchronized batch accounting is structurally sound on the inspected path, but max drawdown / kill-switch peak tracking is NOT ACCEPTED as complete intrabar portfolio risk measurement. No engine changes, tests, API calls, downloads, market replay, PnL or tuning were performed.

### 2026-11-25 — read-only audit: H1 result metrics and acceptance boundary

- Inspected the H1 runner's result-row construction, paired-comparison summaries, validation manifest and the engine's MaintenanceGateAuditor. The runner records per-fold net PnL, return, profit factor, expectancy in R, max drawdown, costs and funding costs, and the manifest preserves the folds, selected universe, code/data hashes and frozen design. The paired comparison checks that arms share the same fold/configuration and portfolio invariants. This is useful reproducibility and comparison infrastructure.
- **Important boundary:** the H1 runner writes the metric rows and paired deltas; it does not itself make a formal strategy-acceptance decision. There is no final accepted/rejected verdict or frozen minimum sample / per-fold robustness / drawdown / cost criterion in the output path inspected. A positive row, a positive paired delta, or a favourable monthly-equivalent return must not be interpreted as acceptance. The geometric monthly return is explicitly a normalized rate, not proof that every month was profitable.
- The general MaintenanceGateAuditor has a separate six-check all_ok flag, but cost_ok is explicitly advisory and is not included in those six checks. Its PF convention also uses 99.9 when there are gains and no losing trades; that is a display sentinel, not an infinite or statistically established profit factor. The H1 runner does not export all_ok as its acceptance verdict, so these general dashboard targets must not be silently reused as the H1 research acceptance protocol.
- The H1 row stores aggregate fold metrics, not a per-calendar-month return distribution or a complete uncertainty/robustness assessment. The three chronological folds are not an independent holdout; the broader project board already records that the existing research periods are contaminated/reused and independent holdout is unavailable. Metrics must therefore remain descriptive until data, execution, drawdown and independence gates are accepted.
- **Decision:** no code change. Do not add a generic PASS badge or invent thresholds now; doing so would create a false sense of validation. Before any future H1 market run, write a separate pre-registered acceptance protocol defining minimum trade count, per-fold and aggregate performance, drawdown convention, cost stress, concentration/robustness and an untouched independent holdout. Cost drag must be an explicit criterion or explicitly justified exclusion. Preserve the current descriptive report and existing provenance manifest.
- No tests, API calls, downloads, market replay, PnL or tuning were performed.


### 2026-11-25 — read-only audit: H1 experiment split and holdout reuse controls

- Inspected the H1 runner, train-only top-five selector and manual GitHub Actions workflow. The intended temporal design is coherent: the selector screens symbols on the first 50% training window; explore mode evaluates parameter grids on folds 1–2 (50–80%); confirm mode evaluates one frozen grid configuration and arm-set on fold 3 (80–100%). The runner checks the selection cutoff is strictly before the first scored fold, verifies exact selected symbols, and hashes selector inputs and replay dependencies. EMA labels are built only from candles through the relevant fold end, with a 1,000-bar pre-roll; no future candles are passed into the label builder.
- **Material governance gap:** the workflow description calls final fold 3 a one-shot holdout, but the implementation does not enforce one-shot use. `workflow_dispatch` can be launched repeatedly with `validation_mode=confirm`; each run accepts caller-supplied frozen volume/breakout thresholds and strategy mode from the allowed grid. There is no consumed-holdout registry, immutable preregistration record, one-time authorization, or automatic rejection if fold 3 has already been inspected. A user can therefore inspect a confirm result, change the selected allowed parameters, and run confirm again. After that, fold 3 is no longer an untouched holdout, even though each individual run passes the timestamp and hash checks.
- The current selection manifest freezes the selected five symbols and its input/code provenance, but it does not freeze a pre-confirm strategy configuration or prove when the confirm parameters were committed relative to first access to fold 3. This is compatible with exploratory tuning followed by a first confirm, but it cannot by itself prove the confirm was truly one-shot.
- A separate, already documented limitation remains: the selector ranks candidates using one-symbol isolated portfolios, not the later shared-capital five-symbol portfolio. That is a screening heuristic, not proof the chosen basket is optimal or even viable as a shared-capital portfolio. The later shared-capital explore/confirm stage is needed to evaluate that basket.
- **Decision:** preserve the temporal split and do not change strategy code. Before any future confirm run, add an external/immutable preregistration and holdout-consumption protocol: record the exact strategy arms, thresholds, code commit, data manifest hashes and timestamp before revealing confirm output; permit only one confirm evaluation per frozen experiment; any rerun or parameter change must permanently retire fold 3 and require a new independent period. A repository-only flag that can be reset by a new commit is not sufficient proof of one-shot use. Until then, label fold 3 as a reserved confirmation segment, not an accepted independent holdout.
- No tests, API calls, downloads, market replay, PnL or tuning were performed.


### 2026-11-25 — read-only audit: H1 universe selection and archive-window look-ahead

- Inspected `scripts/select_h1_top5_train_only.py` and `scripts/snapshot_bybit_linear_universe.py`. The selector does useful safeguards: candidate H1 timestamps must be aligned, strictly increasing and contiguous; candidates are clipped to a common calendar interval; each candidate's training slice is checked not to cross its own 50% validation boundary; lifecycle checks exclude contracts outside recorded launch/delivery bounds; the exact input files and selector code are hashed into the manifest.
- **Material selection-window concern:** the reference symbol is chosen as the candidate with the longest *full archived span*, using each archive's final timestamp. The reference training cutoff is then computed as 50% of that full span. Each candidate's own first-validation boundary is also computed from its full archived history. Thus future archive endpoints and future data availability influence the historical training cutoff and candidate eligibility. This is not direct future-price use in indicator calculations, but it is a look-ahead dependency in sample construction and may favour long-lived / well-covered contracts. The current manifest makes this rule visible, but does not remove the dependency.
- **Historical universe completeness remains unproven:** the lifecycle snapshot is a current Bybit V5 instruments-info collection across statuses and contains launch/delivery bounds for records returned today. Its own code/docstring explicitly treats lifecycle bounds as bounds, not proof of temporary tradability or complete historical closed-contract retention. The selector only evaluates symbols present in both supplied archives and this snapshot. It cannot reconstruct a complete point-in-time universe of all contracts actually tradable at each historical date, including contracts no longer returned by Bybit.
- Consequently, the current selector is not a validated survivorship-free historical universe. It can only be described as a train-only ranking over the supplied, currently evidenced archive candidate set, with future archive-span dependence in its split construction. Do not interpret top-five as an unbiased historical universe selection.
- **Decision:** no code change and no data replay. Before using this selector for market evidence, define a fixed calendar training cutoff independently of candidate archive end dates; require point-in-time universe membership evidence at that cutoff; include delisted/closed instruments and explicit missing-history accounting; and ensure every candidate's data coverage is assessed against the same predeclared interval without using its future archive endpoint to set the split. If full historical universe cannot be evidenced, narrow the claim and keep D4 NOT ACCEPTED.
- No tests, API calls, downloads, market replay, PnL or tuning were performed.


### 2026-11-25 — read-only audit: H1 signal causality and candle timing

- Inspected `QuantStrategyCore.evaluate_signal`, Donchian/volume/ATR helpers, `market_structure.py` EMA series/labels, the H1 wrapper and `run_simulation_pass`/`step_candle` sequencing.
- The core signal calculations are causal for a completed candle: Donchian high/low and volume baseline use `candles[:-1]`; ATR uses the prior history; current close/volume are used only after the current H1 candle is complete. Breakout-ATR distance uses the same prior Donchian boundary. H2 range-fade uses the current candle's high/low/close only at its close, which is also causal.
- EMA50/200 labels are computed recursively from chronological closes; each label at index `i` depends only on EMA states and close through index `i`, plus the slow EMA value `slope` bars earlier. H1 runner truncates the source candles at the scored fold end before constructing labels, requires a 1,000-bar pre-roll, and performs exact timestamp lookup. The fold replay retains pre-fold candles for indicator warm-up but the wrapped evaluator rejects signal generation outside `[start_ts, end_ts]`.
- Execution sequencing is consistent with the signal timing: `step_candle` fills an existing pending signal only when the current candle timestamp equals `signal_ts + timeframe`; a new signal is staged after the current bar and cannot fill on that same candle. The timestamp is the H1 candle-open key, while the decision is made after that candle closes; this convention is consistent in the runner, but should remain explicit in future logs and manifests to avoid interpreting `signal_ts` as the wall-clock decision instant.
- H1 dataset loader sorts timestamps, rejects duplicates, non-hour-aligned timestamps, invalid OHLCV and any missing/irregular hourly candle. Portfolio replay additionally checks synchronized timestamps across selected symbols. EMA labels require contiguous H1 data and exact timestamp matches. This closes common gaps/nearest-label leakage paths.
- **No direct future-price look-ahead was demonstrated in the audited H1 signal path.** This is a scoped code audit, not a proof of the full research process: it does not resolve the already recorded future-archive-endpoint dependence in universe selection, historical universe incompleteness, repeated holdout use, execution realism, or unaccepted data. The general-purpose sparse replay path was not part of this H1 validation path and must not be substituted without a separate audit.
- **Decision:** no code change. Keep the current completed-candle → next-candle execution convention and document `signal_ts` as the candle-open identifier for a close-time decision. Any future signal feature must preserve prefix-causal calculations and exact timestamp alignment. No tests, API calls, downloads, market replay, PnL or tuning were performed.


### 2026-11-25 — read-only audit: Bybit H1 candle archive and Mark-price alignment

- Inspected `scripts/archive_bybit_market_history.py`, `scripts/run_h1_shared_capital_portfolio_validation.py`, `scripts/validate_funding_coverage.py`, `Bybit_Trading_Engine_v14_research.py` Mark loader and the older generic `bybit_downloader.py`.
- The dedicated H1 archive path has strong input controls: UTC-aligned requested ranges; only closed candles; Bybit response rows checked for requested chunk membership; OHLC positivity/order and non-negative volume/turnover; exact expected hourly grid with missing-candle rejection; sorted output; trade and Mark candles collected separately; Mark coverage compared to trade timestamps, with only a justified terminal Mark candle allowed at a funding settlement boundary. The engine independently validates Mark OHLC finiteness/positivity/order and duplicate timestamps when loading full OHLC files. The H1 runner checks exact trade/Mark timestamp alignment and synchronized symbol timestamps.
- The dedicated collector's trade and Mark chunk windows are non-overlapping and use an exclusive internal end boundary (`chunk_end - 1` for the API request). The archive stores trade OHLCV only through the requested exclusive end; a terminal Mark candle is added only when the dated funding schedule requires a settlement at that boundary. This preserves the distinction between candle-open timestamps and settlement close boundaries.
- **Legacy downloader integrity caveat:** `bybit_downloader.py::collect()` stores parsed rows directly in a timestamp dictionary (`rows[ts] = vals`) without rejecting duplicate timestamps or checking that every response timestamp lies inside the requested window. For kline/mark requests it does not enable the page audit that records out-of-window and duplicate statistics. Conflicting or repeated response rows can therefore be silently overwritten in this generic path. This is not a demonstrated defect in the dedicated H1 archive path, which performs stricter range checks and rejects conflicting duplicates; nevertheless, the generic downloader must not be treated as an equivalent authoritative H1 source without hardening and separate validation.
- The H1 loader also independently rejects duplicate trade timestamps, irregular hourly spacing, malformed OHLCV, and non-hour-aligned timestamps. The Mark loader validates complete OHLC when the liquidation model is enabled; the H1 coverage validator requires the expected Mark timestamp grid. The validation manifest hashes all supplied input files but, as its own `data_source` wording correctly notes, hashes do not independently prove remote origin.
- **Decision:** no code change. Keep the dedicated archive path as the only admissible H1 source path; do not substitute the generic downloader. No source-origin claim beyond recorded Bybit V5 collection provenance. A future hardening task for the generic downloader should reject duplicate/out-of-window rows and validate page ordering/coverage before append, but it is not a prerequisite to modify the accepted H1 path. No tests, API calls, downloads, market replay, PnL or tuning were performed.


### 2026-11-25 — read-only audit: H1 funding settlement boundaries and cashflow timing

- Traced the dedicated archive path, funding schedule manifest validator, H1 coverage preflight, `funding_accounting.py`, engine MTM/close calls and fold finalization.
- The archive requests funding history through the scored interval's inclusive close boundary while trade H1 klines remain end-exclusive. If a settlement occurs exactly at the final close boundary, the collector fetches one additional closed Mark candle whose open timestamp equals that boundary; it does not add an extra trade candle. Coverage validation permits this one extra Mark candle only when a funding event exists at the exact terminal boundary.
- The H1 runner explicitly defines the final scored H1 timestamp as candle OPEN and extends accounting/metadata coverage through `end_ts + 3_600_000`, the candle CLOSE boundary. Funding manifest validation reconstructs the expected settlement grid from dated funding-interval snapshots and compares exact expected vs actual timestamps; duplicates, missing events and missing same-timestamp Mark proxies fail closed.
- The engine evaluates cumulative funding over the inclusive interval `[entry_ts, as_of_ts]`. Entry-boundary ambiguity excludes a possible receipt but charges a possible payment. Final-close ambiguity similarly excludes a possible receipt and conservatively charges a possible payment. TP1-boundary handling uses full quantity for a possible payment and remaining quantity for a possible receipt; subsequent settlements use remaining quantity. The remaining-margin helper prorates accumulated lifecycle funding to the remaining position after TP1, while final trade PnL retains full lifecycle funding. The code therefore has explicit boundary policy rather than an accidental one-hour shift or duplicate booking in the audited path.
- MTM is evaluated at H1 close boundaries and final positions are closed at the last candle's close boundary. `signal_ts` and candle timestamps remain candle-open identifiers; the runner's funding/settlement accounting consistently uses the corresponding close boundary where required.
- **No direct one-hour shift or duplicate funding cashflow was demonstrated in the audited H1 path.** This is a code-level conclusion only; no accepted market archive was replayed. The funding cashflow's mark notional remains an exact-timestamp Mark-candle OPEN proxy, explicitly documented in `funding_accounting.py`, not proof of Bybit's exact final settlement mark. Dated snapshots also cannot prove an unobserved funding-interval change/reversion between snapshots. These are still D3 acceptance limitations.
- Conservative edge handling can overstate payment at an ambiguous entry/exit/TP1 boundary by charging a possible payment where event ordering is unknown. This is intentional risk conservatism, not evidence of a duplicate settlement.
- **Decision:** no code change. Keep settlement timestamps inclusive and candle archive end exclusive; preserve the extra terminal Mark candle only for a settlement exactly at the final close boundary. D3 remains NOT ACCEPTED for exact cashflow proof until settlement mark-price fidelity and effective-time interval evidence are independently established. No tests, API calls, downloads, market replay, PnL or tuning were performed.


### 2026-11-25 — deterministic regression: exported trade journal vs shared portfolio equity

- Added `test_exported_journal_summary_reconciles_with_trade_ledger` to `tests/test_portfolio_accounting.py`. It closes a deterministic synthetic position, exports the dashboard journal, reloads the serialized JSON, and independently reconciles: one ledger row; summary equals serialized summary; trade count; gross PnL; total fees + slippage + funding; net PnL; realized equity = initial capital + ledger net PnL; no residual open position; and current equity = realized equity after flattening.
- GitHub Research engine checks for commit `dd606d4c59e33583ad73ad8e4758daef10b52759` completed **SUCCESS** (run `45618224340`). Job logs explicitly show `python tests/test_portfolio_accounting.py` with **28 tests, OK**, and a later portfolio-accounting invocation with **123 tests, OK**; the workflow's configured deterministic checks completed successfully. Python compilation also passed.
- This is a new, directly executed regression test for the reporting boundary, not a market replay. It proves the selected synthetic close and serialized journal summary reconcile under the tested fixture. It does not prove every partial-close/funding/fee/rounding combination or historical H1 portfolio output is correct.
- Existing shared-capital replay test independently asserts ledger net = gross − fees − slippage − funding, audit net equals ledger net, realized equity equals initial capital + net, and current equity equals realized equity when no positions remain. The new test extends that check through the dashboard JSON export path.
- **Decision:** retain the new test; no strategy, execution, or market data changes. Portfolio accounting/reporting has a stronger deterministic regression gate, but H1 market results remain unaccepted due to the independent data/universe/holdout and execution-model limitations recorded above. The separate intrabar drawdown high-water limitation remains unresolved and must not be conflated with ledger PnL reconciliation.
