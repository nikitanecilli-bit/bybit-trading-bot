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
