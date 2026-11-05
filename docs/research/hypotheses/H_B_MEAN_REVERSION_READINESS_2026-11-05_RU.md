# H-B Mean Reversion — readiness assessment

Дата: 2026-11-05  
Ветка: `research/market-regime-v1-main`  
Статус: **DESIGN GAP REVIEW / NOT PREREGISTERED / NO PNL RUN**

## 1. Решение

H-B остаётся приоритетным кандидатом для следующей спецификации, но сейчас **не готова к preregistration и реализации**. Не запускать market PnL, parameter sweep, event study или paper/live. Этот документ фиксирует пробелы, а не утверждает новую стратегию.

Основание: `NEXT_STRATEGY_RESEARCH_PLAN_RU.md` описывает H-B только как mean reversion в подтверждённом range regime и требует сначала определить причинный сигнал, stop/exit и look-ahead tests. Новый источник пользователя предлагает несколько альтернативных условий (падение на 2–3 ATR за 24 часа; RSI ниже 30 или z-score ниже -2; BTC-фильтр; стабилизация через close/VWAP/EMA), но не задаёт одну однозначную конструкцию.

## 2. Сопоставление с текущим кодом

Расширенный статический просмотр исследовательских модулей выявил важное уточнение:
- `Bybit_Trading_Engine_v14_research.py` (SHA `ef09d744be25eb477d886f9afd73b1394f8e0b1a`) содержит Donchian/volume и ATR; готовые RSI, ADX, VWAP, Bollinger Band или z-score pipelines в нём не обнаружены.
- `market_regime.py` (SHA `f4add7dd8a7730e65489a7a29c85281e83bdfe1f`) **уже содержит causal regime classifier**: efficiency ratio, EMA alignment/slope, ATR-normalized slope и ATR-percentile/median volatility ratio; выходы `range`, `trend_up`, `trend_down`, `high_vol_chop`, `transition`, `unknown`.
- `tests/test_market_regime.py` (SHA `e4e1066ef56e2908b895631274513b554a15479f`) содержит synthetic tests для трендовых/колебательных режимов, warm-up, invalid OHLC, timestamp order и future-mutation invariance.
- `market_regime.py` прямо обозначен как отдельный research-only classifier: он не подключён к trading signals, execution или sizing. Его default thresholds существуют, но ещё не обоснованы/заморожены для H-B.
- `market_structure.py` содержит EMA/trend и breakout-quality helpers, но не mean-reversion signal.

Следовательно, утверждение «формального range classifier нет» было бы неверным: classifier есть. Реальный пробел — **нет отдельной H-B preregistration, которая выбирает и фиксирует конкретную конфигурацию этого classifier, правила входа/стабилизации/выхода и причинное соединение с shared-capital runner**. Отсутствие RSI/ADX/VWAP/Bollinger/z-score в просмотренных модулях остаётся верным, но они не обязательны, если H-B использует уже имеющийся classifier.

## 3. Неопределённости, которые нельзя смешивать в первом тесте

| Область | Что пока не определено | Почему это важно |
|---|---|---|
| Таймфрейм | H1 или H4; «24 часа» означает 24 бара или календарное окно | Меняет частоту, задержку и смысл экстремального движения |
| Range regime | Точный causal критерий, окно и момент подтверждения | Без него H-B не соответствует исходной гипотезе |
| Oversold trigger | ATR move, RSI, z-score или иной единственный сигнал | Одновременный выбор создаёт скрытый parameter search |
| Stabilization | Close выше предыдущего high, возврат над VWAP/EMA или иное одно правило | Влияет на цену входа и может запаздывать |
| BTC context | Точный индекс/инструмент, окно и порог запрета | Неясный фильтр может стать post-hoc оправданием |
| Exit | Mean target, time stop, volatility stop; приоритеты при конфликте | Без этого нет законченной торговой гипотезы |
| Short side | Симметричная ли стратегия и допустима ли асимметрия | Long-only и long/short имеют разные режимы и риски |
| Universe | PIT membership, минимальная ликвидность и delisted symbols | Текущий список контрактов создаёт survivorship bias |
| Costs | Fees, slippage, funding, Mark Price, instrument specs | Данные и учёт пока не закрывают Bybit-native requirements |
| Validation | Независимый период после уже просмотренных folds | Повторное использование исследованных периодов не даёт blind OOS |

## 4. Рекомендуемая последовательность спецификации

