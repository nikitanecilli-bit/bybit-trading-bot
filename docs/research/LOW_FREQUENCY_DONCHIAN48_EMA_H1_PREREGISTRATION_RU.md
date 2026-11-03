# Низкочастотная H1-гипотеза: Donchian(48) + EMA50/EMA200

Дата фиксации: 2026-11-04  
Ветка: `research/market-regime-v1-main`  
Статус: **DESIGN FROZEN / NO MARKET PNL RUN / DATA GATE CLOSED**

## 1. Задача

Проверить, уменьшает ли более длинная структура пробоя число слабых входов и долю комиссий относительно существующего H1 Donchian(20), не ухудшая чистое ожидание и просадку.

Это новая исследовательская гипотеза, а не найденная прибыльная стратегия. CryptoFetch/Binance-style proxy архивы уже использованы в предыдущих исследованиях и не являются независимым holdout. Никаких новых PnL-прогонов по ним не проводить.

## 2. Единственная первичная конфигурация

**Candidate:** long-only H1 Donchian(48) breakout + causal EMA50/EMA200-up gate.

Сигнал разрешён только при одновременном выполнении:
1. Текущая завершённая H1 свеча закрылась выше максимума предыдущих 48 завершённых H1 свечей. Сигнальная свеча не входит в окно Donchian.
2. Volume ratio рассчитан по тем же 48 предыдущим свечам и проходит тот же заранее зафиксированный порог, который выбран на Explore до открытия Confirm.
3. EMA50 > EMA200.
4. EMA200 выше своего значения 5 завершённых H1 свечей назад.
5. Текущий завершённый close выше EMA200.
6. EMA labels precomputed по полной доступной причинной истории; фиксированный burn-in 1,000 H1 свечей; lookup только по точному timestamp текущей завершённой свечи. Нет метки/истории — сигнал блокируется.

Никаких H-A relative-strength, H-C invalidation, range-fade или иных дополнительных фильтров.

## 3. Парные контрольные варианты

На каждом разрешённом fold и одинаковых входных данных сравнить три отдельные shared-capital портфеля:

- **Control A:** Donchian(20), EMA gate OFF — исправленный frozen baseline.
- **Control B:** Donchian(48), EMA gate OFF — изолирует эффект длины канала.
- **Candidate C:** Donchian(48), EMA50/EMA200-up gate ON — изолирует добавочный эффект трендового фильтра.

У всех трёх вариантов должны совпадать universe, временные границы, starting capital, portfolio risk cap, лимит позиций, плечо, stop/TP, исполнение и cost multiplier. Капитал между вариантами не общий: каждый — отдельный идентичный replay со стартовым капиталом 10,000 USDT.

Donchian(96) не включать в текущий эксперимент и не выбирать постфактум как «лучший». Если первичный Donchian(48) не пройдёт критерии, не расширять sweep по тем же folds.

## 4. Замороженные параметры исполнения и риска

До отдельной preregistration эти параметры остаются такими же, как в текущем H1 shared-capital runner:

| Параметр | Значение |
|---|---:|
| Таймфрейм | H1 |
| Направление | Long-only |
| Donchian primary | 48 |
| ATR | 14 |
| Stop | 2.5 ATR |
| TP1 | 2R |
| TP2 | 5R |
| ATR trailing | 3.0 ATR |
| Максимальное удержание | 32 H1 бара |
| Вход | Maker limit proxy |
| Limit offset / penetration | 20 / 5 bps |
| Pending TTL | 3 H1 бара |
| Стартовый капитал на вариант | 10,000 USDT |
| Risk per trade | 1.0% |
| Portfolio risk cap | 2.0% |
| Максимум позиций | 5 |
| Плечо | Isolated 5x model |
| Daily stop | 5% |
| Emergency kill switch | 30% |
| Max chase | 1.5% |
| Cost stress | 1.0x / 1.5x / 2.0x; primary = 2.0x |

OHLC maker fill остаётся optimistic proxy: он не моделирует очередь, bid/ask, частичные исполнения и adverse selection. Нельзя называть его доказанным maker исполнением.

## 5. Что намеренно НЕ включать

Не объединять в одном эксперименте все идеи из альтернативного Gemini-варианта. Следующие изменения требуют отдельных preregistered ablations после оценки сигнального edge:

- micro-pullback / maker entry logic;
- минимальный stop 1.8%;
- перевод в breakeven при +0.95R;
- динамический trend TP до 4.2R;
- Donchian(96).

Иначе нельзя будет понять, какой компонент дал улучшение или ухудшение. В частности, breakeven и изменение TP/stop меняют распределение исходов и не должны маскировать качество самого сигнала.

## 6. Дизайн данных и fold protocol

PnL replay запрещён, пока не выполнены все существующие data и accounting gates из `NEXT_STRATEGY_RESEARCH_PLAN_RU.md`, включая:
- официальный Bybit linear USDT perpetual H1 trade OHLCV;
- полную Funding историю и независимо проверяемую settlement schedule;
- соответствующие Mark-price H1 candles;
- dated instrument specifications и risk-limit tiers;
- валидный lifecycle/universe snapshot и исправленный train-only Top-5 manifest;
- общий исторический overlap и полную hash provenance;
- подтверждённую accounting reconciliation на том же replay path.

Текущие CryptoFetch архивы полностью development-only; ни один их временной участок нельзя называть независимым holdout. Не подключать Bybit API, не собирать новые биржевые архивы и не регистрировать runner ради этого исследования.

Когда пригодный независимый набор данных будет доступен в рамках разрешённого этапа:
- folds 1–2 — только Explore, выбор единственного volume/breakout threshold из заранее ограниченного набора;
- fold 3 — однократный Confirm, параметры зафиксировать до открытия fold;
- если Confirm используется для изменения параметров, он считается потраченным и больше не называется untouched holdout;
- после успешного Confirm всё равно нужен следующий независимый исторический holdout и затем paper forward test.

## 7. Критерии решения

Первичный cost case — 2.0x. Candidate C допускается к следующему независимому этапу только если на Confirm одновременно:
1. net PnL строго положительный;
2. net PnL выше Control A и Control B;
3. portfolio profit factor > 1;
4. net expectancy > 0;
5. max drawdown не хуже Control A более чем на 2 п.п.;
6. geometric monthly-equivalent net return не ниже целевого ориентира +20%.

Также публиковать trade count, fill rate, expired entries, maker/taker mix, fees, slippage, funding, losing months, monthly equity, per-symbol attribution и все cost cases. Один fold и geometric monthly-equivalent не доказывают стабильные +20% каждый месяц.

Если вариант не проходит хотя бы один primary критерий — отклонить, не подбирать параметры на Confirm.

## 8. Текущий статус и реализационные замечания

- В текущем runner `cfg.donchian_period` пока фиксирован на 20; для будущего эксперимента потребуется отдельный явный параметр, включённый в manifest и code provenance. Не менять baseline default.
- EMA50/EMA200 paired runner уже реализован для Donchian(20), но не имеет рыночного PnL результата и не является доказательством пользы фильтра.
- Train-only Top-5 selector остаётся long-only и ранжирует кандидатов в отдельных односymbolных screening-портфелях; итоговый выбор пяти инструментов не является доказательством оптимальности общего портфеля. Финальный вывод делается только на shared-capital replay.
- Исторический delisted universe / временная доступность всех контрактов полностью не доказаны; survivorship bias остаётся отдельным ограничением.
- Никакой market PnL replay, paper trading, Bybit API connection или реальные ордера в рамках этого документа не выполнялись.
