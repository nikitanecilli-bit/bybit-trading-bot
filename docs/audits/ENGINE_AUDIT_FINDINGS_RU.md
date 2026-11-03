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

## 2026-11-03 — re-check: same-timestamp symbol processing remains OPEN

Повторно проверен текущий `run_simulation_pass()` на HEAD ветки после изменений 2026-11-03.

Подтверждённый порядок в коде:
1. На каждом общем баре вызывается `_prepare_portfolio_intrabar_marks()` для всех символов.
2. Затем один раз вызывается общий `_update_mark_to_market(bar_close_ts)`.
3. Рассчитываются пакетные `_prepare_pending_entry_risk_budgets()`.
4. После этого `step_candle()` вызывается последовательно в порядке входного списка `symbols`; внутри каждого шага повторно выполняется MTM, а затем обрабатывается позиция, pending fill или новый сигнал.

Пакетное распределение risk budget уже ранжирует eligible pending signals по `vol_ratio` с symbol tie-break, что снижает зависимость от порядка при распределении слотов. Однако последовательные закрытия позиций, повторные MTM/risk-latch updates и новые входы происходят внутри одного прохода по символам. По статическому чтению нельзя утверждать, что итоговый equity path и forced-exit decisions полностью инвариантны к перестановке списка символов.

**Классификация:** OPEN / модельный риск, не доказанный дефект. Не менял код и не запускал PnL replay.

**Обязательный детерминированный тест перед следующим рыночным экспериментом:** взять один и тот же синхронизированный synthetic fixture и выполнить replay с несколькими перестановками `symbols`; сравнить trade ledger (symbol, entry/exit timestamps, fill/exit reason, qty/notional, gross, fees, slippage, funding), realized/unrealized equity по каждому bar-close timestamp, daily-stop/kill-switch latches и final equity. Если есть различия, определить явную фазовую обработку бара (manage all existing positions → resolve pending entries as a batch → evaluate new signals) и закрепить её тестами до любых PnL claims.

### 2026-11-03 — уточнение same-timestamp audit после сверки тестового покрытия

Повторно проверены текущие `tests/test_portfolio_accounting.py` и `run_simulation_pass()`. Предыдущая заметка выше описывала риск слишком широко; она не должна читаться как обнаруженный дефект.

Уже существующие регрессии покрывают важные сценарии перестановки порядка:
- `test_simultaneous_entries_share_risk_budget_independent_of_symbol_order` — одинаковый общий risk budget при обратном порядке прямого fill вызова;
- `test_position_slot_priority_uses_signal_strength_not_iteration_order` — детерминированный выбор при дефиците слотов;
- `test_same_bar_tp1_on_one_symbol_and_stop_on_another_is_order_independent` — TP1 на одном инструменте и stop на другом;
- `test_two_positions_stopped_on_same_bar_reconcile_once_independent_of_order` — два стопа на одной временной границе;
- `test_drawdown_is_order_independent_for_simultaneous_trade_closes` и `test_drawdown_uses_exit_chronology_not_input_list_order` — порядок закрытий и расчёт DD.

Текущая реализация также предварительно размечает все открытые символы на общем баре, выполняет общий MTM и batch-распределение бюджета до последовательного `step_candle()`. Это снижает риск влияния порядка; перечисленные тесты проверяют ключевые компоненты.

**Остаточный пробел:** в найденном покрытии нет отдельного end-to-end regression, который прогоняет один и тот же полный `run_simulation_pass()` на одинаковом multi-symbol candle fixture при нескольких перестановках `symbols` и сравнивает весь trade ledger + equity path по каждому timestamp. Это остаётся дополнительной проверкой, а не основанием утверждать, что текущий код уже зависит от порядка.

**Статус:** no confirmed same-timestamp ordering defect in current code; component-level invariance tests exist; full-replay permutation test remains recommended. Код движка не менялся.

### 2026-11-03 — фактический CryptoFetch archive audit (CI)

Добавлена проверка не только синтетических примеров, но и всех ZIP-архивов, уже находящихся в репозитории. Результат workflow run [41627245037](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41627245037), conclusion: success.

Машинный отчёт сохранён как CI artifact `cryptofetch-archive-audit` (artifact ID `13225893579`, SHA-256 `a885e15711630d411a8c7fc9f8a62782833c445843ae0e00d104b3d0cfdd62ee`).

Результат проверки шести ZIP:
- 67 CSV members обнаружено; все 67 структурно валидны.
- 64 файла содержат не менее 200 свечей; 3 файла пустые (DAIUSDT, MATICUSDT, XMRUSDT в конкретных архивных копиях).
- 53 уникальных H1 символа, из них 50 имеют непустую H1 историю; 8 символов имеют 15m историю.
- Внутри каждого непустого файла не обнаружено пропусков интервала; все временные метки выровнены по сетке timeframe.
- 6 дублирующихся symbol/timeframe групп, 6 попарных сравнений; 0 конфликтующих OHLCV свечей на пересечении.
- Во всех 6 сравнениях файл, который legacy loader выбрал бы по максимальному числу строк, является надмножеством обеих сравниваемых временных сеток.

**Что это доказывает:** текущие ZIP-архивы структурно читаемы; внутри отдельных файлов нет обнаруженных дыр; дублирующиеся архивные копии не расходятся на общих timestamps; выбор самого длинного файла в проверенных дубликатах не теряет timestamps из сравниваемой пары.