До preregistration выполнить только документационную/детерминированную работу:

1. Сначала выбрать один таймфрейм и формально определить календарное окно oversold move.
2. Выбрать один range-regime classifier с causal inputs; не объединять несколько индикаторов.
3. Выбрать один oversold trigger. RSI/z-score/ATR-варианты не превращать в sweep.
4. Выбрать ровно одно правило стабилизации и точный момент исполнения.
5. Зафиксировать long/short scope, stop, target, time stop, same-bar event priority и sizing.
6. Описать baseline, null/shuffled control, folds, N_trials и критерии REJECT/INCONCLUSIVE.
7. Отдельно провести prefix/future-mutation и synthetic tests на границы окон, пропуски баров, свечные гэпы и порядок событий.
8. Только после прохождения действующих data/accounting gates рассматривать один заранее зарегистрированный shared-capital replay на пригодных данных.

Не выбирать параметры по уже использованным CryptoFetch folds. Эти данные не являются независимым holdout; отсутствие Bybit-native provenance, PIT universe, полных funding/Mark и dated instrument specs остаётся блокирующим.

## 5. Предлагаемая структура первого H-B теста (ещё не спецификация)

- Один timeframe.
- Один объективный range-regime gate.
- Один oversold trigger.
- Одно подтверждение стабилизации.
- Один неизменный набор правил выхода.
- Один frozen baseline и один candidate.
- Общий капитал и одинаковая cost/risk модель.
- Никаких дополнительных news, macro, funding-contrarian или momentum фильтров в этом тесте.

Численные значения и точные определения намеренно не заполняются здесь: выбор без предварительного обоснования создавал бы видимость preregistration задним числом.

## 6. Что не делалось

Торговый код не менялся. Индикаторы не добавлялись. Market PnL, parameter sweep, event study, новые сборы данных, Bybit API, paper/live и реальные ордера не запускались. CI для этого документа не запускался. Статус H-B остаётся **CANDIDATE / DESIGN INCOMPLETE / DATA-BLOCKED**.


## 7. Предлагаемый минимальный causal signal contract v0.1

Это **кандидат для synthetic/mechanics validation**, а не разрешение на market replay и не утверждение, что пороги оптимальны. Выбран один вариант из пользовательских идей, чтобы не превращать первый тест в перебор:

**Scope:** long-only, H1, один инструмент за раз на первом механическом этапе. Short-side не включать в ту же гипотезу.

**Range gate:** использовать существующий `market_regime.classify_candles()` с явной frozen `RegimeConfig`. Режим на последнем закрытом баре перед импульсом должен быть `range`. Конфигурация classifier должна быть записана целиком в experiment card; нельзя молча использовать default config. Не добавлять BTC filter, RSI, VWAP, z-score, news или macro.

**Oversold event:** на закрытии бара t:
`close[t] <= close[t-24] - 2.0 * ATR[t-1]`.
ATR — значение classifier ATR, рассчитанное только до shock bar (t-1), чтобы размер импульса не расширял собственный порог. Ровно 24 последовательных H1 бара; если есть gap, событие недействительно. `regime[t-1]` должен быть `range`. Если `ATR[t-1]` пустой/неположительный или warm-up не завершён — fail closed.

**Stabilization:** на следующем закрытом H1 баре t+1 требовать `close[t+1] > high[t]`. Вход не по close подтверждения, а по следующему доступному open `open[t+2]`. Если следующего бара нет, есть gap, или позиция уже занята — сигнала/входа нет. Это исключает использование незакрытого бара и исполнение по цене, известной только после его закрытия.

**Почему именно так:** shock и подтверждение — два отдельных события; range label берётся до shock, а не после него (падение само может перевести classifier в trend/transition). Условие не использует будущие свечи. ATR, порог и 24-барное окно не подбираются на CryptoFetch folds. Порог 2.0 ATR — фиксированная гипотеза из входной идеи, а не эмпирически найденное значение.

### 7.1. Что ещё блокирует полноценную preregistration

До полного frozen experiment card остаются обязательными:
- точное правило initial stop, включая гэп ниже stop и same-bar stop/target priority;
- точный mean-reversion target (например, заранее определённая reference mean) и time stop; нельзя выбирать их после просмотра результатов;
- sizing, max concurrent positions, shared-capital priority и поведение при нескольких одновременных сигналах;
- universe/PIT eligibility, listing/delisting и минимальная история;
- baseline, chronological folds, untouched holdout (если существует), null/control, N_trials и количественные reject/inconclusive criteria;
- audited fee/slippage/funding/Mark accounting.

