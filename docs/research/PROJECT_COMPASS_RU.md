# PROJECT COMPASS — долговременный контекст проекта

> Назначение: компактная путеводная карта для пользователя и AI-агента. Она сохраняет смысл проекта, накопленные решения, доказательства, запреты и ближайшую точку продолжения между чатами.
>
> Последняя содержательная сверка: 2026-11-25. Рабочая база: `research/market-regime-v1-main`. PROJECT COMPASS и обязательная инструкция чтения уже включены в эту ветку через PR #15 (squash commit `f92a21118573990398ffd9727c9e6f8ba0ec299b`). `main` не изменялся.
>
> **Правило чтения:** перед любой новой задачей по проекту прочитать этот документ, затем проверить актуальные файлы/коммиты/CI в GitHub. Этот документ — карта смысла и решений, но не замена исходному коду, Experiment Ledger, аудитам и свежим GitHub-данным.

## 1. Зачем существует проект — северная звезда

**Управленческая цель компании (утверждена 2026-11-24): устойчиво зарабатывать деньги на финансовых рынках, масштабируемо и при контролируемом риске.** Исследовательская лаборатория, торговый робот, алгоритмы, данные и инфраструктура — средства, а не цель. Главный ориентир — реализованный чистый денежный результат после всех торговых расходов, оценённый с учётом риска и операционных затрат.

Компания применяет Theory of Constraints Голдратта: найти главное ограничение, максимально использовать его, подчинить ему остальную работу, расширить ограничение и повторить цикл. Любая существенная задача обязана объяснять, какое ограничение она снимает, какой факт появится и какое решение о торговой прибыли изменится. Работа ради количества кода, тестов, коммитов, отчётов или загрузки запрещена как принцип приоритизации.

Канонический документ: [Философия и операционная модель компании](../COMPANY_OPERATING_PHILOSOPHY_RU.md). Он задаёт экономические показатели, критерии допуска задач, статусы доказательств и управленческий цикл.

### Текущее главное ограничение

Нет ни одного пути, который одновременно содержит **полностью специфицированную торговую гипотезу** и **принятую независимую доказательную базу** для честной проверки net edge на условиях Bybit. H-B имеет только signal/entry mechanics без полного lifecycle; H1 baseline имеет более полный lifecycle, но прежние folds уже использованы и их net-PnL непригоден для доказательства.

**Изменение 2026-11-25 — Bybit-only источник свечей подтверждён, но data gate закрыт лишь частично.** Получен официальный публичный архив Bybit `public.bybit.com/kline_for_metatrader4/BTCUSDT`. Его временные метки в UTC+3; загрузчик нормализует их в UTC. В отдельной сверке за 2025-07-01 24 часа свечей сопоставлены с восстановленными из официального Bybit Linear BTCUSDT trade archive: high/low/close совпали во всех 24 часах, объём — во всех 24 часах, open отличается не более чем на один tick (0.10 USDT). Первоначальный вывод о несовместимости был ошибочным из-за отсутствия поправки UTC+3; исправленный probe и повторный workflow подтверждают идентичность выборки.

Фактический H1 архив содержит 47,085 строк с 2020-04-01 00:00 UTC по 2025-11-03 01:00 UTC. Дубликатов и базовых OHLCV-ошибок не обнаружено. Однако в месячных файлах 2023-12, 2024-01, 2024-02 и 2024-03 есть усечённые участки; нормализованная серия имеет четыре разрыва общей длиной 1,928 пропущенных H1 баров. Эти интервалы нельзя интерполировать или пересекать торговыми позициями. Архив пригоден как Bybit trade-price research input только после явной маскировки пропусков и дополнительной проверки выбранного периода; он не является полным execution dataset.

**Главное ограничение не снято:** нет исторических Mark Price и settled Funding для BTCUSDT Linear, а также подтверждённого lifecycle для однозначного net cashflow. Проверен корень публичного Bybit-архива: доступны `kline_for_metatrader4`, `premium_index`, `spot_index`, `trading` и `spot`; каталоги `premium_index` и `spot_index` содержат BTCUSD (inverse), но не BTCUSDT Linear, поэтому это не замена нужным данным. В официальной V5 документации есть публичные методы `GET /v5/market/mark-price-kline` (linear; до 1000 свечей на страницу), `GET /v5/market/premium-index-price-kline` (linear; до 1000 свечей) и `GET /v5/market/funding/history` (linear; до 200 записей на страницу). То есть данные доступны в модели API Bybit, но текущий GitHub runner получает HTTP 403 на официальном API. Не обходить ограничение, не использовать сторонний прокси и не подключать приватный API. Если публичный доступ будет восстановлен в разрешённой среде, загрузка должна быть пагинирована и проверена на полноту по timestamp, funding interval и сменам параметров контракта. Не запускать market-PnL backtests, parameter sweeps или paper trading до выполнения текущих разрешений и data/method gates. H1 Donchian(48)+EMA50/200 остаётся preregistered кандидатом, а не доказанной стратегией; существующий shared-capital runner требует дополнительных market inputs и не является готовым single-symbol pilot. Следующая работа — минимально выяснить доступность Mark/Funding через разрешённые публичные Bybit-источники и read-only проверить требования существующего lifecycle; не строить новую инфраструктуру и не подменять отсутствующие данные. Подробный scope: [Minimum Viable Edge Validation](MINIMUM_VIABLE_EDGE_VALIDATION_RU.md).



