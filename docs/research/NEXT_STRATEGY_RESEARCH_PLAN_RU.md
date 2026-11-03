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

### H-A — Relative-strength breakout (ОТКЛОНЕНА по результатам E14)

Историческая мотивация эксперимента: E12 показывал, что broad-market direction сам по себе не является универсальным фильтром. H-A была preregistered и проверена в E14, но отклонена: net PnL отрицателен во всех трёх folds, PF ниже 1, expectancy отрицательна; H-A хуже frozen baseline на 499.28 USDT. Не оптимизировать ранги/пороги и не переиспользовать эти folds для новой гипотезы.

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

Продолжить static audit и deterministic tests по lifecycle, TP1-aware PnL/cost reconciliation, sparse/shared-capital event ordering и stop/TP execution semantics. Symbol-order invariance и ledger-to-equity reconciliation уже имеют регрессионные тесты в `tests/test_portfolio_accounting.py`; не дублировать их без выявленного пробела. Результаты аудита записывать отдельно от рыночных PnL. H-A отклонена; не оптимизировать её на использованных folds. H-C реализована только как default-OFF механика базовой H1 breakout-стратегии, но PnL не тестировалась. Новые рыночные прогоны запрещены до закрытия audit/data gates и появления действительно независимых валидных данных.

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

## 10. Post-break continuation is the next research target — 2026-11-03

The final schema-validated artifact-only attribution is complete: workflow [41672420459](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41672420459), artifact ID 13249307987. It reconstructs the prior signal bar and only completed post-entry bars before the modeled exit. Archive SHA provenance matches the original H-A replay.

### What did not work

Pre-entry signal-candle shape/volume features have weak stop-vs-winner separation (AUC mostly 0.48–0.55). The best simple feature was prior-close distance to Donchian boundary at 0.55, which is too weak and not stable across folds. Do not add candle-size, wick, volume or pre-break compression filters from this sample.

### What looks more promising

For H-A:
- 3 completed H1 bars after entry: directional close return averages -0.104R for stop-loss trades (451 eligible) vs +0.222R for profitable exits (486 eligible); lower-return rank AUC ≈0.70 for identifying stop-loss outcomes.
- 6 completed bars: -0.118R (353 eligible) vs +0.313R (475 eligible); lower-return AUC ≈0.734.
- Close back inside the prior Donchian boundary within 3 bars: 61.6% of eligible stop-loss trades vs 41.6% of profitable exit trades.
- This retest association is stable in direction across all three folds, and a similar pattern exists in the frozen baseline.

The realized net PnL of the H-A cohort with a 3-bar retest was negative in every fold (-1,206.64 / -2,540.07 / -2,917.66 USDT); the no-retest cohort was positive in every fold (+589.12 / +1,102.86 / +1,397.25 USDT). These are conditional eventual outcomes, not counterfactual exit PnL. Do not treat them as proof that closing on a retest is profitable.

### Next step: preregister H-C, not optimize H-A

The next candidate should be a post-entry continuation / early invalidation hypothesis:
- Define the exact event using a completed H1 close back inside the breakout level.
- Define a fixed confirmation window and exact event timing before any PnL run.
- Model close-based exit price, taker fees, slippage and any partial TP1 state exactly; never use the close of an intrabar exit candle after the position was already stopped.
- Compare with the frozen baseline under identical universe, capital, shared risk and costs.
- Require a truly unseen time period or new point-in-time archive before judging it as a candidate. Existing three folds are development data only.

The descriptive results justify writing a preregistration; they do not justify running a threshold sweep or claiming an edge.

## 11. H-C preregistration created — 2026-11-03