Не предлагаю заполнять эти пункты произвольными числами: это было бы не preregistration, а скрытая оптимизация/ложная точность. Поэтому текущий статус остаётся **DESIGN CANDIDATE v0.1 / NOT PREREGISTERED / DATA-BLOCKED**.

## 8. Обязательные synthetic tests до адаптера

1. Range gate берётся с t-1; если только t помечен range, сигнал не возникает.
2. Точное равенство порогу `close[t] == close[t-24] - 2*ATR[t-1]` принимается; значение чуть выше не принимается.
3. ATR shock bar не может изменить собственный порог.
4. 23 или 25 баров вместо 24, duplicate timestamp и missing H1 candle fail closed.
5. Стабилизация использует только завершённый t+1 и требует строго `close[t+1] > high[t]`; равенство не подтверждает.
6. Цена входа — `open[t+2]`, а не close[t+1] и не low/high будущей свечи.
7. Prefix/future-mutation: добавление/изменение свечей после t+1 не меняет решение/время сигнала для уже завершённого префикса.
8. Warm-up/unknown/high_vol_chop/trend_up/trend_down/transition не допускаются как range.
9. Один сигнал на один shock event; нельзя повторно генерировать вход на каждом следующем баре из-за сохранённого состояния.
10. Long-only и одна позиция на инструмент: открытая позиция блокирует новые H-B entries до закрытия.

Эти тесты проверяют механику сигнала, не торговую доходность. Их нельзя заменять прогоном по историческим рыночным данным.


## 9. Static integration audit: shared-capital replay seam

Проверены `run_sparse_simulation_pass()`, `run_simulation_pass()`, `UnifiedQuantEngine.step_candle()` и текущий shared-capital H1 validation runner.

**Положительный результат:** отдельная стратегия может быть подключена через уже существующий `signal_evaluator(symbol, history, cfg, context)` callback в `run_simulation_pass(..., allow_sparse_data=True)`. Для каждого timestamp engine сначала обрабатывает существующие позиции/заявки, затем строит completed-bar histories, вызывает evaluator и ставит возвращённый signal в pending. Следующая свеча обслуживает pending fill. Это лучше, чем monkey-patching `QuantStrategyCore.evaluate_signal` в H-B runner: можно оставить базовый Donchian engine без изменений и передавать H-B только через research callback.

**Ограничения seam:**
- `step_candle(..., evaluate_new_signal=False)` возвращает eligibility только для символов без открытой позиции/pending заявки; H-B evaluator не вызывается для уже занятого символа.
- `signal_context_provider` вызывается после обработки всех активных символов на текущей close boundary. Общий cross-sectional context доступен, но H-B первой версии его не требует.
- Sparse replay требует непрерывную timeframe сетку внутри каждого symbol series и общий terminal candle; пропуски H1 не должны автоматически интерполироваться.
- Текущая H1 validation runner `run_h1_shared_capital_portfolio_validation.py` жёстко ориентирована на Bybit-native H1, funding/Mark и dated specs/risk-tier snapshots. Она не является подходящим запуском до прохождения соответствующих data/accounting gates.
- Новый H-B runner должен иметь отдельный manifest/provenance и использовать sparse replay callback, а не расширять существующий Donchian parameter grid.

**Существенная проверка до реализации:** выяснить контракт signal dictionary, который потребляет `_try_fill_pending` / `_prepare_pending_entry_risk_budgets`, и сделать synthetic adapter tests на sizing/stop geometry без вызова рыночных данных. Не переиспользовать Donchian сигнальные поля как будто они автоматически корректны для H-B.

Файлы/ориентиры: `Bybit_Trading_Engine_v14_research.py` (`run_sparse_simulation_pass`, `run_simulation_pass`, `step_candle`); `tests/test_sparse_simulation_replay.py`; `scripts/run_h1_shared_capital_portfolio_validation.py`.

**Вывод:** инфраструктурный seam для отдельного H-B evaluator уже существует; отдельный торговый движок не нужен. Но это пока статический вывод о способе интеграции, не доказательство готовности H-B. Market PnL и code integration не выполнялись.


### 9.1. Signal dictionary and exit-policy boundary