Изначальная идея была создать автономного Bybit-робота, который уменьшит эмоциональные ошибки ручной торговли и сможет системно исполнять торговые правила. По мере развития проекта стало ясно, что робот и исследовательская лаборатория — лишь средства. Исследовательская функция компании нужна для того, чтобы отличать устойчивое рыночное преимущество от случайности, ошибок данных и особенностей симуляции, а затем превращать доказанное преимущество в реализуемый чистый денежный результат.

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
H-B прошла только узкую синтетическую проверку механики, не рыночную проверку:
- h_b_signal.py — pure causal long-only H1 predicate; shock на t, стабилизация на t+1, planned entry на t+2.
- h_b_regime.py — adapter к frozen candidate H-B-RANGE-DEFAULTS-v1; конфигурация унаследована от существующих defaults, не оптимизирована по market PnL.
- h_b_fill.py — offline reference check actual open[t+2] строго между stop и target; это не реальный fill model.
- Финальный bounded Research CI #45466778550 на code commit 84d1da812d1958cbb32f3789895c7d4b56e45488: 13 signal tests, 6 regime adapter tests, 8 next-open geometry tests; полный configured deterministic workflow SUCCESS.
- Synthetic accepted fixture имеет gross reward/risk 0.4. Это искусственная тестовая геометрия, не expectancy и не оценка реальной торговли.
- Нет market PnL, edge, spread/queue/slippage/funding model, engine integration, sizing, persistence или exit lifecycle.

**Решение: H-B SYNTHETIC MECHANICS COMPLETE / FROZEN.** Не добавлять lifecycle, manager, sizing, exits, новые H-B filters или новые strategy families. Продолжение возможно только при появлении легитимного независимого пути market validation, который укладывается в разрешения пользователя и data/provenance gates. До этого — read-only аудит уже имеющихся данных и документационная гигиена.
## 5. Данные и ограничения, которые блокируют рыночные выводы

В provenance-аудитах и новом sample validation выявлены следующие пробелы:
- Bybit-native trades/L2/mark теперь доступны и проверены на одном часу, но непрерывный H1 period и полный historical coverage ещё не приняты;
- trades имеют documented reconnect gaps до примерно 3 минут около 02:00–02:50 UTC; provider backfill пока не опубликован;
- известные Bybit orderbook missing hours: 2025-11-26 10 — 2025-12-26 19 и 2026-04-13 15 — 2026-04-14 21 UTC;
- у provider есть unresolved note о REST depth snapshots, опубликованных как orderbook resets с update IDs от другого depth stream; snapshot/sequence transitions требуют проверки;
- mark-price sample после 2026-09 release имеет полное состояние, но funding_rate/next_funding_time — не settled funding cashflow ledger;
- point-in-time universe, включая delisted/suspended инструменты — частичный/неподтверждённый;
- dated instrument specifications и risk tiers — частичные/неподтверждённые;
- dated account/symbol fee assumptions — не подтверждены.

Tardis sample также доступен, но normalized L2 CSV не сохраняет Bybit matching-engine cts и sequence IDs; поэтому для queue replay он вторичный источник. Paid raw replay API не включён в текущее разрешение.

**До снятия data/method gates:**
- не запускать новые market-PnL backtests, parameter sweeps или strategy replay;
- не подключать Bybit private/account API, ключи или trading endpoints;
- не запускать paper/live trading и не размещать реальные ордера;
- не выдавать Binance proxy, Tardis normalized L2 или OHLC fill за доказательство точного Bybit execution.

Разрешены публичные исторические downloads/samples/backfills в ограниченном scope, их provenance/coverage/schema/hash validation и необходимые scripts/workflows. Платные подписки/API keys требуют отдельного согласования. Также разрешены безопасные статические аудиты, deterministic synthetic tests и точечные исправления подтверждённых дефектов.

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

## 10. Текущая точка на 2026-11-25