**Чего это не доказывает:** корректность источника/биржи OHLCV, отсутствие survivorship bias, исторический point-in-time состав Bybit universe, полноту листингов/делистингов, корректность свечей относительно биржевого оригинала, наличие funding/mark-price данных или прибыльность стратегии. Разные инструменты имеют разные первые timestamps; это не единая синхронная 53-символьная выборка на всём интервале. Три пустых файла нельзя считать торговыми инструментами и они должны быть исключены из загрузки.

Workflow успешно прошёл все последующие deterministic checks после archive audit. Новых рыночных PnL backtests не запускалось; API/runner не использовались.

### 2026-11-03 — подтверждена и исправлена зависимость полного replay от порядка символов

Полный синхронизированный synthetic replay с тремя символами и двумя доступными слотами обнаружил реальный дефект, который не ловили прежние component-level тесты.

**Причина 1 — discovery bias (confirmed):** `step_candle()` проверял `can_open_new_trade(len(open_positions) + len(pending))` до вычисления нового сигнала. При одновременных сигналах цикл прекращал discovery после первых N символов по порядку списка. Остальные инструменты не попадали в пакетный рейтинг `vol_ratio`; фактический приоритет получали первые символы, а не самые сильные сигналы.

**Причина 2 — batch sizing drift (confirmed):** даже после предварительного распределения общего risk budget `_try_fill_pending()` пересчитывал размер очередной позиции по текущему `risk_mgr.current_equity`. Комиссии/MTM от более раннего fill меняли equity до расчёта следующего fill, поэтому порядок исполнения давал разные размеры, PnL и ledger.

**Исправление в engine:**
- `run_simulation_pass()` теперь сначала обрабатывает текущие позиции и pending orders всех символов, затем собирает новые сигналы отдельной portfolio-wide фазой. Полный набор сигналов доступен для пакетного ранжирования на следующем баре.
- `step_candle(..., evaluate_new_signal=False)` используется в portfolio replay для отделения lifecycle processing от signal discovery; прямые вызовы с default сохраняют прежний односивольный путь.
- `_prepare_pending_entry_risk_budgets()` фиксирует equity snapshot начала batch.
- `_try_fill_pending()` применяет заранее выделенную долю риска и один equity snapshot для всех fills этого batch; `calculate_position_size()` получил необязательный `equity_override`. Это устраняет зависимость последующих размеров от комиссии/MTM первого fill.

**Проверка:** новый тест `test_full_run_simulation_pass_is_invariant_to_symbol_order` выполняет полный `run_simulation_pass()` для `[BTC, ETH, SOL]` и обратного порядка. При лимите двух позиций в обоих случаях выбираются ETH и SOL по силе сигналов; совпадают полный trade ledger, equity path, итоговый PnL, max DD и risk latches. Сценарий включает одновременное открытие, adverse stop на общей свече и срабатывание daily stop.

CI [41628558820](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41628558820) завершился success. Portfolio accounting script: 36/36 тестов; включая четыре exchange-sized regression, которые раньше не запускались при прямом выполнении файла.

**Дополнительный дефект тестового harness (confirmed and fixed):** блок `if __name__ == "__main__"` стоял до четырёх последних exchange-sizing тестов. Поскольку CI вызывает файл напрямую через `python tests/test_portfolio_accounting.py`, эти четыре теста объявлялись уже после выполнения test runner и пропускались. Блок перемещён в конец файла; теперь все 36 тестов исполняются.

Это закрывает full-replay symbol-order audit gate на проверенном synthetic fixture. Это не доказывает прибыльность и не является рыночным PnL тестом. Рыночный replay не запускался.

### 2026-11-03 — H1 cross-sectional universe availability audit

**Confirmed engine constraint:** current `run_simulation_pass()` calls `check_alignment()`, which requires every symbol array to contain exactly the same timestamps and length. It cannot directly replay late-starting/shorter histories as a dynamic universe.

**Confirmed research-runner limitation:** E11/E13 `synchronized_data()` first filters symbols by minimum bar count in every future fold, then intersects all selected timestamp sets to create one fixed synchronized panel. The `covers` decision uses bars from all folds, including periods later than the signal timestamp. This is a complete-case research cohort, not a causal point-in-time universe. It excludes symbols that list later and can induce survivorship/availability selection.

The archive audit found 50 nonempty H1 series, with differing first timestamps (e.g. GRAM/AERO begin in July 2026 and HYPE in September 2026); the files are gap-free internally but do not form one common universe from the beginning of the full year.

**Decision for H-A:** do not reuse E11/E13's fixed-cohort construction as if it represented all available instruments. Before H-A PnL, implement and test a sparse/dynamic shared-capital replay that:
- iterates the union of timestamps while only processing symbols with an actual candle at that timestamp;
- enforces per-symbol warm-up (at least the 72h feature lookback) before admitting a symbol to cross-sectional ranks;
- fails closed if an open position or pending order lacks its required next candle;
- calculates relative strength against only the symbols genuinely available at that timestamp;
- keeps signal discovery and batch entry sizing order-invariant;
- uses a common valid end boundary (or explicit per-position terminal close chronology).

Until that is implemented and tested, H-A may be specified but not run as an all-universe portfolio PnL experiment.

