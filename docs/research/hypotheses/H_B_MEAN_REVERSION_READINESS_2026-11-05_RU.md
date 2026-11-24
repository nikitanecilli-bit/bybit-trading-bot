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

**Restore/audit:** pending payload H-B и открытая позиция должны проходить fail-closed validation; старые payload без H-B ключей сохраняют прежнее поведение. При закрытии `TradeRecord` должен сохранять policy version, shock timestamp, frozen target и фактический initial stop. В текущем `TradeRecord` есть `initial_stop_price`, `initial_stop_dist`, `final_stop_price`, `strategy` и общие execution/accounting поля, но нет H-B target/policy/shock provenance. При реализации добавить только optional H-B audit fields (`h_b_exit_policy_version`, `h_b_shock_ts_ms`, `h_b_target_price`) с defaults и backward-compatible trade-log serialization; не перегружать `tp2_price`. `_close_position()` сейчас вычисляет `TradeRecord.initial_stop_price` как `entry_price ± initial_stop_dist`, поэтому при корректном H-B `initial_stop_dist = fill - shock_low` это поле точно восстановит frozen shock-low stop. H-B закрытие обязано оставлять `tp1_hit=False`, `realized_tp1_gross_usdt=0` и `remaining_fraction=1`; `tp1_price`/`tp2_price` — обязательные legacy-поля dataclass, но не H-B exit semantics. Их значения не должны влиять на H-B branch; не считать эти поля H-B partial/secondary targets. H-B metadata нельзя молча терять при serialization или переводить H-B позицию в legacy breakout exits.



### 10.8. Решение по chase guard и точные sizing-инварианты

**Решение для H-B v0.1: общий market-entry `max_chase_limit_pct` обходится только для H-B.** H-B сигнал означает безусловную попытку исполнения на следующем H1 open, а не лимитированную погоню за ценой. Включение общего chase cap создало бы дополнительный неописанный фильтр и изменило бы гипотезу. Это не разрешает ухудшать вход произвольным образом: вход всё равно отклоняется при нарушении `0 < shock_low < actual_fill < frozen_mean_target`, невалидных данных, недостаточном размере/лоте, нарушении risk budget, dated instrument specs или risk tiers. Для legacy strategies общий chase guard остаётся без изменений. Для H-B не вводить альтернативный cap, slippage threshold или поздний fill.

**Sizing invariant уточнён по реализации `calculate_position_size()`:** функция уже принимает абсолютные `entry_price` и `stop_price` и рассчитывает stop distance как `abs(entry-stop)`, учитывая entry/stop fees, taker slippage, per-trade budget и portfolio allocation. Adapter должен передавать туда фактический fill и shock-low stop; в `OpenPositionState.initial_stop_dist` сохранять тот же `fill - shock_low`, а не исходный `sig["stop_dist"]`. После dated exchange rounding необходимо повторно проверить фактические notional/risk, stop/target geometry и ограничения портфельного бюджета; любое превышение или нарушение — reject, без переноса stop.

**Fill-bar exit invariant:** `_manage_position(fill_bar=True)` сначала увеличивает `bars_held`, затем проверяет liquidation/kill-switch/stop. Для H-B mean target и time stop на fill bar намеренно не исполняются; target проверяется начиная со следующей полной H1 свечи. Stop на fill bar остаётся активным. Для H-B ветка должна быть отдельной и завершать общую discretionary breakout-ветку до TP1/TP2/trailing; иначе фиктивные legacy TP levels могут влиять на выход.

**Дополнение к synthetic test matrix:**
- H-B гэп выше общего `max_chase_limit_pct`, но `stop < fill < target` и risk checks проходят → исполнение на open; legacy сигнал при том же гэпе → прежняя отмена.
- Проверить, что H-B `initial_stop_dist == fill - shock_low`, а sizing получает тот же абсолютный stop.
- Dated lot/qty rounding, приводящий к превышению risk budget или нарушению геометрии → reject.
- Fill-bar target touch не закрывает H-B; fill-bar stop touch закрывает.
- H-B позиция не попадает в TP1/TP2/trailing/time-stop breakout path.

Статус: chase policy решена на уровне контракта; реализация остаётся заблокированной до санкционированного code-write пути. Это synthetic-only design, не market preregistration.


### 10.9. Точки внедрения и привязка synthetic tests к существующим тестам

Повторная проверка тестового каркаса показала, что H-B не требует отдельного simulation harness: достаточно расширить существующие узкие regression suites, сохранив legacy assertions.

**Engine integration points:**
- `_try_fill_pending()`: распознать строгое имя стратегии H-B; для H-B валидировать обязательные absolute fields до расчёта размера; использовать фактический `curr.open`; обойти только общий chase guard; передать абсолютный stop в `calculate_position_size(fill, stop_price, ...)`; не вызывать `QuantStrategyCore.build_levels()` для H-B.
- После `size_to_exchange_constraints()`: дополнительно проверить post-rounding stop/target geometry и риск. Ветка сейчас присваивает `size_usdt = exchange_order.notional_usdt` и `risk_usdt = exchange_order.risk_usdt`; H-B adapter обязан fail closed, если итоговый риск превысил выделенный budget либо округлённый qty не соответствует сохранённой геометрии. Не менять общий legacy path.
- `OpenPositionState`: добавить optional H-B fields в конец dataclass с defaults. Restore использует строгий allowlist из `dataclasses.fields()`; поэтому старые backups останутся читаемыми, а новые поля автоматически станут известными, но H-B values всё равно требуют отдельной strategy-specific validation. H-B restore должен проверить policy version, timestamps, finite positive prices, long-only, `stop < entry < target`, `initial_stop_dist == entry - stop`, `bars_held` и отсутствие TP1 partial state.
- `_manage_position()`: после общих liquidation/kill-switch/protective-stop проверок, но до TP2/TP1/trailing/time-stop breakout logic, добавить изолированную H-B ветку. Она проверяет frozen target начиная с non-fill bar; time stop на close 24-й свечи; при любом H-B исходе не проваливается в legacy discretionary exits.
- `_close_position()`: передать H-B audit fields в optional поля `TradeRecord`; общая финансовая арифметика остаётся неизменной. H-B позиция закрывается целиком, без TP1, так что `remaining_fraction=1`, `tp1_hit=False`, `realized_tp1_gross_usdt=0`.