- **Цель:** доказать или опровергнуть устойчивый net edge после реалистичных издержек и независимой проверки. Доказанного edge нет.
- **H-A:** проверенная конфигурация отклонена; не тюнить на использованных folds.
- **H-C:** mechanics behind default-OFF flag; проверенная proxy-конфигурация не показала прибыльного преимущества; не продолжать tuning на использованном окне.
- **Базовая H1/E01–E13:** deferred/no edge. Исторические proxy результаты не являются актуальным доказательством; есть survivorship/PIT и execution gaps.
- **H-B:** synthetic signal + frozen regime adapter + next-open geometry complete/frozen. Final bounded Research CI #45466778550 passed 13 + 6 + 8 tests. Synthetic gross R/R fixture 0.4. Это не market PnL и не edge. Никакого engine lifecycle/exit/persistence/sizing integration.
- **Данные:** шесть старых CryptoFetch ZIP остаются Binance-style proxy. CryptoHFTData BTCUSDT 2026-11-01 12:00 UTC: trades 25 700 rows; L2 655 729 rows/105 736 updates; mark_price 5 728 rows. Все три Parquet файла скачаны, schema и базовые инварианты проверены; L2 book восстановлен без crossed states. Отчёт — Actions run #45625276612 / artifact #15028337972. Event-time сверка 2026-11-01 с Tardis (соседние receive partitions): 360 226 Tardis trades, 360 227 CryptoHFTData rows, 0 missing, 1 extra в 18:11:26.056 UTC. Отчёт — run #45629444005; старый same-receive-hour summary не использовать. L2 cross-check event-hour 12:00: 655 631/655 631 updates exact match после загрузки CryptoHFTData receive-hour files 12 и 13; 11 updates event_time 12:59:59.934 лежали в receive-hour 13. Отчёт — run #45626768545 / artifact #15027383267. Ingestion rule: adjacent receive-hour files + event-time filter. Tardis normalized L2 не содержит cts/sequence IDs.

