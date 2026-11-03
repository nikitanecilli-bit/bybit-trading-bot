# Quant Lab и загруженные исследовательские материалы — аудит и сортировка (2026-11-03)

## Резюме

Пакет полезен как набор исследовательских идей, протоколов и UI-прототипов. Он **не является готовой версией v16 и не должен подключаться к активному H1 engine целиком**. В материалах смешаны:
1. методология и гипотезы;
2. прототипы математических признаков;
3. прототипы анализа журнала;
4. UI-демо с намеренно встроенными синтетическими закономерностями;
5. проектное ТЗ на Quant Lab.

Файлы сохранены. В активный торговый контур ни один из legacy Python/JS модулей этим аудитом не подключался.

## 1. Новый файл пользователя

- [Гипотезы пользователя — исходный документ](hypothesis_inputs/Гипотезы_пользователя_2026-11-03.md)
- Исходник загружен без смыслового редактирования, 842 строки.
- Роль файла: входной backlog гипотез, а не инструкция автоматически менять стратегию.
- Перед каждым экспериментом нужна карточка-предрегистрация: гипотеза, причинный механизм, признаки as-of, target, baseline, dataset hash, run_id, параметры, издержки, число попыток, критерий успеха и правило остановки.
- Сначала использовать уже имеющиеся результаты и не повторять ранее отвергнутые проверки без новой причины.

## 2. Классификация файлов main

| Материал | Статус | Решение |
|---|---|---|
| `docs/audits/Фундаментальный_Квантовый_Аудит_и_Матрица_25_Гипотез_Альфы_v2.md` | Полезная методология и каталог H-01…H-25/R-01…R-04 | Сохранить как reference; адаптировать приоритеты под текущий H1-проект |
| Файл `...v2-1.md` | Полностью идентичен v2 по Git blob SHA | Дубликат с суффиксом загрузки; оставить для provenance, считать canonical-файлом `...v2.md` |
| `docs/audits/AI_audit_dashboard.md` | Сильная QA-спецификация: false discovery, интервалы, импорт, run_id, holdout, гипотезы | Сохранить; результаты внутри — синтетические демонстрации качества аналитики, не результаты торгового бота |
| `docs/operations/Оптимизатор расхода токенов.md` | ТЗ на AI Snapshot, Causal Metrics Library, Numbers Linter и Skill | Сохранить как design brief; это не реализованный Quant Lab и не готовый skill |
| `research/legacy_tools/Institutional Quant Math Core (Part 1).py` | Набор изолированных feature-прототипов | Оставить в legacy; отдельные функции можно переносить только после unit/property/prefix-invariance tests |
| `research/legacy_tools/Quant Pattern Miner & Survival Optimizer (Part 2).py` | Прототип статистики/майнинга | Оставить в legacy; текущие оценки нельзя использовать как доказательство edge или counterfactual PnL |
| `research/legacy_tools/Institutional V16 Bridge & Enriched Runner.py` | Неисполняемый и логически небезопасный bridge | Не запускать и не подключать; см. конкретные дефекты ниже |
| `dashboards/quant_analytics/Quant Analytics Dashboard v2.3.html` | Самостоятельный UI-прототип с импортом CSV/JSON и seeded demo | Сохранить как demo/инструмент просмотра; не считать backtest engine |
| `dashboards/quant_analytics/Quant Analytics Dashboard v2.2 + AI Lab (Full Single-File).html` | Более ранняя самостоятельная версия | Архивировать; не развивать параллельно v2.3 без отдельного решения |
| `dashboards/quant_analytics/Quant AI Lab Plugin ... (Complete).js` | Плагин с UI-renderer и расчётными функциями | Прототип; не интегрирован и не протестирован на текущем journal schema |
| `dashboards/quant_analytics/Quant AI Lab Plugin ... (Part 3.1).js` | Частичный вариант вычислительных функций без полного renderer | Архивная/фрагментная версия; не подключать вместе с Complete |
| `dashboards/quant_analytics/duplicates/*` | HTML-части с теми же blob SHA, что и файлы в родительской папке | Точные копии; сохранить в duplicates для происхождения, не редактировать отдельно |
| `dashboards/quant_analytics/Quant Analytics Dashboard v2.2 + AI Lab (Part 1/2).html` | Составные фрагменты | Архивные исходники; предпочтительнее single-file прототип для просмотра |

