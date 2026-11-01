# Аудит движка — подтверждённые наблюдения и дефекты

Дата: 2026-11-02  
Проверенная версия: `Bybit_Trading_Engine_v14_research.py`  
Blob SHA: `e4501bd3666d7fe25ae8c1a10a9813da89b535dd`

## Статусы
- CONFIRMED: прямо следует из кода или лога.
- DEFECT: подтверждённая некорректность/опасное поведение.
- RISK: ограничение модели, которое может искажать результат.
- OPEN: требуется отдельное воспроизведение/проверка.

## 1. DEFECT — не проверяется соответствие интервала CSV таймфрейму конфига

**Код:** `load_candles_csv()` (строки 1378–1421), `check_alignment()` (1424–1436), `step_candle()` (1013–1022), `run_simulation_pass()` (1439–1456).

Загрузчик проверяет, что timestamps положительные, уникальные и интервалы между соседними свечами одинаковы. Однако он не сравнивает фактическую дельту timestamp с `cfg.timeframe`. При этом движок вычисляет время закрытия свечи, дневные границы и длительность удержания из `cfg.timeframe`.

**Влияние:** CSV 15m при конфиге 1h пройдёт проверки равномерности/синхронизации, но каждая свеча будет считаться часовой. Это искажает exit timestamps, UTC-day stop reset, session/day accounting и интерпретацию max_hold_bars. Обратное несовпадение аналогично.

**Классификация:** подтверждённый дефект валидации входных данных, severity P1 для доверия к результатам.

**Не исправлено в рамках этого коммита.** Следующий безопасный шаг — добавить pure validation helper и тесты на matching/mismatching timeframe; не менять результаты старых прогонов задним числом.

## 2. RISK — session и blocked hour/weekday привязаны к OPEN timestamp свечи

**Код:** `QuantStrategyCore.evaluate_signal()`, строки 477–486; `Candle.ts` документирован как open timestamp (строки 1010–1022).

`get_utc_session(curr.ts)`, weekday и hour filters используют timestamp открытия сигнальной свечи, хотя сигнал становится известен только после закрытия. На H1 сигнал с open timestamp 07:00 фактически подтверждается в 08:00 UTC, но будет классифицирован как Asia и проверен по часу 07.

**Влияние:** границы UTC-сессий и блокируемые часы смещены на длительность таймфрейма. Не обязательно ошибка, если таково явное определение стратегии, но текущее поведение должно быть задокументировано; иначе фильтры работают не в тот момент, который трейдер обычно понимает как время сигнала.

**Классификация:** подтверждённая семантика, решение о корректности зависит от спецификации. Не менять без фиксации intended semantics.

## 3. RISK — maker fills по касанию OHLC чрезмерно оптимистичны

**Код:** `_try_fill_pending()`, строки 1082–1088.

Лимитный ордер считается исполненным, если low/high свечи коснулись лимитной цены. Для long при касании fill = min(limit, open), для short — max(limit, open). Нет bid/ask, очереди, объёма на цене, latency, partial fill, cancel/replace и adverse selection.

**Влияние:** maker PnL может быть завышен, особенно когда цена только касается уровня и разворачивается. Множитель комиссий/проскальзывания не моделирует вероятность отсутствия fill или adverse selection.

**Классификация:** ограничение симулятора P1 для выводов о прибыльности maker стратегии. Не дефект арифметики, но не считать maker edge доказанным.

## 4. RISK — данные Binance proxy не подтверждают Bybit execution

Исторические результаты с Binance OHLCV не содержат Bybit order book / trades / funding. Ранее запрос Bybit fresh-data validation вернул HTTP 403. Не экстраполировать эти результаты на реальное исполнение Bybit.

## 5. CONFIRMED — причинный порядок индикаторов в основном сигнале

В `evaluate_signal()`:
- текущая свеча отделяется от истории (`history = candles[:-1]`);
- Donchian и ATR вычисляются только на предыдущих свечах;
- текущая свеча используется для close breakout и volume ratio;
- pending сигнал исполняется на следующей свече.

Это корректная причинная схема для этого участка кода. Полный look-ahead аудит остальных research scripts, regime features и fold construction ещё не завершён.

## 6. CONFIRMED — приоритет стопа над TP на одной свече

В `_manage_position()` стоп проверяется до TP1/TP2. При одновременном касании stop и target в одной OHLC-свече движок выбирает stop. Это консервативное допущение, но не восстановление реального внутрисвечного пути цены.