**Existing regression suites to extend (tests are not yet written):**

| File | Existing coverage | H-B additions |
|---|---|---|
| `tests/test_gap_execution.py` | market chase cancel/fill, fill-bar stop, stop-first, journal costs | H-B gap above chase cap still fills on next open; same legacy signal still cancels; reject stop/target geometry; stop-first vs target same candle; no target on fill bar; target gap exits fixed target; frozen stop gap exits min(stop, open) |
| `tests/test_state_persistence.py` | pending strict allowlist, finite values, immediate-next-bar freshness, position round-trip, legacy backups | H-B pending and position round-trip; missing/unknown/wrong-version H-B fields reject; non-finite target/stop/timestamps reject; wrong strategy/direction/stop-distance/TP1 state reject; legacy pending and position fixtures unchanged |
| `tests/test_gap_execution.py` + portfolio sizing tests | risk budget and position sizing | actual fill-to-shock-low distance passed to sizing; post-rounding risk over budget rejects; invalid exchange lot/min notional rejects without stop adjustment |

**Persistence detail:** pending payload is not restored by dataclass; `PlanBStatePersistence.load_state()` validates it as a dictionary against a separate strict field allowlist. Adding H-B pending keys therefore requires updating both pending save validation and pending restore validation, plus tests that save rejects payloads the reader would reject. Do not loosen the unknown-field rejection globally. The current pending tests at `tests/test_state_persistence.py` cover unknown fields and missing required fields and should remain passing.

**Test execution order when code writes are available:**
1. targeted H-B tests in `test_gap_execution.py` and `test_state_persistence.py`;
2. complete persistence + gap execution suites;
3. complete repository CI.
No market PnL, parameter sweep, external API, archive data, or paper/live execution is part of these checks.

Status: **ADAPTER CONTRACT + TEST MAP COMPLETE / IMPLEMENTATION NOT PRESENT / NO TESTS RUN**.


### 10.10. Дополнительный persistence blocker: pending allowlist и signal provenance

Прямое чтение `PlanBStatePersistence.load_state()` выявило конкретное несоответствие ранее описанному payload:
- текущий `required_pending`: `symbol, direction, strategy, signal_ts, entry_price, stop_dist, order_type`;
- текущий `allowed_pending`: те же поля плюс `stop_price, tp1_price, tp2_price, atr, vol_ratio, session, breakout_level`;
- **`signal_origin_ts` сейчас отсутствует в allowed_pending**, хотя `_try_fill_pending()` читает его и валидирует как исходный timestamp сигнала.

Для H-B нужно расширить allowlist точечно, не меняя смысл legacy полей:
- добавить `signal_origin_ts` как optional positive integer timestamp, не позже `signal_ts` и не позже backup `saved_at_utc`;
- добавить H-B поля `h_b_shock_ts_ms`, `h_b_stop_price`, `h_b_target_price`, `h_b_exit_policy_version` только как strategy-specific optional fields;
- H-B pending обязан иметь все четыре H-B поля, `signal_origin_ts` и `strategy == "H-B-mean-reversion"`; не-H-B pending с любым H-B ключом отвергается;
- shock timestamp должен быть положительным integer и строго раньше stabilization `signal_ts`; shock-low/target — конечные положительные числа, `stop < target`; policy version строго известна (v0.1);
- на fill дополнительно проверить `shock_ts < signal_ts < curr.ts` и точное соседство signal→entry bar по общему freshness guard;
- legacy payload без этих ключей остаётся валидным; неизвестные поля по-прежнему reject.

Это также означает, что regression test на H-B pending restart должен проверять не только успешное чтение, но и round-trip через `save_state()` (который валидирует candidate тем же строгим reader) и фактическое заполнение на следующем баре. Existing test `test_pending_original_signal_timestamp_cannot_follow_freshness_guard` проверяет timestamp consistency в fill path, но не покрывает сериализацию этого поля.

**Обязательные новые persistence tests:** H-B complete payload round-trip; missing each H-B key; H-B key on legacy strategy; unknown key; bool/string/zero/future timestamps; NaN/Inf/zero/negative stop or target; wrong policy version; `signal_origin_ts > signal_ts`; valid legacy payload unchanged. Проверить, что failed save сохраняет прежний backup byte-for-byte.

Status remains **SPEC ONLY**; no code/test execution.


### 10.11. Критичный конфликт legacy TP1/TP2 restore validation с H-B

Новый статический проход restore validation обнаружил, что H-B нельзя безопасно представить только добавлением metadata:
- `tp1_price` и `tp2_price` входят в обязательные поля позиции и positive numeric allowlist;
- restore безусловно требует `entry < TP1 < TP2` для long;
- exchange-sized restore дополнительно проверяет minNotional через `min(stop_price, tp2_price)`;
- `_close_position()` безусловно экспортирует `tp1_price/tp2_price` в TradeRecord, хотя TP1 cost leg учитывается только при `tp1_hit`.

Для H-B эти поля не имеют экономического смысла. Заполнять их target-like sentinel values опасно: это сохраняет ложную семантику breakout TP и может ошибочно повлиять на restore/exchange validation или dashboard analytics.

