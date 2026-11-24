# PROJECT COMPASS — долговременный контекст проекта

> Назначение: компактная путеводная карта для пользователя и AI-агента. Она сохраняет смысл проекта, накопленные решения, доказательства, запреты и ближайшую точку продолжения между чатами.
>
> Последняя содержательная сверка: 2026-11-24. Рабочая база: `research/market-regime-v1-main`. PROJECT COMPASS и обязательная инструкция чтения уже включены в эту ветку через PR #15 (squash commit `f92a21118573990398ffd9727c9e6f8ba0ec299b`). `main` не изменялся.
>
> **Правило чтения:** перед любой новой задачей по проекту прочитать этот документ, затем проверить актуальные файлы/коммиты/CI в GitHub. Этот документ — карта смысла и решений, но не замена исходному коду, Experiment Ledger, аудитам и свежим GitHub-данным.

## 1. Зачем существует проект — северная звезда

Изначальная идея была создать автономного Bybit-робота, который уменьшит эмоциональные ошибки ручной торговли и сможет системно исполнять торговые правила.

В ходе работы цель была осознанно расширена. Теперь главная задача — **не просто написать бота, а построить исследовательскую лабораторию, которая умеет отличать устойчивое рыночное преимущество от случайности, ошибок данных и особенностей симуляции**.

Искомый ответ один:

> Существует ли на конкретном рынке, инструментах и временном горизонте воспроизводимая закономерность, которая после всех реалистичных издержек остаётся прибыльной, выдерживает независимую проверку и может быть исполнена в реальности?

Приоритет — доказательство или опровержение edge, а не количество кода, стратегий, тестов, дашбордов или инфраструктуры.

Целевая последовательность:
1. Quant Research Lab: корректные данные, воспроизводимые гипотезы и тесты.
2. Подтверждённая стратегия: положительный net expectancy/PnL на независимых периодах и общем капитале.
3. Paper/forward validation: подтверждение результата без реальных ордеров.
4. Только после прохождения предыдущих этапов — обсуждение подключения биржи. Live-торговля требует отдельного явного разрешения пользователя.

**Текущий статус:** доказанного устойчивого торгового преимущества нет. Проект не является разрешённым live-ботом.

## 2. Как менялось понимание рынка и задачи

- Пользователь начинал с идеи конкретного автономного робота, затем согласился на более фундаментальную цель — исследовать рынок и искать проверяемые закономерности.
- Важное наблюдение пользователя при изучении стакана: рынок — не загадочный алгоритм или замок, который можно «разгадать». Это взаимодействие реальных участников, потоков рыночных и лимитных заявок, ликвидности, интересов и ограничений. Нельзя исходить из предположения, что рынок обязан подчиняться красивой формуле.
- Следствие для исследований: любая закономерность должна быть измерима и проверяема; корреляция или визуально убедительная картина не равна причинному механизму и не доказывает возможность исполнения.
- Архитектурная идея Quant Lab: данные → признаки/состояния рынка → гипотезы → воспроизводимый replay/backtest → независимая проверка → отчёт и анализ. Код отвечает за расчёты и метрики; AI помогает формулировать вопросы и анализировать уже проверенные результаты, но не должен выдумывать метрики или подменять вычисления повествованием.
- Предпочтение пользователя — автономная работа ассистента без постоянных запросов разрешения, но с полной прозрачностью, честной оценкой неопределённости и понятными объяснениями.

## 3. История проекта в крупных этапах

### Этап A — торговый движок и базовая стратегия
Создавался и развивался исследовательский движок `Bybit_Trading_Engine_v14_research.py`, первоначально вокруг H1 breakout/Donchian + volume gate. Формировались сигналы, pending orders, входы/выходы, stop/TP1/TP2/trailing, sizing, risk limits, portfolio state, журнал сделок и восстановление состояния.

