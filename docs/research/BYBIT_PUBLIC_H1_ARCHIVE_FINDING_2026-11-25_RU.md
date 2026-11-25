# Сверка публичного каталога Bybit H1 BTCUSDT с уже принятым состоянием проекта — 2026-11-25

## Результат проверки

Публичный каталог Bybit существует:
- https://public.bybit.com/kline_for_metatrader4/BTCUSDT/
- В годовых каталогах размещены месячные gzip CSV вида `BTCUSDT_60_YYYY-MM-01_YYYY-MM-DD.csv.gz`; `60` — часовой интервал.
- В публичном листинге, доступном при этой проверке, видны 2020 (апрель–декабрь), 2021–2023 (полные годы) и 2024 (январь–ноябрь).

Это **не новый источник для проекта**. В актуальном `PROJECT_COMPASS_RU.md` уже зафиксировано, что официальный Bybit H1 archive был получен, нормализован и проверен:
- 47,085 H1 строк;
- диапазон 2020-04-01 00:00 UTC — 2025-11-03 01:00 UTC;
- исходные временные метки каталога `kline_for_metatrader4` нормализуются из UTC+3 в UTC;
- на контрольном дне 2025-07-01 24 свечи сверены с восстановлением из официального Bybit Linear BTCUSDT trade archive: high/low/close и объём совпали во всех 24 часах, open отличается не более чем на один tick (0.10 USDT).

Таким образом, текущая проверка публичных листингов лишь повторно подтвердила структуру уже известного источника. Новый downloader, новый collector или повторная загрузка полного H1 архива не нужны.

## Оставшаяся проблема H1

Принятый H1 ряд всё ещё содержит четыре разрыва общей длиной 1,928 баров:
- 2023-12-09 07:00 → 2024-01-01 00:00 UTC: 544 bars;
- 2024-01-09 07:00 → 2024-02-01 00:00 UTC: 544 bars;
- 2024-02-17 15:00 → 2024-03-01 00:00 UTC: 296 bars;
- 2024-03-09 07:00 → 2024-04-01 00:00 UTC: 544 bars.

Нельзя интерполировать эти бары или незаметно пересекать разрывы открытыми позициями. Любое будущее использование должно либо получить и проверить точные Bybit bars, либо явно исключить разрывы с заранее определённой семантикой индикаторов/позиций. Текущий BTC-only manifest builder намеренно отказывает при gaps.

## Что эта проверка не закрывает

1. **Mark Price BTCUSDT Linear:** публичный каталог `premium_index` содержит inverse BTCUSD и другие inverse symbols, а не BTCUSDT Linear. Это не замена нужному Mark Price ряду.
2. **Settled Funding:** в корневом публичном каталоге отдельный архив Funding Rate не обнаружен. V5 Funding History документирован, но доступ из текущей среды ранее блокировался HTTP 403.
3. **Mark Price history:** V5 Mark Price Kline документирован, но доступ из текущей среды ранее блокировался HTTP 403.
4. **Dated instrument specs / risk tiers:** текущие endpoints не восстанавливают исторические effective-time значения.
5. Каталог 2025 при этой проверке не открылся; это не доказывает отсутствие файлов 2025. Фактический принятый H1 dataset уже содержит данные до 2025-11-03, как указано выше.

## Решение и следующий шаг

- Не строить второй архиватор для уже принятого H1 источника.
- Не скачивать повторно полный H1 архив.
- Не менять preregistration, не ослаблять data gates и не запускать market-PnL, sweeps, event studies или paper trading.
- Продолжать по `MINIMUM_VIABLE_EDGE_VALIDATION_RU.md`: искать минимально достаточный Bybit-native путь для одного заранее ограниченного BTCUSDT периода, с отдельным подтверждением Mark Price, settled Funding и execution assumptions.
- Если следующий шаг не закрывает конкретный обязательный gate или не меняет решение о возможности честной проверки net edge, его не выполнять.

## Источники

- Bybit public root: https://public.bybit.com/
- Bybit BTCUSDT H1 archive: https://public.bybit.com/kline_for_metatrader4/BTCUSDT/
- Bybit V5 Kline: https://bybit-exchange.github.io/docs/v5/market/kline
- Bybit V5 Mark Price Kline: https://bybit-exchange.github.io/docs/v5/market/mark-kline
- Bybit V5 Funding History: https://bybit-exchange.github.io/docs/v5/market/funding/history
- Bybit instrument info: https://bybit-exchange.github.io/docs/v5/market/instrument
- Bybit risk limits: https://bybit-exchange.github.io/docs/v5/market/risk-limit

Статус: read-only повторная сверка публичного каталога и действующих проектных записей. Новый рыночный расчёт, повторная загрузка данных и PnL replay не выполнялись.
