# Проверка официального публичного архива Bybit H1 BTCUSDT — 2026-11-25

## Вывод

Найден дополнительный официальный публичный источник Bybit:
- Каталог: https://public.bybit.com/kline_for_metatrader4/BTCUSDT/
- Внутри годовых каталогов лежат месячные gzip CSV с именами вида `BTCUSDT_60_YYYY-MM-01_YYYY-MM-DD.csv.gz`.
- Суффикс `60` соответствует часовому интервалу, нужному для H1-исследования.

Проверенные каталоги:
- 2020: месяцы апрель–декабрь;
- 2021: январь–декабрь;
- 2022: январь–декабрь;
- 2023: январь–декабрь;
- 2024: январь–ноябрь.

Примеры точных каталогов:
- https://public.bybit.com/kline_for_metatrader4/BTCUSDT/2020/
- https://public.bybit.com/kline_for_metatrader4/BTCUSDT/2021/
- https://public.bybit.com/kline_for_metatrader4/BTCUSDT/2022/
- https://public.bybit.com/kline_for_metatrader4/BTCUSDT/2023/
- https://public.bybit.com/kline_for_metatrader4/BTCUSDT/2024/

## Возможная польза для текущего архива

Текущий нормализованный H1 архив имеет четыре крупных разрыва:
- 2023-12-09 07:00 → 2024-01-01 00:00 UTC;
- 2024-01-09 07:00 → 2024-02-01 00:00 UTC;
- 2024-02-17 15:00 → 2024-03-01 00:00 UTC;
- 2024-03-09 07:00 → 2024-04-01 00:00 UTC.

Публичный Bybit H1 каталог содержит месячные файлы за декабрь 2023 и январь–апрель 2024. Это потенциальный способ закрыть эти разрывы, но только после скачивания, проверки формата, временных меток, непрерывности и сравнения пересекающихся свечей с уже имеющимися Bybit-данными.

## Ограничения, которые остаются

1. Каталог `kline_for_metatrader4` — отдельная публикация Bybit. До сравнения с V5 Kline нельзя считать его свечи взаимозаменяемыми с уже используемым источником.
2. Каталог по 2024 году, который удалось прочитать, заканчивается ноябрём 2024. Запрос каталога 2025 в этой проверке не дал доступного листинга. Это не доказывает, что файлов 2025 не существует; доступность не подтверждена.
3. Корневой публичный каталог Bybit содержит `premium_index` только для inverse-символов, включая BTCUSD, а не BTCUSDT linear. Он не закрывает требование Mark Price для BTCUSDT linear.
4. В корневом публичном каталоге не обнаружен отдельный архив Funding Rate.
5. V5 Funding и Mark Price endpoints документированы, но доступ к ним из текущего GitHub-hosted runner ранее блокировался HTTP 403. В этой проверке прямой API-запрос также не удалось прочитать через веб-клиент.
6. Исторические instrument specifications и risk tiers остаются отдельным пробелом: текущие endpoints не восстанавливают полную историю изменений.

## Безопасный следующий шаг

- Не запускать PnL и не менять preregistration.
- Добавить отдельный небольшой архиватор только для официальных Bybit `kline_for_metatrader4` BTCUSDT H1 месячных файлов.
- Сначала скачать один файл и проверить схему/таймзону/сортировку и точное совпадение перекрывающихся свечей с текущим источником.
- Затем скачать только месяцы, необходимые для четырёх известных разрывов, а не весь архив.
- Слить данные только после успешной проверки совпадения и полного timestamp grid.
- Funding, linear Mark Price и point-in-time execution snapshots оставить закрытыми gates.

## Источники

- Bybit public root: https://public.bybit.com/
- Bybit BTCUSDT H1 archive: https://public.bybit.com/kline_for_metatrader4/BTCUSDT/
- Bybit V5 Kline: https://bybit-exchange.github.io/docs/v5/market/kline
- Bybit V5 Mark Price Kline: https://bybit-exchange.github.io/docs/v5/market/mark-kline
- Bybit V5 Funding History: https://bybit-exchange.github.io/docs/v5/market/funding/history
- Bybit instrument info: https://bybit-exchange.github.io/docs/v5/market/instrument
- Bybit risk limits: https://bybit-exchange.github.io/docs/v5/market/risk-limit

Статус документа: проверка доступности каталогов по публичным листингам. Сами gzip-файлы пока не скачаны и не провалидированы.