Параллельно создавались backtest/walk-forward runners, отчёты, дашборды, конфигурации и GitHub Actions. Важно: наличие этой инфраструктуры само по себе не подтверждает качество стратегии.

### Этап B — техническая надёжность
Значительная часть работы была посвящена тому, чтобы симулятор не создавал ложные результаты из-за ошибок реализации:
- приоритеты stop/TP/kill-switch и временная семантика событий;
- корректный учёт комиссий, slippage и execution notional;
- восстановление состояния без тихой потери/частичного применения повреждённого backup;
- строгие схемы pending orders, positions, risk snapshots и timestamps;
- идентичность сделок и запрет дублирующихся/несогласованных состояний;
- валидация данных, символов, категорий инструментов и публичных trade records.

В истории проекта сообщались результаты отдельных регрессионных серий (например, 23/23, 87/87, 213/213 в разных аудитах). Их нельзя автоматически считать доказательством состояния текущего HEAD: перед ссылкой на них нужно проверять конкретный commit, тестовый набор и CI run.

### Этап C — широкие рыночные исследования
Проводились сравнения направлений, типов исполнения, фильтров и рыночного контекста; строились chronological folds и shared-capital portfolio replay. Результаты заносились в `docs/research/EXPERIMENT_LEDGER_RU.md` и отдельные отчёты.

Ключевой урок: локальные положительные результаты на выбранных монетах/периодах исчезают или меняются при расширении universe, общем капитале, учёте расходов и проверке вне выборки. Результаты per-symbol нельзя выдавать за результат единого портфеля.

### Этап D — переход от «улучшать стратегию» к «проверять доказательства»
Исследования показали, что главным ограничением стала не архитектура, а качество доказательств:
- Binance/CryptoFetch OHLCV использовался как proxy, а не как Bybit execution replay;
- OHLC limit-touch fill оптимистичен: не моделирует очередь, bid/ask spread, partial fills и adverse selection;
- отсутствовали или не были подтверждены полные исторические Bybit mark, funding, point-in-time universe/specifications и fee assumptions;
- отсутствие надёжного holdout не позволяет заявлять о переносимости результата.

Были добавлены provenance checks, manifests, data gates и fail-closed validation. Это повышает качество исследования, но не создаёт edge.

### Этап E — переосмысление масштаба и защита от избыточной сложности
Пользователь прямо указал на риск повторить прошлый опыт чрезмерной разработки KOS для ещё не существовавшего агентства недвижимости: строить сложную инфраструктуру раньше, чем доказана её практическая необходимость.

Принят обязательный стандарт: каждая задача должна отвечать на пять вопросов:
1. Что делаем?
2. Зачем?
3. Какую конкретную проблему решаем?
4. Как проверим, что это полезно?
5. Что произойдёт, если этого не делать?

Уровни глубины:
- **Необходимое:** минимальная логика и проверки, без которых нельзя принять следующее решение.
- **Усиление:** только если предыдущий этап доказал пользу.
- **Продвинутая инфраструктура:** откладывается до реальной необходимости.

Не делать тесты ради тестов, не создавать документы ради документов и не расширять архитектуру без влияния на исследовательское решение.

## 4. Что уже проверяли и что нельзя забыть

### Базовая H1 breakout-линия
В ранних исследованиях сравнивались market/limit execution, long-only/long-short, chase/body gates, контекстные фильтры, per-symbol и shared-capital варианты. Некоторые локальные результаты выглядели положительно, но были ограничены выбранными инструментами, уже использованными folds и упрощённой моделью исполнения.

В журнале отражены эксперименты E01–E13 и последующие аудиты. Для любого точного численного утверждения открыть соответствующую запись и artifact; не копировать старые цифры без проверки provenance.