Created H_C_POST_BREAK_INVALIDATION_PREREGISTRATION_RU.md and implemented the frozen event in the research engine:
- It closes only when a completed H1 candle closes back inside the signal-time prior 20-bar Donchian boundary during the first three completed bars after entry.
- Scope is the frozen H1 baseline strategy H1-momentum-breakout only; H-A is a rejected candidate and is excluded.
- Existing intrabar liquidation/kill-switch/stop/TP priority is preserved; TP1 partial realization and remaining quantity flow through the normal close accounting, with market-close costs.
- The exact signal-time breakout level is persisted through pending orders, open positions, state restore and TradeRecord.
- The feature is behind execution_and_exits.enable_post_break_invalidation=false by default. Synthetic regression and state-restore tests pass in Research CI; see the H-C preregistration for the exact latest run and coverage.
- Status: implemented and mechanically tested; NOT PnL-tested, NOT enabled for live and NOT approved for deployment.

No new market PnL run is authorized by this preregistration. The current CryptoFetch/Binance-style archives are not Bybit-native and lack historical point-in-time Bybit universe, dated instrument specs/risk tiers and verified full funding/mark coverage. The user had previously deferred Bybit API connection until strategy research is ready; do not bypass that constraint. TradeRecord now retains TP1 hit/time/realized gross, remaining fraction, stop geometry and breakout level; existing H-A artifacts predate these journal extensions. Legacy state backups remain loadable when H-C is disabled.

Next safe work: finish static review of position lifecycle, TP1-aware PnL/cost reconciliation, and sparse/shared-capital event ordering; add deterministic tests only for confirmed gaps. Do not run H-C on the already-used folds or tune the three-bar window.


## 2026-11-03 — reporting gate for the user's 20% net monthly hurdle