**Рекомендуемый adapter/data-model контракт (требует отдельного code review):**
1. Сохранить legacy TP1/TP2 поля и их строгую геометрию для всех legacy strategies.
2. Для H-B разрешить `tp1_price=None` и `tp2_price=None` в `OpenPositionState`; сделать типы optional с defaults только если это не меняет positional constructor compatibility (лучше appended H-B optional metadata плюс стратегия-специфичная нормализация при создании).
3. В restore validation разделить strategy branches: legacy требует текущую TP геометрию; H-B требует обе TP цены null, `tp1_hit=false`, `tp1_ts_ms=null`, `realized_tp1_gross_usdt=0`, `remaining_fraction=1`. Не допускать H-B с любым TP1 partial state.
4. В exchange-sized validation для H-B проверять minNotional для фактических допустимых full-close уровней: frozen stop и frozen mean target, а не legacy TP2; qty remains full initial quantity. При округлении не менять stop/target.
5. В `_close_position()` экспортировать legacy TP fields как null для H-B; не выполнять TP1 fee leg; добавить отдельные H-B поля в TradeRecord: `h_b_shock_ts_ms`, `h_b_initial_stop_price`, `h_b_mean_target_price`, `h_b_exit_policy_version`. Существующий `initial_stop_price` может оставаться общим derived stop, но H-B explicit field сохраняет provenance.
6. `export_journal_for_dashboard()` сериализует TradeRecord через `dataclasses.asdict()`; новые optional fields автоматически попадут в JSON. Нужен consumer audit dashboard/report readers на неизвестные поля и null TP values до включения H-B.
7. В H-B restore проверять `initial_stop_dist ≈ entry_price - h_b_initial_stop_price` с согласованным денежным tolerance; stop_price должен совпадать с frozen H-B stop; target/policy/shock timestamp неизменны.

**Synthetic tests:** legacy long/short TP geometry unchanged; H-B backup accepts null TP fields; H-B backup rejects non-null TP1/TP2 and any partial state; exchange-sized H-B checks minNotional against stop and target; TradeRecord JSON has null legacy TP fields and complete H-B provenance; legacy dashboard journal shape remains semantically unchanged.

Это отдельный blocker перед кодовой реализацией. Предыдущие разделы 10.7–10.10 остаются действующими; статус **SPEC ONLY / NO CODE / NO TESTS**.


### 10.12. TradeRecord close-path audit: null TP crash и end-of-replay flatten

Проверен полный `_close_position()` и export path. Уточнение к разделу 10.11:
- Если H-B хранит `tp1_price=None` и `tp2_price=None`, текущий конструктор `TradeRecord` вызывает `round(pos.tp1_price, 12)` и `round(pos.tp2_price, 12)` без strategy guard. Закрытие H-B упадёт с TypeError, даже если TP1 partial leg не исполнялся.
- Передавать H-B null в TradeRecord корректно только после изменения обеих строк на strategy-aware optional mapping; legacy значения должны сериализоваться прежними числами.
- TP1 fee/PnL leg уже условно исполняется только при `pos.tp1_hit`; H-B invariant `tp1_hit=False` корректно исключает её. Остаточная нога учитывается как полный размер при `remaining_fraction=1`.
- Финальный close fee рассчитывается для фактического exit_price; exchange-sized `_close_position()` отдельно проверяет final qty alignment, minOrderQty и minNotional по фактической цене закрытия. Это не заменяет restore-time проверку допустимых H-B stop/target.
- `export_journal_for_dashboard()` формирует `trades: [asdict(t)]`; новые optional TradeRecord fields автоматически войдут в JSON. В доступной ветке обнаружен engine-side producer, но независимые dashboard consumers этим поиском не подтверждены; до включения H-B нужен отдельный consumer/schema audit. Нельзя считать совместимость dashboard доказанной.
- `finalize_open_positions()` намеренно закрывает все оставшиеся позиции по последнему синхронному close с общим `end_of_test` reason и taker costs. H-B не должен подменять этот terminal cleanup своей обычной mean/time-stop логикой; synthetic test должен подтвердить, что финализация закрывает H-B ровно один раз, сохраняет H-B provenance и не пытается читать null TP.

**Требуемые дополнительные tests:** close H-B via stop, mean target, time stop, liquidation, kill-switch and end_of_test; each creates exactly one TradeRecord, no TP1 fee leg, full remaining qty; TP1/TP2 journal fields null; H-B metadata retained; legacy TradeRecord numeric TP fields unchanged; JSON export round-trip with optional fields.

Status **SPEC ONLY**. No code changes, no tests run.


### 10.13. Dashboard scope уточнён; end-to-end consumer не найден

Прочитан tracked `dashboards/v15/Bybit Profit Dashboard v15 (Чистый HTML).html`:
- это самостоятельный JS backtest/simulator: создаёт собственные объекты position/trades, считает KPI и портфель внутри браузера;
- он не читает `export_journal_for_dashboard()` JSON и не обращается к engine TradeRecord schema;
- поэтому этот HTML dashboard **не является downstream consumer** H-B journal и его нельзя использовать как доказательство совместимости null TP/new provenance fields.

В текущем доступном дереве подтверждён producer `export_journal_for_dashboard()` с `asdict(TradeRecord)`; прямой независимый consumer engine journal в проверенных tracked files не установлен. Следовательно, формулировка корректного статуса: **consumer compatibility unknown / not evidenced**, а не «dashboard совместим». Перед интеграцией проверить все реально используемые внешние импортёры/дашборды по фактическому формату journal; если таких consumers нет, зафиксировать это как deployment inventory, не придумывать их.

Этот аудит не меняет blocker из 10.12: strategy-aware null mapping в TradeRecord constructor обязателен. Код и тесты не менялись.


### 10.14. Contract refinement: dataclass compatibility and H-B manager isolation

Дополнительная проверка всех tracked constructor callsites в engine и трёх основных test modules:
- Все найденные OpenPositionState(...) и TradeRecord(...) вызовы используют keyword arguments; positional callsites в проверенных файлах не обнаружены.
- Тем не менее публичный порядок dataclass полей лучше не менять: новые H-B provenance поля добавлять только в конец с defaults. Для OpenPositionState.tp1_price/tp2_price предпочтительно изменить аннотации на Optional[float], но оставить их обязательными constructor arguments (без default), передавая None явно для H-B. Это сохраняет порядок/арность конструктора и не вызывает dataclass ordering conflict. Не делать их default=None без отдельного решения по API совместимости.
- TradeRecord.tp1_price/tp2_price уже Optional в типах; проблема не в типах, а в unconditional round() в producer. H-B provenance fields добавлять в конец dataclass с defaults; producer должен передавать null TP values без round(None).