### H-A — relative-strength breakout
H-A была preregistered и проверена на уже исследованных CryptoFetch/Binance-style OHLCV периодах. Результат отрицательный: суммарный proxy net для H-A около **−6,135.26 USDT** против baseline около **−5,635.98 USDT**; H-A хуже baseline примерно на **499.28 USDT**, отрицательна во всех трёх folds и не переносит преимущество между периодами. Это не полный Bybit net PnL, поскольку отсутствовали funding и реальная модель maker execution.

**Решение:** tested H-A configuration rejected. Не подбирать параметры и не выбирать монеты на тех же folds.

Источник: `docs/research/H_A_RELATIVE_STRENGTH_BREAKOUT_PREREGISTRATION_RU.md`.

### H-C — post-break invalidation
H-C — идея раннего выхода, если цена после пробоя закрывается обратно за исходную Donchian-границу в первые три завершённые H1-свечи. Реализована в исследовательской ветке под default-OFF флагом с синтетическими/regression tests и сохранением signal-time boundary в состоянии.

**Статус:** PnL не подтверждён; baseline parity не подтверждена. Нужны независимые данные/период и preregistered shared-capital comparison. Нельзя выдавать синтетические тесты за прибыльность.

Источник: `docs/research/H_C_POST_BREAK_INVALIDATION_PREREGISTRATION_RU.md`.

### H-B — mean reversion
H-B обсуждалась как отдельная гипотеза: сильное движение/падение, затем подтверждение стабилизации/бокового режима и возврат к среднему. Подготовлены readiness/synthetic design specifications в исследовательском контексте, но на текущем этапе **нет подтверждённого рыночного результата и нет основания для полной интеграции в торговый движок**.

Ближайший безопасный шаг, согласованный в диалоге 2026-11-24: проверить только чистую механику сигнала на синтетических данных — временную причинность/no-look-ahead, вход, stop и mean target; оценить минимальный изолированный seam. Не переписывать весь lifecycle/engine до доказательства, что гипотеза хотя бы механически определена и реализуема без утечки будущего.

Перед продолжением перепроверить наличие и актуальность файлов H-B в выбранной ветке. Историческое упоминание спецификации не является доказательством, что она присутствует в текущем HEAD.

## 5. Данные и ограничения, которые блокируют рыночные выводы

В provenance-аудитах были выявлены пробелы:
- Bybit-native H1 trade OHLCV — отсутствует/не подтверждён в исследовательском пакете;
- mark-price history — отсутствует/не подтверждён;
- funding settlements/history — отсутствуют/не подтверждены;
- point-in-time universe, включая delisted/suspended инструменты — частичный/неподтверждённый;
- dated instrument specifications и risk tiers — частичные/неподтверждённые;
- representative L2 order book/trades — отсутствуют (имелся лишь ограниченный диагностический пример);
- dated account/symbol fee assumptions — не подтверждены.

GitHub-hosted runner ранее получал HTTP 403 от Bybit. В предыдущем scope были установлены ограничения: не обходить блокер запуском collectors, не скачивать новые архивы и не подключать account/private API без отдельного пересмотра разрешений и протокола данных.

**До снятия data/method gates:**
- не запускать новые market-PnL backtests, parameter sweeps или replay;
- не подключать Bybit private/account API, ключи или live;
- не запускать paper/live trading;
- не выдавать Binance proxy или OHLC fill за Bybit-native доказательство.

Допустимы безопасные статические аудиты, чтение уже сохранённых артефактов, проверка provenance, deterministic synthetic tests и точечные исправления подтверждённых дефектов — если они не обходят действующие gates.

## 6. Архитектурные и методологические принципы

