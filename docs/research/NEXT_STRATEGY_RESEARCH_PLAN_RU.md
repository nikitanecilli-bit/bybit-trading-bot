# Следующий план поиска устойчивого edge

Дата: 2026-11-03  
Ветка: `research/market-regime-v1-main`  
Статус: PRE-REGISTRATION / NO NEW PNL RUNS

## 1. Текущий вывод

Устойчивая прибыльная стратегия пока не найдена. Не продвигать ни одну конфигурацию E01–E13 к paper/live без дальнейшей проверки.

Подтверждённые ориентиры из существующих отчётов:
- E10 cross-sectional body gate: 47 символов, независимые per-symbol прогоны остаются отрицательными; это не портфельная доходность.
- E11 shared-capital replay: базовая конфигурация дала net -617.62 / -2,970.05 / +409.06 USDT по трём fold; body gate ON также отрицателен в fold 1/2.
- E13 causal compression gate: сумма трёх независимых fold улучшилась с -3,178.61 до -2,741.72 USDT, но все три fold не стали устойчиво прибыльными; fold 3 ухудшился с +409.06 до +167.76.
- E12 показывает, что единый broad-market direction filter не обоснован: в fold 1 часть победителей возникала при слабом broad-market momentum, в fold 3 победители чаще совпадали с положительной breadth/momentum, а fold 2 почти не разделял winners/losers по этим признакам.
- E08/E09 limit-варианты выглядят лучше market, но OHLC touch/penetration fill не моделирует очередь, bid/ask, partial fills и adverse selection. Это пока верхняя оценка maker исполнения, не доказанный edge.

Все результаты выше основаны на Binance-style OHLCV proxy, ранее исследованных периодах и неполной point-in-time выборке. Funding/mark-price и Bybit-native execution не подтверждены. Старые PnL до исправления exit fee/slippage basis не считать окончательными.

## 2. Жёсткий gate перед следующим PnL replay

Не запускать новые рыночные PnL backtests или parameter sweeps, пока не закрыты следующие проверки:
1. Независимая сверка gross PnL, entry/exit fees, slippage, partial TP1, funding и realized/unrealized equity.
2. Проверка инвариантности shared-capital replay к порядку символов и same-timestamp событий. Если порядок влияет на результат, зафиксировать детерминированную event policy и покрыть её тестами.
3. Проверка stop/TP/TP1 при гэпах и неоднозначных OHLC свечах; документировать консервативные правила.
4. Проверка, что каждый отчёт/скрипт использует один и тот же исправленный движок и не читает старые provisional CSV как актуальные.
5. Полная фиксация состава архива, SHA-256, coverage и временных границ каждого инструмента. Не называть доступный архив point-in-time Bybit universe.

Детерминированные unit/regression tests и read-only static audits разрешены; новые рыночные PnL эксперименты пока нет.

## 3. Приоритетные семейства гипотез после закрытия gate

### H-A — Relative-strength breakout (первый приоритет)

Мотивация: E12 показывает, что broad-market direction сам по себе не является универсальным фильтром. В слабом рынке отдельные локальные победители всё же встречались. Поэтому проверять не «рынок растёт/падает», а силу конкретного инструмента относительно доступного universe.

Предварительная конструкция для будущего preregistered test:
- На каждом закрытом H1 баре вычислять causal relative strength инструмента относительно cross-sectional median за 24h и 72h.
- Нормировать локальный импульс на ATR/realized volatility, чтобы не ранжировать только самые волатильные монеты.
- Сохранять возможность long и short, если симметричная логика подтверждена аудитом сигнального движка.
- Не отбирать постоянные top-5 по будущему PnL; ранжировать доступные символы только по информации, известной на timestamp сигнала.
- Сравнивать базовый breakout и breakout + relative-strength rank при одинаковом исполнении, капитале, риске и costs.
- Заранее определить один ранговый порог на train/validation; holdout не использовать для настройки.

Критерий продолжения: улучшение net expectancy и portfolio PF без ухудшения максимальной просадки на нескольких хронологических окнах, а не только рост суммы независимых symbol PnL.

### H-B — Mean reversion в подтверждённом range regime

Мотивация: текущий Donchian breakout систематически слаб в отдельных сжатых/боковых периодах. Вместо попытки фильтровать все плохие breakout-сигналы можно исследовать отдельную логику возврата к среднему.

До PnL replay сначала сформулировать причинный сигнал и правила stop/exit, затем проверить отсутствие look-ahead, реалистичность стопов и частоту сигналов. Не смешивать mean reversion с breakout в одной конфигурации на первом тесте.

### H-C — Breakout continuation quality

