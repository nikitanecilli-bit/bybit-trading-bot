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