### 2026-11-03 — sparse/dynamic shared-capital replay добавлен и проверен

Чтобы H-A не требовал фиксированной полной timestamp-панели E11/E13, добавлен отдельный режим `run_simulation_pass(..., allow_sparse_data=True)` через `run_sparse_simulation_pass()`.

Режим:
- проходит по объединению timestamp grids;
- на каждом timestamp обрабатывает только символы с реальной свечой;
- требует непрерывную индивидуальную сетку timeframe для каждого символа;
- допускает разные first timestamps и включает символ в signal discovery только после 26 доступных баров (warm-up);
- обрезает все выбранные серии к самому раннему общему terminal timestamp;
- fail-closed останавливает replay, если открытая позиция или pending entry не имеет свечи на требуемом timestamp;
- использует тот же двухфазный signal discovery и frozen batch-equity sizing, что и исправленный aligned replay.

Добавлен `test_sparse_replay_admits_late_symbols_after_warmup_and_is_order_invariant`: BTC начинает в t0, ETH в t+5h, SOL в t+10h; сигналы появляются только после индивидуального warm-up. Полный sparse replay в прямом и обратном порядке даёт одинаковые выбранные инструменты, ledger, equity path и итоговые метрики.

CI [41629995066](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41629995066) — success; portfolio accounting suite 37/37; все 39 CI steps успешны.

**Ограничение:** sparse replay — инфраструктура корректной обработки разной доступности данных, но сам по себе не является доказательством исторического point-in-time состава Bybit. Cross-sectional H-A rank должен на каждом timestamp использовать только инструменты с фактическими барами и полным 72h lookback; будущие listing/coverage сведения не должны влиять на решение в прошлом. Рыночный PnL replay пока не запускался.

### 2026-11-03 — H-A feature tests and archive preparation

- `relative_strength_breakout.py`: pure H1 cross-sectional strength/rank and Donchian breakout evaluator; 24h/72h returns normalized by prior 14 completed bars ATR%; midrank ties; minimum cross-section 5; no future bar access.
- H-A deterministic suite: 9/9 passed (including exact lookback indexing, ATR exclusion of current signal candle, tie ranks, min breadth and timestamp guards).
- `scripts/cryptofetch_sparse_loader.py`: uses existing ZIPs, verifies duplicate overlaps and longest-file timestamp coverage, preserves different symbol start dates, and fails closed on conflicts/gaps.
- `scripts/run_h_a_relative_strength_replay.py`: baseline/H-A shared-capital runner; default prepare-only, PnL requires explicit `--execute`; no exchange API or new data access. Adds timestamped equity snapshots for monthly attribution.
- CI run `41632126319`: success. Actual prepare-only archive manifest: 50/50 H1 symbols included; six duplicate groups, zero conflicting bars, zero longest-file coverage failures; common terminal candle `2026-10-26T00:00:00Z`. First-history dates: 25 on 2025-10-27, 22 on 2026-04-29, and three later starts in July/September 2026.
- The three old research folds remain reused, not blind holdout. Funding is absent; any OHLCV-only result is not full Bybit net PnL. No market PnL replay has been run.

### 2026-11-03 — H-A replay outcome and execution-cost review

- Preregistered H-A replay completed successfully in GitHub Actions run 41633199418 (commit 3ac4bb0c20c48e31e0264df7fe39235cb5c8a658). Results and archive manifest are preserved in artifact h-a-preregistered-ohlcv-results.
- H-A lost in all three reused folds: -1,601.57 / -2,225.91 / -2,307.78 USDT; PF 0.74 / 0.66 / 0.74; expectancy -0.140 / -0.194 / -0.136R. The H-A candidate is rejected; do not tune on these folds.
- Existing ledger attribution shows stop-loss cohorts dominate losses; the direction responsible changes by fold (long in fold 1, both in fold 2, short in fold 3). A global direction block is not supported.
- Static review of _close_position(): gross PnL is formed from realized TP1 gross plus remaining-leg gross; fees/slippage are calculated on entry notional and each executed exit leg; net = gross - fees - slippage - funding. Existing reconciliation tests passed in run 41632815378 (including full shared-capital ledger/equity reconciliation and exchange-fee/slippage-related regression cases). This validates arithmetic consistency, not the empirical accuracy of fee/slippage assumptions.
- H-A's total modeled fees + slippage were 6,164.79 USDT versus gross +29.53 USDT. Costs use 2x engine taker fee and slippage constants; maker fills were disabled. Funding is absent from the OHLCV replay.
- Runner export was extended to retain MAE/MFE, gross-R, risk, session and order type for future diagnostic work. This reporting-only edit is after the last successful Research engine checks run; no claim is made that the latest export edit has been CI-tested.
- No new PnL replay, API, runner, exchange download, or live order was initiated after the H-A result. Main remains untouched.

### 2026-11-03 — повторный аудит H-A artifact, universe и причинности сигнала