**Новый обязательный manager guard:** _manage_position() сейчас безусловно вычисляет TP2 touch и далее TP1/trailing, обращаясь к pos.tp2_price/pos.tp1_price. Поэтому одних nullable полей недостаточно: H-B обязан иметь отдельную discretionary ветку до legacy TP2/TP1 блока. Рекомендуемый control flow:
1. Общие проверки liquidation → portfolio kill-switch → protective stop остаются первыми и неизменными.
2. Если позиция H-B и ни один общий forced/protective exit не сработал, проверить frozen mean target; затем 24-bar time stop по close. Целевой exit не активировать на fill bar; stop остаётся активным.
3. После H-B ветки не проваливаться в breakout TP1/TP2/trailing. Сохранить общую нижнюю часть обработки close, _close_position, MTM, persist и post-execution kill-switch safeguards.
4. Для legacy стратегий оставить текущий TP2 → TP1 → trailing → max_hold path без семантических изменений.

Это отдельный runtime blocker: если branch расположить после legacy блока, null TP приведёт к TypeError ещё до формирования TradeRecord.

**Forced flatten paths:** _force_flatten_open_positions_after_kill_switch() и finalize_open_positions() вызывают общий _close_position() напрямую, минуя _manage_position(). Это желаемо для forced liquidation/kill-switch и terminal cleanup: они должны сохранять общую accounting и H-B metadata, но не запускать H-B target/time logic повторно. Проверить idempotency/one-record semantics и journal provenance на каждом из путей.

**TP1 restore invariant:** H-B backup требует одновременно tp1_hit=false, tp1_ts_ms=null, realized_tp1_gross_usdt=0, remaining_fraction=1, tp1_price=null, tp2_price=null; любые частичные/legacy TP состояния отклоняются.

**Статус:** contract уточнён, code/test implementation отсутствует. Никакие constructor callsites не менялись.


### 10.15. Единый end-to-end data contract и порядок реализации

Этот раздел сводит решения 10.6–10.14 в один контракт между lifecycle слоями. Это спецификация для будущей реализации, не утверждение, что код уже поддерживает H-B.

| Этап | Канонические данные / invariants | Проверка и отказ |
|---|---|---|
| Signal evaluator на close t+1 | strategy = `H-B-mean-reversion`; direction = long; `signal_ts=t+1`; `signal_origin_ts`; `h_b_shock_ts_ms=t`; абсолютный `h_b_stop_price=low[t]`; frozen `h_b_target_price=mean(close[t-24:t])`; policy `v0.1` | Только причинные H1 бары; ровно 24 непрерывных pre-shock close; gap/duplicate/invalid ATR или timestamp => fail closed |
| Pending save/restore | Тот же полный H-B набор; legacy pending schema остаётся прежней; H-B metadata допустима только при точной H-B strategy | Save и load используют одинаковую строгую валидацию; missing/unknown/mixed-strategy fields, неверный тип/порядок timestamp, NaN/Inf или неизвестная policy => reject; прежний backup не повреждается |
| Fill на open t+2 | Реальный fill = `curr.open`; frozen stop/target не пересчитываются; проверка `0 < stop < fill < target`; `shock_ts < signal_ts < curr.ts`; немедленно следующий H1 бар | Любая геометрическая, временная или freshness ошибка => cancel pending; H-B-only bypass chase cap не отменяет остальные проверки |
| Shared sizing и exchange validation | Передать фактические `fill` и `stop`; distance = `fill - stop`; сохранить distance в `initial_stop_dist`; общий portfolio budget, dated specs, risk tiers, lot/minQty/minNotional | После округления повторно проверить geometry и риск; reject вместо перемещения stop/target или увеличения риска |
| OpenPositionState | strategy H-B; `tp1_price=None`, `tp2_price=None`; frozen shock timestamp, initial stop, mean target и policy version; full position only | Restore H-B branch требует null TP, `tp1_hit=false`, `tp1_ts_ms=null`, realized TP1 = 0, remaining fraction = 1; stop и target совпадают с frozen metadata; legacy restore остаётся без изменений |
| Position manager | Общие liquidation → kill-switch → protective stop; далее H-B target → 24-bar time stop; fill bar — bar 1, но target/time-stop на fill bar запрещены | Same-bar stop/target => stop first; target gap без improvement; stop gap по min(stop, open); H-B всегда return до legacy TP1/TP2/trailing/max-hold ветки |
| Close/accounting | Общий `_close_position()`; полный объём; без TP1 financial leg; TradeRecord сохраняет H-B shock/stop/target/policy provenance | Null-safe TP serialization (никакого `round(None)`); один close — одна запись; legacy TP значения и accounting не меняются |
| Journal/export | `asdict(TradeRecord)` включает optional H-B поля; legacy TP fields у H-B null | Проверить JSON round-trip и фактические downstream importers; consumer compatibility пока unknown/not evidenced |
| Forced close/finalize | Kill-switch flatten и end_of_test идут напрямую через общий close, не через H-B target/time logic | Сохранить provenance и exactly-once semantics; не запускать H-B discretionary exit повторно |

**Рекомендуемый порядок реализации после восстановления санкционированного code-write пути:**
1. Зафиксировать типы и invariants dataclasses/TradeRecord и backward-compatible persistence reader/writer; добавить round-trip и malformed-state tests.
2. Реализовать узкий fill adapter с абсолютными stop/target, actual-fill sizing и изолированным chase bypass; проверить legacy signal path.
3. Реализовать H-B manager branch и forced-close-safe TradeRecord producer; добавить детерминированные механические tests на все приоритеты выхода.
4. Проверить journal schema/export, импортёров и legacy regression suites.
5. Запустить targeted tests, затем полные offline code tests и CI; дождаться завершения и разобрать каждый failure.