## 3. Критические дефекты legacy v16

### 3.1 Bridge — BLOCKED

Файл `Institutional V16 Bridge & Enriched Runner.py` нельзя запускать:

1. Объявление `classQuantV16SignalGate:` синтаксически неверно — отсутствует ключевое слово `class`.
2. Импортируется `Bybit_Trading_Engine_v14_Audit_Fixed`, которого нет в текущем main; bridge также импортирует `quant_math_lab_v16` и `quant_pattern_miner_v16`, тогда как файлы в репозитории имеют другие имена и лежат в другой папке.
3. Даже после механического исправления синтаксиса есть бесконечная рекурсия: `run_v16_pipeline` заменяет `E.QuantStrategyCore.evaluate_signal` на `evaluate_v16`, а `evaluate_v16` вызывает тот же `E.QuantStrategyCore.evaluate_signal`.
4. В toxicity gate вместо среднего исторического объёма передаётся `curr.volume * 0.65`. Поэтому отношение текущего объёма к «среднему» искусственно становится примерно 1.538, и volume-компонент перестаёт измерять относительный объём. Переменная `avg_v` вычислена, но не используется.
5. Фильтр CRR трактует maker-вход как maker+maker round trip. В реальной breakout-сделке стоп обычно taker; funding, spread и реальная цена исполнения не включены.
6. При отсутствии `--data-dir` bridge генерирует synthetic candles. Любой PnL такого запуска — только демонстрация кода, не рыночное доказательство.

Вывод: не «чинить на месте» и не подключать к H1 engine. Если понадобится, переписать как новый адаптер с явным dependency injection, без monkey-patching, с отдельным feature pipeline и тестами.

### 3.2 Math Core — RESEARCH ONLY

- `kaufman_efficiency_ratio` возвращает 0.5 при недостаточной истории. Такой fallback выглядит как нейтральное наблюдение и способен пройти пороговый фильтр; безопаснее возвращать отсутствие значения/ошибку warm-up.
- `hawkes_cascade_intensity` — эвристическая экспоненциальная сумма нормированных candle shocks, а не полноценная оценённая Hawkes point-process модель. Название не является доказательством модели.
- `levy_area_2d` вычисляет ориентированную площадь пути; знак сам по себе не доказывает «умное накопление», причинный lead-lag или ловушку.
- `check_friction_budget_crr` использует фиксированные тарифы и maker+maker для maker-варианта; не учитывает раздельные роли входа/выхода, funding, spread, частичные исполнения и фактический slip. Это не валидный execution gate для текущего движка.
- `is_pullback_toxic` зависит от корректно переданного исторического avg volume; текущий bridge передаёт искусственный знаменатель.
- Для функций нет отдельного test suite, калибровки по Bybit данным и prefix-invariance тестов.

### 3.3 Pattern Miner — NOT VALIDATED

- DSR — приближённая реализация с per-trade Sharpe и параметром `n_trials=25`; число попыток не берётся из общего experiment ledger. Не учитываются все исторические переборы и зависимость сделок. Не использовать как формальную DSR-верификацию.
- `optimize_mae_mfe_survival` не реализует Kaplan–Meier и не выполняет последовательную симуляцию. Он использует финальный PnL и экстремумы MAE/MFE, не знает порядок событий внутри сделки и называет оценку «сэкономленным PnL». Это не доказанный counterfactual.
- Риск восстанавливается как `abs(pnl / r_multiple)`; текущий TradeRecord уже имеет `risk_usdt`, а `r_multiple` — NET R. Следует использовать фактический `risk_usdt`, а не восстанавливать знаменатель из PnL.
- Subgroup miner делит записи пополам по порядку входного списка, не проверяя сортировку timestamps; использует небольшой `min_count=8`, много параллельных сегментов и наивный t-stat без FDR/перестановочной проверки.
- CRR в subgroup tags использует `gross_pnl / r_multiple` вместо фактического `risk_usdt`, не включает funding; дефолты неизвестной стороны/сессии/типа ордера могут незаметно формировать ложные группы.
- Даже после исправления формул это должен быть exploratory miner с preregistered trials и независимой проверкой, а не механизм автоотключения монет.