Мотивация: локальные volume/breakout thresholds не создали переносимого edge. Проверить post-break continuation features, которые доступны на момент решения: close location within candle range, wick/body balance, volatility expansion после предшествующего сжатия, relative volume trajectory. Не использовать будущие бары для классификации сигнала.

## 4. Дизайн первого разрешённого эксперимента

- Одна гипотеза и один заранее зафиксированный набор правил на эксперимент.
- Один shared-capital portfolio replay; никаких per-symbol независимых счетов как главного результата.
- Полный фактический universe из доступных архивов с manifest и причинами исключения.
- Сохранить per-symbol и per-fold отчёты, включая нулевые/отрицательные результаты.
- Train/validation/holdout строго хронологические. Все уже использованные периоды E01–E13 считать исследованными, не blind holdout.
- Holdout открыть только после фиксации правил; если нет независимого временного отрезка, честно отметить, что исторический OOS отсутствует.
- Fees/slippage стрессовать минимум в нескольких заранее заданных сценариях; maker fills отдельно маркировать как optimistic/upper-bound до появления более точной модели.
- Решение принимать по net expectancy, portfolio PF, max drawdown, recovery, monthly consistency, trade count и устойчивости по fold.
- Никакого подбора порогов по всем folds и последующего объявления лучшего результата.

## 5. Внешние зависимости — отложены

По подтверждённому указанию пользователя:
- не регистрировать self-hosted runner;
- не подключать Bybit API;
- не собирать новые биржевые архивы;
- не запускать реальные ордера.

Возвращаться к этим задачам только после того, как кандидат покажет устойчивый положительный результат на доступных данных и будет понятно, какая конкретная валидация исполнения необходима.

## 6. Следующий технический шаг

Продолжить static audit и deterministic tests, начиная с same-timestamp order invariance в `run_simulation_pass()`, accounting reconciliation и stop/TP execution semantics. Результаты аудита записывать отдельно от рыночных PnL. После закрытия audit gate выбрать H-A как первую проверяемую гипотезу; H-B/H-C оставить отдельными экспериментальными ветками, не объединять в одну большую оптимизацию.

## 7. Фактический archive audit — 2026-11-03

CI проверил все шесть уже имеющихся CryptoFetch ZIP (67 CSV members): 67/67 структурно валидны, 64 имеют не менее 200 баров, 3 пустые; 0 пропусков временной сетки в непустых файлах; 0 конфликтующих свечей на пересечениях шести дублирующихся symbol/timeframe групп. В каждой паре legacy longest-file selection покрывает временные метки обоих файлов.

Сводка: 53 уникальных H1 символа (50 с непустой H1 историей), 8 символов с 15m историей. Полный отчёт — artifact `cryptofetch-archive-audit` из [CI run 41627245037](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41627245037); методика и ограничения добавлены в `ENGINE_AUDIT_FINDINGS_RU.md`.

Этот результат закрывает только структурную проверку локальных OHLCV ZIP. Он не подтверждает point-in-time Bybit universe, provenance биржи, funding/mark coverage или отсутствие survivorship bias. Перед H-A требуется causal cross-sectional availability mask по каждому timestamp; не считать все 53 символа одновременно доступными на всём периоде.

Проверка полного replay permutation regression теперь закрыта: обнаруженная зависимость signal discovery и batch sizing от порядка символов исправлена; CI run 41628558820 прошёл, полный portfolio accounting suite исполнил 36/36 тестов. Подробности — в `ENGINE_AUDIT_FINDINGS_RU.md`.

Оставшиеся audit gates до PnL: независимая сквозная reconciliation торгового журнала/equity path, сверка accounting на полном сценарии с partial TP1 + funding, и подтверждение, что каждый будущий research runner использует один и тот же audited input manifest и исправленный engine. Stop/TP gap semantics покрыты отдельными deterministic regressions (включая stop precedence и gap fills), но перед новым экспериментом нужно проверить, что выбранный runner не обходит эти правила. До закрытия оставшихся gates рыночный PnL replay не запускать.

### Важное последствие engine fix для прежних результатов

E01–E13, E11 и E13 shared-capital цифры, а также другие исторические отчёты, полученные до исправления signal-discovery/batch-sizing, остаются историческими наблюдениями, но **не являются baseline для сравнения с будущим replay на исправленном движке**. Новый порядок может изменить набор сделок, приоритет одновременных сигналов и размеры fills. После закрытия audit gates потребуется заново выполнить frozen baseline на исправленном engine и тех же audited CryptoFetch inputs; только затем сравнивать H-A с baseline. Уже использованные временные folds всё равно остаются исследованными и не становятся blind holdout.