**Нельзя объединять в один недифференцированный этап:** persistence schema, fill geometry и manager exit semantics должны иметь отдельные regression assertions. Иначе успешный signal/fill тест не доказывает restart или close correctness.

**Границы:** synthetic fixtures/FakeTransport only; никаких live/paper execution, private/account/exchange API, market data collection, archive extraction, market PnL или parameter sweeps. До отдельной preregistration/data-accounting clearance статус остаётся **SPEC ONLY / SYNTHETIC-ONLY / DATA-BLOCKED**.


### 10.16. Liquidation / portfolio-risk / replay boundary audit

Дополнительная read-only проверка выявила важное ограничение модели риска:

1. mark_price_liquidation.py прямо определяет расчёты как **single-position isolated approximation**. calculate_mark_price_maintenance_margin() выбирает maintenance tier по mark notional одной позиции; evaluate_isolated_margin_health() учитывает initial margin, extra margin, unrealized PnL и funding net cost. В docstring указано, что account/order aggregation, AMR, точные funding transfer timestamps и exchange rounding не моделируются.
2. H-B может использовать общий локальный kill-switch и позиционный liquidation guard, но это не доказывает корректность cross/portfolio margin или exchange-level liquidation. Нельзя описывать это как полную модель портфельной ликвидации.
3. В _manage_position() liquidation имеет приоритет над kill-switch и last-price stop; kill-switch — над discretionary exits; stop — перед target. H-B branch должна находиться после этих общих защитных проверок.
4. В _close_position() exchange-sized quantity берётся из remaining_contract_qty; при H-B full-only invariants это должно совпадать с полной исходной позицией. Для liquidation отдельная ветка обходит обычные minQty/minNotional проверки, поскольку settlement не является обычным reduce order. Не менять это поведение без отдельной модели liquidation settlement.
5. Forced kill-switch flatten использует сохранённый intrabar liquidation exit, если он есть, иначе intrabar risk mark/last mark, и вызывает общий _close_position(). H-B metadata обязана попасть в TradeRecord независимо от инициатора close.
6. Persistence сохраняет risk.kill_switch_triggered и восстанавливает его в candidate risk manager до commit состояния. H-B restore не должен очищать или пересчитывать этот latch; после restore общий kill-switch сохраняет приоритет.
7. Replay finalization вызывает общий close напрямую по последнему синхронному mark/candle. Это forced administrative close, а не H-B target/time exit; provenance/policy должны сохраниться, exit_reason остаётся end_of_test (или явно переданный reason).

**Новые synthetic-only assertions:** liquidation touch + stop touch => liquidation; поднятый kill-switch блокирует mean target/time stop; flatten закрывает все H-B позиции ровно один раз с полной provenance; restore с kill_switch_triggered=true не возобновляет discretionary exits; exchange-sized full close использует полный remaining qty; replay finalization закрывает H-B один раз без TP1 fee leg; отчёты не называют isolated approximation полноценной portfolio/cross-margin моделью.

**Ограничение readiness:** даже после синтетических тестов эта модель не доказывает реальную биржевую ликвидацию, cross-margin, общий risk-tier aggregation или account-level protection. Это отдельный data/model validation gate. Рыночные и account/API проверки остаются закрытыми.


### 10.17. Новая блокировка: portfolio MTM безусловно использует TP1

Read-only проверка фактического пути portfolio mark-to-market выявила блокер, который возникает **до** H-B manager и независимо от nullable исправления в _close_position():

- _unrealized_pnl_at_marks() для каждой открытой позиции безусловно вычисляет tp1_qty, затем выполняет `tp1_notional = float(tp1_qty * Decimal(str(pos.tp1_price)))`. Это происходит даже когда `pos.tp1_hit` равно false. При H-B `tp1_price=None` вызов Decimal('None') завершится исключением во время обычного MTM.
- Этот helper вызывается из _update_mark_to_market(), который исполняется на каждом bar-close до _manage_position(). Значит H-B позиция с корректными null TP1/TP2 не дойдёт даже до своего exit manager: replay остановится на portfolio accounting.
- _close_position() имеет отдельные TP1-условные fee legs, поэтому TP1 fee leg не начисляется при `tp1_hit=false`; однако сериализация TradeRecord всё ещё безусловно делает round(pos.tp1_price/pos.tp2_price), что подтверждает ранее найденный close blocker.

**Требуемый контракт MTM:** вычислять TP1 quantity/notional/cost только внутри ветки `tp1_hit=true`; при H-B full-only state это условие обязано оставаться false, а realized TP1 leg — нулём. Не подменять null фиктивной ценой. Добавить regression tests: H-B null TP поля проходят MTM при нескольких mark prices; TP1 costs остаются нулевыми; legacy partial TP1 MTM сохраняет прежнюю математику; H-B MTM + close + journal выполняются без TypeError.

**Portfolio accounting finding:** _close_position() удаляет закрываемую позицию из open_positions до пересчёта unrealized PnL оставшихся позиций, затем добавляет net realized PnL. При `_defer_close_risk_evaluation=true` пакетные close последовательно обновляют realized equity и оставшийся unrealized snapshot без промежуточной оценки drawdown; после batch вызывается общий _update_mark_to_market(). Это выглядит как намеренная защита от порядка обхода словаря, но требует synthetic multi-position assertions: сумма realized net + оставшийся unrealized не меняется от порядка закрытия при одинаковом timestamp; закрытая позиция не учитывается в unrealized повторно; kill-switch latch оценивается по агрегированному snapshot после синхронного batch, а не по искусственному промежуточному состоянию.

**Статус:** новая критическая H-B integration blocker. Код не менялся; только статический аудит. См. research plan 13.15.


### 10.18. Полная карта nullable TP consumers и restore blockers

Продолжен read-only аудит всех найденных обращений к `pos.tp1_price`, `pos.tp2_price`, `tp1_contract_qty` и `tp1_hit` в основном engine-файле. Помимо MTM/close blockers из 10.17 обнаружено:

1. **Intrabar MTM (около `_unrealized_pnl_at_marks`)** безусловно строит TP1 quantity/notional и обращается к `Decimal(str(pos.tp1_price))`, хотя TP1 fee/slippage затем условны по `tp1_hit`. При H-B `None` исключение происходит раньше условного fee расчёта. Требуется целиком перенести вычисление TP1 qty/notional внутрь `if pos.tp1_hit`; при false не трогать TP1 price или quantity.
2. **Restore schema** (`PlanBStatePersistence.load_state`) объявляет `tp1_price` и `tp2_price` обязательными числовыми положительными полями; их безусловно проверяет, а для exchange-sized позиции использует TP2 в `lowest_planned_exit`. H-B null TP не сможет восстановиться. Требуется strategy-aware схема: legacy прежняя строгая геометрия; H-B обе TP цены null, TP1 false, TP1 timestamp null, realized TP1=0, remaining_fraction=1 и full remaining quantity. Exchange-sized H-B minNotional проверять по H-B stop/mean target, а не TP2.
3. **`_apply_tp1()`** напрямую вычисляет расстояние до `tp1_price`, использует TP1/TP2 для minNotional и меняет остаточную долю. Это legacy-only helper; H-B manager обязан обходить его полностью.
4. **`_manage_position()`** перед общей discretionary логикой вычисляет TP2 touch, затем TP1 touch, затем trailing. Наличие стратегии H-B само по себе эту ветку не исключает. Нужна явная strategy branch после общих liquidation/kill-switch/stop checks и до TP1/TP2 блока; H-B target/time-stop обрабатываются там, затем обязательный return/исключение из legacy ветки.
5. **Save path** сериализует `asdict(pos)` и затем проверяет временный backup тем же strict reader. Поэтому расширение dataclass без синхронного strategy-aware reader всё равно блокирует сохранение H-B позиции. Нельзя ослаблять unknown-field rejection глобально.
6. **Close path** по-прежнему безусловно округляет TP цены при создании TradeRecord (см. 10.12), а **journal export** сериализует `asdict(TradeRecord)`. Для H-B null TP должны пройти close и JSON export; downstream consumer audit остаётся отдельным пунктом.

Проверяемая матрица после реализации: legacy long/short position save-load и MTM parity; H-B null TP save→restore→intrabar MTM→bar-close MTM→manager→stop/target/time close→journal; попытка вызвать `_apply_tp1` для H-B невозможна; malformed H-B TP state отвергается; exchange-sized H-B minNotional использует frozen stop/target; старые backup остаются совместимыми.

**Вывод:** nullable TP — сквозное изменение модели позиции, а не локальная правка TradeRecord. Все потребители должны быть исправлены одним согласованным контрактом. Код не менялся, тесты не запускались; это статический аудит source на текущей ветке.


### 10.19. TradeRecord, auditor и downstream journal consumer audit

Read-only проверены `TradeRecord`, `MaintenanceGateAuditor.evaluate_portfolio()`, `export_journal_for_dashboard()`, тесты accounting/persistence, аналитические скрипты и dashboard v15.

**Подтверждено:**
- `TradeRecord.tp1_price` и `tp2_price` уже объявлены `Optional[float]`; добавление H-B полей возможно append-only с defaults, не меняя существующие обязательные positional/keyword поля.
- `MaintenanceGateAuditor.evaluate_portfolio()` не читает TP1/TP2, `tp1_hit` или remaining fraction. Его метрики строятся на `pnl_usdt`, `gross_pnl`, fees/slippage/funding, `risk_pct`, `r_multiple`, exit timestamp и группировке по активу/сессии. При корректном H-B `TradeRecord` агрегатный аудитор не требует TP-специфичной ветки.
- `export_journal_for_dashboard()` пишет `trades=[asdict(t)]`, не фильтруя поля. Новые optional H-B provenance поля автоматически попадут в JSON; старые поля TP могут быть null. В payload нет явного schema_version — рекомендуется добавить версионирование отдельным согласованным изменением и зафиксировать consumer contract, не ломая прежние поля.
- Внутренние attribution scripts используют `engine.closed_trades` напрямую и агрегируют net/gross/fees/slippage/R/MFE/MAE/exit_reason; TP-поля не читают. Это не доказательство совместимости внешних потребителей JSON.
- `report_io.py` не содержит journal parser/consumer. Dashboard v15 — самостоятельный HTML simulator со своей моделью сделок и генерацией данных; в inspected source не найдено чтение JSON journal engine. Не считать его подтверждённым downstream consumer.
- Accounting tests уже проверяют journal JSON и конкретные числовые TP значения для legacy; persistence tests строго проверяют старую TP геометрию и TP1 lifecycle. H-B потребует отдельной null-TP ветки, сохраняя legacy assertions без ослабления.

**H-B TradeRecord контракт:** сохранить общие `pnl_usdt`, `gross_pnl`, fees, slippage, funding, `risk_usdt`, net/gross R и `exit_reason`; `tp1_price=null`, `tp2_price=null`, `tp1_hit=false`, `tp1_ts_ms=null`, `realized_tp1_gross_usdt=0`, `remaining_fraction_at_exit=1`. Добавить append-only optional поля с defaults: `h_b_shock_ts_ms`, `h_b_initial_stop_price`, `h_b_mean_target_price`, `h_b_exit_policy_version`. Поля обязаны заполняться для H-B при normal stop/target/time, liquidation, kill-switch flatten и replay finalization; не-H-B записи должны иметь null H-B provenance. `initial_stop_price` должен совпадать с абсолютным frozen shock-low stop; при точном actual fill-to-stop `initial_stop_dist` его derived значение это обеспечивает, но тест должен сравнить оба.

**Journal consumer compatibility gate:** проверить минимум JSON snapshot tests для legacy и H-B, `json.dumps(... allow_nan=False)`, null preservation, required H-B provenance, unknown-field behavior внешних readers (если они будут предоставлены), summary parity между `MaintenanceGateAuditor` и TradeRecord sums. Не утверждать отсутствие неизвестных внешних потребителей: доступный репозиторий не содержит обнаруженного parser для engine journal.