Проверен контракт `_try_fill_pending()`:
- обязательные поля pending signal: `signal_ts`, `direction`, `entry_price`, `order_type`, `stop_dist`;
- опционально сохраняется `signal_origin_ts`; для приоритизации batch sizing используются `priority_score` или `vol_ratio`;
- исполнение проверяет, что candle timestamp равен `signal_ts + timeframe_ms`, затем строит уровни через общий `QuantStrategyCore.build_levels()` и sizing через общий risk manager.

Это подтверждает возможность подать H-B entry signal через callback, но **не решает H-B exits**: текущий engine после открытия вызывает общий `_manage_position()`, который реализует существующую stop/TP/trailing/time-stop механику breakout engine. Одного custom `signal_evaluator` недостаточно, чтобы получить mean-reversion exit contract. Нельзя маскировать это, записав в signal произвольные TP-поля: уровни строятся централизованно из `stop_dist` и глобального cfg.

Поэтому перед кодовой интеграцией нужно использовать уже существующее поле OpenPositionState.strategy и добавить изолированную ветку H-B внутри общего _manage_position(), без изменения поведения остальных стратегий. Этот путь подтверждён последующим статическим аудитом ниже.


### 9.2. Position state, restore compatibility and exit ordering

Проверены OpenPositionState, PlanBStatePersistence.save_state()/load_state(), _manage_position() и _close_position() в Bybit_Trading_Engine_v14_research.py на ветке research/market-regime-v1-main.

**Persistence contract:**
- OpenPositionState.strategy уже сохраняется и восстанавливается; отдельный discriminator для выбора H-B exit policy не нужен.
- Backup сериализует позиции через dataclasses.asdict(pos).
- Restore сначала вычисляет допустимые поля из dataclasses.fields(OpenPositionState), отклоняет неизвестные ключи, проверяет обязательные/числовые поля и затем вызывает OpenPositionState(**pos_dict).
- Следовательно, новые optional H-B metadata fields можно добавить в конец dataclass с безопасными defaults: старые backups без этих ключей продолжат восстанавливаться. Но это не автоматическая гарантия: если поле влияет на H-B управление, загрузчик должен отдельно валидировать его тип, конечность/диапазон и взаимную согласованность.
- Текущий TradeRecord уже фиксирует strategy, исходный/финальный stop, TP1/TP2, TP1 state, final stop и breakout level. Если H-B использует отдельную target reference/exit metadata, нужно решить, какие сведения являются audit provenance и должны пережить закрытие сделки; не перегружать tp2_price без явного общего контракта.

**Порядок управления позицией:**
1. _manage_position() сначала вычисляет возможную ликвидацию по Mark Price.
2. Далее идут liquidation, portfolio kill-switch и protective stop. При stop gap текущая модель использует худшую цену min(stop, open) для long.
3. Только если защитные условия не сработали, выполняется discretionary exit logic.
4. Любой выход проходит через _close_position(), который централизованно считает gross PnL, TP1 realized component, fees, slippage, funding, net PnL, TradeRecord и обновляет risk manager.

**Рекомендуемая точка интеграции H-B:** после общих protective checks (liquidation / kill-switch / stop) и до breakout-specific TP1/TP2/trailing/time-stop block. Ветка должна включаться только при pos.strategy == "H-B-mean-reversion". Общие protective checks и _close_position() остаются едиными. Не выносить расчёт PnL в отдельный H-B код и не менять глобальную стратегию.

**Неразрешённые execution semantics, которые нужно заморозить до реализации:**
- Если stop и H-B mean target задеты одной H1 свечой, stop-first (консервативный исход), поскольку OHLC не раскрывает последовательность событий.
- Stop gap: для long выход не лучше худшей из open и stop; это согласуется с существующей защитной логикой.
- Target gap: не засчитывать улучшение относительно target без отдельной модели исполнения; консервативная механика — моделировать выход ровно по target (без gap improvement) либо заранее определить и последовательно применять иное правило open/target.
- На fill bar discretionary target не исполнять по экстремумам, которые могли возникнуть до фактического входа; защитный stop остаётся активным согласно существующей модели.
- Exit reason должен однозначно различать H-B mean target и H-B time stop, чтобы trade ledger позволял аудит.
- Пережившие restart позиции должны восстанавливать ту же target reference и exit-policy version, что были зафиксированы при входе; нельзя пересчитывать target по текущему rolling window после рестарта.

