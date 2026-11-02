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


### Static scan: live order endpoints — 2026-11-02

- Searched the engine copy in all six relevant branches (main, Audit, funding-data, data-adapter, market-regime, v15-donchian, plus active research branch) for `place_order`, `/v5/order/create`, `create_order`, `pybit.unified_trading`, `HTTP.post`, `requests.post`, `submit_order`, and `set_trading_stop`: no matches.
- Searched all Python research scripts in `research/market-regime-v1-main` for the same terms: no matches.
- Conclusion is limited to the inspected Python engine/scripts. It is not a proof about every non-Python file, installed package, or external runtime configuration. No live order endpoint was found in the audited research code.


### P2 diagnostic defect fixed: MAE/MFE on stop candle

- In `_manage_position`, the engine previously updated MAE/MFE from the entire candle high/low before applying the stop. If a long hit its stop and then printed a high wick, the trade journal could count that later high as favorable excursion; a deeper low wick could overstate MAE beyond the modeled stop fill. OHLC does not reveal the order of those extremes.
- Fix: when stop is crossed, do not update favorable excursion from that candle; cap adverse excursion at the modeled stop fill (including gap-through-stop open). Apply symmetrically to long and short.
- Tests: `test_stopped_long_mae_uses_stop_fill_and_does_not_count_later_wick_as_mfe` and short counterpart.
- CI [41357102546](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41357102546), commit `4c5f26ccbd0a7861ac3da587ef20e4855952d152`: completed successfully.
- Scope: fixes journal MAE/MFE diagnostics only; does not change modeled stop price or net PnL.


## 2026-11-02 — margin, exchange constraints and funding review

### Confirmed model limitations (no code changes made)

1. **No exchange lot/tick enforcement in the research engine.** `calculate_position_size()` returns a USDT notional rounded to cents. It does not convert notional to contract quantity and does not apply `qtyStep`, `minOrderQty`, `minNotionalValue` or `tickSize`. The Bybit downloader can fetch a current instrument-info JSON, but this specification is not consumed by the engine and is not a historical spec archive. P1 limitation for executable fill/quantity validation; not a live-order bug in the audited engine.
2. **Leverage is a sizing cap, not a margin/liquidation model.** The engine caps an individual position notional using `equity * leverage / max_concurrent_positions * 0.95`. It does not track initial/maintenance margin, risk tiers, isolated/cross collateral, liquidation fees, bankruptcy price or mark-price liquidation triggers. It therefore cannot estimate liquidation events or guarantee that a modeled position is margin-feasible on Bybit.
3. **Funding is downloaded but not charged in PnL.** `bybit_downloader.py` supports historical funding-rate collection and parses the exchange `fundingRateTimestamp`, but the v14 research engine has no funding cashflow integration. Any multi-hour/day hold backtest omitting funding is incomplete for instruments/periods with material funding.
4. **Mark-price/basis data are not used in position PnL or liquidation.** Downloader supports mark, index and premium-index candles, but the engine's stop/TP replay uses one OHLC candle stream. Mark/index divergence and mark-triggered liquidation are absent.
5. **Current instrument info is not historical.** A newly downloaded instrument JSON represents the specification at fetch time; it must not be assumed to describe prior contract limits or leverage tiers across the entire historical test.

### Confirmed positive scope
- `bybit_downloader.py` has datasets for kline, mark, index, premium, funding, OI and instrument info.
- The downloader is public-data only and does not place orders.
- The engine position-size calculation includes modeled entry/stop fees and taker slippage, but that does not replace the missing exchange margin, quantity and funding mechanics.

### Severity and decision
These are P1 limitations for claims about net profitability or exchange-executable performance. They are not proof that the signal itself is unprofitable, nor evidence of a code path placing live orders. Keep historical strategy results labeled as model-level until these costs/constraints are incorporated and validated.

### Next safe implementation sequence
1. Define a versioned instrument-spec schema and capture `qtyStep`, `minOrderQty`, `minNotionalValue`, `tickSize`, leverage/risk-limit fields with fetched-at timestamps.
2. Add pure notional-to-quantity and price-to-tick rounding helpers, using Decimal and direction-aware rounding; unit-test boundaries without changing old runs.
3. Add funding settlement cashflows using exact exchange settlement timestamps and position notional at each funding event; test long/short sign and entry/exit exactly on settlement boundaries.
4. Only then model mark-price liquidation and margin tiers from versioned contract data.
5. Re-run historical validations as new, versioned experiments; never overwrite E01–E09.