- **Историческая trade-проверка (event-time corrected, run #45632069094):** 2025-07-01 — Tardis 1 116 359, CryptoHFTData 2 683 702, 521 missing / 1 567 865 extra, систематический тройной multiplicity в активных часах. 2025-08-01 — 2 360 190 vs 2 360 132, 102 missing / 44 extra. В обоих месяцах trade_id=0 в проверенных partitions; это структурно непригодный идентификатор, payload dedup небезопасен. 2026-11-01 — 360 226 vs 360 227, 0 missing / 1 extra. 2025-07-02, 2025-07-03 и 2025-08-15 — Tardis HTTP 401, не оценены (access failures, не нулевые данные). Повторное расширение run #45633254036 не добавило новых сравнимых дней. Июль/август NOT ACCEPTED для L2 replay; ноябрьский один день не доказывает качество всего архива.
- **Первичная проверка Bybit archive (run #45636437695):** 2025-07-01 — официальный 1 116 387 строк, CHD 2 683 702, 521 missing / 1 567 836 extra; все CHD trade_id нулевые, 0/1 115 866 IDs совпали (REJECTED). 2025-08-01 — 2 360 261 vs 2 360 132, 129 missing, все CHD IDs нулевые (NOT ACCEPTED). 2025-09-01 — 1 606 155 vs 1 606 086, 69 missing, все CHD IDs нулевые (NOT ACCEPTED). 2026-11-01 — полное совпадение payload + 360 227 hashed IDs (PASS только sample). Artifact #15034026218.
- **Проверка семантики trade_id:** документация CryptoHFTData для Bybit утверждает, что trade_id — стабильный 64-bit hash UUID и что reconnect REST/WS дубли удаляются по нему. В июльском и августовском sample trade_id=0 у всех строк проверенных receive partitions (один unique ID на partition). Это противоречие wire spec и фактических данных; причина не установлена. order_type=Market, напротив, ожидаемая заглушка. См. [Bybit wire format](https://www.cryptohftdata.com/docs/wire-format-bybit) и [trade schema](https://www.cryptohftdata.com/docs/rest-trades). До ответа поставщика/исправления sample не принимать эти периоды для dedup или L2 queue replay.
- **Критические пробелы:** нет принятого полного independent period, H1 bars coverage, settled funding ledger, dated instrument/risk-tier history, PIT tradable universe и account/symbol fee assumptions. У CryptoHFTData известны reconnect gaps и missing orderbook hours; см. Board и Minimum Viable Edge Validation.
- **Разрешения:** пользователь разрешил публичные исторические downloads/samples/backfills и их проверку. Не разрешены private/account API, paid subscriptions, paper/live trading, реальные ордера. Market-PnL backtests/sweeps/event studies остаются заблокированы до приёмки выборки и preregistration.
- **Рабочая ветка:** research/market-regime-v1-main; HEAD при последней сверке 1e08da2cff4b07159b80664da79c70110b2f80ad. Последний принятый code/test CI #45466778550 относится к 84d1da812d1958cbb32f3789895c7d4b56e45488; последующие commits в цепочке документируют freeze.
- **PR:** #15 (Compass) и #16 (H-B signal contract) merged в research branch; PR #13 закрыт как superseded by PR #15; старый context-recovery protocol не является параллельным источником инструкций. main не изменялась.
- **Следующий безопасный режим:** ограниченный CryptoHFTData backfill одного заранее выбранного инструмента после фиксации candidate/execution contract; сначала соседние часы, reconnect/missing-hour audit и settled funding/spec gates. Market PnL пока не запускать.


### 2026-11-25 — разрешение и первый реальный Bybit historical sample
- Пользователь явно разрешил поиск и получение публичных независимых исторических рыночных данных. Это не включает private/account API, paid subscriptions, paper/live trading или реальные ордера.
- CryptoHFTData BTCUSDT 2026-11-01 12:00 UTC: скачаны trades (459,261 bytes), orderbook (6,209,377 bytes), mark_price (95,633 bytes). Все три Parquet schema совпали с ожидаемыми; gzip/Parquet decode завершён.
- Trades: 25,700 rows, 25,700 unique IDs, 0 null/duplicate IDs, 0 timestamp regressions.
- Orderbook: 655,729 rows, 1 snapshot, 105,736 update messages, 0 crossed message states, итоговая книга 50 bid/50 ask; final_update_id/last_update_id не регрессировали и не имели скачков в этом sample. prev_final_update_id отсутствует; transaction_time отсутствовал только на 100 snapshot rows.
- Mark Price: 5,728 rows; mark_price/index_price/funding_rate/next_funding_time не null. Это не settled funding ledger.
- Cross-feed timestamp check: Bybit publicTrade.T и orderbook.cts на общей миллисекундной шкале; 4.482% trade rows имеют точное совпадение миллисекунды с book update, nearest book timestamp median 5ms / p95 14ms / p99 18ms / max 75ms. Не трактовать это как причинную связь или гарантированный порядок доставки.
- Full-day trade cross-check: Tardis и CryptoHFTData совпали по всем 360 226 Tardis rows; у CryptoHFTData одна дополнительная запись в 18:00 UTC, без дубля trade ID; расхождение не разрешено.
- L2 cross-check: 655 631 update rows совпали точно только после чтения receive-hour 12+13. Это выявило partition-boundary effect, не потерю данных. Сверка message.ts/event_time не валидирует cts/sequence; Tardis normalized L2 их не сохраняет.
- Report artifact: Actions run #45625276612, artifact #15028337972; сырые файлы не загружались в публичный artifact.
- Tardis BTCUSDT 2026-11-01 full-day trades/L2 sample тоже скачан и прошёл gzip/CSV validation. Его normalized L2 schema теряет cts/sequence IDs; использовать только как secondary cross-check, не как основной queue replay input.
- Решение: data access permission + one-hour sample gate пройдены. Full data coverage, reconnect gaps, missing hours, settled funding, dated specs/risk, PIT universe, fees и candidate execution contract остаются блокирующими. Ни market-PnL backtest, ни parameter sweep не запускались.

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


### 2026-11-24 — H-B economic boundary after synthetic fill geometry
- The synthetic accepted next-open example has gross reward/risk 0.4 (reward 2 per unit vs risk 5). The fill helper intentionally checks only strict positive geometry, not economic acceptability.
- No minimum R:R threshold is frozen; none should be invented or tuned on already-used folds. A valid economic gate requires explicit fees, spread, slippage, funding, fill probability and win-rate assumptions.
- Therefore H-B remains mechanics-only and must not proceed to engine lifecycle. Current data/provenance and authorization gates block the independent market validation needed to decide economic value.


## 2026-11-24 — H-B scope freeze

- Final bounded Research CI run `45466778550` on `84d1da812d1958cbb32f3789895c7d4b56e45488` completed SUCCESS after deleting the temporary exit module/tests and removing all CI references. H-B signal predicate tests: 13; frozen regime adapter: 6; next-open fill geometry: 8. All corresponding workflow steps and the full configured deterministic workflow passed.
- A temporary standalone H-B exit evaluator was explored and removed before acceptance because it crossed the agreed scope boundary. No active `h_b_exit.py` or exit-test layer remains. Do not infer it is part of the accepted design from intermediate commits.
- H-B has completed its narrow synthetic mechanics purpose. The synthetic accepted fill example has gross reward/risk 0.4; this is not an estimate of live expectancy, but reinforces that geometric validity is not economic evidence.
- Freeze further H-B code, engine integration, persistence, sizing, exits and new strategy families. Current data and authorization gates do not permit independent market validation. Additional implementation would add activity without resolving edge.
- Until a legitimate validation route is available under the user's explicit permissions and data/provenance requirements, restrict work to read-only audits, existing-data provenance/coverage review and documentation/decision hygiene.


- Added `H-B-SYNTHETIC-001` to `EXPERIMENT_LEDGER_RU.md`, recording the exact causal signal contract, frozen default regime candidate, 13/6/8 synthetic test suites, final Research CI, the 0.4 synthetic gross R/R fixture, and all non-claims/limitations. This is a mechanics record, not a market experiment.

### 2026-11-24 — актуализация H-B freeze и data inventory
- Сверены текущий branch HEAD, последние commits, Research CI и архивный audit artifact. Принятый H-B результат — только synthetic mechanics pass (13 signal + 6 regime + 8 fill geometry tests), не market edge. Временный exit layer не входит в accepted design и удалён.
- Текущий Git tree содержит шесть CryptoFetch ZIP; исторический archive audit artifact #13187466159 сообщает 67 valid CSV members, 64 non-empty/legacy-eligible, 3 empty, zero irregular intervals, zero conflicting overlaps and zero longest-file timestamp loss in duplicate comparisons.
- Отредактирован верхний статус карты, чтобы он не противоречил более позднему scope-freeze log. Никаких данных не скачивали, Bybit/API/runner не подключали, market-PnL не запускали.


### 2026-11-24 — read-only audit of historical evidence

- Reconciled E01–E14, H-A/H-C, legacy holdout/walk-forward reports and ENG-EXEC-037–041 against their primary reports and Ledger. E01–E03 have a provisional engine-fee caveat requiring commit-level provenance; positive OHLC limit results remain execution-model upper bounds. E04/E07 are selection/multiple-testing exposed; E08 confounds factors; E09–E11 do not establish body-gate edge (E11 shared-capital net remains negative); E12 is descriptive; E13 improves but remains negative.
- H-A and H-C tested configurations are negative after modeled costs and use reused CryptoFetch/Binance-style proxy windows without complete funding/Bybit PIT provenance. E14 is post-hoc attribution, not counterfactual PnL. Legacy holdout reports overlap previously inspected periods and/or have very small trade counts.
- L2/public-trade audits identify unresolved passive-fill realism limits: price-through and cancellation allocation are not modeled; cross-stream event ordering and historical trade sequence fields are unverified. The replay cannot be promoted as validated maker execution.
- Conclusion: prior experiments provide useful negative/exploratory evidence, not a defensible positive edge claim. No backtest, sweep, event study, data collection or exchange connection was performed. Project remains BLOCKED pending a legitimately permitted independent validation route.
- The documentation-only reconciliation sequence includes the E01–E04/E07 exit-cost provenance updates in Experiment Ledger and Research Board; no strategy code or market results changed. Check the live branch ref at the next task start rather than treating a SHA embedded in this log as current.


### 2026-11-24 — E04/E07 exit-cost provenance follow-up

- Read-only workflow-log and source audit confirms E04 (checkout `4b291265`) and E07 (checkout `a5a98516`) also used engine implementations charging exit fees/slippage from entry notional rather than exit execution notional. E01–E03 were already confirmed on the same pre-fix engine family. Therefore E01–E04 and E07 historical net-PnL totals are not reusable as accurate net results; E04/E07 also retain their independent selection/multiple-testing limitations. No PnL was recalculated; see Experiment Ledger for exact workflow and engine blob provenance.

### 2026-11-24 — E08–E13 exit-cost provenance reconciliation
- Exact Actions checkout/source review confirms E08, E09, E10, E11 and E13 used engine versions whose `_close_position()` charged TP1/final exit fees and slippage from entry notional rather than exit execution notional. E12 is descriptive context analysis with no PnL and is not affected by this accounting defect.
- Confirmed affected net-PnL experiments now include E01–E04, E07–E11 and E13. E05/E06 remain unclassified pending exact commit-level review. Preserve non-PnL descriptive observations, but do not use affected net aggregates for ranking or economic claims. No recalculation or new market run was performed.


### 2026-11-24 — E05/E06 classification correction
- E05 is a failed Bybit public-data download attempt (HTTP 403 across tested endpoints), not a PnL experiment; it is a data-access blocker, not affected by exit-cost accounting.
- E06 is not merely descriptive: its signal/trade diagnostic workflow ran `UnifiedQuantEngine.run_simulation_pass()` on Binance proxy data. Exact checkout `9601f4d855f69d58e7353655a0c62060f519de13` uses the pre-fix engine blob `e4501bd...`; therefore E06's reported net-PnL is affected. E12 remains descriptive-only. Confirmed affected PnL scope is E01–E04, E06–E11 and E13.

### Salvageable historical observations after exit-cost audit (2026-11-24)

A read-only review of E06/E11/E12 artifacts verified that the old PnL defect does not erase every raw observation:
- E12 is a descriptive-only artifact (4,249 hourly rows; 47 included symbols). Its completed-bar breadth, rolling returns, efficiency, ATR and cross-sectional dispersion can be retained as descriptive features. Joining its rows to E11 baseline selected-signal timestamps reproduced 499 / 499 / 730 hours and the reported fold medians exactly. Fold 2's selected-signal hours had lower broad 72h breadth/return, ATR and IQR than folds 1 and 3.
- E06/E11 raw candidate signal features are computed from historical candles plus the completed signal candle before engine replay; they may be retained for exploratory description. Deduplicate E11 factorial copies by (symbol, signal_ts). Forward-return columns are future labels, not features. Exclude engine-derived fill/status/trade selection and all trade/PnL outputs from reliable evidence.
- The timestamp stored as Candle.ts is the H1 bar OPEN; features using its close are only available at bar close (ts + 1 hour).
- This is not evidence of edge: the three folds are contiguous, cross-sectionally correlated, based on a fixed Binance-style proxy universe and already inspected. The compression q25 rule was formed on the same sample and is not independently validated. No new market test or PnL calculation was performed.

Current boundary: preserve raw signal/context observations as exploratory historical data; do not use them to tune/promote filters or claim profitability.


E08–E13 artifact cross-check: raw candidate feature rows are constructed before engine replay and can be retained as exploratory descriptions; future-return columns are labels only, while engine status/fill/trade outputs remain tainted. Candidate rows repeat across configs and must be canonicalized/deduplicated. This does not change the NO EDGE / DEFERRED status.


The artifact-level salvage classification now covers E01–E13: E01–E03/E07 are summary-only; E04/E06/E08–E11/E13 contain candidate signal CSVs with pre-engine raw features (exploratory only, canonicalized/deduplicated); E12 is descriptive-only hourly context; E05 is a failed data-access attempt. All engine-derived fills, trade selection/status and PnL remain excluded from economic evidence. No new market calculation was performed and the strategy status remains DEFERRED / NO EDGE.


Candidate deduplication across E04/E06/E08–E13 found only two main historical signal samples: the same 1,012 five-symbol candidates repeated across E04/E06/E08/E09 configurations, and the same 9,236 47-symbol common-timestamp candidates repeated in E11/E13 (E10 overlaps all 9,236 plus 79 extra timestamps due per-symbol coverage). E12 summarizes E11 timestamps, not a separate sample. Experiment IDs/configuration rows are not independent replications.


### 2026-11-24 — official D5/D6 endpoint boundary re-confirmed

- Current V5 `instruments-info` documents online instrument specifications and lifecycle timestamps, but no historical version/time query; max order quantity fields are explicitly adjusted twice monthly. `instrument-summary` is also current-only in its documented contract.
- Current `risk-limit` returns the current symbol tier table, not historical tier versions. Bybit's own risk-limit help article says the account's applied tier changes dynamically with positions, active orders and mark price; account-level replay therefore needs both dated exchange tier schedules and account-state history.
- Official historical-data downloads are referenced by the public-trades documentation, but no historical spec/risk archive is established by that reference.
- D5 and D6 remain NOT ACCEPTED. No archives/API collectors/PnL runs were started. Detailed evidence: [ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md, section 38](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#38-official-market-api-and-risk-limit-documentation-historical-data-boundary).


### 2026-11-24 — Bybit official docs Git history reviewed

- Public repository `bybit-exchange/docs` has versioned V5 instrument and risk-limit documentation from 2022-12-05 onward. Instrument page history contains 100 commits through the queried range; risk-limit page contains 34.
- Recovered schema milestones include status-filter expansion (2023-04), funding-bound fields (2024-02), order-size field changes (2024-02 and 2025-10/11), risk-limit pagination (2024-05 and page-size reduction 2024-12), PreLaunch risk-limit support (2025-08), periodic order-size adjustments (documented 2026-02), and further instrument schema/price-limit changes in 2026.
- This is useful evidence of **schema chronology**, not a complete historical archive of per-symbol numeric values. Documentation code examples contain timestamped but limited/possibly illustrative payloads; the risk-limit example is still a single BTCUSD tier with ellipsis.
- D5/D6 remain NOT ACCEPTED. Details and primary commit links: [ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md, section 39](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#39-bybit-official-documentation-git-history-schema-chronology-recovered-historical-values-not-recovered).


### 2026-11-24 — third-party dated Bybit metadata snapshots identified

- Found a 2026-09-29 mainnet fixture in `mannar-hielal/crypto-dashboard`: 9 Spot + 9 Linear instrument rows and risk tiers for 9 symbols. Its recorder source documents public GETs, but stores only result objects and one capture-start timestamp, not per-response server times.
- Found raw API-envelope snapshots in `aoventuresdomain-cloud/sleeve-fund`: a manually pasted/hand-checked BTC risk-tier table dated 2026-10-15; on 2026-10-21, raw BTC instrument info plus raw risk tiers for BTC/ETH/SOL/XRP. The Oct 21 workflow preserves response envelopes and timestamps.
- Exact cross-source comparison: all 35 risk tiers for BTC/ETH/SOL/XRP match between the 2026-09-29 and 2026-10-21 projects; BTC's manually pasted Oct 15 tier table also matches the Oct 21 raw response, but is corroboration rather than an independent recorder capture. BTC Linear instrument row matches 2026-09-29 vs 2026-10-21.
- BNB Linear tick 0.1 in the Sep 29 fixture is consistent with Bybit's Oct 12 official 0.1→0.01 announcement and the later Oct 12 drift correction in the third-party project.
- **Status correction:** external partial candidate snapshots now exist. D5/D6 are no longer "no candidate snapshots found", but remain PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED due to short date coverage, partial universe, capture/provenance limits and absent account-state history. No data was imported and no market-PnL run was authorized.
- Full evidence and exact file/commit links: [ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md, section 40](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#40-third-party-dated-bybit-metadata-snapshots-partial-raw-captures-and-cross-source-replication).


### 2026-11-24 — exact E11/E13 universe coverage measured

- Read-only inspection of historical E11/E13 workflow logs recovered the exact same 47-symbol universe in both experiments (47 fold-eligible out of 50 valid H1 symbols; 4,321 common H1 bars). This is the fixed Binance-style proxy universe, not a Bybit PIT universe.
- The 2026-09-29 Bybit Linear metadata fixture overlaps **9/47 = 19.1%**: ADA, AVAX, BNB, BTC, DOGE, ETH, LINK, SOL, XRP.
- 2026-10-21 raw captures cover BTC instrument specs (**1/47 = 2.1%**) and BTC/ETH/SOL/XRP risk tiers (**4/47 = 8.5%**). The extra nine Spot rows are not Linear coverage.
- The 38 uncovered proxy symbols are listed in Section 41 of the acceptance ledger.
- This quantifies coverage of the existing research sample only. It does not establish Bybit PIT listings, full-market coverage or effective-dated history. D4 remains partial/unverified; D5/D6 remain PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED.
- Follow-up read-only verification downloaded only the existing E11/E13 result-artifact ZIPs (not market archives): both 50-row universe manifests and all six archive SHA-256 entries match exactly; 47 symbols included, same three exclusions. No market/PnL experiment, collector or Bybit API request was run.
- Full audit: [ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md, section 41](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#41-coverage-of-dated-metadata-snapshots-against-the-exact-e11e13-47-symbol-proxy-universe).


### 2026-11-24 — sbt2 daily Bybit snapshot lead assessed

- `sbOogway/sbt2` can write one dated current-spec snapshot per symbol/day, but its public repo excludes local `/data/` and contains no published raw Bybit daily archive. Its snapshot captures only the lowest risk tier as margin fields, not the full D6 tier table.
- D5 is a potential lead only if the maintainer's local dated files become independently available; D6 is insufficient as implemented. No API call, archive download, collector or PnL run. Details: [acceptance ledger Section 43](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#43-sboogwaysbt2--daily-instrument-snapshots-are-a-source-lead-not-a-public-archive).


### 2026-11-24 — third raw risk-tier source found

- CandleViewer preserves full public REST envelopes for BTCUSDT and ETHUSDT Linear risk limits on 2026-10-25 18:45 UTC, 35 tiers each, no auth. Its README documents the capture process and its manifest gives the per-file capture date.
- All 35 tier rows/fields for BTC and ETH match exactly with sleeve-fund's 2026-10-21 raw captures; they also match the 2026-09-29 crypto-dashboard fixture. This gives three-repository agreement for BTC/ETH across three observation dates.
- CandleViewer's instrument-before/after examples are documented-shape fixtures, not live instrument-info captures. No new D5 evidence.
- A separate Oct 6 report prints tier-1 summaries for BTC/ETH/SOL/BNB/XRP matching Sep 29 values, but its referenced raw results.json is not committed; secondary corroboration only.
- Unique D6 raw-replicated symbols remain BTC/ETH/SOL/XRP = 4/47 (8.5%); new contribution is additional dates/repository for BTC/ETH, not broader universe coverage. D6 remains PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED.
- Full audit: [ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md, section 44](ALT_SYSTEM_DATA_ACCEPTANCE_001_RU.md#44-third-independent-raw-risk-tier-capture-candleviewer-2026-10-25).


### 2026-11-25 — ограниченный BTCUSDT GET pilot

Пользователь разрешил пять точечных публичных V5 GET для BTCUSDT (H1, Mark, Funding, текущие specs/risk tiers). Рабочая среда не смогла получить ответы: web retrieval сообщил URL inaccessible/403, container HTTPS не прошёл DNS resolution. Ни один валидный Bybit JSON не получен; это ограничение сетевого маршрута среды, а не доказательство отказа Bybit. Gates D1–D6 не изменились. Повторять только при появлении разрешённого прямого маршрута или при предоставлении пользователем исходных ответов; прокси/зеркала не использовать.


### 2026-11-25 — независимый holdout повторно проверен

В repo нет accepted independent dataset для H1 D48+EMA: шесть CryptoFetch proxy ZIP заканчиваются не позднее 2026-10-27 и уже использованы. Старый Bybit holdout script — другая гипотеза (D20, 11 ранее выбранных Binance symbols, independent per-symbol capital, approximate funding, Last-price exits) и сам указывает на календарное пересечение с Binance study; нужных Bybit файлов нет. Archive workflow требует self-hosted по умолчанию и предупреждает о hosted US egress block; self-hosted/collector запрещены. Значит текущее ограничение точнее формулируется как **BLOCKED BY DATA + INDEPENDENCE**. Не строить runner и не перемаркировать старые folds. Полный аудит — acceptance ledger Section 49.


### 2026-11-25 — official Bybit trade archive cross-check: transition window completed

Actions run #45639262986, artifact #15033673197. The run completed; its red conclusion is a data mismatch verdict, not an infrastructure failure. Four BTCUSDT UTC dates were compared against Bybit's official daily trade archive, including payload and documented trade-ID hash:

- **2026-05-01:** 1,507,843 official rows vs 1,507,453 CryptoHFTData rows; 390 missing, zero extra. All 1,507,453 CryptoHFTData IDs are zero; 0 hashed-ID matches. REJECT.
- **2026-06-01:** 2,307,090 official vs 2,307,067 CryptoHFTData; 23 missing, zero extra. All 2,307,067 comparable hashed IDs match. NOT ACCEPTED because of missing trades.
- **2026-08-01:** 531,091 official vs 531,087 CryptoHFTData; 4 missing, zero extra. All 531,087 comparable hashed IDs match. NOT ACCEPTED because of missing trades.
- **2026-09-01:** 2,017,359 official and CryptoHFTData rows; zero missing/extra; all 2,017,359 hashed IDs match. EXACT_PAYLOAD_AND_ID_MATCH for this date only.

Combined with earlier checks: the tested ID repair boundary is between May and June 2026; completeness is still imperfect in June and August; September 1 passes. This is a sparse set of daily samples, not a claim that every intervening day or the whole period is complete. The workflow now runs by manual dispatch only to avoid repeated downloads.

**Correction to the immediately preceding chat status:** run #45639262986 did not test September 2 and did not test L2 synchronization. It tested May 1, June 1, August 1 and September 1 trades only. Do not cite it as an L2/trade synchronization result.

### 2026-11-25 — first strategy-path simplification decision

The next experiment should not be blocked on L2 queue reconstruction if the chosen execution contract is taker-only. L2 remains necessary for a maker/queue claim, not for a conservative taker-only first pass. However, the frozen H1 D48+EMA preregistration currently specifies maker entry with OHLC penetration and maker TP1; switching its flags is a different execution hypothesis and must be separately frozen before any market PnL. Engine mechanics show market-mode pending entries fill at the next bar open, while maker-mode entries use an intrabar OHLC touch proxy. A taker-only variant must explicitly fix next-bar entry timing, taker exits, fee/slippage stress, ambiguous-bar policy, funding and sizing; it must not inherit the old D20/11-symbol holdout runner or its invalid assumptions.

**Immediate decision gate:** first determine whether a single-symbol BTCUSDT H1 taker-only experiment can be supported by a sufficiently long independent Bybit period with verified H1/Mark/funding inputs and usable dated BTC specifications/risk constraints. If yes, preregister that narrow experiment and run only after the existing accounting and data gates are satisfied. If not, state the exact missing input and stop adding unrelated infrastructure. No L2 expansion, multi-symbol universe rebuild, new general-purpose runner, market PnL, paper trading or live orders are authorized by this decision.

The north-star remains realized positive net expectancy after all costs and risk, not test count, code volume, GitHub activity or data archive size.


### 2026-11-25 — static feasibility audit of the BTCUSDT taker-only shortcut

Read-only inspection of the frozen H1 preregistration, shared-capital runner and engine resolved an important execution detail:

- The current runner hardcodes `maker_entry_and_tp1=True` and `maker_tp1_and_target=False`. Because the latter explicitly overrides exit behavior, the actual frozen implementation is **maker-proxy entry + taker TP1/final exits**, not maker TP1/target exits.
- The runner does not expose a ready taker-only switch in its frozen config; a taker-entry arm would require a small, explicit execution ablation and a separate preregistration. It must not silently replace the frozen primary.
- In the engine, market-mode pending entry is filled at the next H1 bar open, subject to the existing max-chase rejection. Limit-mode entry uses an OHLC touch/penetration proxy. Thus a taker-entry variant can avoid L2 queue reconstruction, but it still needs a frozen rule for next-open price, gap/chase rejection and costs.
- Current base model constants are taker fee 5.5 bps and taker slippage 2.25 bps per executed leg; the H1 preregistration's primary cost multiplier is 2.0x. The runner applies stress multipliers to fee/slippage constants. These are assumptions, not verified historical realized fills.
- Protective stop/TP trigger detection in the audited engine uses Last/Trade OHLC; liquidation checks use Mark candles. Same-bar stop precedence is conservative, but OHLC cannot reveal intrabar event order. The taker-only contract must preserve explicit stop-first ambiguity handling and distinguish trigger price from modeled execution cost.

**BTC single-symbol feasibility remains blocked, for specific reasons:**
1. No Bybit-native H1 or Mark candle files are present in the repository; the earlier five-endpoint BTC pilot returned no valid response. D1/D2 remain unverified.
2. No settled BTC funding history has been accepted for the intended period. Funding interval/formula regime and exact settlement cashflow still need an evidence-backed treatment; D3 remains unverified.
3. BTC has partial dated specification/risk-tier candidate snapshots from Sep/Oct 2026, but they do not cover a continuous historical period or establish effective-time changes. D5/D6 remain not accepted.
4. The official-vs-CryptoHFTData trade archive match on 2026-09-01 is a one-day integrity sample only; it is not H1/Mark/funding coverage and does not create an independent strategy holdout. The wider Bybit period remains absent. The old proxy data are contaminated by prior research.

**Decision:** do not write a taker-only runner or run market PnL yet. The minimum next useful input is a user-provided, provenance-preserving BTCUSDT Bybit public-data package for one sufficiently long, genuinely unseen interval: H1 trade candles, matching H1 Mark candles, complete settled funding events, and the available dated BTC instrument/risk evidence. Include original endpoint/archive identifiers, UTC capture/download details, raw response/files and SHA-256; do not normalize away missing rows. Until such a package exists, stay in design/static-audit mode. No new API attempts, collectors, archive expansion, PnL, paper or live trading under the current scope.

This audit narrows the implementation change to a possible **entry execution ablation only**; it does not establish that taker-only has positive expectancy or that the data gate is close to passing.