**Статус:** внутренний аудитор и видимые скрипты не имеют TP-specific dependency; экспорт сохраняет optional поля через `asdict`, но внешняя совместимость неизвестна. Статический аудит; код/тесты не менялись и не запускались.


### 10.20. Strategy KPI, readiness badge and validation-report boundary audit

Read-only просмотрены `MaintenanceGateAuditor.evaluate_portfolio()`, daily odometer formatter, Bybit H1 single-symbol holdout и shared-capital H1 validation runner.

**Критический вывод:** общий `evaluate_portfolio()` математически принимает список любых `TradeRecord` и не фильтрует по `strategy`. Он вычисляет net PnL/return от `cfg.capital_usdt`, Win Rate, PF, средний NET R, drawdown по агрегированному exit timestamp, average risk и `all_ok` по шести общим целям. `format_daily_odometer_report()` переводит `all_ok` в «All Systems Normal / Зелёный коридор». Это не strategy-specific readiness и не preregistration gate. Если H-B сделки попадут в этот общий список, результат может смешать H-B с breakout/другими стратегиями и выдать misleading green status.

**Требуемая изоляция H-B reporting:**
1. Для любого H-B research report группировать строго по `strategy == "H-B-mean-reversion"`; показывать отдельно число сделок и долю пропущенных/отклонённых сигналов, net/gross PnL, все costs, net R, PF, win rate, drawdown, expectancy, duration/monthly-equivalent только при валидном интервале, exit reason, stop/target/time counts.
2. Указывать статус явно: `SYNTHETIC_ONLY`, `NOT_MARKET_VALIDATED`, `NOT_PREREGISTERED`, `NOT_DEPLOYMENT_APPROVED`; синтетические результаты не могут попадать в market PnL KPI или общий «зелёный коридор».
3. `all_ok` общего аудитора нельзя переименовывать в H-B readiness. Нужен отдельный readiness state machine, где прохождение mechanical tests не открывает data/PnL gate.
4. Общая equity/portfolio risk оценка может агрегировать стратегии для портфельного риска, но strategy edge attribution и readiness обязаны оставаться раздельными. Любая смешанная метрика должна явно иметь scope `portfolio`, а не `H-B`.
5. Отдельно фиксировать sample size, дату/границы периода, data provenance, code/config hashes, exit-policy version, instrument/universe, cost model, funding/mark assumptions, blind-vs-seen period status и known limitations.

**H1 runner incompatibility:** `scripts/run_h1_shared_capital_portfolio_validation.py` сейчас hardcodes `strategy="H1-momentum-breakout"`, Donchian/volume/EMA variants, their parameter grid and a manifest that names breakout-specific rules. It is not an H-B runner and must not be reused by merely passing H-B signals. H-B needs a dedicated runner/manifest with frozen signal/exit policy and no breakout factorial grid. `run_bybit_h1_long_only_holdout.py` is a cross-venue breakout holdout, uses per-symbol starting capital and explicitly is not a combined portfolio curve; it is also not an H-B validation route.

**Additional caveats:** generic evaluator's `ret_pct` divides cumulative closed-trade net PnL by initial `cfg.capital_usdt`; its closed-trade drawdown aggregates same-exit-timestamp PnL but does not itself establish a complete intrabar MTM portfolio DD. `all_ok` has six configurable thresholds and is a product KPI, not evidence of statistical robustness or independent OOS. The H1 portfolio runner adds an input/code manifest and caveats but those manifest semantics are tied to breakout validation. A dedicated H-B manifest must capture H-B-specific classifier config, exact 24-close mean window, shock/stabilization/fill timing, frozen shock-low stop, target, 24-bar time stop, event priority, and synthetic-vs-market data tier.

**Synthetic-only report contract:** a synthetic mechanics report may state pass/fail of deterministic invariants and test coverage, but must not print market return, PF, monthly return, profitability, edge, or green readiness. If any such fields are included for debugging, label them `NOT_MARKET_METRICS` and exclude them from strategy decision summaries.

**Статус:** найдена конкретная reporting/readiness опасность при смешении стратегий; H-B runner отсутствует. Статический аудит; код и тесты не менялись/не запускались.


### 10.21. Synthetic test specification v0.1

Создан отдельный документ `docs/research/hypotheses/H_B_SYNTHETIC_TEST_SPEC_2026-11-05_RU.md` (16 разделов): точная временная семантика H-B; детерминированные fixtures; signal predicates; pending persistence fail-closed; actual-fill sizing; nullable TP position restore; MTM/manager/exit priority; close/accounting/provenance; portfolio/report isolation; legacy parity; структура будущего тестового модуля; последовательность offline test suites; release gates G0–G6. Документ фиксирует, что synthetic pass не открывает market validation или deployment. Это спецификация, не реализация: код не менялся, тесты не писались/не запускались.


### 10.22. Implementation seam map and additional manager dependency — 2026-11-05

Повторная адресная read-only проверка актуального Bybit_Trading_Engine_v14_research.py на HEAD ветки зафиксировала точные места будущей интеграции (номера строк относятся к проверенному blob; при реализации искать по именам методов, а не полагаться на номера):

| Узел | Текущий участок | Требуемое изменение для H-B |
|---|---:|---|
| OpenPositionState | 401–447 | Добавить только appended optional H-B provenance; TP1/TP2 типизировать nullable без изменения legacy defaults/порядка полей |
| TradeRecord | 787–839 | Добавить appended optional H-B поля; существующие TP поля уже Optional |
| PlanBStatePersistence.load_state | 1412–1625+ | Strategy-aware required/numeric/geometry validation; H-B null TP; H-B metadata; exchange minNotional по stop/target; строгий unknown-key rejection |
| _unrealized_pnl_at_marks | 2392–2435 | Сейчас TP1 qty/notional вычисляются безусловно на строках 2410–2412 до проверки tp1_hit на 2418. Перенести TP1-specific расчёты внутрь условной ветки; H-B не должен требовать TP1 |
| _try_fill_pending | 2647–2785+ | Сейчас market chase guard 2712–2714, build_levels 2717 и sizing от fill-relative stop. Добавить strategy-specific absolute stop/target path, actual-fill geometry, H-B-only chase bypass и legacy parity |
| _apply_tp1 | 2855+ | Не вызывать для H-B; не менять семантику legacy |
| _manage_position | 2889–3043 | Отдельная H-B ветка после liquidation/kill-switch/stop и до TP1/TP2/trailing. Сохранить bars_held и запрет discretionary exit на fill bar |
| _close_position | 3050–3191 | Null-safe TradeRecord TP serialization и H-B provenance для обычного и forced close; общая accounting логика сохраняется |
| export_journal_for_dashboard | 3284–3297 | asdict() автоматически экспортирует новые поля; проверить null и строгую JSON сериализацию |