## 2026-11-02 — funding-ветка: дополнительный риск mark-to-market

В `research/bybit-funding-data-v1` funding учитывается только внутри `_close_position()`. Метод `_unrealized_pnl_at_marks()` считает unrealized gross PnL и торговые комиссии/проскальзывание, но не добавляет accrued funding по settlement events, уже прошедшим для открытых позиций.

**Следствие:** ежедневный стоп и kill-switch в funding-ветке могут не увидеть часть текущей просадки до закрытия позиции. При закрытии итоговый net PnL funding вычитает, но риск-контроль в ходе удержания работает по неполному equity.

**Классификация:** подтверждённый P1 пробел риск-учёта в funding-ветке. Не переносить этот патч целиком. При интеграции нужен единый pure helper accrued_funding(position, as_of_ts), используемый одновременно в mark-to-market и final close, с тестом отсутствия двойного учёта и TP1 partial notional.


## 2026-11-02 — Bybit instrument constraints groundwork

Добавлен независимый модуль `bybit_instrument_specs.py` (schema version 1), который читает сохранённый `instruments-info` snapshot и fail-closed проверяет обязательные `tickSize`, `qtyStep`, `minOrderQty`, `minNotionalValue`. Сохраняются отдельные `maxOrderQty` и `maxMktOrderQty`, а также leverage filter. `instrument_spec_history.py` выбирает только самый свежий полный snapshot не позже as-of времени; запрещает использование будущей спецификации, snapshot старше заданного max age и инструмента, отсутствующего/не Trading в последнем полном universe. Все значения переводятся в `Decimal`; buy limit округляется вниз, sell limit вверх, quantity — вниз. Проверка ордера отвергает несоответствие tick size, min/max quantity и min notional.

Модуль пока **не подключён к v14 engine** и не меняет поведение бэктеста. Нет исторического архива instrument specs; текущие snapshots нельзя задним числом считать историческими. Следующий этап — версионированный сбор спецификаций по датам и интеграция в sizing/fill только после тестов.

## 2026-11-02 — dated instrument snapshots and funding helper groundwork

Добавлен `scripts/snapshot_bybit_instruments.py`: постранично выгружает полный публичный Bybit V5 instruments-info universe, проверяет пагинацию/дубликаты и сохраняет исходные строки с provenance (`schema_version`, category, fetched_at, count). Имя файла содержит UTC timestamp, чтобы повторный запуск в тот же день не перезаписывал предыдущий snapshot. Workflow `bybit-instrument-snapshots.yml` запускает архивирование при изменении сборщика/самого workflow; он пишет только в `data/instrument_specs/linear/`.

Добавлен pure helper `funding_accounting.py`: единый cumulative funding calculation с as-of timestamp, timestamp-aligned open mark-price candle proxy, положительным cost для long при положительной ставке и обратным знаком для short, полным notional до TP1 candle-close boundary и remaining fraction после неё. Добавлены unit tests. Helper позднее подключён к v14 MTM и final close (см. следующий раздел). CI и фактическое появление первого snapshot пока не подтверждены.

## 2026-11-02 — v14 funding cashflow integration

Funding теперь опционально подключается к активному v14 через `--funding-dir` + `--mark-price-dir` (аргументы обязательны вместе). Один `accrued_funding_cost(position, events, marks, as_of_ts)` используется и для открытого MTM, и для финального close: funding попадает в equity до daily stop/kill-switch и ровно один раз в realized net PnL. TP1 candle-close timestamp хранится в позиции; settlements до/на этой границе используют full initial quantity, после — remaining fraction. Funding rate и mark-candle open читаются из CSV как `Decimal`, без промежуточного `float` преобразования. Отсутствие CSV или timestamp-aligned mark candle open proxy приводит к hard error. Это всё ещё proxy: он не гарантирует равенство фактической settlement mark price. Notional/quantity пока рассчитывается как `size_usdt / entry_price`; точный биржевой qtyStep ещё не подключён к позиции.