1. **Разделение слоёв:** data ingestion → validation/provenance → features/signals → execution simulation → accounting/risk → experiment report. AI не является источником ground-truth метрик.
2. **Воспроизводимость:** фиксировать commit SHA, workflow run, входные файлы и hashes, universe, временные границы, параметры, costs, folds и artifacts.
3. **Causality:** сигнал использует только информацию, доступную на момент решения; отдельно проверять timestamp semantics, look-ahead и future leakage.
4. **Costs first:** учитывать комиссии, slippage, spread, funding, queue, partial fills, adverse selection, quantity steps, margin/liquidation где применимо.
5. **Shared capital:** портфельный вывод строится на общем капитале, одновременных позициях и лимитах риска; независимые per-symbol equity curves не складывать как портфель.
6. **Out-of-sample:** хронологическая независимая проверка; holdout/lockbox нельзя использовать для подбора параметров.
7. **No cherry-picking:** сохранять отрицательные результаты и причины отказа; не менять критерии задним числом.
8. **Fail closed:** отсутствующие/некорректные данные и provenance должны блокировать расчёт, а не молча подменяться дефолтами.
9. **Technical CI ≠ edge:** зелёный workflow доказывает только то, что выполнились конкретные шаги. Он не доказывает прибыльность.
10. **Никаких production/live действий:** исследовательская система не должна размещать реальные ордера.

## 7. Правила совместной работы и объяснений

Пользователь разрешил максимальную автономность в безопасной исследовательской работе: самостоятельно выбирать следующий разумный шаг, проверять код и артефакты, выполнять разрешённые deterministic tests, фиксировать результаты и обновлять документацию. Не спрашивать «продолжать ли» после каждого шага.

При этом:
- объяснять простым языком, не прятаться за техническим жаргоном;
- отделять подтверждённое от гипотез и неизвестного;
- прямо говорить о пределах данных, модели и собственной уверенности;
- не обещать фоновую работу после завершения ответа;
- задавать вопрос только при реальном блокере или решении, которое действительно принадлежит пользователю;
- сообщать только о значимых результатах, решениях и блокерах, не присылать пустые статусные сводки;
- каждый шаг должен приближать к ответу о реальном edge или закрывать конкретную неопределённость.

## 8. Постоянный процесс обновления этой карты

Обновлять этот документ после значимого изменения:
- цель/приоритет проекта или разрешения пользователя;
- решение ACCEPT/REJECT/OPEN по гипотезе;
- новый подтверждённый результат, методологический дефект или data gate;
- смена рабочей ветки/важного commit SHA;
- изменение ближайшего безопасного шага;
- выявление противоречия между разговором и GitHub.

Формат обновления — короткая датированная запись в конце документа или корректировка соответствующего раздела. Не превращать карту в стенограмму и не переписывать прошлые решения задним числом.

При каждом старте новой сессии:
1. Прочитать этот PROJECT COMPASS.
2. Прочитать `AGENTS.md`, `PROJECT_WORKING_RULES_RU.md`, `docs/README_RU.md`.
3. Подтвердить текущую рабочую ветку и HEAD из GitHub; старые SHA считать только историческими снимками.
4. Сверить ближайшую задачу с `NEXT_RESEARCH_PLAN_RU.md`, актуальными audit/data gates и релевантной записью `EXPERIMENT_LEDGER_RU.md`.
5. Проверить актуальные CI/PR только там, где они влияют на текущую задачу.
6. Если данные противоречат карте, GitHub/code/artifacts имеют приоритет для технического состояния; пользовательские решения и ограничения имеют приоритет для целей и разрешений. Зафиксировать расхождение и обновить карту.

## 9. Что не является частью ядра проекта

Обсуждение Hash Hedge / prop-trading challenge business model в ноябре 2026 было отдельной темой о бизнес-модели челленджей и выплат. Это не цель и не часть реализации Bybit Trading Bot, если пользователь отдельно не свяжет эти направления.

Попытка переноса/восстановления репозитория `tradernijita-stack/Trader` в ноябре 2026 — отдельная операция с репозиторием. Источник исследовательской истории и текущей рабочей кодовой базы, который здесь рассматривается, — `nikitanecilli-bit/bybit-trading-bot`. Не путать два репозитория и не считать перенос успешным без проверки.

