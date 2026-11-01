# Сравнение исследовательских веток: funding, data adapter, v15

Дата: 2026-11-02  
Базовая ветка: `research/market-regime-v1-main`  
Сравниваемые ветки: `research/bybit-funding-data-v1`, `research/data-adapter-v1`, `research/v15-donchian-signal`.

## 1. Сводка

| Ветка | Найдено полезного | Статус интеграции |
|---|---|---|
| `research/bybit-funding-data-v1` | Bybit funding downloader, mark-price downloader, funding cashflow в engine, тесты загрузчиков и PnL | НЕ интегрировано в текущую ветку; engine существенно расходится |
| `research/data-adapter-v1` | Адаптер Bybit klines с проверкой interval, общей временной сетки и пропусков | НЕ интегрировано; безопасный кандидат на перенос после тестов |
| `research/v15-donchian-signal` | Изолированный signal module, H1 backtester, portfolio replay и регрессионные тесты | НЕ интегрировано; отдельная экспериментальная реализация |

Ветки не являются последовательными чистыми патчами: GitHub compare показывает diverged history. Снимок GitHub Compare на 2026-11-02 после обновления навигации `main` относительно `main`:

| Ветка | Ahead | Behind | Статус |
|---|---:|---:|---|
| `Audit` | 0 | 2 | behind |
| `research/bybit-funding-data-v1` | 27 | 3 | diverged |
| `research/data-adapter-v1` | 11 | 3 | diverged |
| `research/market-regime-v1-main` | 171 | 3 | diverged |
| `research/market-regime-v1` | 30 | 3 | diverged |
| `research/v15-donchian-signal` | 59 | 4 | diverged |

`main` — default branch, но не содержит актуальный исследовательский слой. `research/market-regime-v1-main` — текущая рабочая ветка с документацией, аудитом и основной серией экспериментов. `Audit` почти совпадает с `main` и не содержит отдельной исследовательской ценности, подтверждённой этим сравнением.

**Важно:** counts — число коммитов в сравнении с текущим `main`, а не оценка качества или количества уникального кода. Ветки расходятся по истории и имеют общий базис не на одном уровне; merge всей ветки или копирование engine целиком небезопасны. До завершения инвентаризации не удалять ветки и не переписывать историю. Полезные модули переносить только как изолированные патчи с тестами и сохранением исходной ветки.

## 2. Funding branch — полезное, но не production-ready доказательство

### Что реализовано
- `bybit_funding_downloader.py`: публичный Bybit V5 funding history, пагинация, сортировка, дедупликация, проверка символа и ставки.
- `bybit_mark_price_downloader.py`: загрузка исторических mark-price klines, по умолчанию 1h.
- В engine добавлены `--funding-dir` и `--mark-price-dir`, funding cashflow включается в net PnL и portfolio total costs.
- Funding cashflow: positive rate — long платит, short получает; после TP1 учитывается остаточная доля позиции.
- Missing funding file / missing exact mark timestamp приводит к явной ошибке, а не к молчаливому нулю.

### Ограничения и открытые вопросы
1. Funding интеграция существует только в отдельной ветке. Все текущие E01–E09 и holdout результаты текущей ветки не являются funding-adjusted, если конкретный runner явно не использовал эту ветку и оба каталога данных.
2. Mark downloader использует 1h mark candle open на timestamp settlement. Это proxy цены, а не точный mark-price tick на момент начисления. Для точности нужны минутные/тик-данные либо подтверждённая семантика Bybit endpoint.
3. В engine предусмотрен fallback на open/close обычных traded-price свечей, если `--funding-dir` включён без `--mark-price-dir`. Комментарий предупреждает, что это не mark price, но пользователь может случайно получить приближённый funding расчёт. Для официального funding-adjusted research лучше сделать mark-price directory обязательным.
4. Funding tests используют синтетические фикстуры и проверяют формулы/границы, но не доказывают точность скачанных реальных mark prices или API pagination на полном периоде.
5. Нужно проверить funding timestamp semantics: settlement event включается при `entry_ts < ts <= exit_ts`; это разумно, но требует согласования с фактическим моментом входа/выхода и timestamp свечей.
6. Engine funding branch отличается от текущего engine не только funding: в diff присутствуют другие изменения trade lifecycle / data / cost logic. Не переносить файл движка целиком.

