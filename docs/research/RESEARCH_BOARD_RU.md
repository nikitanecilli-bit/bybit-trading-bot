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
| H-B mean reversion | **SIGNAL + CLASSIFIER MECHANICS PASS / ENGINE LIFECYCLE BLOCKED** | Pure predicate (10 tests) и explicit-config classifier adapter (+3 tests) прошли Research CI #45464213667; нет engine integration, pending/fill/exit lifecycle и market PnL | Независимо проверить entry open[t+2], gap/cancel, stop/target geometry и exit/persistence contract синтетически; не запускать PnL |
| Новые стратегии/фильтры | **DEFERRED** | Ни один новый кандидат не обоснован достаточно, чтобы оправдать расширение | Не добавлять до закрытия текущего H-B mechanical question |

Статусы REJECTED относятся к конкретным проверенным конфигурациям/окнам, а не к утверждению, что любой вариант семейства стратегий математически невозможен.

## 4. Данные: что реально есть

В рабочем дереве на момент аудита обнаружены шесть ZIP в `data/archives/cryptofetch/`. Аудит архива сообщает 67 CSV entries: 64 непустых/пригодных для legacy loader, три пустых; перекрывающиеся дубликаты прошли сравнение без обнаруженных конфликтов.

Это Binance-style OHLCV proxy. В репозитории нет подтверждённого Bybit-native пакета trade OHLCV + mark + funding + dated instrument/risk-tier snapshots и нет полного point-in-time universe. Наличие collector-кода и его mocked/offline tests не означает, что реальные архивы были получены.

Следствие: текущий data package не открывает путь к достоверному Bybit execution replay. Не маскировать этот пробел новыми расчётами на той же выборке.

## 5. Ближайшая последовательность

1. Довести PR #16 до актуальной базы рабочей ветки без потери изменений.
2. Включить H-B signal-only module/tests в технический Research CI так, чтобы CI выполнял только compile и deterministic tests — без market-PnL workflows. **Выполнено.**
3. Получить фактический запуск точных H-B tests и релевантных legacy regression tests; прочитать логи и убедиться, что выполнялись именно нужные тесты. **Выполнено:** первый запуск #45463120336 остановился на отсутствии pytest (assertions не запускались); после перехода на unittest повторный run #45463406898 завершился SUCCESS, H-B 10/10.
4. Провести независимый code review временной семантики и входных контрактов. Исправлять только подтверждённые дефекты.
5. Зафиксировать результат как **SIGNAL MECHANICS PASS**, не как strategy/edge pass. Не расширять сразу на pending/fill/position lifecycle.
6. Отдельно проверить causal RegimeConfig, timestamp semantics и следующий-bar/fill boundary без рыночного PnL. Если режим нельзя обосновать без tuning на использованных folds — H-B остаётся design-blocked.

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