## 10. Текущая точка на 2026-11-24

- Большая исследовательская/техническая инфраструктура существует, но её объём не должен диктовать следующий шаг.
- Рыночное преимущество не доказано.
- H-A tested configuration rejected.
- H-C implemented behind default-OFF flag; no PnL proof.
- H-B signal candidate v0.1 описан: H1 long-only; range label на t-1; shock на close t; stabilization на close t+1; entry на open t+2; stop `low[t]`; target — среднее 24 pre-shock closes; time stop — close 24-го бара удержания. Это спецификация, не реализация.
- В H-B документах есть подробный lifecycle/adapter plan (pending, actual-fill sizing, nullable TP, restore, manager, accounting, journal). Он значительно шире минимальной проверки сигнала. Не начинать эту полную интеграцию до доказательства необходимости.
- `market_regime.py` уже содержит causal classifier; `tests/test_market_regime.py` проверяет future-mutation invariance. Однако classifier не обеспечивает H1 cadence validation, а H-B требует ровно 3,600,000 ms между последовательными свечами.
- H-B `RegimeConfig` ещё не frozen для гипотезы. Не использовать незаметно default config и не выбирать пороги по результатам. Для первого изолированного теста режим `range` подавать как заранее заданный synthetic input; отдельно проверять temporal predicates. Выбор/freeze classifier config — отдельное решение до рыночного исследования.
- H-B readiness spec и synthetic spec содержат несколько уровней детализации и открытых вопросов (например numeric tolerance, downstream JSON consumers, liquidation model limits). Не считать все lifecycle требования обязательными для первой проверки чистого сигнала.
- Bybit-native data/provenance gaps остаются критическими; не обходить действующие запреты на новые collectors/data/PnL.
- Пользователь подтвердил максимальную автономность 2026-11-24, включая управление документами и исследовательской лабораторией. Это разрешает самостоятельные безопасные изменения в research-ветке, но не отменяет явные gates по сбору данных/подключению Bybit, paper/live и реальному капиталу.
- PR #15 объединён в `research/market-regime-v1-main` (squash commit `f92a211...`); `main` не затрагивался. Обнаруженная ошибка прошлого статуса исправлена: до merge карта и правило фактически отсутствовали в рабочей ветке.
- H-B signal-only implementation находится в PR #16 (`research/hb-signal-contract`), не объединён: добавлены `h_b_signal.py` и `tests/test_h_b_signal.py` (10 тестов). Изменений торгового движка нет.
- В отдельной Python-сессии вручную проверены 10 основных сценариев/инвариантов на точной копии функции: все прошли. Это не запуск pytest из репозитория и не CI.
- Для PR #16 не обнаружены связанные workflow runs; автоматическое подтверждение тестового набора отсутствует. Не объединять PR до получения репозиторного тестового результата и проверки legacy suite.
- Следующий практический шаг: получить фактический запуск `pytest tests/test_h_b_signal.py` и relevant legacy regression suite. Если GitHub Actions не запускается автоматически, найти разрешённый способ выполнения; не создавать инфраструктуру только ради красивого статуса. Затем исправить обнаруженные дефекты и принять решение по узкой интеграции.

---

## Журнал изменений карты

### 2026-11-24 — первый глобальный контекстный аудит
- Сформулирована единая цель проекта: лаборатория доказательства/опровержения edge, а не просто автономный бот.
- Сведены в одну карту история движка, технической надёжности, рыночных исследований, H-A/H-C/H-B, data gates и правила совместной работы.
- Отделены факты репозитория от исторического контекста диалогов; отмечено, что все SHA/CI/PR должны перепроверяться при продолжении.
- Добавлено правило обязательного чтения и постоянного обновления карты.