- Повторно скачан artifact run 41633199418; результаты в ZIP совпадают с ранее зафиксированными direction/exit aggregates. Это чтение существующего artifact, не новый PnL replay.
- Archive manifest содержит 50 включённых H1 symbols; по времени активное покрытие не равно 50 постоянно: fold 1 — 25–47 активных symbols (median 47), fold 2 — 47–49 (median 49), fold 3 — 49–50 (median 49). Median first timestamp архива — 2026-01-27; самый поздний старт — 2026-09-24. Это подтверждает динамическую неполноту universe, но не доказывает Bybit point-in-time listing coverage.
- В сохранённом H-A artifact trade ledger не содержит MAE/MFE/risk_usdt/gross_R/session/order_type. Эти поля появились в runner позже. Старый artifact нельзя использовать для MAE/MFE attribution; текущие runner-поля ещё не проверены отдельным replay.
- Семантика TradeRecord.mae/mfe ограничена модельным исполнением: adverse excursion на stop bar обрезается до stop fill/gap open, а favourable excursion на fill bar не учитывается из-за неизвестного порядка OHLC. MAE stop-out сделок поэтому execution-bounded и не отражает полный stop-bar wick.
- Статический review relative_strength_breakout.py: strength context использует закрытые H1 бары, проверяет as_of timestamp, 24/72-bar close индексы, ATR только по предыдущим барам; breakout Donchian строится по предыдущим 20 барам, а сигнал формируется по закрытию текущего. В текущей реализации очевидного timestamp lookahead не обнаружено; причинность дополнительно покрыта tests/test_relative_strength.py. Это не устраняет survivorship/listing bias источника данных.
- H-A allocator priority_score действительно использует abs(relative_strength_score); при ограниченных слотах сортировка идёт по силе сигнала, затем по symbol. Ошибочного alphabetical-first allocation в этой версии не обнаружено.
- Research engine checks run 41634060290 успешен на cf74d8afcd65d4da7e04f80aab8e858a65fb0142; workflow includes H-A causality tests, archive audit, gap execution and portfolio accounting. Текущий HEAD отличается от него только документацией аудита/результатов.

### 2026-11-03 — статический аудит stop/TP1/trailing и risk sizing

Проверены актуальные реализации `_manage_position()`, `_apply_tp1()`, `_close_position()`, `AdaptiveRiskManager.calculate_position_size()`, а также существующие тесты `tests/test_gap_execution.py` и portfolio accounting.

**Подтверждённое поведение:**
- Stop проверяется раньше TP1/TP2. Если OHLC одной свечи пересекает и stop, и target, модель выбирает stop; это явно консервативная политика неоднозначного внутрисвечного порядка.
- Gap-stop исполняется по худшему из stop и open: long — `min(stop, open)`, short — `max(stop, open)`. Есть отдельные long/short gap tests.
- TP1 фиксирует 50% позиции; оставшаяся часть учитывается отдельно. После TP1 stop не может ослабляться: long использует максимум старого stop / break-even-plus / ATR trail, short — минимум.
- Новый trailing stop не применяется задним числом к диапазону той же свечи, на которой он был рассчитан; тест явно фиксирует это правило.
- TP2 на одной свече с TP1 моделируется как последовательное исполнение TP1 и остатка на TP2, если partial leg допустим.
- Комиссии и проскальзывание начисляются по каждой фактически смоделированной ноге: entry, TP1, final exit. Stop/trailing/time/kill-switch final exits считаются taker; maker-класс final exit допускается только для take_profit при включённой maker exit модели.
- Risk sizing учитывает начальную дистанцию до стопа плюс ожидаемые entry/stop fees и slippage. Это оценка планового риска, а не верхняя граница фактического убытка: gap, funding и фактическое исполнение могут увеличить его.

**Что не является дефектом, но ограничивает достоверность:**
- OHLC не позволяет узнать, какой экстремум свечи был первым. Stop-first снижает оптимистичное смещение, но не восстанавливает реальную тиковую последовательность.
- Fill-bar stop тестируется по stop price, без возможности установить внутрисвечной gap/порядок до и после фактического входа.
- Trailing обновляется на основании экстремума завершившейся свечи и начинает действовать со следующей свечи — это причинно и консервативно, но отличается от тикового trailing.
- При exchange-sized позиции TP1 может быть отклонён, если после округления по qtyStep/minQty/minNotional обе части не проходят ограничения. В таком случае partial не считается выполненным; позиция остаётся целой, а при TP2 может закрыться целиком. Это допустимый fallback, но в журнале полезно отдельно фиксировать причину пропуска TP1.
- Плановый risk_usdt не включает возможный gap сверх stop и funding. Поэтому риск в журнале нельзя трактовать как гарантированный максимальный убыток.

**Результат проверки:** в просмотренных stop/TP1/trailing/risk-sizing путях подтверждённого арифметического дефекта не найдено. Тесты покрывают long/short gap stops, stop-vs-TP при конфликте одной свечи, partial TP1, trailing остатка, три execution legs и запрет ретроактивного применения нового trailing stop. Это статический аудит плюс проверка состава уже успешного CI run 41634060290 (commit cf74d8a); новый CI на текущем HEAD не запускался. PnL replay не запускался.


### 2026-11-03 — аудит shared portfolio risk, MTM и drawdown

Проверены актуальные реализации `_open_portfolio_risk_usdt()`, `_prepare_pending_entry_risk_budgets()`, `_try_fill_pending()`, `step_candle()`, `_prepare_portfolio_intrabar_marks()`, `_risk_mark_for_position()`, `_unrealized_pnl_at_marks()`, `AdaptiveRiskManager.mark_to_market()` и `_evaluate_drawdown_stops()`; сопоставлены с deterministic tests в `tests/test_portfolio_accounting.py`.