**Дополнительная находка:** _manage_position() безусловно вызывает QuantStrategyCore.compute_atr(hist[:-1], cfg.atr_period) на строке 2896 до exit branching. H-B exit contract не использует ATR после сигнала. Поэтому реализация должна либо вычислять ATR только для стратегий, которым он нужен, либо доказать, что H-B manager не зависит от него; нельзя вводить скрытое требование достаточной ATR-истории для уже открытой H-B позиции. Тест: валидная H-B позиция после restore управляется без ATR-зависимого discretionary path, при этом legacy ATR/trailing остаётся прежним.

**Уточнение по _close_position():** TP1 fee leg уже защищён if pos.tp1_hit (3095–3100), но TradeRecord создаётся с безусловными round(pos.tp1_price, 12) и round(pos.tp2_price, 12) (3155–3156). Следовательно, None TP ломает сериализацию даже при корректном tp1_hit=False; это отдельный обязательный тест close path.

**Граница изменений:** перечисленные участки связаны; частичное внедрение nullable TP без одновременного MTM, manager, restore и close изменений создаёт неработоспособное промежуточное состояние. Требуется согласованный набор изменений с legacy regression. В этой сессии production code не менялся; source map — read-only engineering audit.


### 10.23. Existing offline regression harness inventory — 2026-11-05

Проверены реальные test modules на текущей ветке (read-only, без запуска):

| Модуль | Объём | Релевантное покрытие | Роль в H-B acceptance |
|---|---:|---|---|
| `tests/test_portfolio_accounting.py` | 1,905 строк; 56 функций `test_*` | MTM, TP1 lifecycle, close accounting, journal precision, portfolio risk budget, exchange sizing, liquidation/kill-switch и close ordering | Обязательная accounting/MTM regression suite; дополнить отдельным H-B модулем, не менять legacy expectations |
| `tests/test_state_persistence.py` | 2,116 строк; 123 test methods | backup round-trip, legacy compatibility, fail-closed schema, unknown fields, atomic save/fsync/replace, pending validation, exchange metadata restore | Обязательная persistence regression suite; новые H-B fixtures должны расширять схему без ослабления старых assertions |

**Harness conventions observed:** accounting module dynamically imports engine under a test-specific module name and defines lightweight `make_position()` / `make_engine()` fixtures; persistence module uses `unittest.TestCase`, imports engine normally, and has reusable `sample_position()`, `sample_risk_data()` and atomic-backup helpers. New H-B module should follow the local conventions appropriate to each tested subsystem and avoid duplicating production logic in mocks.

**Important caveat:** the presence of these test modules and test functions does not prove they currently pass on this branch. The repository files were inspected through the GitHub connector; there is no authorized local checkout/test execution path in this session, and repository archive download/extraction remains outside the approved scope. No test result is claimed. A future CI run must be observed and its logs inspected; current latest docs commit has no associated workflow run/status evidence.

**Suggested next code-stage ordering, once sanctioned code editing/test execution is available:**
1. Extend dataclasses and strategy-aware persistence schema with direct round-trip/fail-closed tests.
2. Add pending H-B provenance and absolute fill geometry; test actual fill sizing and unchanged legacy fill fixtures.
3. Make MTM null-safe and remove unnecessary H-B ATR dependency; add intrabar/close MTM tests.
4. Add H-B manager branch and priority tests, including fill-bar stop-only behavior and 24th-bar close.
5. Add normal/forced close provenance, null TP journal serialization and legacy JSON parity tests.
6. Add strategy-isolated synthetic report/manifest; only then run targeted suites, accounting/persistence regressions and full offline suite.

**Статус:** test infrastructure is present and relevant; no evidence yet of a successful run, no H-B tests exist, and no production code changed.


### 10.24. Isolated causal signal predicate — 2026-11-24

В отдельной ветке `research/hb-signal-contract` добавлены:
- `h_b_signal.py` — чистая функция `evaluate_h_b_signal()`, которая проверяет только H-B v0.1 signal contract до close t+1 и возвращает ожидаемое время входа на open t+2;
- `tests/test_h_b_signal.py` — 10 deterministic synthetic pytest cases: happy path, range gate на t-1, inclusive shock threshold с ATR[t-1], strict stabilization, future mutation, exact H1 cadence, duplicate timestamp, invalid ATR/OHLC и insufficient history.

**Границы реализации:** торговый движок не изменён; нет pending/fill adapter, sizing, position state, persistence, manager, exits, TradeRecord или отчётов. Range labels и ATR подаются как входы; RegimeConfig не выбрана и не заморожена. Это намеренно узкий тест временной механики, а не полноценная H-B стратегия.

**Проверка:** прямое выполнение скопированной из GitHub реализации прошло 4 базовые assertions. Это не равно запуску pytest из репозитория. PR #16 открыт; GitHub workflow runs для head commit пока не обнаружены. Полный pytest/CI результат не подтверждён.

**Решение:** не начинать полный lifecycle adapter. Сначала добиться исполнения 10 тестов в репозитории и проверить независимую legacy regression. После этого оценить, имеет ли смысл следующий изолированный слой. Market PnL, data collection, exchange APIs, parameter sweep и paper/live остаются запрещёнными текущими gates.