## 7. OPEN — риск последовательной обработки символов

`run_simulation_pass()` обрабатывает символы одного timestamp по очереди. Перед этим `_prepare_portfolio_intrabar_marks()` предварительно размечает уже открытые позиции по всем символам. Это снижает зависимость risk gate от порядка, но новые сигналы/заполнения и освобождение капитала всё ещё происходят последовательно. Нужен отдельный тест инвариантности результата при перестановке списка symbols.

## 8. OPEN — полная арифметическая сверка PnL и риска

Проверить независимо:
- позиционный notional vs margin/leverage;
- actual risk vs planned risk при гэпах;
- округление каждой ноги и итоговых fee/slippage;
- частичный TP1 + final exit;
- equity reconciliation при нескольких одновременных позициях;
- drawdown по equity curve, включая intrabar marks;
- funding и liquidation (сейчас в модели отсутствуют).

## 9. CI: подтверждённое смешение уровней проверки

Workflow `.github/workflows/research-checks.yml` в одном job выполняет py_compile, secret scan, исторические backtests, walk-forward, regime holdout comparisons и regression tests. Один зелёный статус смешивает качество кода и рыночные расчёты. Run `41355263006` прошёл все шаги; логи подтверждают 18/18 gap tests и 37/37 time-model tests. Время выполнения job около двух минут; в нём есть несколько исследовательских расчётов.

Рекомендация: после аудита разнести быстрый CI и manual/dispatch-only research workflows. Не менять сейчас результаты и не запускать дополнительные рыночные прогоны.

## 10. Приоритеты
- P1: проверка фактического candle interval против timeframe.
- P1: консервативная модель/стресс maker fill прежде чем использовать limit PnL как основание стратегии.
- P1: проверить portfolio order invariance и equity reconciliation.
- P2: уточнить timestamp semantics session/hour filters.
- P2: полная сверка fee/slippage/funding and liquidation assumptions.
- P2: разнести CI и research runs, сохранить существующие run/artifact ссылки.


## 2026-11-02 — повторная проверка портфельной математики

### Проверено в текущем v14

- Position sizing использует notional, а не маржу как базу PnL: оценка риска = stop distance + entry fee/slippage + taker stop fee/slippage.
- При входе учитывается общий лимит `max_portfolio_risk_pct`: из него вычитается сумма оценочного риска открытых позиций; размер новой позиции ограничивается остатком.
- После TP1 оставшийся открытый риск в сумме портфеля умножается на `remaining_fraction`. Это консервативно, поскольку не пересчитывает риск по подтянутому trailing stop.
- Перед обработкой каждого синхронного бара движок формирует adverse marks по всем уже открытым символам; это снижает зависимость risk kill-switch от порядка символов.
- Внутрисвечной стоп имеет приоритет над TP; гэп через stop учитывается по худшей цене open vs stop. Это консервативная OHLC-модель, но не восстановление реального пути цены.
- При закрытии сделки комиссия/проскальзывание суммируются по ногам входа, TP1 и финального выхода. Для финального выхода maker допускается только при take_profit; стоп/time-stop/kill-switch идут taker.
- Equity строится как realized equity + unrealized PnL; unrealized оценка включает ориентировочные комиссии/проскальзывание выхода.

### Открытые риски / не доказано тестами

1. **Порядок символов не доказан инвариантным.** Предварительная оценка риска общая, но при одновременных входах и ограниченном остатке портфельного риска первый символ в списке может получить весь доступный бюджет, а следующий — нулевой. Итоговый PnL может зависеть от порядка символов. Это может быть допустимой политикой приоритета, но она должна быть явной и протестированной.
2. `_open_portfolio_risk_usdt()` использует исходный `risk_usdt` с масштабированием по остаточной доле позиции, но не пересчитывает риск по текущему stop после трейлинга. Это консервативная оценка, а не точный текущий риск.
3. Позиционный риск оценивается до стопа плюс базовые издержки. Gap loss, ликвидация, funding, basis/mark divergence и биржевые ограничения могут увеличить фактический убыток.
4. Лимит notional = equity × leverage / max_concurrent_positions × 0.95 — грубый лимит ёмкости. Он не моделирует maintenance margin tiers, доступную маржу, cross/isolated collateral, комиссии ликвидации или биржевые шаги qty/tick.
5. Плавающий PnL и закрытый PnL reconciled в коде локально, но нет отдельного end-to-end property test на несколько одновременно открытых позиций, TP1 частичное закрытие, гэп, daily reset и kill-switch в одном сценарии.
6. При portfolio replay символы обрабатываются последовательно. Нужен отдельный тест на перестановку symbols с одновременными сигналами; без него нельзя заявлять, что shared-capital результаты не зависят от порядка списка.