### 2026-11-24 — автономность и исправление контекста
- Пользователь подтвердил полную автономность в управлении исследовательской лабораторией и документацией; сохранены ранее действующие ограничения на биржевое подключение, сбор новых данных и любые реальные ордера.
- PR #15 объединён только в `research/market-regime-v1-main`; `main` не менялся. Обязательное чтение PROJECT COMPASS теперь присутствует в `AGENTS.md` и `docs/README_RU.md` рабочей ветки.
- Повторная проверка H-B показала: signal contract уже описан, но production implementation и H-B synthetic tests отсутствуют. Большой lifecycle plan преждевременен для первого этапа.
- Выбран более узкий следующий шаг: проверить чистую временную механику сигнала отдельно от исполнения/позиционного lifecycle. Никаких market-PnL тестов или сбора данных.

### 2026-11-24 — H-B signal-only implementation candidate
- Создан PR #16 (`research/hb-signal-contract`) с отдельной pure-функцией H-B signal predicate и 10 deterministic tests. Не тронут торговый движок и не реализованы pending/fill/position lifecycle.
- Тестовая функция вручную исполнена в изолированной Python-сессии; 10 ключевых проверок прошли. Результат не является pytest/CI evidence.
- GitHub connector не вернул workflow runs для PR head; автоматическое тестовое подтверждение пока отсутствует. PR оставлен открытым, не объединён.
- H-B RegimeConfig не frozen; range labels и ATR в механическом тесте — контролируемые входы. Market PnL, новые данные и Bybit подключение не выполнялись.


## 2026-11-24 — управленческая доска и проверка H-B signal-only PR

- Создана короткая управленческая панель `docs/research/RESEARCH_BOARD_RU.md`: текущие статусы H-A/H-B/H-C, реальные ограничения данных, запреты и ближайшие решения. Это не новый журнал экспериментов; подробные результаты остаются в Experiment Ledger и первичных отчётах.
- Актуальная инвентаризация Git tree рабочей ветки: шесть ZIP CryptoFetch в `data/archives/cryptofetch/`; Bybit-native trade OHLCV, mark, funding и dated instrument/risk-tier snapshots в дереве данных отсутствуют. Архивный аудит ранее зафиксировал 67 CSV entries, 64 валидных для legacy loader и три пустых; это Binance-style proxy, не Bybit data.
- PR #16 (`research/hb-signal-contract`) открыт, не объединён. Head `7d10b7bddc093584b676736dd66691143f27a8c9`; на момент проверки рабочая ветка была `b6f7d45412a0ea8b348bc6262b2850f85b68de9e`. PR отстаёт от базы на один commit и имеет статус compare `diverged` (4 ahead / 1 behind); workflow runs и commit statuses для PR head отсутствуют.
- Содержимое PR #16 — чистый `h_b_signal.py` и 10 deterministic tests; engine, pending/fill, sizing, persistence, exits и market PnL не менялись. По статическому чтению контракт использует range/ATR на t-1, shock на t, stabilization на t+1 и планирует вход на open t+2. RegimeConfig не frozen, фактический open t+2 и fill geometry ещё не проверяются; это осознанно оставленные следующие слои, а не доказанные свойства стратегии.
- Текущий `.github/workflows/research-checks.yml` запускается push только на рабочую ветку и включает `tests/**` в path filter, но явный compile/test command для новых H-B файлов отсутствует. Поэтому PR #16 пока не имеет repository pytest/CI evidence. Прямой ручной запуск скопированной функции не заменяет pytest.
- Следующий безопасный шаг: review/rebase PR #16 на актуальную рабочую базу; добавить H-B compile + deterministic test command в технический Research CI; выполнить CI и прочитать логи, убедившись, что market-PnL workflows не запускались. Не объединять и не расширять H-B lifecycle до получения реального тестового evidence.
- Никаких Bybit API, runner, новых архивов, market-PnL backtests, paper/live trading или реальных ордеров не выполнялось. Действующие запреты сохранены.


