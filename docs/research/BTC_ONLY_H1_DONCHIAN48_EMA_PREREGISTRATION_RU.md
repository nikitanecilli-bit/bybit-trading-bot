# BTCUSDT-only H1 Donchian(20/48) + EMA50/200 — отдельная preregistration

**Протокол:** `h1-btc-single-symbol-v1`  
**Статус:** протокол зафиксирован до запуска рыночного PnL; результаты стратегии ещё не исследовались в рамках этого маршрута.  
**Источник рынка:** только официальные данные Bybit. Другие биржи и независимые наборы данных не смешиваются с этим экспериментом.

## 1. Scope и отличие от Top-5 эксперимента

- Единственный инструмент: `BTCUSDT`, USDT linear perpetual Bybit.
- Направление: long-only.
- Никакого ранжирования монет и train-only Top-5 selector нет. BTC выбран как фиксированный объект исследования, а не как победитель отбора по исторической доходности.
- Этот протокол является отдельным single-symbol экспериментом. Он не заменяет и не считается эквивалентом исходного Top-5 протокола из `LOW_FREQUENCY_DONCHIAN48_EMA_H1_PREREGISTRATION_RU.md`.
- Входные H1 данные должны содержать только BTCUSDT, быть упорядоченными, без дубликатов и пропусков. Manifest builder требует не менее 6,001 свечи, чтобы до первого validation бара было не менее 3,000 train bars.

## 2. Разделение истории

Граница train/validation фиксируется на 50% непрерывной H1 истории BTCUSDT:

- Train заканчивается на последней завершённой свече перед границей 50%.
- Explore fold 1: 50–65% истории.
- Explore fold 2: 65–80% истории.
- Confirm fold 3: 80–100% истории.

Граница вычисляется один раз из конкретного архива и сохраняется в manifest с timestamp и SHA-256 всех файлов. Если история содержит пропуски, этот маршрут отказывает в создании manifest; нельзя незаметно сшивать разрывы или менять границу после просмотра результатов.

## 3. Зафиксированные варианты

Все три варианта используют общий капитал и одинаковые правила исполнения, риск-лимиты, даты fold и cost stress.

| Вариант | Donchian | EMA-фильтр | Volume lookback |
|---|---:|---|---:|
| Control A | 20 | выключен | 20 |
| Control B | 48 | выключен | 48 |
| Candidate C | 48 | EMA50/EMA200-up | 48 |

Условия сигнала и EMA-фильтра — как в основном preregistration документе. Дополнительного breakout-distance ATR-фильтра нет: `min_breakout_atr = 0` фиксирован во всех arms.

## 4. Единственная Explore-размерность

- Допустимая сетка `min_volume_ratio`: `[1.2, 1.6, 2.0, 2.5]`.
- Выбор делается только на Explore folds 1–2.
- Нельзя подбирать Donchian period, EMA параметры, breakout ATR, execution assumptions или cost model по Explore результатам.
- Confirm использует один заранее зафиксированный volume threshold и только fold 3.
- Cost stress всегда: `1.0x / 1.5x / 2.0x`.

## 5. Данные и provenance gates

До любого market-PnL replay обязательны:

1. Bybit H1 trade OHLCV для BTCUSDT с непрерывной сеткой и достаточным периодом.
2. Полное историческое Bybit funding покрытие и проверка расписания settlement.
3. Bybit mark-price история для funding/mark-to-market/liquidation accounting.
4. Датированные Bybit instrument specifications и risk tiers, применимые на каждый момент истории.
5. Bybit linear-universe lifecycle snapshot, подтверждающий, что BTCUSDT был USDT perpetual на train cutoff и в границах архива.
6. Точные SHA-256 и размеры файлов, плюс hash всех replay dependencies.

Manifest создаётся отдельным builder `scripts/create_h1_btc_single_symbol_manifest.py`, который не запускает PnL. Он использует protocol `h1-btc-single-symbol-v1`, фиксирует ровно `BTCUSDT` и отказывает при посторонних CSV-символах, gaps или неполной lifecycle-проверке.

## 6. Условия остановки

- Любой незакрытый data/accounting gate означает **не запускать PnL**.
- Успешный CI подтверждает только код и детерминированные проверки, но не доходность.
- Положительный результат Explore не является доказательством edge; решение возможно только после заранее зафиксированного Confirm и stress checks.
- Если Confirm не проходит primary criteria, гипотеза отклоняется. Нельзя повторно подбирать параметры на fold 3.
- Никаких paper/live ордеров и приватных API ключей в рамках этого исследования.

## 7. Ограничения исполнения

Maker fill по OHLC остаётся оптимистичным proxy; очередь, partial fills, spread и adverse selection полностью не моделируются. Текущая модель ликвидации и исторических exchange rules также имеет ограничения, описанные в основном preregistration. Эти ограничения должны быть явно отражены в итоговом выводе; они не дают права называть симуляцию фактической исполнимой доходностью.

**Текущий статус:** single-symbol manifest route реализован и проходит инженерные тесты. Market-PnL replay не выполнялся; Bybit data/accounting gates остаются закрытыми.


## 8.1. Строгий preflight single-symbol manifest

До создания manifest builder обязан проверить не только наличие файлов, но и:

- Funding CSV и query-provenance audit manifest, включая SHA-256, полноту запросов и dated settlement schedule evidence.
- Полное совпадение Mark Price H1 timestamp grid с Bybit trade-kline grid и наличие settlement marks.
- Непрерывность и актуальность датированных Bybit instrument-spec и risk-tier snapshots на всём архивном интервале (максимальный возраст snapshot задаётся проверкой).
- BTCUSDT lifecycle на train cutoff по официальному Bybit universe snapshot.

Если любой gate не проходит, builder отказывает в создании manifest. Создание manifest не запускает PnL.
