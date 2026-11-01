# Карта репозитория

| Путь | Назначение |
|---|---|
| `.github/workflows/` | Технический CI и вручную запускаемые research workflows |
| `data/archives/cryptofetch/` | Шесть исходных ZIP-архивов CryptoFetch; immutable |
| `dashboards/v15/` | HTML/PDF экспорт дашборда v15 и инструкция |
| `docs/audits/` | Технический аудит, сравнение веток, audit findings |
| `docs/reports/` | Исторические backtest, holdout и regime отчёты |
| `docs/research/` | Experiment ledger, coverage matrix, следующий план |
| `research/config/` | Конфигурационные данные исследовательского universe |
| `scripts/` | Backtest runners, диагностика, сбор данных и утилиты |
| `tests/` | 16 детерминированных регрессионных тестов |
| корень | Исследовательский движок, downloader, README и инструкции |

## Важные границы

- `Bybit_Trading_Engine_v14_research.py` остаётся в корне: скрипты импортируют его напрямую.
- ZIP-архивы перемещены без изменения содержимого; runner читает только `data/archives/cryptofetch/`.
- Все 16 тестов находятся в `tests/`; тесты, загружающие движок через `__file__`, используют путь на уровень выше.
- Market backtests не входят в технический CI и не запускаются по push.
- Данные Binance OHLCV являются proxy; fills по касанию OHLC не моделируют очередь и partial fills.
- Не сливать ветки автоматически: main и исследовательская линия имеют независимую историю и разные версии движка.