### Решение

Не менять risk formulas без эталонных fixtures. Следующий безопасный шаг — добавить детерминированные unit/property tests на:
- сумму оценочного риска открытых позиций и остаточный portfolio budget;
- частичный выход TP1 и остаточную долю риска;
- reconciliation: стартовый equity + сумма net closed PnL + unrealized = current equity;
- permutation test на одновременные сигналы, сначала зафиксировав ожидаемую политику распределения бюджета.


### Regression evidence — 2026-11-02

- CI run [41356694461](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41356694461), commit `de748c505e515510b346d2ccefcb5fd4f21d4ac5`: completed successfully.
- `test_portfolio_accounting.py` is included in compilation and executed successfully.
- Covered: realized + unrealized equity identity; conservative TP1 partial-position mark accounting; risk-budget cap and zero-budget rejection; long/short mark sign; closed-trade gross PnL, fee, slippage, net PnL and realized-equity reconciliation.
- This is focused deterministic unit coverage, not a full portfolio event simulation. It does not yet prove symbol-order invariance, exchange margin/liquidation behavior, funding, or real fill quality.
- Earlier CI run [41356653378](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41356653378), commit `4b662e2ea62460705dfd39e38e021b89ee57fd80`, also completed successfully with timeframe validation and the initial portfolio accounting tests.

Current known issue remains: sequential simultaneous-entry allocation can be symbol-order-dependent under a binding portfolio risk cap. No behavior change has been made.


### Confirmed defect: simultaneous-entry allocation depends on symbol order

- Regression: `test_simultaneous_entry_selection_is_order_dependent_under_binding_risk_cap` in `test_portfolio_accounting.py`.
- CI run [41356762102](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41356762102), commit `36bd4b8f8a448207d9d74f439d39bdc345853624`: passed.
- Fixture: 3 simultaneous symbols, $10,000 equity, 1% per-trade risk and 2% total portfolio risk cap. Processing BTC, ETH, SOL opens BTC+ETH; reversing order to SOL, ETH, BTC opens SOL+ETH. The same signals and prices select a different portfolio.
- Cause: `run_simulation_pass` processes `symbols` sequentially; `_try_fill_pending` immediately consumes remaining portfolio risk for each symbol. No batch allocation / pro-rata distribution exists.
- Severity: P1 research-integrity defect for shared-capital backtests; it can change instrument selection and resulting PnL based solely on input list order.
- No engine behavior has been changed yet. Next safe action: implement a deterministic batch allocation policy for all same-bar pending signals (e.g. equal pro-rata or explicit fixed ranking), then test invariance to input permutation and document the policy. Do not silently sort by symbol name: that would make results reproducible but still arbitrary.


### Fix applied: deterministic batch allocation for simultaneous entries

- Commit `15444377b5fcc56296ae5147e0a06cd8585d74a5` adds a per-bar allocation stage in `run_simulation_pass`.
- All pending entries on the same bar receive a precomputed share of remaining portfolio risk; they no longer consume the budget in symbol iteration order.
- When pending entries exceed available position slots, priority is descending `vol_ratio`; symbol name is used only as a deterministic tie-breaker. This policy is explicit and tested.
- Budget is allocated conservatively before per-symbol position management; risk freed by a same-bar exit is not redistributed until the next bar. Unfilled or rejected entries do not cause mid-bar reallocation.
- `_try_fill_pending` consumes the allocated budget if present; direct focused calls without a batch allocation retain the legacy remaining-budget fallback.
- Regression tests now verify same selected portfolio and total risk under reversed symbol order, plus stable slot priority by signal strength.
- CI run [41356881313](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41356881313), commit `3246eb1df4b9d4cfbd109fa6e6a6316e44710200`: completed successfully, all technical checks passed.
- Earlier intermediate CI runs failed because focused engine tests instantiate the engine with `__new__` and do not run `__init__`; compatibility fallback was added. Those failed runs are retained in history and are not treated as successful evidence.

The previous P1 order-dependent allocation is considered fixed in the research engine subject to the limitations above. This is a new portfolio allocation policy; historical E01–E09 results must not be silently reinterpreted as if this policy had been active.