## 4. Dashboard и плагины

- v2.3 содержит функцию `genDemo(seed, N=180)` и явно хранит `source: 'demo'`; seeded demo имеет заранее встроенные различия по токенам/сессиям. Это полезно для проверки UI и аналитических smoke-tests, но не для оценки торговой доходности.
- Dashboard импортирует пользовательские CSV/JSON. Его метрики и преобразования должны быть сверены с каноническими полями текущего `TradeRecord` прежде, чем использовать отчёт в принятии решений.
- Текущий `TradeRecord` содержит `pnl_usdt`, `gross_pnl`, `r_multiple` (NET R), `risk_usdt`, комиссии, slippage, MAE/MFE, token, direction, order_type, bot_version. Любая аналитика должна использовать эти значения без переопределения R по среднему убытку и без двойного учёта издержек.
- В v2.3 для записей без R используется оценка масштаба риска через `median(gross / r)`; это несовместимо с NET-R semantics и может искажать denominator. Не использовать вычисленный fallback R для сравнительного PnL до отдельной сверки.
- Плагины Complete и Part 3.1 — не взаимозаменяемые релизы; один содержит renderer, другой — неполный расчётный фрагмент. В текущем CI их нет.
- AI dashboard audit предлагает хороший порядок: сначала честный импорт и бухгалтерия, затем интервалы/holdout, затем AI интерфейс. Его синтетические тесты относятся к самому аналитическому инструменту, а не к стратегии.

## 5. Что переносить в активную Quant Lab архитектуру

Переносить идеи, а не старый код:

1. **AI Snapshot**: compact/detailed JSON из подтверждённого run artifact, с dataset/config/code hashes и data-quality flags.
2. **Единая метрика**: единицы, знак, gross/net, fees, slippage, funding, R denominator и portfolio equity должны определяться только канонической accounting library.
3. **Causality/data interface**: as-of timestamps, закрытые бары, point-in-time universe, prefix-invariance и запрет на доступ к будущим барам.
4. **Numbers Linter**: каждое число в отчёте должно иметь `run_id`, путь к метрике, единицу, источник и статус VERIFIED/MISMATCH/UNVERIFIED/STALE/UNIT_ERROR.
5. **Experiment registry**: все гипотезы/пороги/варианты считаются попытками; отвергнутые тесты сохраняются; lockbox не открывается для подбора.
6. **UI**: dashboard может визуализировать только уже рассчитанные результаты и предупреждения; не становится источником истины для PnL.

Это согласуется с текущим engine-first workflow. Не создавать параллельную библиотеку R/PnL и не строить AI Skill до появления валидных snapshots и registry.

## 6. Приоритетная очередь экспериментов для текущего проекта

Новая пользовательская записка содержит 10 общих гипотез; документ v2 — 25 H-гипотез и 4 R-кандидата. Это backlog, а не 39 независимых обязательных тестов.