`TradeRecord.funding_cost_usdt`, `total_costs` и `funding_cost_usdt` в summary учитывают cashflow отдельно. Добавлены `test_funding_accounting.py`, `test_funding_pnl.py`, `test_funding_mark_to_market.py`. CI run пока не подтверждён. Ограничение: mark-price loader требует точного совпадения funding timestamp с mark candle timestamp; текущий архив hourly mark candles не покрывает settlements вне этих границ.

## 2026-11-02 — correction: v15 multi-bar limit TTL

Повторная проверка вложенности `pending = None` в `research_v15/backtest.py` показала, что удаление заявки находится внутри `if entry > 0`. Если лимитка не коснулась цены (`entry is None` → `entry = 0`), `pending` сохраняется, а на следующем баре возраст снова проверяется через `limit_order_expired(age, limit_valid_bars)`. Поэтому утверждение, что v15 безусловно удаляет pending после первой свечи, было ошибочным и отозвано.

Открытый вопрос — только покрытие: существующие тесты helper-функции и fill helper не доказывают end-to-end удержание заявки внутри `backtest_symbol()`. Нужен интеграционный тест на fill во второй/последней допустимой свече и expiry после TTL. Дефект реализации пока не подтверждён.


## 2026-11-02 — exchange quantity sizing groundwork

Добавлен pure helper `exchange_order_sizing.py`: пересчитывает target notional в контрактный qty после tick rounding для limit, округляет qty вниз по `qtyStep`, выбирает разные max quantity caps для market/limit и пересчитывает notional/risk так, чтобы округление не увеличивало бюджет риска. Если min qty/min notional/max qty не выполняются, helper отклоняет ордер; автоматического split на несколько ордеров нет.

Helper пока не подключён к v14 и не меняет старые результаты. Для полноценной интеграции сначала требуется подтверждённый dated snapshot archive и as-of lookup на timestamp каждой сделки; текущий snapshot нельзя применять к старым историческим периодам.



## 2026-11-02 — checkpoint: verification against current branch head

Проверка выполнена непосредственно по `research/market-regime-v1-main`, HEAD на момент проверки: `10908cd42bd71a3ac64bde6504023399ab9a0a0b`.

### Current engine identity
- Current `Bybit_Trading_Engine_v14_research.py` blob SHA: `1a19ae8c3a321cf1efcba85223c2aded13da5868`.
- SHA в шапке этого отчёта (`e4501bd3666d7fe25ae8c1a10a9813da89b535dd`) не совпадает с текущим файлом. Поэтому старые замечания сверены с текущим кодом ниже; шапка отчёта требует синхронизации.

### Verified fixed in current engine
- `validate_candle_timeframe()` compares every adjacent candle timestamp delta with configured timeframe; `run_simulation_pass()` invokes it before replay.
- `_prepare_pending_entry_risk_budgets()` batches same-bar pending entries, allocates equal risk shares to eligible entries and uses descending `vol_ratio` plus symbol tie-break only for scarce position slots.
- Funding helper `accrued_funding_cost()` is called from both `_unrealized_pnl_at_marks()` and `_close_position()`; the same cumulative cashflow is reflected in MTM and final net PnL. TP1 timestamp boundary and remaining fraction are passed through.
- CI run `41363939889` on the current HEAD completed successfully. Its logs show successful tests for instrument constraints, dated snapshot collector, as-of history, exchange sizing helper, cumulative funding, realized funding PnL, funding MTM, funding coverage preflight, timeframe validation and portfolio accounting.
- The simultaneous-entry allocation fix was introduced in commit `15444377b5fcc56296ae5147e0a06cd8585d74a5`; regression evidence is run `41356881313`, commit `3246eb1df4b9d4cfbd109fa6e6a6316e44710200`.

### P1 — dated instrument snapshot archive is blocked, not merely unintegrated
- `instrument_spec_history.py` and `exchange_order_sizing.py` exist and have offline unit tests, but the as-of history and sizing helper are not wired into v14 position creation / fill.
- The expected repository path `data/instrument_specs/linear/` is absent on the active branch (GitHub Contents API returns 404). The root `data/` currently contains `archives/`; `data/archives/cryptofetch/` contains market-data ZIP archives, not instrument-spec snapshots.
- Workflow `.github/workflows/bybit-instrument-snapshots.yml` has six recorded failed runs: `41358102945`, `41358128366`, `41358414340`, `41358634175`, `41362632896`, `41362639497`. Logs from the latest runs show HTTP 403 Forbidden against the configured Bybit public regional hosts, including `api.bybit.kz`; workflow exits nonzero and no snapshot is committed.
- Consequence: no evidence yet of a real dated snapshot archive. Do not use current instrument specs retrospectively; exchange-valid historical sizing remains unverified.

