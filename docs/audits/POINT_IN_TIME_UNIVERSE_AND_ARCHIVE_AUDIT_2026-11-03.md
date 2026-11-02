# Аудит архива данных и point-in-time universe

Дата: 2026-11-03  
Ветка: `research/market-regime-v1-main`  
Статус: STATIC AUDIT — DATA PROVENANCE PARTIAL / SURVIVORSHIP CONTROL INSUFFICIENT

## Краткий вывод

Исторические результаты E01–E13 воспроизводимы по ряду workflow/artifact checks, но текущий набор данных не является point-in-time universe Bybit. Доступные ZIP содержат Binance-style OHLCV proxy; funding history, mark-price history и dated Bybit instrument/risk-tier snapshots в репозитории отсутствуют.

Для E11/E13 дополнительно подтверждён selection/survivorship limitation: общий universe строится из инструментов, для которых уже имеются достаточные данные во всех трёх заданных folds. Это полезно для сопоставимого replay на фиксированной выборке, но исключает инструменты без полной истории и не восстанавливает состав рынка, доступный на каждую историческую дату.

## 1. Что фактически хранится в репозитории

В `data/archives/cryptofetch/` находятся шесть ZIP-архивов:

- три архива с диапазоном в имени 2025-10-27 — 2026-10-27;
- три архива с диапазоном 2026-04-29 — 2026-10-26.

В исследовательском отчёте CryptoFetch зафиксированы 67 CSV entries в этих архивах. Схемы распознаны как Binance-style OHLCV. Отдельных funding-history CSV и mark-price datasets в проверенном архиве не обнаружено. В дереве текущей ветки нет сохранённых файлов в `data/funding/`, `data/mark_price/`, `data/instrument_specs/` или архиве risk tiers; каталог `data/` содержит только CryptoFetch ZIP.

Источники:
- `docs/research/CRYPTOFETCH_PER_SYMBOL_BACKTEST_2026-11-02.md`
- `scripts/audit_cryptofetch_archives.py`
- `scripts/run_uploaded_dataset_backtests.py`
- `scripts/archive_bybit_market_history.py`

## 2. Проверки целостности OHLCV

`read_zip_datasets()` в `scripts/run_uploaded_dataset_backtests.py` выполняет для CSV:
- проверку обязательных колонок;
- числовую проверку timestamp/OHLCV и положительных цен;
- проверку OHLC ordering и неотрицательного volume;
- сортировку по timestamp;
- отказ при дубликатах timestamp;
- проверку равномерного шага свечей для timeframe;
- выбор самого длинного валидного файла на пару symbol/timeframe.

Это полезные проверки структурной целостности выбранного файла. Однако выбор самого длинного файла не является доказательством, что он исторически репрезентативен или что universe не имеет survivorship bias. При нескольких версиях одного symbol/timeframe остальные файлы не объединяются; выбирается один кандидат, а решение зависит от числа строк и имени архива.

Отдельный `scripts/audit_cryptofetch_archives.py` — только инвентаризатор: считает строки, определяет schema/kind и first/last timestamp. Сам по себе он не проверяет duplicate timestamps, missing intervals, OHLC invariants или cross-archive consistency. Для этих проверок используется loader backtest-скрипта, но не отдельный архивный отчёт.

## 3. Неравномерность истории

В CryptoFetch per-symbol report отмечены:
- часть H1 инструментов имеет примерно годовую историю;
- многие инструменты покрывают только 2026-04-29 — 2026-10-26;
- GRAM начинается 2026-07-02;
- HYPE содержит только 758 H1 bars за 2026-09-24 — 2026-10-26;
- пустые DAIUSDT, MATICUSDT и XMRUSDT файлы пропущены;
- 15m выборка ограничена восемью инструментами.

Следствие: количество сделок, PF и net PnL нельзя напрямую сравнивать между символами без учёта разных окон, листингов, ликвидности и числа наблюдений. Короткая история и малое число сделок делают положительные оценки особенно нестабильными.

## 4. E11/E13: подтверждённый selection bias механизма формирования universe