**Подтверждённая логика распределения риска:**
- Перед обработкой синхронного бара allocator фиксирует текущую MTM equity, число свободных position slots и свободный риск: `equity × max_portfolio_risk_pct − sum(open risk)`.
- Открытый риск считается как сумма `risk_usdt × remaining_fraction`. После TP1 учитывается только оставшаяся доля позиции; риск не уменьшается дополнительно из-за подтянутого stop. Это консервативная оценка, а не точный mark-to-stop.
- Pending batch сортируется по `priority_score`, иначе по `vol_ratio`, с symbol как стабильным tie-breaker. Доступный риск равномерно делится между выбранными слотами; все входы batch используют один pre-fill equity snapshot. Перебор symbols при исполнении не может забрать бюджет у следующего сигнала.
- Если выбранный сигнал не исполнился (например, limit не коснулся цены, chase limit отменил вход или биржевые ограничения отклонили размер), его доля не перераспределяется оставшимся сигналам в этом же баре. Это может недоиспользовать риск-бюджет, но не создаёт превышения лимита.
- После TP1/закрытия equity пересчитывается как realized equity + unrealized PnL. Закрытая позиция перестаёт входить в open-risk sum; TP1 фиксирует реализованную часть и оставляет MTM только для остатка.
- Перед последовательной обработкой символов формируются adverse marks для всех уже открытых позиций. При пересечении stop используется моделируемый stop/gap fill; иначе для long/short берётся adverse low/high. Это снижает зависимость portfolio stop/kill-switch от порядка символов.
- Daily stop считается от equity на начало UTC-дня; emergency kill-switch — от peak equity до текущей MTM equity. Оба контроля обновляются по MTM, а не только по закрытым сделкам.

**Подтверждено существующими regression tests:**
- Одновременные входы делят общий risk budget одинаково при перестановке symbols.
- При дефиците слотов выбираются сигналы с большей силой, а не первые symbols в списке.
- TP1 обновляет и сохраняет MTM equity.
- TP1 одного инструмента и stop другого на одной свече дают одинаковый результат при обратном порядке обработки.
- Два одновременных stop-close согласованно обновляют realized/current equity и drawdown.
- Drawdown для одновременных закрытий не зависит от порядка ledger; разные timestamps обрабатываются по exit chronology.
- Полный shared-capital replay проверяет инвариантность ledger/equity path/daily stop/kill-switch к перестановке symbols и сверяет сумму net ledger с final realized equity.
- Sparse replay отдельно проверяет позднее появление инструментов после warm-up и order invariance.

**Ограничение семантики лимита — важно для интерпретации:**
- `max_portfolio_risk_pct` — это лимит допуска **новых входов**, а не непрерывная гарантия, что сумма планового стоп-риска открытых позиций всегда остаётся ниже этого процента текущей equity. Если equity падает после открытия позиций, их абсолютный `risk_usdt` не масштабируется автоматически вниз; новые входы будут ограничены/запрещены по уменьшившемуся бюджету, но уже открытые позиции остаются до stop/exit/kill-switch.
- Следовательно, процент open risk относительно текущей equity может временно стать выше заданного cap. Это не ошибка распределения batch, а свойство текущей политики. Kill-switch ограничивает drawdown по MTM equity, но не является точным ограничителем совокупного будущего stop-loss.
- Плановый риск остаётся оценкой: гэп за stop, mark/last divergence, funding, ликвидация и фактические комиссии/проскальзывание могут увеличить реальный убыток. OHLC adverse marks — консервативная модель, не tick-level replay.

**Итог:** в проверенных путях не найдено подтверждённого дефекта превышения risk budget из-за порядка символов или двойного учёта/потери PnL при TP1 и закрытиях. Существующие тесты покрывают ключевые batch/order/accounting сценарии. Не следует называть portfolio cap гарантированным максимальным убытком или непрерывным процентным ограничителем уже открытых позиций.

**CI evidence:** Research checks run [41634060290](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41634060290), commit `cf74d8afcd65d4da7e04f80aab8e858a65fb0142`, job `tests` — success; шаг `Test portfolio accounting and risk budget` завершён успешно. Сравнение `cf74d8a...d334f6f` показывает только четыре документационных коммита и изменения двух Markdown-файлов; engine и tests не менялись. Поэтому новый CI и тем более PnL replay для этого статического аудита не запускались.


### 2026-11-03 — аудит lifecycle kill-switch / daily stop / pending и восстановления

Проверены `AdaptiveRiskManager._evaluate_drawdown_stops()`, `UnifiedQuantEngine._update_mark_to_market()`, `_try_fill_pending()`, `_manage_position()`, `_close_position()`, `_prepare_portfolio_intrabar_marks()`, `run_simulation_pass()`, `run_sparse_simulation_pass()`, `PlanBStatePersistence.save_state()/load_state()`, конструктор движка и CLI `main()`; сопоставлены с `tests/test_portfolio_accounting.py` и `tests/test_state_persistence.py`.