### P1 — funding coverage is tested as a helper, but no real dataset coverage evidence
- `validate_funding_coverage.py` verifies that every funding event timestamp has a same-timestamp mark candle for the requested symbols. Its tests are synthetic/offline.
- No `data/archives/funding/` or `data/archives/mark_price/` directories are present on the active branch. The workflow run proves the helper tests pass, not that real funding and mark datasets exist or cover any tested trade period.
- The engine uses the mark candle `open` at exact funding timestamp as a proxy, not the exchange's actual settlement mark. Missing exact timestamp fails closed. This is safer than silently dropping events but can reject otherwise usable periods and does not establish exact exchange cashflow.
- Before any funding-aware strategy result is accepted, run the coverage preflight on actual per-symbol datasets and publish the report with first/last timestamps, event counts and missing-event counts.

### Current execution-integrity limitations
- `InstrumentSpecHistory.get_spec()` is standalone and has no call site in the v14 engine; quantity sizing therefore remains notional-derived `size_usdt / entry_price`, without historical qtyStep/minQty/minNotional/tickSize validation.
- Maintenance margin tiers, available collateral, cross/isolated margin, liquidation fees and mark-price liquidation are not modeled in the engine.
- OHLC maker touch remains optimistic: no order book, queue position, traded volume at limit, latency, partial fill or adverse-selection model.
- CI run success is technical regression evidence, not market profitability evidence and not exchange execution validation.

### Next safe sequence
1. Resolve the public-data 403 through an officially permitted data-access path; do not bypass regional restrictions or use proxies to evade them. If unavailable from GitHub runners, a user-controlled local export of public snapshots can later be committed as dated provenance files.
2. Obtain and archive actual funding and mark-price datasets, run coverage preflight for the full test window and all candidate symbols, retain the machine-readable report.
3. Add engine-level tests before integrating historical spec as-of sizing; reject any trade where a dated full-universe snapshot is missing/stale or the rounded exchange quantity violates constraints.
4. Add margin/liquidation modeling from documented historical risk tiers before describing results as exchange-executable.
5. Keep all changes on this research branch. Do not merge to `main`, do not place live orders, and do not reinterpret historical E01–E13 results as if the new execution constraints had been active.


## 2026-11-02 — re-verification: leverage, margin and liquidation model

Current branch HEAD: `87e7e7bd5af2df339849459d463e8a9dc93cf83e`. Current engine blob SHA: `2152729b2f32d9c1cc14dc7f94d2baf962166184`.

### Confirmed limitation (P1 execution-model blocker; not a newly discovered code regression)
- `RiskManager.calculate_position_size()` at engine line 602 sizes notional from risk-to-stop and caps each position at `0.95 * equity * leverage / max_concurrent_positions` (lines 631–635). It does not calculate initial margin, maintenance margin, tiered risk limits, liquidation price, liquidation fee or exchange-side closeout. The configured leverage therefore acts as a coarse notional ceiling; it is not a liquidation simulation.
- Current engine has no liquidation or maintenance-margin implementation and no call to `InstrumentSpecHistory` or `size_to_exchange_constraints`. Position quantity remains represented as USDT notional and PnL is computed as notional × percentage price move.
- The standalone `exchange_order_sizing.py` and `instrument_spec_history.py` modules are present and have offline tests, but they are not wired into v14. Current `data/` contains only `archives/`; `data/instrument_specs/linear/`, `data/archives/funding/` and `data/archives/mark_price/` are absent.
- The instrument snapshot workflow tries the configured official public Bybit regional hosts and fails closed if none succeeds. Earlier recorded runs failed with HTTP 403; no dated snapshot archive exists to support historical as-of sizing. No attempt was made to bypass regional restrictions.

### Decision
Do not integrate current instrument specifications retrospectively and do not claim exchange-executable performance. Next valid step is to obtain a dated, complete instrument-spec snapshot and historical funding/mark datasets through a permitted data-access route; then wire as-of validation and margin/liquidation tiers with regression tests. Until then, backtest PnL remains a strategy-research estimate under simplified notional sizing, not a faithful Bybit account simulation. No engine code change was justified by this re-verification.