### Дополнительный обязательный gate для H-A: dynamic universe

Статический аудит выявил, что существующий shared-capital runner E11/E13 использует фиксированную синхронизированную панель: символ включается только если у него есть достаточное число баров во всех будущих folds, после чего временные сетки пересекаются. Это не point-in-time universe. Текущий `run_simulation_pass()` также требует полного совпадения timestamp arrays.

Поэтому H-A не запускать на фиксированной панели E11/E13 как на «всех доступных инструментах». Сначала нужен sparse/dynamic replay: union timestamp grid, per-symbol actual availability, 72h warm-up до включения в cross-sectional rank, fail-closed для открытой позиции/заявки без следующей свечи, общий terminal boundary, сохранение order-invariant batch fills. Подробно — `ENGINE_AUDIT_FINDINGS_RU.md`.

### Sparse replay gate — implemented, no PnL yet

Добавлен `allow_sparse_data=True` режим shared-capital engine: union timestamp grid, индивидуальная continuous history, per-symbol warm-up, common terminal timestamp, fail-closed для отсутствующей свечи открытой позиции/pending заявки. Новый late-listing fixture проверяет разные first timestamps и order invariance. CI run 41629995066: success, portfolio accounting 37/37, все 39 steps успешны.

Теперь следующий шаг — не запуск PnL немедленно, а аудит реализации H-A feature pipeline: causal 24h/72h relative strength, ATR normalization, cross-sectional ranks только среди активных символов с достаточной историей, без будущей информации; затем independent unit tests и preregistration. После этого — corrected-engine frozen baseline, и лишь затем один H-A replay.

H-A теперь preregistered до любых рыночных PnL прогонов: `H_A_RELATIVE_STRENGTH_BREAKOUT_PREREGISTRATION_RU.md`. Зафиксированы 24h/72h returns normalized by ATR%, midrank, top/bottom quintiles, Donchian(20), min breadth 5, market next-open, `|score|` priority, отсутствие дополнительных фильтров и ограничения funding/universe. Не менять правила после просмотра результата.

## 8. Фактический статус H-A и следующий диагностический шаг — 2026-11-03

Этот раздел supersedes прежние формулировки разделов 6–7 о том, что H-A ещё не запускалась.

### Результат H-A

- Preregistered replay завершён в CI run [41633199418](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41633199418); правила не подбирались по результатам.
- Universe по fold: 47 / 49 / 50 символов; состав менялся по мере появления доступной истории. Общая последняя свеча архива — 2026-10-26 00:00 UTC.
- Baseline: 1,022 сделки; gross +587.02 USDT; fees 4,416.37; slippage 1,806.63; net -5,635.98 USDT.
- H-A: 1,033 сделки; gross +29.53 USDT; fees 4,375.03; slippage 1,789.76; net -6,135.26 USDT.
- H-A хуже baseline на 499.28 USDT. H-A отрицательна по net PnL во всех трёх folds; PF ниже 1 и expectancy отрицательна во всех folds. Fold 3 активировал 30% emergency kill-switch.
- H-A отклонена как кандидат. Не оптимизировать ранги/пороги, не отбирать инструменты и не отключать глобально long/short на этих же folds.
- Это CryptoFetch/Binance-style OHLCV proxy с удвоенной моделью taker fee/slippage; funding не включён, Bybit point-in-time universe не подтверждён, folds ранее исследовались и не являются holdout.

Подробный frozen результат и attribution находятся в `H_A_RELATIVE_STRENGTH_BREAKOUT_PREREGISTRATION_RU.md`.

### Что известно о причинах убытка

- В каждом fold основную отрицательную сумму создаёт stop-loss cohort; time-stop и trailing-stop cohorts положительны, но не компенсируют стопы.
- Убыточное направление меняется между folds: нельзя обосновать постоянный long-only или short-only режим.
- Median holding time H-A — 19–20 H1 bars; максимальная длительность ограничена 32 bars.
- Старый artifact содержит gross/fees/slippage/net, направление и exit reason, но не содержит MAE/MFE, risk_usdt, session и order_type. Поэтому полноценная attribution по excursion и фактическому типу исполнения из старого artifact невозможна.

### Диагностическая задача

Текущий runner уже экспортирует MAE_R, MFE_R, risk_usdt, gross_R, session и order_type. Нужен один диагностический повтор тех же заранее зафиксированных folds — без изменения сигналов, параметров, universe, стоимости или правил исполнения — только чтобы проверить новые поля и построить stop-loss / winner attribution. Это не новый поиск стратегии и не независимый OOS.