### 2026-11-24 — H-B Research CI dependency failure and correction
- Первый CI run [45463120336](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45463120336) прошёл compile и все предшествующие regression steps, но завершился на H-B test command: GitHub runner не имеет установленного `pytest` (`No module named pytest`). Само тело 10 H-B assertions не запускалось; не трактовать как логическую ошибку сигнала.
- H-B tests переведены на стандартный Python `unittest`, workflow-команда заменена на `python tests/test_h_b_signal.py`; внешняя зависимость не добавлялась.
- Повторный CI [45463406898] для commit `582ccedf943ed7d4a5a60db0436bbb63d4f5741c` запущен и на момент записи ещё выполняется. До результата не объявлять H-B mechanics pass.


### 2026-11-24 — H-B signal mechanics confirmed by repository CI
- PR #16 объединён в `research/market-regime-v1-main`; H-B pure predicate и 10 tests находятся в рабочей ветке. Research CI wiring выполняет compile и synthetic tests без рыночного PnL.
- Первый run [45463120336](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45463120336) не запустил assertions из-за отсутствующего pytest. Тесты переведены на stdlib unittest.
- Повторный run [45463406898](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45463406898) — SUCCESS; лог подтверждает `Ran 10 tests`, `OK`; все остальные шаги Research CI также прошли.
- Статус: **SIGNAL MECHANICS PASS**, не strategy/edge pass. Не frozen RegimeConfig, не проверены фактический t+2 fill, geometry, engine lifecycle или profitability.
- Следующий безопасный этап: read-only audit существующего causal regime classifier/RegimeConfig и timestamp convention; без market PnL, tuning, Bybit, новых архивов и engine integration.


## 2026-11-24 — H-B predicate and classifier review

- Research CI run `45463406898` on commit `582ccedf943ed7d4a5a60db0436bbb63d4f5741c` completed SUCCESS. The exact H-B step ran `python tests/test_h_b_signal.py`: 10 tests, OK. This is a signal-predicate synthetic pass only.
- Independent static review: predicate reads regime[t-1], ATR[t-1], close[t], high/low[t], close[t+1], and schedules entry at t+2. It does not read future candles beyond t+1. It freezes stop=low[t] and target=mean of 24 pre-shock closes. No engine fill/position/exit behavior is covered.
- Predicate currently accepts precomputed regime and ATR arrays; it does not bind them to a specific `RegimeConfig` or prove that `market_regime.classify_candles()` generated them. This remains the principal H-B mechanics/design gap before any engine adapter.
- `RegimeConfig.validate()` had a validation gap: non-finite slope thresholds and some wrong threshold types could pass. Added finite numeric validation and tests in commits `65da09dce517a93d089bc88fc716707891eecd59` and `e9782d15ff4f5ab226d4c89d842a544ed4cddf6a`. Research CI run `45463921785` completed SUCCESS: compile, causal market-regime classifier tests, H-B signal tests and all other configured deterministic steps passed.
- The next allowed step is a pure, explicit-config adapter from causal classifier to predicate, plus synthetic tests that prove config binding, regime/ATR index alignment and prefix/future invariance. Do not select RegimeConfig values by inspecting CryptoFetch PnL. If a configuration cannot be justified independently, retain H-B as design-blocked.


## 2026-11-24 — H-B explicit classifier adapter

- Added `evaluate_h_b_signal_with_classifier(candles, config, shock_index)` in `h_b_signal.py`. It requires a concrete `RegimeConfig`, validates it, classifies only the prefix ending at t+1, passes causal regime/ATR to the predicate, and returns the exact config values as signal provenance. No default config is selected silently.
- Added 3 synthetic tests for required explicit config, config provenance, and exclusion of rows after t+1 from the classifier prefix.
- Research CI run `45464213667` on `7d27224942a7082889d8e98f3155668d18a9c5bb` completed SUCCESS. H-B test step: 13/13 OK; causal regime classifier tests and other configured deterministic checks passed.
- This establishes mechanical wiring from an explicit causal classifier to the H-B predicate. It does not establish that the classifier thresholds are economically justified, nor does it validate pending/fill, sizing, exits, persistence, market PnL or edge.
- Next possible isolated task: synthetic pending-entry contract for open[t+2], missing/gap cancellation, and entry/stop/target geometry without engine integration or PnL. Do not use CryptoFetch PnL to select RegimeConfig.


