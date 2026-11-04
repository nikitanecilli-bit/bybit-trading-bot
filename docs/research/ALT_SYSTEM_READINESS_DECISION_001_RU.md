# ALT-SYSTEM-RESEARCH-001 — итоговое решение о готовности

Дата: 2026-11-05  
Ветка: `research/market-regime-v1-main`  
Тип решения: read-only evidence review; документ не разрешает запуск новых исследований или операций.

## Решение

**Стратегическая готовность: BLOCKED.**  
**Готовность Bybit-native PnL validation: BLOCKED.**  
**Готовность maker execution validation: BLOCKED.**  
**Инженерная база исследовательского движка: частично подтверждена deterministic CI; не является доказательством торгового edge.**

Ни одна из рассмотренных конфигураций не имеет воспроизводимого положительного результата после консервативных затрат на независимых хронологических данных. Не запускать paper/live и не считать какую-либо конфигурацию кандидатом на капитал.

Это решение не означает, что проект потерял цель. Оно означает, что текущие доказательства пока не позволяют отличить реальный edge от proxy data, selection bias и исполнения, которое исторические данные не подтверждают.

## 1. Решение по стратегии

| Область | Текущее доказательство | Статус |
|---|---|---|
| Базовые H1 Donchian/volume варианты | Исторические результаты после затрат отрицательные или неубедительные; ранние варианты имеют optimistic OHLC fills | REJECTED / PROVISIONAL |
| E11 shared-capital | Суммарно −3,178.61 USDT; body gate ON −2,774.00 USDT; первые два fold отрицательны | REJECTED |
| E13 compression gate | Суммарно −2,741.72 USDT; fold 2 отрицателен, fold 3 хуже baseline | REJECTED |
| H-A relative strength | −6,135.26 USDT против baseline −5,635.98; хуже на 499.28; все три fold отрицательны | REJECTED |
| H-C post-break invalidation | −2,880.12 USDT proxy net против −2,720.47; PF ниже 1; обе версии достигли kill switch | REJECTED |
| Maker/limit edge | OHLC touch и aggregate-L2 approximation не подтверждают очередь, исполнение или устойчивую доходность | BLOCKED |
| E12 | Диагностика контекста, не независимый PnL результат | DIAGNOSTIC ONLY |

Результаты E01–E11 и E13, кроме отдельно отмеченных исключений, затронуты прежней формулой exit fee/slippage на entry notional. Без исходных fill legs нельзя вычислить корректировку; знак смещения зависит от цены выхода. Не применять единый процентный дисконт и не пересчитывать результаты по догадке.

H-A final и H-C использовали исправленную execution-price fee basis, но остаются отрицательными и имеют независимые ограничения по данным, universe, funding и holdout.

## 2. Bybit-native market data gate

Для корректного H1 shared-capital validation отсутствует подтверждённый полный пакет:

- H1 trade OHLCV и Mark OHLCV за единый период и полный universe;
- полная point-in-time история линейных инструментов, включая delisted/temporarily suspended состояния;
- датированные instrument specs и risk tiers на момент каждой заявки;
- полный Funding history с проверяемыми settlement timestamps и соответствующей settlement Mark price;
- immutable manifests с source, query, UTC range, row counts, gaps/duplicates, SHA-256 исходных байтов и parser version.

CryptoFetch/Binance-style proxy данные не заменяют Bybit-native историю. Наличие downloader/collector кода или unit tests не является подтверждением, что требуемый пакет собран и полон.

Ранние E01–E07 workflow/artifact provenance в значительной степени восстановлены, но исходные SHA-256 CryptoFetch archive bytes и содержимое ряда исторических artifacts остаются неизвестными. SHA-256 ZIP-артефакта GitHub Actions не является SHA-256 исходного market dataset.

**Data acceptance: BLOCKED.** Не использовать текущие snapshots вместо исторических спецификаций и не заполнять отсутствующие settlement/market data предположениями.

## 3. Maker execution gate

### 3.1 Что улучшено в коде

В research branch реализованы и статически документированы:

- строгий parsing timestamps, orderbook metadata и public-trade IDs;
- snapshot-first и atomic candidate-state application;
- fail-closed обработка malformed BT/RPI flags, CSV headers/rows и conflicting aliases;
- idempotent overlapping trade replay и rollback состояния заявки при ошибках;
- canonical instrument-spec validation hook для tick/qty/min-notional;
- per-fill records, VWAP, explicit per-fill fee-rate ledger и per-fill markout;
- разделение fill-to-future-mid return и post-fill midpoint movement;
- no-overwrite serialization диагностических reports.

Эти свойства делают прототип аккуратнее и воспроизводимее. Они не устраняют фундаментальную ограниченность aggregate L2 и не подтверждают реальные исполнения.

### 3.2 Почему сохранённый AAVE sample непригоден для maker PnL

Повторно использованный artifact исходного run #41814167058 фиксирует схему AAVEUSDT trade CSV от 2025-09-02:

- 346,131 строк и 346,131 уникальных `trdMatchID`;
- колонка `RPI` есть, все значения равны 0;
- отсутствуют и `BT`, и `isBlockTrade`;
- 66 trades предшествуют первому matching-engine book timestamp.

Строгий replay требует достоверный block-trade classification и поэтому обязан отклонить этот CSV. Нельзя считать отсутствие BT эквивалентом `False`. Четыре старых hypothetical order outcomes (58%, 100%, 100%, 33%) были получены до обязательной BT validation; это не подтверждённые fills и не fill-rate estimate. Старые markout values также нельзя трактовать как чистый adverse-selection metric, поскольку тогда не отделялось движение midpoint от захваченного spread.

Документированный public REST recent-trade endpoint не предоставляет произвольную историческую выборку; private execution history не является market-wide public tape. Без уже существующего WS capture или другого проверенного исторического источника BT флаг не восстановить безопасно.

### 3.3 Остальные execution gaps

- Нет подтверждённого исторического instrument spec для AAVE sample на дату 2025-09-02.
- Нет account/symbol/date-specific fee rates для каждого fill.
- Нет измеренных order-entry/cancel latency и модели отмен/очереди.
- Aggregate L2 не показывает L3 order priority и не разделяет executions/cancellations.
- Historical trade CSV не подтверждён как содержащий cross-stream `seq`; same-millisecond ambiguity сохраняется.
- Нет broad-symbol, multi-regime sample; четыре заявки — не статистическая выборка.

**Maker execution realism: BLOCKED_FOR_STRATEGY_PNL.** Не ослаблять parser ради прохождения старого CSV и не подключать queue replay к strategy PnL.

## 4. Инженерная верификация и границы утверждений

Research CI подтверждал отдельные deterministic patches, включая:
- #41891208250: positive normalized public-trade timestamp regression; aggregate-L2 primitive 85/85, runner/inspector 26/26; workflow SUCCESS;
- #41875905360: strict orderbook inspector integer parsing; 57/57 workflow steps SUCCESS;
- #41875093214: strict trade CSV structure validation; 57/57 workflow steps SUCCESS;
- #41874277483: BT/RPI alias-value validation; 57/57 workflow steps SUCCESS;
- #41873425668: fail-closed trade ID inspector validation; 57/57 workflow steps SUCCESS.

Каждый CI run доказывает только тесты и код, входившие в конкретный commit. Он не подтверждает strategy PnL, dataset completeness, historical fill validity или все более поздние изменения ветки. В частности, если для последующих source/test commits нет terminal CI run, не приписывать им pass на основании предыдущего зелёного запуска.

Документационные изменения provenance/data/readiness не проходили CI, поскольку не меняли исполняемый код.

## 5. Что должно произойти до снятия блокировок

Порядок открытия gate:

1. **Data gate:** получить разрешённый, воспроизводимый Bybit-native пакет и полные source-byte manifests; закрыть OHLCV/Mark/Funding/universe/spec/risk-tier completeness.
2. **Accounting gate:** провести независимую сверку fee/funding/settlement arithmetic и portfolio shared-capital accounting на deterministic fixtures; не заменять её тестом на proxy PnL.
3. **Candidate gate:** только после отдельного пересмотра текущего holdout запрета — preregister ровно одну гипотезу, заморозить правила и universe, применить shared capital и хронологические train/validation/untouched holdout, консервативные costs и multiple-testing controls.
4. **Execution gate:** maker research допустим только если существует положительный conservative market/taker candidate; затем нужен валидный исторический BT/RPI feed, dated order specs, queue/latency/cancel assumptions и per-fill fee/markout ledger.
5. **Operational gate:** paper/live остаются закрыты до прохождения предыдущих gates, reconciliation и отдельного решения пользователя.

## 6. Разрешённая работа сейчас

Пока пользовательские ограничения не пересмотрены, допустимы только:
- read-only provenance reconciliation и аудит документации;
- статический анализ кода и контрактов;
- deterministic unit/regression tests на synthetic fixtures при наличии воспроизводимого дефекта;
- исправление подтверждённых fail-closed/integrity defects;
- обновление этой карты статусов без запуска market PnL.

Запрещённые действия остаются запрещёнными: live/paper orders, private/account API, collectors, новые archive downloads/extraction, self-hosted runner registration, market PnL backtests/replays и parameter sweeps.

## 7. Контроль веток и интеграции

Research branch остаётся отдельной от `main`. Сравнение на момент этого аудита показывает diverged history; не выполнять merge/rebase/fast-forward ветки целиком. Любая будущая интеграция должна быть отдельной выборочной reviewed series от актуального `main`.

Не менять `main`; PR #4 и PR #13 не сливать.

## Итог

Сейчас есть **инженерный research framework**, но нет доказанной прибыльной стратегии и нет валидированного execution/data substrate, на котором можно честно подтвердить такую прибыльность. Следующий рациональный шаг — не новая стратегия и не новый sweep, а сохранение строгих gates и закрытие доказательных пробелов только разрешёнными способами.