На момент записи такой повтор не подтверждён: изменение workflow для unbuffered logging закоммичено в `3f762a4`, но соответствующий H-A Actions run не появился. Инструментальное подключение позволяет читать Actions, но не отправлять workflow_dispatch. Не считать диагностический replay выполненным и не делать выводов по отсутствующим MAE/MFE.

### Техническое состояние

- Portfolio kill-switch regression commit `917f74f` прошёл Research CI [41669101893](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41669101893); новый gap-execution тест 28/28 PASS. В `test_time_model.py` также уже есть более сильный полный сценарий `test_full_step_candle_kill_switch_flattens_portfolio_and_blocks_reentry`.
- Коммит `3f762a4` меняет только запуск H-A runner на `python -u` для потокового вывода; торговая логика и правила эксперимента не менялись.
- `main` не изменялась. Ни Bybit API, ни новые архивы, ни live orders не использовались.

### Следующее решение

1. Не запускать parameter sweeps и не пытаться «исправить» H-A подбором порогов.
2. Получить диагностический ledger с excursion/entry execution fields на том же frozen replay; если workflow dispatch недоступен, оставить этот пункт явно заблокированным.
3. Параллельно завершить статический аудит причин stop-loss: сигнал → цена следующего открытия → gap/chase → stop distance → adverse/favourable excursion → exit reason → per-leg costs. MAE после стопа трактовать как execution-bounded, не как полный внутрисвечной диапазон.
4. Только после диагностики сформулировать отдельную preregistered гипотезу с меньшим turnover. H-B mean reversion и H-C continuation quality остаются отдельными кандидатами; не смешивать их.
5. Не использовать эти folds как holdout и не переходить к API/self-hosted runner/live до появления обоснованного кандидата.

## 9. Диагностический ledger H-A получен — 2026-11-03

Этот раздел supersedes в разделе 8 прежнее утверждение, что диагностический повтор не подтверждён.

- Повторный frozen replay завершён: [Actions #41670116033](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41670116033), SUCCESS.
- Artifact содержит `mae_r`, `mfe_r`, `risk_usdt`, `risk_pct`, `gross_r_multiple`, `session`, `order_type`.
- Финансовые метрики совпали с предыдущим H-A artifact на опубликованной точности. Это диагностический повтор без изменения торговой логики, а не новый кандидат и не OOS.
- Отдельный regression для TradeRecord diagnostic fields прошёл в [Research CI #41670688299](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41670688299), SUCCESS.

### Подтверждённые наблюдения

- H-A: 528 stop-loss из 1,033 сделок (51.1%); суммарный stop-loss net PnL -20,294.80 USDT; средний -38.44 USDT на сделку.
- Stop-loss MFE: среднее 0.447R, медиана 0.31R; 37.7% сделок достигли MFE >=0.5R, 13.8% — >=1R, 3.2% — >=1.5R.
- По folds средний stop-loss MFE устойчив: 0.463R / 0.430R / 0.448R; доля MFE >=0.5R: 38.6% / 38.3% / 36.5%.
- Frozen baseline: 523 stop-loss из 1,022 сделок (51.2%), средний stop-loss MFE 0.449R. H-A не улучшила частоту стопов или измеряемый MFE этой когорты.
- Time-stop cohort: 325 сделок, +5,805.54 USDT net, средний MFE 1.509R. Trailing-stop: 148 сделок, +6,821.00 USDT, средний MFE 2.779R. Take-profit: 18 сделок, +1,617.69 USDT, средний MFE 5.687R.
- MAE stop-loss cohort ограничен модельным stop fill; MFE stop-bar также консервативен. Это execution-bounded excursions, не полная внутрисвечная траектория. Последовательность достижения MFE/MAE неизвестна.

Подробности и все оговорки — в `H_A_RELATIVE_STRENGTH_BREAKOUT_PREREGISTRATION_RU.md`, раздел 11.

### Следующая работа

1. Не оптимизировать H-A и не вводить breakeven-at-0.5R, stop widening или глобальный direction/session filter на этих же folds.
2. Провести read-only attribution по сигналу: body/range к ATR, close location, upper/lower wick, volume ratio, breakout distance за предыдущий Donchian и pre-break compression.
3. Привязывать признаки только к закрытой signal candle перед фактическим next-bar entry; никаких будущих баров и будущих universe members.
4. Сравнить распределения признаков для stop-loss, time-stop и trailing-stop когорт без PnL parameter sweep.
5. Лишь если обнаружится устойчивое и экономически правдоподобное разделение, preregister отдельную H-C continuation-quality гипотезу. Текущие folds уже использованы и не являются holdout.
