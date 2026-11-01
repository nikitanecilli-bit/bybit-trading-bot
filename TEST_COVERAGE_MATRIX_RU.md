# Матрица покрытия аудита и исследовательских гипотез

Статус относится к подтверждённым доступным материалам на 2026-11-02, а не к обещанию корректности.

| Область | Статус | Что известно | Что требуется |
|---|---|---|---|
| Архитектура репозитория | PARTIAL | Найдены engine, downloader, scripts, workflows, reports, tests | Сверить все ветки и зависимости |
| Live execution / безопасность | PARTIAL | README утверждает, что v14 research engine не отправляет ордера | Проверить весь репозиторий/ветки на API order endpoints |
| Свечи и временные метки | PARTIAL | Есть `test_time_model.py`, синхронизация проверяется в скриптах | Проверить semantics каждого источника и boundary cases |
| Look-ahead | NOT_TESTED | E09 заявляет completed-bar context | Статический аудит всех сигналов/фич/выходов |
| Stop/TP внутри свечи | NOT_TESTED | Есть общие тесты времени и гэпов | Проверить collision и OHLC path assumptions |
| Market gap execution | PARTIAL | `test_gap_execution.py` и gap report существуют | Повторить тесты, проверить точное покрытие |
| Limit fills | PARTIAL | E03/E07/E09 моделируют лимитное касание | Нет queue/partial fill/spread/adverse selection |
| Fees | PARTIAL | Моделируются maker/taker комиссии; E09 использует multiplier | Проверить round-trip, разные типы exit и фактические тарифы |
| Slippage | PARTIAL | В движке есть модель slippage | Проверить применение к фактической цене и sizing |
| Funding | NOT_TESTED | Отдельная funding-data ветка существует | Проверить point-in-time funding integration и влияние |
| Position sizing / leverage | NOT_TESTED | Есть параметры риска и плеча в движке | Проверить формулы, округления, margin/liquidation |
| Portfolio shared capital | PARTIAL | E07 портфельный тест | Проверить event ordering, simultaneous signals и capital accounting |
| Concurrency / risk gates | PARTIAL | E07/E09 учитывают max positions и risk gates | Проверить последовательность символов и зависимость результата от порядка |
| Market regimes | PARTIAL | Есть regime scripts/reports и E06 diagnostics | Внешняя независимая проверка, стабильность по периодам |
| False breakout classifier | NOT_TESTED | Гипотеза описана в проектном контексте | Формализовать признаки без leakage и проверить out-of-sample |
| Universe screening | PARTIAL | E01/E02/holdout отчёты | Survivorship, delisted symbols, point-in-time universe |
| Holdout integrity | PARTIAL | Holdout report существует; Bybit 403 noted | Проверить даты/данные и факт отсутствия повторного подбора |
| Multiple testing / DSR/PBO | PARTIAL | В отчётах есть caveats | Текущие упрощённые расчёты не считать валидированными |
| Reproducibility | PARTIAL | Есть GitHub workflows и артефакты | Сверить SHA, dataset hashes, configs, exact artifacts |
| E09 factorial | PARTIAL | 24 клетки заявлены в журнале | Сверить run commit SHA, job logs, 3 CSV и фактические различия факторов |

## Ключевые непроверенные риски
1. Корректность порядка исполнения входа/выхода на одной OHLC-свече.
2. Влияние funding и реальных Bybit комиссий.
3. Реалистичность maker fills.
4. Look-ahead и leakage через market context / universe.
5. Влияние порядка обработки символов на общий портфель.
6. Реальная устойчивость edge по каждому fold, инструменту и независимому периоду.