В `scripts/run_e11_h1_shared_capital_replay.py`:
1. выбираются H1 datasets с не менее чем 500 bars;
2. для каждого символа считаются бары в трёх фиксированных folds;
3. символ включается только если в каждом fold есть не менее 100 bars;
4. затем строится пересечение timestamp sets всех включённых символов;
5. портфельный replay запускается только на этом общем синхронизированном окне.

Это обеспечивает сравнимую сетку и синхронный общий капитал. Но это не point-in-time universe:
- активы с короткой историей или поздним появлением в архиве исключаются;
- исключённые активы не участвуют в оценке доходности соответствующего исторического периода;
- состав universe формируется из доступности данных в собранном архиве, а не из исторического списка торгуемых Bybit linear contracts на каждый timestamp;
- delisted/renamed instruments не представлены как гарантированно полная историческая выборка.

Дополнительно `scripts/h1_symbol_universes.json` сообщает, что primary/reserve shortlist ранжировался по прежним результатам H1 signal-quality ablation на тех же архивах. Поэтому этот shortlist — отобранная исследовательская выборка, а не независимый набор для подтверждения преимущества. E11/E13 folds уже использовались для анализа и не являются blind holdout.

**Классификация:** подтверждённое ограничение дизайна и отбора выборки; не доказательство арифметической ошибки в E11/E13.

## 5. Bybit-native data gate остаётся закрытым

В репозитории есть сборщик `scripts/archive_bybit_market_history.py` для:
- trade OHLCV H1 через `/v5/market/kline`;
- mark-price H1 через `/v5/market/mark-price-kline`;
- funding settlements через `/v5/market/funding/history`.

Также есть collectors dated instrument specifications и risk-limit tiers. Их offline tests подтверждают обработку ответов, но это не равно наличию реального архива. В журнале указаны HTTP 403 на публичных Bybit endpoints из GitHub Actions, и текущий tree не содержит полученных Bybit snapshots. Обход региональных ограничений не предпринимался.

Следовательно, E01–E13 остаются Binance OHLCV proxy experiments. Funding в этих результатах не подтверждён; mark-price liquidation, точные instrument specs, maintenance tiers и exchange-valid contract quantity не представлены.

## 6. Статус старых PnL

Все исторические net PnL, полученные через v14 `_close_position()` до исправления exit fee/slippage notional basis, помечены в журнале как provisional. Ошибка расчёта exit costs была исправлена позднее, но E01–E13 не пересчитаны на исправленном коде. Даже после пересчёта Binance OHLCV proxy и optimistic OHLC limit fills не станут Bybit execution replay.

Старый результат CryptoFetch (14/50 H1 symbols positive; 0/8 15m positive) — только исторический screening snapshot. Число 14/50 и список символов нельзя использовать как актуальный рейтинг кандидатов до повторного расчёта на исправленном движке и общего капитала.

## 7. Что необходимо для честного point-in-time validation

До следующего рыночного PnL replay:
1. Получить разрешённым способом исторический список Bybit linear instruments с датами листинга/делистинга или другой проверяемый point-in-time universe source.
2. Для каждого timestamp формировать universe только из инструментов, которые были доступны на эту дату; сохранять и исключённые инструменты с точной причиной отсутствия.
3. Сохранить immutable manifest: источник, archive filename, SHA-256, symbol, timeframe, first/last timestamp, count, duplicate count, missing intervals, schema version.
4. Не выбирать между дублирующими архивами только по максимальному числу строк без объяснения различий; сравнивать overlapping rows и фиксировать правило разрешения конфликтов.
5. Получить Bybit-native trade OHLCV, mark-price candles, funding settlements и dated instrument/risk-tier snapshots с полным coverage.
6. Только после этого интегрировать exact exchange quantity, fees/funding, spread/slippage and margin/liquidation assumptions.
7. Отделить universe selection period от validation period; сохранить будущий untouched holdout, который не участвует ни в выборе символов, ни в настройке стратегии.

## Решение

- Не запускать новые market backtests и parameter sweeps на текущих данных.
- Не продвигать E13 compression gate и старый top-symbol shortlist.
- Сохранить E01–E13 как исторические диагностические результаты с ограничениями.
- Следующий безопасный этап — point-in-time universe/data provenance; если источник исторических Bybit listings недоступен, это остаётся явным blocker, а не поводом подменять его сегодняшним списком инструментов.