**Вывод:** сохранить загрузчики и тесты как самостоятельную полезную наработку; перед интеграцией добавить точный mark-price validation и обязательный data provenance manifest.

## 3. Data adapter branch — наиболее прямое исправление P1

### Что реализовано
- `scripts/adapt_bybit_klines.py` читает Bybit kline CSV.
- Проверяет positive integer timestamp, OHLCV, дубликаты и ожидаемый шаг интервала.
- Пересекает временные ряды символов и отказывается создавать общий dataset при пропусках.
- `test_data_adapter.py` содержит тесты конвертации/выравнивания, gap и duplicate timestamp.
- Отдельный `prepare_backtest_data.py` проверяет irregular intervals и данные до преобразования.

### Ограничения
- Это проверка ожидаемого шага в адаптере, но текущий engine сам по себе всё ещё не получает метаданные timeframe и не гарантирует, что arbitrary CSV соответствует cfg.timeframe.
- Пересечение общих timestamps может обрезать начало/конец отдельных символов. Это допустимо для синхронного portfolio run, но должно быть отражено в manifest.
- Перед переносом нужно проверить формат downloader, timezone, inclusive/exclusive границы и совместимость имени столбцов.

**Вывод:** адаптер — кандидат P1 на точечный перенос после копирования тестов и проверки входного формата. Он не заменяет проверку timeframe внутри engine.

## 4. V15 branch — изолированный прототип, не замена v14

### Что реализовано
- `research_v15/donchian_signal.py`: Donchian breakout по предыдущим свечам, EMA trend filter, валидация OHLC.
- `research_v15/backtest.py`: H1 backtester, ATR, maker limit, stops/targets, breakeven, sizing, costs, mark-to-market.
- `research_v15/portfolio.py`: portfolio risk capacity helper.
- `research_v15/portfolio_replay.py`: хронологический replay отдельных symbol trades с общим equity и лимитом риска.
- Тесты сигналов, исполнения, комиссий, sizing, equity и portfolio reconciliation.

### Существенные ограничения, прямо признанные кодом
- `backtest.py` указывает, что funding не моделируется.
- `portfolio_replay.py` прямо говорит, что не пересчитывает сигналы после отклонённых входов, не моделирует portfolio mark-to-market и funding.
- Portfolio replay накладывает общий капитал на уже сформированный список per-symbol сделок. Это диагностический overlay, а не полноценная shared-capital симуляция.
- OHLC limit touch остаётся упрощённой моделью исполнения.
- Binance OHLCV proxy, не Bybit execution data.

### Что нельзя заключить
- Наличие тестов не доказывает положительное expectancy.
- Успешная изолированная per-symbol симуляция не гарантирует прибыльность при общем капитале.
- Положительный результат одного H1 runner не является независимым подтверждением v14/E07/E09.

**Вывод:** v15 полезен как независимая контрольная реализация отдельных механик и тестов. Не объединять с v14 до сопоставления правил входа/выхода и исполнения.

## 5. Предлагаемая последовательность безопасной интеграции
1. Не сливать ветки целиком.
2. Сначала перенести/адаптировать timeframe validator из data-adapter как маленький отдельный патч с тестами.
3. Затем перенести funding downloader + mark downloader без engine changes, добавить manifest и тесты пагинации/диапазона.
4. Отдельным изменением интегрировать funding в engine, требуя точные mark data; сравнить funding cashflow с ручным расчётом на fixtures.
5. V15 оставить изолированным reference implementation; сделать таблицу соответствия v14/v15 механик, не объединять код.
6. Только после code audit и test validation разрешить исторические replays с теми же датасетами/параметрами. Это будет проверка корректности, а не новая оптимизация.

## 6. Приоритет
- P1: timeframe mismatch guard в v14.
- P1: funding data integrity / mark price exactness before funding-adjusted results.
- P1: full portfolio simulator vs v15 replay overlay.
- P2: v14/v15 signal, fill, stop, TP, fee and sizing parity.
- P2: unify data adapters only after provenance and path checks.


