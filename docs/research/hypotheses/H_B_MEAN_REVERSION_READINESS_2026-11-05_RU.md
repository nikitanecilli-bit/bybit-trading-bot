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