**Что ещё не выбрано:** сама target reference (например, заранее определённая середина диапазона или causal rolling mean), stop placement, time-stop horizon, а также конкретная формула для gap target. Здесь не назначаются числа или формулы задним числом. Это остаётся блокером preregistration.

**Synthetic-only acceptance tests для будущей реализации:**
1. Старый backup без новых H-B полей восстанавливает legacy position без изменения значений.
2. H-B backup round-trip сохраняет target reference, exit-policy version и все lifecycle поля без потери точности.
3. Неизвестная/некорректная H-B metadata отклоняется fail-closed.
4. Одновременное касание stop и target закрывает по stop.
5. Stop gap закрывает по худшей цене open/stop.
6. Target gap следует одному заранее frozen правилу и не получает незаслуженного улучшения исполнения.
7. На fill bar нет discretionary target fill по предшествовавшему входу экстремуму.
8. H-B exit проходит через общий _close_position() и сохраняет fees/slippage/funding/gross/net ledger invariants.
9. Legacy breakout strategy regression fixtures дают идентичный результат до/после добавления H-B branch.
10. Restart между сигналом и выходом не меняет target reference, time-stop counter или exit-policy version.

**Ограничение текущего этапа:** это статический контрактный аудит. Торговый код не менялся, тесты не запускались, market PnL не рассчитывался, CI после документации не запускался. Реализация остаётся заблокированной до завершения H-B exit preregistration и появления санкционированного пути изменения code files.


## 10. Exit contract candidate v0.1 — synthetic-only, not market preregistration

Ниже зафиксирован **один механически однозначный кандидат** для закрытия design gap. Это не результат оптимизации и не разрешение на рыночный PnL. Значения выбраны из структуры уже зафиксированного H1 signal contract и пользовательского диапазона удержания 12–48 часов; они не объявляются оптимальными.

### 10.1. Frozen candidate rules

Все ссылки на свечи используют индексы signal contract раздела 7: shock bar — t, stabilization bar — t+1, entry — open[t+2].

| Элемент | Кандидат v0.1 | Причина / fail-closed |
|---|---|---|
| Initial stop | low[t] — минимум shock-свечи, фиксируется при сигнале и не расширяется | Структурная граница распродажи; без подбора ATR-buffer. Если entry_price <= low[t], pending entry отменяется |
| Mean target | Простое среднее close[t-24:t], то есть 24 закрытия до shock bar; значение фиксируется при сигнале | Явная pre-shock mean reference, не использует shock/stabilization/future bars. Если target <= entry_price, вход отклоняется |
| Target execution | Полное закрытие по зафиксированной target price; gap не даёт улучшения выше target | Консервативно, без моделирования недоказанного price improvement |
| Time stop | 24 H1 бара удержания, считая fill bar первым; если target/stop не сработали — выход по close 24-го бара | Один горизонт внутри исходного диапазона 12–48h; не sweep и не «лучший» горизонт |
| Partial exits / trailing | Не использовать; только один полный discretionary target либо time exit | Убирает лишние степени свободы из первого теста |
| Stop update | Не переносить в breakeven, не трейлить, не усреднять | Сохраняет один фиксированный риск-уровень |
| Direction | Только long | Соответствует signal contract v0.1 |

close[t-24:t] — полуоткрытый интервал: включает t-24 и исключает t; ровно 24 наблюдения. Если любое из них отсутствует, timestamps не образуют непрерывную H1 сетку или значение невалидно, mean target не вычисляется и сигнал отклоняется.

### 10.2. Event ordering

Приоритет для одной H1 свечи:

1. liquidation по существующему Mark-price механизму;
2. portfolio kill-switch;
3. protective stop;
4. mean target;
5. time stop на close бара.

Если stop и target затронуты одной свечой, закрытие по stop. Stop gap для long: min(stop_price, candle.open) вне fill bar, как в существующем общем stop path. Если entry candle открывается на/ниже initial stop — pending entry отменяется, позиция не создаётся. На fill bar discretionary target не проверяется по high: экстремум мог произойти до фактического входа. На 24-м баре, если stop/target не сработали, time stop использует его close в соответствии с текущей close-based time-stop convention движка.

Target gap-through не получает улучшения: цена закрытия остаётся ровно зафиксированной target price. Если stop и target потенциально сработали на одном баре, stop всегда выигрывает независимо от open/high/low/close последовательности.

### 10.3. Lifecycle and persistence