## Дополнение: полезные компоненты из расходящихся веток (2026-11-02)

### `research/bybit-funding-data-v1`
- Добавлены `bybit_funding_downloader.py`, `bybit_mark_price_downloader.py`, `prepare_backtest_data.py` и тесты, включая `test_funding_pnl.py` (10 тестов).
- В этой ветке есть интеграция funding cashflows в PnL, строгий отказ при отсутствующих funding/mark rows и временная семантика TP1 для settlement.
- **Не переносить engine целиком:** ветка содержит старую копию движка. Переносить funding как отдельный патч после проверки на актуальном engine. Mark candle open на settlement timestamp — proxy, не tick-level settlement mark; fallback к traded-price OHLC ещё слабее.

### `research/data-adapter-v1`
- Содержит адаптер Bybit klines → engine CSV, поиск linear universe и per-symbol backtest/report scripts.
- `prepare_backtest_data.py` из funding-ветки и `scripts/adapt_bybit_klines.py` выполняют близкую роль; выбрать один канонический адаптер после тестов, не держать два расходящихся формата.
- Адаптер проверяет формат/интервалы и не заполняет пропуски. Это полезная основа для reproducible Bybit data pipeline.

### `research/v15-donchian-signal`
- Отдельный `research_v15/` модуль содержит pure backtest, portfolio replay и тесты для limit expiry, stop/target, breakeven, economics и risk sizing.
- Это независимая исследовательская реализация, не drop-in replacement v14. Использовать для cross-check execution semantics и portfolio replay, сохраняя обе модели отдельно.
- У v15 есть явная функция expiry многобарной лимитки; в v14 pending entry сейчас одно-свечный. Сравнение TTL должно быть отдельным экспериментом, а не молчаливым изменением.

### Обновлённый GitHub Compare snapshot (относительно `main`)
| Ветка | Ahead | Behind | Статус |
|---|---:|---:|---|
| `Audit` | 0 | 2 | behind |
| `research/bybit-funding-data-v1` | 27 | 3 | diverged |
| `research/data-adapter-v1` | 11 | 3 | diverged |
| `research/market-regime-v1-main` | 181 | 3 | diverged |
| `research/market-regime-v1` | 30 | 3 | diverged |
| `research/v15-donchian-signal` | 59 | 4 | diverged |

Counts обновляются при каждом коммите в `main` или исследовательских ветках; это навигационный снимок, не оценка качества.


### Дополнительный finding по funding-патчу (не интегрирован)

В `research/bybit-funding-data-v1` funding вычитается из net PnL при закрытии позиции, но `_unrealized_pnl_at_marks()` не включает уже начисленный funding для открытых позиций. Следовательно, daily stop / kill-switch mark-to-market в этой ветке могут недооценивать текущую просадку до закрытия сделки. Это подтверждённый пробел риск-учёта в funding-ветке, а не в активной ветке (там funding пока отсутствует полностью). Перед переносом funding-патча нужно вынести расчёт accrued funding в единый helper и использовать его и в открытом equity mark, и при финальном PnL, исключив двойной учёт. Также сверить funding расчёт с текущей maker-exit конфигурацией активной ветки: funding-ветка старше и имеет отличающуюся структуру исполнения.


### Повторная проверка v15: multi-bar limit TTL реализован, но end-to-end теста нет

Повторно проверена фактическая вложенность в `research_v15/backtest.py`: `pending = None` находится внутри ветки `if entry > 0`, а не выполняется после неудачного касания. При `entry is None` заявка остаётся pending; на следующих барах возраст проверяется через `limit_order_expired(age, limit_valid_bars)`. Следовательно, предыдущий вывод о безусловном удалении заявки после первой свечи был ошибочным и отозван.

Остаётся более узкий пробел покрытия: тесты проверяют helper `limit_order_expired()` и limit fill отдельно, но не проверяют end-to-end, что `backtest_symbol()` удерживает заявку несколько баров и истекает ровно после N допустимых свечей. Это не подтверждённый дефект реализации; добавить интеграционный тест для фиксации фактической семантики TTL.