| Очередь | Направление | Связанные гипотезы | Статус / следующий допустимый шаг |
|---|---|---|---|
| P0-A | Достоверность Bybit данных, датированные instrument specs/risk tiers, Mark OHLC, funding, point-in-time universe | INF-1…INF-5, R-03 | Блокер. На GitHub-hosted runner Bybit public endpoints ранее возвращали 403; без подтверждённого официального архива market PnL не запускать |
| P0-B | Единая baseline H1 и cost decomposition: maker/taker по ногам, spread/slip, funding, net R на фактическом risk_usdt | User H1-1/2, H-01, R-01, R-03 | Использовать существующий engine accounting; не вводить фиксированный CRR=6%/12% без эмпирической калибровки |
| P1-A | Market regime / trend vs chop и волатильность | User H1-5/7/10, H-16/17/18, R-02 | Один заранее заданный простой признак/семейство за раз; только closed-bar as-of; тест на untouched fold |
| P1-B | False breakout / close-back-inside / post-break follow-through | User H1-6, H-05, H-20 | E14 уже обнаружил post-entry association на повторно использованных folds; это не причинная проверка. H-C реализован за disabled flag, но market PnL не запускался. Нужен preregistered signal-time classifier и новый holdout |
| P1-C | Инструменты / relative strength / BTC leader | User H1-3/9, H-13/14/15 | H-A relative-strength replay уже проиграл baseline на трёх reset-capital folds; не повторять ту же идею на тех же folds. Нужны новые data/fold и заранее заданная альтернатива |
| P1-D | Portfolio correlation / shared-capital constraints | H-25 | Проверять на совместной временной линии и общих ограничениях капитала; независимые per-symbol кривые не складывать |
| P2-A | Maker-first / limit pullback | User H1-1, H-02, R-04 | Только после реального bid/ask/L2 или консервативной fill-модели, TTL, пропущенных сигналов и adverse selection; OHLC penetration не является очередью заявок |
| P2-B | Выходы по MAE/MFE, 4-bar kill, trailing | H-20/21/22 | Только последовательная path replay на исходных барах/тиках. Нельзя «пересчитать» по максимальным MAE/MFE как по известному заранее исходу |
| P3 | Ликвидационные каскады, TWAP traces, lead-lag | H-07/08/15 | Отложить: нужны liquidation stream, trade aggressor/L2 или 1s data; свечные proxy недостаточны |

### Обязательная последовательность для каждого эксперимента

1. Сверить с experiment ledger и найти прошлые тесты; определить, что именно нового добавляет тест.
2. Создать preregistration до просмотра результата: сигнал, feature availability timestamp, target, baseline, costs, folds, primary metric, minimum effect, rejection criteria, total trial count.
3. Использовать один baseline, один фактор и одинаковый universe/folds/capital/risk/accounting.
4. Запустить unit/leakage tests; проверить отсутствие look-ahead и правильный порядок событий.
5. Выполнить только на доступных официальных данных; хранить hashes, config, commit и run_id.
6. Оценить net PnL, expectancy, PF, drawdown, costs, trade count, confidence intervals, multiple-testing correction, robustness to ×1.5/×2 costs.
7. Не переносить положительный эффект в engine до независимой проверки на нетронутом holdout и paper/forward evidence.

## 7. Открытые блокеры

- Нет подтверждённого полного Bybit-native H1 archive и датированных snapshots на весь требуемый период.
- GitHub-hosted runner ранее получал HTTP 403 с Bybit public market-data endpoints; доступ self-hosted runner не подтверждён.
- UTA isolated vs Classic isolated режим пользователя не подтверждён; текущая модель — position-level isolated, не полный account engine.
- Нет исторического L2/очереди/partial fills/adverse selection.
- Текущий funding settlement Mark — proxy, а не independently verified settlement price.
- Никакие файлы этого пакета не подтверждают live readiness или положительный net edge.

## 8. Решение по хранению

- Сохранить исходные пользовательские документы и все legacy артефакты без потери истории.
- Не удалять дубликаты в этом проходе: для Markdown v2 и v2-1 подтверждён одинаковый blob SHA; multipart HTML duplicates также имеют те же blob SHA, что исходные части. В дальнейшем ссылаться на canonical-файлы.
- Python-прототипы остаются в `research/legacy_tools/`; dashboard prototypes остаются в `dashboards/quant_analytics/`; документы — в `docs/audits/`, `docs/operations/`, `docs/research/`.
- Не подключать Bridge, Pattern Miner или AI plugin к активному engine/CI до переписывания и независимых тестов.
