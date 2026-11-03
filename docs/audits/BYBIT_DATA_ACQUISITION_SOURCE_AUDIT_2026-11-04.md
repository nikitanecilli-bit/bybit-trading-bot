# Аудит источников исторических данных Bybit — 2026-11-04

## Цель

Найти допустимый источник Bybit-native H1 trade OHLCV, Mark Price и Funding, который позволит закрыть текущий data/accounting gate без подмены биржевых данных прокси.

## 1. Официальный Bybit V5 API

Проверены официальные страницы:

- Integration Guidance: https://bybit-exchange.github.io/docs/v5/guide
- Get Kline: https://bybit-exchange.github.io/docs/v5/market/kline
- Get Mark Price Kline: https://bybit-exchange.github.io/docs/v5/market/mark-kline
- Get Funding Rate History: https://bybit-exchange.github.io/docs/v5/market/history-fund-rate

Документация подтверждает:
- Public market endpoints для H1 trade candles, Mark Price candles и Funding history существуют.
- Mainnet hostnames включают https://api.bybit.com и https://api.bytick.com; для отдельных регионов указаны региональные hostname.
- Bybit прямо указывает, что IP из США и материкового Китая ограничены и получают HTTP 403.
- Funding history API возвращает исторические funding rates, но интервалы различаются по инструментам и должны проверяться отдельно через instruments-info.

### Практическое следствие

Предыдущий HTTP 403 из GitHub-hosted runner согласуется с документированным US IP restriction, но точную геолокацию IP того конкретного runner по старым логам не доказали. Текущие snapshot/archive workflows уже требуют self-hosted runner вне US/Mainland China и умеют принимать BYBIT_API_BASE_URL через GitHub variable. Вариант api.bytick.com также уже разрешён в allowlist collector.

Не пытаться обходить региональные ограничения прокси или маскировкой IP. Рабочий вариант — runner в разрешённой сети/регионе, законно доступный владельцу проекта, с публичными endpoints без приватных API keys. Это не подключение аккаунта и не торговые полномочия, но всё равно требует реального сетевого доступа.

## 2. Официальный исторический Data Download

Официальная документация Bybit ссылается на Historical Market Data download:
https://www.bybit.com/en/derivative-activity/history-data

Страница описывает публичные OHLCV и trade-history datasets в CSV. На момент проверки веб-страница раскрывает только оболочку каталога; по доступным данным не подтверждено, что этот архив включает Mark Price candles, Funding settlements, dated risk tiers или historical instrument specifications.

Решение: считать потенциальным источником официальных trade OHLCV/trades после проверки конкретных продуктов и coverage; не считать его заменой Mark/Funding/spec archives без доказательств.

## 3. Независимый архив CryptoHFTData — проверен, но не принят как primary source

Страница: https://www.cryptohftdata.com/datasets/bybit-funding-rate-data

Заявленные свойства:
- Bybit Futures mark/index/funding event data в hourly Parquet.
- История начинается 2025-06-28.
- Доступ к отдельным hourly files заявлен без API key на free tier; SDK/API требует free API key.
- Это независимый архив, не официальный Bybit API.

Критичные ограничения из собственной документации поставщика:
- Bybit missing hours: 2025-11-26 10 UTC — 2025-12-26 19 UTC; 2026-04-13 15 UTC — 2026-04-14 21 UTC.
- До data-integrity release сентября 2026 Mark Price / ticker / open-interest rows были change-only deltas: unchanged fields are null. Требуется stateful forward-fill, в том числе через границы файлов/часов.
- Поставщик прямо указывает, что часть пропусков и неполных периодов не восстановлена.
- Архив не является официальным Bybit source; независимость поставщика не равна независимой верификации exchange completeness.

Источники:
- https://www.cryptohftdata.com/exchanges/bybit
- https://www.cryptohftdata.com/docs/data-gaps-and-corrections

Решение:
- Не использовать этот архив как единственный источник для market PnL validation.
- Можно использовать ограниченно для exploratory diagnostics или cross-check только после обработки null-delta semantics, проверки known gaps и сравнения выборочных часов с официальным Bybit API.
- Не выдавать его данные за official Bybit archive.

## 4. Текущий технический статус проекта

- В collector scripts уже поддержаны official Bybit base URL override, пагинация, проверка timestamp grid, OHLC ordering, duplicate detection и atomic archive writes.
- Snapshot/archive workflows уже требуют self-hosted runner вне US/Mainland China; обычный hosted runner может быть заблокирован географически.
- Нет подтверждения, что у проекта сейчас доступен подходящий self-hosted runner.
- Нет полного historical effective-time journal для Funding interval, risk tiers, tick/qty filters и instrument lifecycle. Точечные snapshots — observations, не event history.
- Нет доказанной полноты Mark/Funding/risk-tier/instrument-spec архивов по всему целевому периоду.

## 5. Решение и следующие шаги

1. Не запускать PnL и не ослаблять preflight.
2. Для получения официальных архивов использовать self-hosted GitHub runner в разрешённой сети/регионе или другой легитимный execution host; только публичные market endpoints, без private account API.
3. Сначала проверить небольшой известный интервал BTCUSDT: H1 trade OHLCV, Mark H1 OHLC и Funding rows. Сохранить response metadata, raw files, hashes, page coverage и UTC timestamps.
4. Затем проверить все выбранные top-5 + reserve-5 инструменты, lifecycle, exact Funding settlement schedule, Mark settlement proxy, dated risk tiers и instrument specs.
5. Сверить выборочные интервалы с официальным UI/data download там, где доступно.
6. CryptoHFTData оставить только supplementary until proven complete and reconciled; явно учитывать указанные missing periods and delta encoding.
7. После закрытия каждого data gate пересоздать train-only selection manifest из новых immutable inputs и только потом проводить preregistered H1 experiments.

## Вывод

Наиболее чистый путь остаётся официальный Bybit V5 public market API с подходящего self-hosted runner. Официальный download center может помочь с trade OHLCV/trades, но пока не доказано, что он закрывает Mark/Funding/specification history. Независимый CryptoHFTData архив полезен как дополнительный источник, но его собственные documented gaps и change-only deltas не позволяют принять его за единственную основу PnL validation.

Никаких PnL, paper/live tests, private API calls или order operations в рамках этого аудита не выполнялось.