**Kill-switch: подтверждённый lifecycle в backtest/replay**
- MTM по всем синхронным adverse marks считается до обработки отдельных символов. При достижении порога latch `kill_switch_triggered` фиксируется и состояние сохраняется.
- `_manage_position()` проверяет latch до обычных stop/TP/time-stop. При активном kill-switch позиция закрывается с `exit_reason="kill_switch"`; для цены используется сохранённый adverse intrabar mark, а не благоприятный close/TP. После закрытия PnL/fees/slippage/funding проходят через общую бухгалтерию `_close_position()`.
- При синхронном replay все активные символы проходят portfolio pre-mark и затем обработку; все открытые позиции должны быть принудительно закрыты в этом баровом цикле. Порядок символов не должен менять выбранные adverse marks.
- Pending entry не может исполниться после latch: `_try_fill_pending()` сначала извлекает pending signal, затем вызывает `can_open_new_trade()`; при kill-switch сигнал удаляется и вход отклоняется. Это предотвращает исполнение уже ожидавшего входа после защитного события.
- В sparse replay отсутствие свечи для любой открытой позиции или pending symbol приводит к немедленному `ValueError` до продолжения бара. Это fail-closed поведение: движок не притворяется, что способен безопасно закрыть позицию без свежей свечи.
- Ранее возникшее подозрение, что kill-switch только блокирует новые входы, было неполным: принудительное закрытие находится в `_manage_position()`, а не в самом risk manager.

**Daily stop — другая политика, не дефект**
- Daily stop latch блокирует новые входы до следующей UTC-даты; `on_new_timestamp()` сбрасывает только дневной флаг и переустанавливает `day_start_equity` на текущую equity.
- Уже открытые позиции продолжают обычное управление по стопам/целям/тайм-ауту. Это явно отражено в уведомлении daily stop и отличается от emergency kill-switch, который принудительно flatten-ит открытые позиции.
- Kill-switch latch не сбрасывается при смене дня. Это корректно для аварийной остановки, требующей отдельного ручного вмешательства/новой сессии.

**Persistence и восстановление**
- При переходе daily-stop/kill-switch в true `_update_mark_to_market()` сохраняет latch даже без закрытия сделки. Сами flags включены в сериализуемый risk state.
- `test_mtm_daily_stop_transition_is_persisted_without_trade_close` и `test_mtm_kill_switch_transition_is_persisted_without_trade_close` проверяют именно сохранение флага при отсутствии trade close на момент MTM transition.
- `tests/test_state_persistence.py` проверяет round-trip одновременно открытой позиции, pending сигналов, equity и обоих защитных flags; восстановленный kill-switch остаётся true. Также проверяются persisted last marks, fail-closed на испорченном/неполном state и отказ от свежего backtest поверх restored state.
- При crash сразу после сохранения latch, но до обработки всех символов, в backup могут оставаться открытые позиции и pending signals. Это не позволяет pending сигналу пройти следующий `_try_fill_pending()` при сохранённом latch. Однако автоматический recovery execution loop в текущем CLI отсутствует.

**Критическое ограничение готовности к live**
- Наличие `restore_plan_b=True` и валидатора backup не означает, что реализован безопасный live resume. `run_simulation_pass()` и sparse replay явно запрещают запуск поверх restored state; отдельного цикла reconciliation/исполнения открытых ордеров в этом файле нет.
- CLI не предоставляет флаг восстановления; `--persist-state` только включает запись backup. Режим `watch` после первичного запуска ожидает изменения config и повторно запускает backtest, а не ведёт live market/order loop.
- Следовательно, подтверждён только lifecycle защитных механизмов в OHLCV simulation/replay и сериализация recovery state. Нельзя считать это доказательством, что при реальном подключении к Bybit аварийное закрытие ордеров/позиций будет исполнено. Для этого потребуются отдельный live loop, exchange reconciliation, reduce-only close workflow, проверка частичных fills/ошибок сети и подтверждённые тесты исполнения. Это остаётся вне текущей стратегии-only фазы.

**Модельное ограничение цены kill-switch:** OHLC не содержит точного момента срабатывания внутри свечи. Движок использует adverse mark (low для long / high для short, либо modeled stop/gap fill при пересечении stop) как цену forced exit. Это консервативная replay-модель, а не подтверждённая цена реального рыночного исполнения; её нельзя смешивать с фактическим market fill.

**Итог:** в просмотренном replay lifecycle не обнаружено подтверждённого пути, где pending ордер исполняется после активного kill-switch, или где синхронно доступная открытая позиция игнорирует forced flatten. Daily stop намеренно не закрывает позиции. Главный незакрытый вопрос — не арифметика replay, а отсутствие live execution/reconciliation loop: backup сам по себе не делает восстановленную сессию торгуемой или безопасной.


**Пробел в regression coverage:** найденные тесты проверяют MTM latch persistence, round-trip восстановление kill-switch флага, общий порядок одновременных stop-close и отказ pending fill при общем risk gate (в state persistence tests — stale pending lifecycle). Но в просмотренных тестах нет отдельного end-to-end regression test, который выставляет kill-switch, содержит несколько открытых позиций и подтверждает, что каждая получает `exit_reason="kill_switch"`, закрывается по adverse mark, а pending batch не открывает новых позиций. Поэтому forced-flatten подтверждён чтением кода, но не отдельным тестом полного сценария. Это следующий небольшой тестовый приоритет до любого live-подключения; движок не менялся, так как defect не установлен.


### 2026-11-03 — аудит risk tiers, maintenance margin, mark price и liquidation model