При создании позиции H-B должны быть сохранены как минимум:
- strategy = H-B-mean-reversion;
- h_b_exit_policy_version = v0.1;
- h_b_target_price — конечная положительная цена;
- h_b_shock_ts_ms и h_b_entry_signal_ts_ms для provenance;
- h_b_max_hold_bars = 24 либо эквивалентная неизменяемая версия политики.

Initial stop уже находится в общем stop_price; время удержания — в общем bars_held. Не дублировать их без необходимости. Restore обязан проверить, что H-B target выше entry для long, stop ниже entry, policy version поддерживается, timestamps согласованы с timeframe, а поля конечны и положительны. Legacy positions без H-B metadata продолжают идти по прежней ветке. H-B позиция с отсутствующей/некорректной metadata должна fail closed, а не попадать в breakout exit logic.

При рестарте target и policy version восстанавливаются из backup; не пересчитываются из новой истории. После закрытия target и версия должны попасть в audit trail TradeRecord или однозначно сохраняемую exit metadata.

### 10.4. Synthetic acceptance cases specific to this exit contract

1. Stop равен low[t]; target равен mean ровно 24 pre-shock closes, исключая close[t].
2. Мутация shock/stabilization/future closes не меняет зафиксированный target.
3. 23/25 pre-shock closes, missing H1, duplicate timestamp, NaN/inf, zero/negative target — reject.
4. entry <= stop или target <= entry — pending entry отклоняется до открытия позиции.
5. Fill-bar target wick не закрывает позицию; fill-bar protective stop остаётся активным.
6. Stop/target на одной свече — stop-first; gap stop — худшая из stop/open.
7. Target gap-through закрывается по target, не по более выгодному open.
8. Time stop срабатывает ровно на close 24-го бара, считая fill bar первым; на 23-м ещё не срабатывает.
9. Restore round-trip сохраняет target, policy version, shock/signal timestamps и bars held; restart не сдвигает time-stop deadline.
10. H-B проходит через общий _close_position(); legacy breakout fixtures не меняются.

### 10.5. Decision status

Этот контракт закрывает **механический design gap** для synthetic tests, но не все preregistration gates. До market experiment всё ещё необходимы: утверждённая frozen RegimeConfig и полный experiment card; sizing и portfolio concurrency/priority; PIT universe и независимые chronological folds; null/control и N_trials accounting; количественные reject/inconclusive criteria; Bybit-native OHLC/Mark/Funding, dated specs/risk tiers и audited costs.

**Статус:** EXIT CANDIDATE v0.1 / SYNTHETIC-ONLY / NOT MARKET-PREREGISTERED / DATA-BLOCKED. Никаких market PnL, parameter sweeps, data downloads, API, paper/live или code changes этим решением не разрешается.


### 10.6. Entry seam compatibility check — absolute stop is not yet representable

Повторно просмотрен реальный код `_try_fill_pending()` на текущей ветке. Это выявило дополнительное ограничение, которое важно не скрывать:

- callback может передать `stop_dist`, но при fill движок заново строит `stop_price`, TP1 и TP2 через `QuantStrategyCore.build_levels(direction, fill, sig["stop_dist"], cfg)`;
- затем sizing и `initial_stop_dist` используют эту fill-relative геометрию;
- отдельные абсолютные поля `h_b_stop_price` / `h_b_target_price` в pending contract сейчас не потребляются;
- для H-B stop должен быть ровно `low[t]`, а не расстоянием от неизвестного заранее следующего open. Вычислить точный `stop_dist` в callback нельзя без знания будущего fill open. Подстановка close[t+1] создаст расхождение при gap между сигналом и входом и изменит риск.

**Следствие:** существующий `signal_evaluator` seam достаточен для генерации/передачи сигнала, но не достаточен для точной реализации exit candidate v0.1. До кода нужен узкий strategy-aware fill contract: на фактическом fill вычислить абсолютный H-B stop из сохранённого shock low, проверить stop < fill и target > fill, затем вычислить фактический stop distance и передать его общему risk sizing. Не-H-B ветка должна продолжить использовать прежний `build_levels()` без изменения. H-B target должен переноситься из pending в position state, а стандартные TP1/TP2 не должны случайно управлять H-B позицией.