### 2026-11-24 — H-B regime adapter and causal cadence gate
- Static audit: `market_regime.classify_candles()` is causal but only requires strictly increasing timestamps; it does not enforce a timeframe cadence. H-B therefore must validate its entire classifier prefix, not only the local shock window.
- Added `h_b_regime.py` with an explicit frozen candidate config inherited from pre-existing RegimeConfig defaults (not market-calibrated), exact uninterrupted H1 validation through t+1, and causal regime/ATR feed into the H-B signal predicate. The wrapper slices input at t+1; later bars cannot affect the candidate.
- `RegimeConfig.validate()` now rejects non-finite, boolean and non-numeric threshold values; regression tests cover these cases.
- Research CI [45464653488](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45464653488) — SUCCESS on SHA `6540e375d6d2ad7dfd321202973e60e2e0815dae`. Market-regime tests passed; H-B signal tests: 13/13; H-B regime adapter tests: 6/6; full technical workflow successful.
- Status: **SIGNAL + REGIME MECHANICS PASS** only. The RegimeConfig is an uncalibrated candidate; no actual t+2 fill, fill geometry, engine lifecycle, market PnL or edge is validated.
- Next safe step: isolated pure next-open fill-geometry check (bar availability, timestamp, actual open between frozen stop/target), without engine integration or PnL.


## 2026-11-24 — H-B next-open entry contract

- Added `prepare_h_b_entry()` as a pure synthetic contract: validates H-B long identity and policy version, exact next-H1 timestamp, presence of t+2 candle, no existing position, finite positive entry open, and strict entry/stop/target geometry. Missing/gapped t+2, occupied symbol, or invalid geometry fail closed.
- The returned price is the observed candle open reference, not an executable fill. No spread, queue, partial fill, slippage, fee or adverse-selection model is present. No engine or pending-order integration was changed.
- Research CI run `45465175545` on `83ebd2f644b9a1f26b2928135b3c5b0b82ac37fc` completed SUCCESS. H-B signal/entry test file contains 21 tests and passed; frozen regime adapter test file contains 6 tests and passed. The full configured deterministic workflow passed.
- Current H-B result is a synthetic signal + classifier + entry contract pass only. No market PnL, execution proof or edge. A synthetic exit/persistence contract may be the next bounded step; do not connect the engine or run PnL before that is independently specified and needed.


### 2026-11-24 — H-B next-open geometry pass and lifecycle stop gate
- Added `h_b_fill.py`, a pure offline reference check for actual t+2 H1 open: validates exact shock/signal/entry timestamps and OHLC, then accepts only `stop < open[t+2] < target`. It reports per-unit risk/reward geometry only; no fees, spread, queue, slippage, funding, partial fills or adverse selection.
- Added 8 deterministic tests. Research CI [45465377742](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45465377742) — SUCCESS on SHA `b72c15575170fc8f49691706d88a3599ed94b954`; logs confirm H-B signal 19/19, regime adapter 6/6, next-open geometry 8/8; full technical workflow passed.
- Status: **SIGNAL + REGIME + NEXT-OPEN GEOMETRY PASS** on synthetic inputs only. No market PnL, no Bybit, no new archives, no paper/live, no engine integration.
- Decision: stop H-B expansion before pending/fill lifecycle, sizing, persistence and manager integration. Building those layers without a permitted independent market-validation path would repeat premature infrastructure growth. Resume only when the data/provenance gate can be satisfied within the user's existing permissions.