Проверены `bybit_risk_tiers.py`, `bybit_instrument_specs.py`, `exchange_order_sizing.py`, `Bybit_Trading_Engine_v14_research.py`, H1 validation runner `scripts/run_h1_shared_capital_portfolio_validation.py`, H-A runner `scripts/run_h_a_relative_strength_replay.py` и соответствующие тесты.

**Что реализовано корректно как pre-trade metadata/validation:**
- История instrument specs и risk tiers выбирается as-of timestamp, не использует будущие snapshots и отклоняет отсутствующий/устаревший symbol metadata.
- Размер позиции округляется вниз по qtyStep; market/limit quantity caps различаются; проверяются minQty, minNotional, tickSize, trading status и leverage filter.
- Risk tier выбирается по position value и проверяет maxLeverage. Maintenance margin рассчитывается как `position_value × MMR − mmDeduction`; mmDeduction проверяется на согласованность между ступенями.
- Если risk-tier history передана в движок, вход отклоняется при отсутствии as-of tier, устаревшем snapshot, превышении highest riskLimitValue или maxLeverage.
- H1 validation runner требует dated instrument-spec/risk-tier snapshots на всём scored fold с max-age 30 дней; требует Bybit mark/funding coverage и официальные Bybit H1 trade klines. Это хороший fail-closed preflight для источников данных.

**Критическое ограничение: liquidation не моделируется.**
- В engine нет расчёта liquidation price, нет сравнения mark price с liquidation threshold, нет liquidation event/exit reason и нет моделирования частичного/полного биржевого liquidation.
- `initial_margin_usdt` и `maintenance_margin_usdt` записываются в OpenPositionState как metadata. В просмотренном lifecycle эти поля не участвуют в MTM equity, open-risk budget, stop management или forced exits.
- Tier выбирается при открытии позиции по entry notional. Повторного выбора tier при изменении mark price/position value нет; следовательно, переход позиции между risk tiers во время удержания не моделируется.
- Сам risk-tier module в docstring явно оговаривает: это position-level IM/MM, не account-level solvency или liquidation-price calculation. Это не скрытый арифметический баг в функции, а незакрытый слой модели.

**Критическое расхождение last price vs mark price:**
- `_prepare_portfolio_intrabar_marks()` формирует adverse marks из OHLCV trade candles: long использует low, short high (либо modeled stop/gap fill). Эти marks питают unrealized PnL, daily stop и kill-switch.
- Mark-price OHLC архив загружается в `_funding_mark_prices` и используется в accrued funding accounting для settlement timestamp proxy. Он не подставляется в portfolio MTM, stop/kill-switch или liquidation logic.
- H1 validation runner проверяет полноту Bybit mark-price свечей, но это покрытие используется для funding accounting; само наличие mark archive не означает, что риск оценивается по mark OHLC.
- H-A replay ещё дальше от Bybit execution: runner использует CryptoFetch Binance-style OHLCV, явно указывает `funding_included=False` и `bybit_point_in_time_universe_confirmed=False`. Его PnL нельзя трактовать как liquidation-aware Bybit PnL.

**Почему это материально:** официальные правила Bybit для USDT perpetual указывают, что liquidation trigger основан на Mark Price, а не Last Traded Price; position value и maintenance margin пересчитываются по Mark Price, и tier может измениться при изменении position value. Формула liquidation price зависит от entry, size, leverage, extra margin, MMR/MM deduction и estimated close fee. Поэтому OHLC last-price stop replay может не увидеть mark-price liquidation, произошедшую раньше stop, и может неверно оценить потери/выживаемость позиции.

Источники для требований модели:
- Bybit Help Center, Maintenance Margin (USDT Perpetual and Expiry Contracts): https://www.bybit.com/en/help-center/article/Maintenance-Margin-USDT-Contract
- Bybit Help Center, Trading Rules: Liquidation Process (Unified Trading Account): https://www.bybit.com/en/help-center/article/UTA-Trading-Rules
- Bybit KZ Help Center, FAQ — USDT Perpetual and Expiry Contracts: https://www.bybit.kz/en-KAZ/help-center/article/FAQ-USDT-Perpetual-and-Expiry-Contracts

**Риск-мод режима и данных:**
- `risk_tiers_dir` и `instrument_specs_dir` опциональны в базовом `UnifiedQuantEngine`; при их отсутствии движок способен открыть обычную не-exchange-sized позицию без Bybit tier validation. Это приемлемо для абстрактного OHLC research, но не является Bybit-executable validation.
- H1 validation runner передаёт эти директории и fail-closed проверяет историю. Но даже этот runner не становится liquidation-aware, поскольку trade OHLC adverse marks остаются источником MTM/stop path.
- `leverage_mode` хранит строку вроде `ISOLATED_5X` и парсит из неё leverage; отдельной реализации isolated/cross account margin, shared available balance, extra margin или account MMR в engine не обнаружено. Значит, режим маржи — конфигурационная метка/источник плеча, а не полноценная симуляция режима Bybit.

**Итог и приоритет:** не обнаружен дефект в расчёте формулы IM/MM или округлении контрактов. Но обнаружен P0/P1 scope gap для любого утверждения о Bybit liquidation safety: движок не моделирует mark-price liquidation и не учитывает динамическое изменение tier/maintenance margin. До появления отдельной mark-price risk/liquidation модели и её тестов нельзя использовать текущий backtest для вывода «позиция не ликвидируется» или «stop гарантированно сработает раньше ликвидации». Это важнее следующего сигнального оптимизатора. Код торгового движка не менялся; market PnL replay и сбор новых данных не запускались.