**Обязательные synthetic adapter tests:** gap между signal close и entry open; entry open на/ниже shock low; target на/ниже fill; расчёт size/risk по фактическому fill-to-stop distance; точное сохранение absolute stop/target в позиции; legacy signal dict без H-B полей даёт прежние уровни побитово/численно идентичные; H-B не попадает в breakout TP/trailing/time-stop ветку.

Это design/integration blocker, не повод приближать stop к close[t+1] или молча менять stop. Торговый код не менялся.


### 10.7. Pending/fill adapter contract and remaining policy mismatch

Статическая трассировка `step_candle()` → `_try_fill_pending()` → `OpenPositionState` уточняет минимальный adapter contract.

**Pending payload для H-B (все поля должны пережить backup):**
- `strategy = "H-B-mean-reversion"`;
- `direction = "long"`;
- `signal_ts` = timestamp stabilization bar t+1; именно он задаёт обязательный следующий entry bar t+2;
- `signal_origin_ts` = исходный timestamp shock bar t для общего provenance, если сохраняется текущая семантика поля;
- `h_b_shock_ts_ms` = timestamp shock bar t;
- `h_b_stop_price` = абсолютный `low[t]`;
- `h_b_target_price` = frozen mean `mean(close[t-24:t])`;
- `h_b_exit_policy_version = "v0.1"`;
- `order_type = "market"`; fill price — фактический `curr.open` свечи t+2.

**Fill-time validation и sizing:**
1. До sizing проверить типы/конечность всех H-B чисел и целочисленность/порядок timestamps.
2. Проверить, что текущая свеча — ровно H1 бар после signal_ts; старый pending уже отсекается общим freshness guard.
3. Получить `fill = curr.open`; потребовать `0 < h_b_stop_price < fill < h_b_target_price`. Иначе pending отклоняется, позиция не открывается.
4. Вычислить `actual_stop_dist = fill - h_b_stop_price`; именно это значение использовать в общем `calculate_position_size(fill, stop_price, ...)`, `risk_usdt` и `OpenPositionState.initial_stop_dist`.
5. Создать позицию с `stop_price = h_b_stop_price`, H-B target/policy/shock timestamp metadata; обычные TP1/TP2 не должны участвовать в H-B exit branch. Для полей dataclass, которые технически обязательны для legacy accounting, допустимы только явно определённые neutral/sentinel values, не используемые H-B manager; нельзя подставлять фиктивные близкие TP.
6. Dated instrument specs, risk tiers, lot/min-notional validation и shared portfolio risk budget остаются общими. Если фактический exchange sizing после округления нарушает stop/target геометрию или risk budget, entry отклоняется, а не «чинится» переносом stop.

**Новый policy mismatch: generic chase guard.** Текущий market-entry path отменяет вход, если `abs(curr.open - sig["entry_price"]) / sig["entry_price"]` выше `max_chase_limit_pct`. H-B signal contract говорит входить на следующем open, но не определяет этот дополнительный фильтр. Его нельзя молча считать частью H-B: это меняет набор сделок. Перед реализацией требуется одно явное решение в experiment card: (a) H-B строго исполняет следующий open, обходя только общий chase guard для этой стратегии; или (b) фиксирует конкретный chase cap как часть гипотезы. До такого решения не кодировать adapter. При любом варианте проверки `stop < fill < target` и sizing по фактическому fill обязательны.

**Bars-held convention проверена:** `step_candle()` вызывает `_manage_position(..., fill_bar=True)` сразу после fill на t+2; `_manage_position()` увеличивает `bars_held` до проверки выходов. Поэтому fill bar естественно считается баром №1. H-B ветка должна использовать собственный frozen `h_b_max_hold_bars=24`, а не общий `cfg.max_hold_bars`.

**Restore/audit:** pending payload H-B и открытая позиция должны проходить fail-closed validation; старые payload без H-B ключей сохраняют прежнее поведение. При закрытии `TradeRecord` должен сохранять policy version, shock timestamp, frozen target и фактический initial stop. В текущем `TradeRecord` есть `initial_stop_price`, `initial_stop_dist`, `final_stop_price`, `strategy` и общие execution/accounting поля, но нет H-B target/policy/shock provenance. При реализации добавить только optional H-B audit fields (`h_b_exit_policy_version`, `h_b_shock_ts_ms`, `h_b_target_price`) с defaults и backward-compatible trade-log serialization; не перегружать `tp2_price`. H-B metadata нельзя молча терять при serialization или переводить H-B позицию в legacy breakout exits.