- H1 fold reports now include `duration_days`, `duration_months` and `geometric_monthly_return_pct`, derived from the fold's cumulative net PnL after modeled fees, slippage and funding and the exact inclusive H1 duration (first candle open through final candle close).
- This is a geometric monthly-equivalent normalization of the whole fold, not proof that each calendar month was profitable and not a standalone deployment criterion.
- The user's 20% net monthly objective must be evaluated against this normalized metric, alongside fold stability, max drawdown, trade count and cost stress. Before calling a candidate consistently profitable, a later report must also expose actual calendar-month returns and losing-month frequency; a single fold average cannot establish monthly consistency.
- The metric is reporting-only: no strategy parameters, symbol ranking, entry/exit rules or risk sizing changed. No market PnL was run.
- Regression coverage includes one-month +20% and two-month +44% compounded examples, invalid duration and total-loss handling. CI [#41708149842](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41708149842) and [#41708141158](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41708141158) both SUCCESS, 50/50 steps.


## 12. Funding archive completeness gate — 2026-11-03

Static audit found a P1 preflight blind spot documented in `docs/audits/FUNDING_ARCHIVE_COMPLETENESS_AUDIT_2026-11-03.md`: current funding coverage checks prove that recorded settlement rows have matching Mark timestamps, but do not prove that no settlement rows are missing from the CSV. The H1 runner only additionally requires at least one settlement inside each scored fold. Do not run another market PnL replay until the collector emits per-symbol API pagination/coverage provenance, dated funding-interval evidence is preserved, and the validator rejects a missing-middle-settlement fixture without assuming a universal 8-hour cadence. Funding arithmetic tests remain valid for supplied events but do not close archive completeness.


## 13. Funding archive provenance implementation — 2026-11-03

Implemented query-provenance sidecars in `bybit_downloader.py` / `funding_archive_manifest.py`. H1 selector and portfolio validation now bind sidecar hashes; the H1 runner fails closed if the sidecar is missing, altered, does not cover the scored fold, or lacks dated settlement-schedule verification. Regression tests cover collector pagination metadata, incremental runs, hash tampering and query-window gaps.

Do not manually set `settlement_schedule_verified=true`. The collector leaves it false by design. Remaining work is to derive a dated schedule from authoritative Bybit instrument-history evidence (including interval changes), prove expected settlement timestamps for each scored period, and only then allow a manifest to carry verifiable schedule evidence. Until then no H1 market PnL replay.


The schedule gate was strengthened after implementation: H1 now requires a separately hashed schedule-evidence file and checks its identity, interval coverage, raw Bybit instrument snapshot hashes/metadata, and exact expected-vs-observed funding timestamps in the scored fold. A boolean override is not accepted. A trustworthy schedule builder and sufficient dated historical snapshots remain outstanding; no market PnL replay until those exist.


Incremental Funding archive updates also verify the existing CSV hash and row count against the previous sidecar before downloading/appending. Any drift fails closed; a later download cannot silently bless a modified historical archive.


### Active Bybit archive collector provenance — 2026-11-03

The production research workflow uses `scripts/archive_bybit_market_history.py`, not the legacy `bybit_downloader.py`. The active collector now records Funding pagination pages (including saturated/incomplete 200-row pages and recursively complete child windows), writes per-symbol `SYMBOL.csv.audit.json` sidecars, and includes its own SHA-256 in the archive-level manifest. H1 replay code provenance includes this active collector. CI [#41712680254](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41712680254) passed 50/50 steps, including the active archive collector integration test.

No actual Bybit archives or dated historical funding schedule evidence are present in the repository. Do not run H1 market PnL until both are available and the schedule-evidence gate passes.


Further active-collector hardening: output roots are immutable (no silent overwrite), duplicate Funding timestamps are rejected, and saturated 200-row API pages do not count as complete coverage; only complete recursive leaf windows count. The archive-level manifest records the active collector code hash. Research CI [#41713006331](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41713006331) passed 50/50 steps. Real H1 PnL remains blocked by absent Bybit archives and dated settlement schedule evidence.


### TP1 Funding allocation into remaining isolated margin — 2026-11-03

A confirmed accounting-model mismatch was corrected: pre-TP1 funding settlements were previously charged 100% to the remaining position after a partial close. Bybit's partial-close PnL rules prorate accumulated funding across the closed and remaining quantities. The margin helper now uses the exact remaining-contract ratio for all historical Funding once TP1 is effective; full trade-lifecycle Funding remains unchanged. Tests cover both funding signs, exact quantity, as-of timing and engine liquidation integration. See the portfolio-accounting and execution-integration audit reports.

Remaining caveat: Bybit first deducts Funding from available balance and only deducts it from isolated position initial margin if available balance is insufficient. The simulator has no account-wide available-balance ledger and conservatively subtracts the remaining-leg Funding allocation from position margin. This is a stress assumption and may overstate liquidation risk. Do not describe the model as full UTA fidelity.

CI run [#41715596303](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41715596303): all 50 configured steps, including Funding accounting and Mark liquidation integration tests, reported success at last inspection; overall run/job terminal status was not yet returned. No market PnL replay was run.


### Exact entry/Funding boundary — 2026-11-03

The funding ledger no longer silently excludes a settlement whose timestamp equals the modeled entry candle open. Bybit documents that fills within five seconds before/after settlement may or may not be included. With no exchange fill timestamp, the simulator now charges a possible payment and excludes a possible receipt at that exact boundary; events strictly before entry remain excluded. This is a conservative boundary convention, not a reconstruction of actual exchange event order.

Research CI [#41716240400](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41716240400) passed 50/50 steps. The isolated margin funding treatment remains account-level approximate: net Funding is applied directly to position margin without modeling whether available balance covers it. Depending on funding sign and wallet balance this can overstate or understate liquidation risk. Do not interpret it as uniformly conservative or full UTA fidelity.


### Open Funding schedule proof gap — 2026-11-03

The current Funding manifest validator checks CSV timestamps against a supplied `expected_settlement_timestamps_ms` list and verifies each listed event aligns with the most recent preceding dated instrument snapshot. It does not independently derive the complete expected event list or prove the effective timestamp of an interval change. A CSV and expected list that omit the same event can therefore be internally consistent. Snapshot `fetched_at` is observation time, not interval-effective-time evidence.

This is a confirmed validator limitation, not evidence that a current archive is damaged. Keep H1 market PnL blocked until an authoritative, independently auditable historical Funding-interval schedule is available. Do not treat a green manifest check alone as proof of settlement completeness; do not hardcode an 8h cadence.


### Funding settlement grid reconstruction — 2026-11-03

The manifest validator now independently reconstructs the expected UTC Funding grid from dated instrument snapshots when all snapshots across the scored interval report one stable fundingInterval; the supplied expected-timestamp list must match that grid. A CSV and schedule that omit the same settlement now fail. If snapshots show different intervals, validation fails closed because fetch time does not prove the exact effective time of a change.

Residual: equal snapshots cannot rule out an interval change and reversion between observations. Live instrument snapshot capture remains blocked by HTTP 403 and the collector is manual. Treat the grid check as a consistency check conditional on observed interval stability, not as proof of complete historical metadata. H1 PnL remains blocked until this residual is addressed with authoritative historical effective-time evidence or independently verifiable continuous observations. Official Bybit terms define 1h/2h/4h/8h UTC settlement grids; do not substitute a fixed 8h rule.


### Funding archive pagination coverage — 2026-11-03

The Funding collector now records descending/unique timestamp-order evidence for each response page. The manifest validator accounts for the upper segment of a saturated 200-row page from its oldest returned event to the requested end, and requires complete earlier query windows to join it without gaps. A 201-settlement regression fixture covers one saturated page plus one complete tail page; a lone saturated page with an uncovered lower segment still fails. This resolves a false-negative that would have rejected normal multi-page histories.

The endpoint docs specify the 200-record limit and endTime behavior but do not explicitly state response ordering; the collector verifies the actual returned ordering and refuses to attest saturated pages if the order is not descending or timestamps are not unique. This is query-window provenance, not a substitute for the independently reconstructed Funding settlement grid.


Research CI [#41719390878](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41719390878) completed SUCCESS, 52/52 steps, including the new Funding manifest, schedule reconstruction, saturated pagination, downloader-integrity and H1 preflight tests. This confirms deterministic fixture coverage only; no live Bybit archives were collected and no market PnL replay was run.


### TP target gap liquidity classification — 2026-11-03

The replay previously treated configured TP1/TP2 exits as maker even when a candle opened beyond the resting limit target. This is now gap-aware: a target crossed by the open is taker (fee + slippage); a non-gap intrabar touch remains the configured maker proxy. TP1 per-leg liquidity status is persisted and applied consistently in MTM/final PnL; final TP2 status is recorded. Gap prices remain at the target level, without optimistic opening-price improvement.

Research CI [#41720537099](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41720537099) passed 52/52. This corrects execution-cost accounting but does not establish queue fills. Do not interpret it as evidence of profitability. No market PnL replay was run; the Bybit Funding completeness gate remains the next blocker before any frozen-baseline replay.


H1 runner scope check: the shared-capital H1 validator explicitly uses maker entry and taker TP1/TP2 exits (maker_entry_and_tp1=True, maker_tp1_and_target=False). The new gap-aware maker-target logic therefore does not change the frozen H1 baseline; it hardens the generic engine and future maker-exit experiments.


### Bybit-native H1 limit-fill sensitivity — queued behind Funding gate

Current H1 shared-capital runner uses a 20 bps entry offset, 5 bps additional penetration, and a 3-H1-bar pending TTL. A normal intrabar OHLC touch is a maker proxy; marketable opening gaps are taker. No queue position, bid/ask, partial fills or price improvement are modelled. The existing h1-limit-fill-stress script is Binance OHLCV proxy with independent capital per symbol, so it cannot validate the current Bybit-native shared-capital model.

After Funding archive completeness is proven and the frozen top-5/reserve universe is fixed, run a Bybit-native shared-capital fill sensitivity (offset 10/20/30 bps × penetration 0/5/10 bps × TTL 1/3/5 H1 bars) with unchanged signals and cost assumptions. Report fill rate, expired signals, maker/taker mix, trade count, costs and net PnL separately. Do not run this as a market PnL experiment before the Funding gate is closed.


### Directional-scope blocker in current H1 Top-5 workflow — 2026-11-03

Audit found that run_portfolio_variant filters out every signal except long, and select_h1_top5_train_only.py imports that function. Thus both the current H1 shared-capital portfolio replay and its Top-5 train-only selection are long-only. This is narrower than the generic H1 strategy and must be labelled as such. The historical E01 long-only limit result is proxy OHLCV, independent-symbol capital and optimistic fill evidence; it does not justify permanent long-only deployment.

Keep the existing runner unchanged as a reproducible long-only variant. After Funding completeness is proven, add a separate Bybit-native shared-capital directional ablation (long-only / short-only / both) with direction-aware train-only selection or a common predeclared universe, identical costs and risk limits, and final chronological holdout untouched. See docs/audits/H1_DIRECTIONAL_SCOPE_AUDIT_2026-11-03.md. No directional PnL replay was run.


## 2026-11-04 — H-C reverse-time proxy protocol frozen

- Audit/engineering gates now cover per-leg TP liquidity, TP1 mark-to-market, H-C event priority, exact taker exit accounting, state persistence, shared-capital equity reconciliation and deterministic symbol-order invariance.
- One reverse-time CryptoFetch proxy check is preregistered in H-C doc section 6.1: 2025-10-30 00:00 through 2026-04-26 23:00 UTC; fixed 25-symbol archive-available set; same frozen baseline vs baseline+H-C; no H-A, no top-five selection, no tuning; 2x fee/slippage; funding omitted.
- This is not forward OOS and cannot prove Bybit net PnL or 20% net/month. The workflow will run once on already committed archive bytes only. No Bybit API, external download, account access or orders.


## 2026-11-04 — H-C reverse-time result and next research boundary

- The one preregistered H-C reverse-time CryptoFetch proxy replay completed [#41722545731](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41722545731), artifact 13272957989. Baseline proxy net before funding: -2,720.47 USDT; H-C: -2,880.12 USDT. H-C improved gross by +1,502.18 but added +1,661.83 fees/slippage and increased trades 94.9%; net was worse by -159.65 USDT. Both variants hit the 30% kill switch.
- H-C is rejected for this window. No tuning/replay on this year of CryptoFetch data. The full archive is now development-only; no additional PnL sweep may be presented as an independent holdout.
- The next strategy direction is lower-frequency entry quality: longer H1 Donchian structure plus a causal EMA50/EMA200 trend-regime gate, with a fixed cost-aware execution model. This is a new hypothesis, not a proven edge. First complete static design, code audit and deterministic tests; any future proxy experiment must be separately preregistered and clearly labelled development-only. A real 20% net/month claim still requires funding, mark-price and Bybit execution validation, which remains on hold.
- No Bybit API connection, external exchange-data download, private account access, paper/live order submission.


### 2026-11-04 — EMA50/EMA200 deterministic trend-filter audit

- The research-only full-history EMA helper remains causal and prefix-invariant; the 50/200 direction requires fast/slow alignment, slow-EMA slope and close location, so a countertrend rally below a falling slow EMA remains labelled bearish until the slow trend confirms reversal.
- Two synthetic tests had encoded contradictory end states: one asserted EMA alignment before its synthetic fast EMA had actually crossed; another expected neutral while fast < slow, slow EMA was falling and close remained below slow EMA. Test data/expectations were corrected; strategy logic was not loosened to satisfy the tests.
- Research CI [#41726204938](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41726204938) passed 53/53 steps at commit `2f7c590e70da47ab855db31d9f823d8134ac7cd5`.
- This remains deterministic indicator validation only. The EMA50/200 filter is not integrated into the execution engine and has no PnL evidence. Do not treat it as an accepted strategy improvement or run market PnL until the Funding/Mark and Bybit-native data gates are actually satisfied.


### EMA50/EMA200 integration constraint

A separate static audit found that the engine's `CALC_WINDOW=200` is shorter than the 206 candles required for the first directional EMA50/200 label (slow=200 plus slope lookback=5, zero-based index 205). Calling the helper directly inside `evaluate_signal()` would therefore return `neutral` on every H1 bar. The filter is not currently integrated. Any future variant must precompute causal labels once over the full available per-symbol history and look them up by the exact current completed-candle timestamp; do not blindly enlarge the engine window or recalculate full-history EMAs per signal. See `docs/audits/EMA50_200_INTEGRATION_WINDOW_AUDIT_2026-11-04.md`. This is a design gate, not PnL evidence.


EMA200 initialization also needs a frozen burn-in policy: the helper seeds from the first close, so 206 candles are only the minimum for a directional label, not convergence. The seed retains about 13.53% weight after 200 updates; a conservative pre-roll candidate is 1,000 bars (5× EMA200) before the first scored signal. This is a research-design constraint, not a tuned parameter. Non-finite EMA inputs are now rejected; Research CI #41727040877 passed 53/53.


## 2026-11-04 — EMA50/EMA200 H1 gate implementation status

- Added an exact timestamp-to-label index with fixed 1,000 H1 bar EMA200 seed burn-in, strict chronological/contiguous H1 input, and fail-closed exact lookup.
- Added an opt-in `ema_trend_labels_by_symbol` input to `run_portfolio_variant`; long-only H1 signals are allowed only when the same completed candle label is `up`. The default path remains unchanged.
- Research CI [#41727906187](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41727906187) SUCCESS, 54/54.
- This optional map is not yet passed by the H1 main grid and has no PnL evidence. Do not claim it improves results. Next implementation task is a separately identified fixed EMA-gated variant using the same frozen selected basket, execution assumptions and shared capital; only execute when Bybit-native data gates pass. No CryptoFetch PnL retest.


### 2026-11-04 — paired EMA50/200 ablation wiring

The earlier note saying the EMA labels were not passed into the main H1 grid is superseded. The current runner can build the exact-timestamp, 1,000-bar pre-roll EMA map and pass it into the signal wrapper when `H1_EMA50_200_GATE=1`. A follow-up comparison audit found that this opt-in previously replaced the baseline output instead of producing a paired control.

Correction: default mode remains baseline-only. With `H1_EMA50_200_GATE=1`, every fold/volume/breakout/cost configuration now runs **both** baseline and EMA50/200-up-gated variants, each with the same frozen five-symbol basket, fold boundaries, shared starting capital, engine settings and cost multiplier. They are independent portfolio replays, not simultaneous capital-sharing portfolios. Output labels are deterministic and distinct (`...` vs `..._ema50_200_up`).

This is comparison plumbing only, not evidence of improved expectancy. It does not relax the Bybit data gates. No market PnL replay was run. Research CI must pass before treating the paired runner as ready.


Paired comparison wiring was verified in Research CI [#41728994842](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41728994842): **55/55 steps SUCCESS**, including the EMA trend gate, paired-row matching and fail-closed missing-pair tests. The dedicated workflow exposes `ema50_200_comparison=off|paired`; `paired` produces baseline and gated rows in one immutable result manifest. Research branch head: `8ed9a1688d51538e2c31adf68edcfd41a9a7792c`.

The Bybit-native market archive and dated instrument/risk snapshots are still absent from the repository, so the H1 runner remains data-gated. Do not launch a market replay or infer strategy performance from synthetic tests.


## 2026-11-04 — final EMA/lifecycle integrity hardening

- The paired EMA manifest now fails closed if baseline and candidate differ in timeframe, selected symbols, common H1 bar count, fold boundaries, starting capital or max concurrent positions. The H1 runner explicitly sets 5x isolated leverage in config and manifest.
- Funding schedule snapshots may omit a symbol outside its lifecycle window, but any dated snapshot inside the requested funding interval must contain it. Regression tests cover both cases.
- Research CI [#41730087544](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41730087544) SUCCESS, 54/54.
- No Bybit market PnL, no private API, no external downloads, no orders. The Bybit-native archive remains the only data blocker for the preregistered paired comparison.