### 2026-11-03 — этап 1: изолированная liquidation-price формула

Добавлен отдельный чистый модуль `mark_price_liquidation.py` без изменения lifecycle торгового движка.

**Реализовано:**
- Decimal-расчёт liquidation price для USDT-linear isolated long/short по опубликованной Bybit формуле.
- Учитываются entry price, quantity, leverage, extra isolated margin, taker fee rate, MMR и mmDeduction.
- Проверяется entry notional против dated risk tiers и maxLeverage.
- LP рассчитывается по tier, выбранному на entry notional; не подменяет фиксированную LP динамическим tier на candidate LP. Отдельная функция считает текущую MM по mark notional и соответствующему Mark-Price tier для одной позиции.

**Тесты:** `tests/test_mark_price_liquidation.py` покрывает официальный пример Bybit (40,000 entry, 1 BTC, 50x, 0.5% MMR, 3,000 extra margin → 36,380.25 LP), long/short adverse direction, fixed entry-tier LP despite crossing LP notional boundaries, dynamic Mark-Price tier/MM changes for long and short, directional estimated close fees, превышение risk limit, maxLeverage и некорректные входы. Тест подключён к Research CI.

**Границы модели (не заявлять как готовую Bybit liquidation simulation):**
- Это только isolated position-level LP estimator. Он не моделирует Cross/Portfolio Margin, account-wide MMR/available balance, hedged offsets, AMR, funding-driven margin depletion, partial liquidation, ADL, bankruptcy-price execution или задержки/очередность биржевого liquidation engine.
- Текущий движок пока не вызывает этот модуль и не использует mark-price OHLC для liquidation events. Интеграция с mark candles — отдельный следующий этап.
- При TP1/частичном сокращении quantity и entry/position margin должны пересчитываться для оставшейся позиции; пока lifecycle integration отсутствует.
- Формула и результат являются оценкой по опубликованным правилам; фактический LP может немного отличаться из-за биржевых fee/margin details.

Источник формулы и опубликованного контрольного примера: Bybit Help Center, "Trading Rules: Liquidation Process (Unified Trading Account)", https://www.bybit.kz/en-KAZ/help-center/article/UTA-Trading-Rules-Liquidation-Process (USDT perpetual isolated long/short formulas and 40,000/50x/3,000 extra-margin example).

Изменены только новый модуль, его тест и Research CI workflow; торговый движок и торговая логика не менялись. PnL replay, API и новые market data не запускались.


**Уточнение по актуальной модели Bybit (официальная статья обновлена 2026-06-18):**
- Для USDT/USDC isolated IM остаётся привязанной к Entry Price, а MM пересчитывается от Mark Price. Risk-limit tier динамически меняется по Mark Price и совокупной стоимости позиций/ордеров; изменение tier меняет MM и в резком движении может приблизить/вызвать ликвидацию.
- При этом Bybit указывает, что isolated liquidation price остаётся фиксированной для неизменной позиции. Поэтому LP formula и текущая Mark-Price MM — два разных расчёта, а не один candidate-tier root search.
- Модуль скорректирован: `calculate_isolated_usdt_liquidation_price()` выбирает tier по entry notional; `calculate_mark_price_maintenance_margin()` отдельно выбирает tier по текущему mark notional и включает estimated close fee (long: entry notional × (1−1/lev) × taker fee; short: entry notional × (1+1/lev) × taker fee). `mark_candle_crosses_liquidation()` определяет пересечение фиксированной LP по Mark-Price high/low; `calculate_isolated_usdt_bankruptcy_price()` отдельно рассчитывает bankruptcy price по entry/leverage и направленно округляет по tickSize. Это всё ещё не моделирует фактическую очередь/исполнение liquidation settlement.
- Dynamic-MM helper пока рассматривает только одну позицию. Bybit risk tier учитывает совокупную стоимость позиций и ордеров, поэтому до учёта account/order aggregation результат — position-level approximation, не account-exact liquidation engine.
- Предыдущая гипотеза о выборе LP tier по candidate liquidation notional была снята до интеграции в движок; тесты теперь проверяют fixed LP entry-tier и отдельно dynamic Mark-Price MM tier.

Официальный источник: Bybit, "The New Margin Calculation: Adjustments and Implications", last updated 2026-06-18, https://www.bybit.com/en/help-center/article/Understanding-the-Adjustment-and-Impact-of-the-New-Margin-Calculation (isolated IM/MM, dynamic Mark-Price risk tiers, fixed liquidation price, lines 160–165, 169–173, 256–265). Bankruptcy price reference: https://www.bybit.com/ru-RU/help-center/article/Bankruptcy-Price-Perpetual-and-Expiry-Contracts.


**Статус проверки кода на момент фиксации:** 10 unittest-методов добавлены и включены в Research CI (py_compile + отдельный запуск тестового файла). GitHub connector вернул пустой список commit statuses; поэтому автоматический CI run нельзя считать подтверждённо завершившимся. Независимые арифметические проверки контрольного примера, fixed-entry-tier LP, dynamic Mark-Price MM, directional fees, bankruptcy price и tick rounding выполнены отдельно (15/15 assertions), но это не подменяет запуск полного unittest-файла.
