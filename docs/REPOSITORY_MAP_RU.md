# Карта репозитория

| Путь | Назначение |
|---|---|
| `.github/workflows/` | Технический CI и вручную запускаемые research workflows |
| `data/archives/cryptofetch/` | Шесть исходных ZIP-архивов CryptoFetch; immutable |
| `dashboards/v15/` | HTML/PDF экспорт дашборда v15 и инструкция |
| `docs/audits/` | Технический аудит, сравнение веток, audit findings |
| `docs/reports/` | Исторические backtest, holdout и regime отчёты |
| `docs/research/` | Research Board, Project Compass, Experiment Ledger, coverage matrix, hypotheses and plans |
| `research/config/` | Конфигурационные данные исследовательского universe |
| `scripts/` | Backtest runners, диагностика, сбор данных и утилиты |
| `tests/` | Детерминированные regression tests и отдельные H-B synthetic mechanics suites |
| `h_b_signal.py` | Изолированный H-B signal predicate; без engine integration |
| `h_b_regime.py` | Frozen candidate RegimeConfig + causal H1 cadence gate |
| `h_b_fill.py` | Offline t+2 open geometry check; не execution simulator |
| корень | Исследовательский движок, downloader, README и инструкции |

## Важные границы

- `Bybit_Trading_Engine_v14_research.py` остаётся в корне: скрипты импортируют его напрямую.
- ZIP-архивы перемещены без изменения содержимого; runner читает только `data/archives/cryptofetch/`.
- Автоматические проверки находятся в `tests/`; H-B signal/regime/fill tests являются отдельными synthetic-only suites.
- `h_b_signal.py`, `h_b_regime.py` и `h_b_fill.py` не подключены к торговому движку и не размещают ордера.
- Market backtests не входят в технический CI и не запускаются по push.
- Данные Binance OHLCV являются proxy; fills по касанию OHLC не моделируют очередь и partial fills.
- Не сливать ветки автоматически: main и исследовательская линия имеют независимую историю и разные версии движка.

## Новые research workflows и runners

| Workflow | Runner | Назначение |
|---|---|---|
| `e10-h1-body-gate-replication.yml` | `run_e10_h1_body_gate_replication.py` | Per-symbol body gate OFF/2% на 47 H1 инструментах |
| `e11-h1-shared-capital-replay.yml` | `run_e11_h1_shared_capital_replay.py` | Shared-capital portfolio replay, 47 symbols, max 5 positions |
| `e12-h1-market-context-diagnostics.yml` | `run_e12_h1_market_context_diagnostics.py` | Causal broad-market context snapshot; без симуляции |
| `e13-h1-compression-gate-replay.yml` | `run_e13_h1_compression_gate_replay.py` | Shared-capital replay с frozen expanding-q25 compression gate |

Подробные результаты E09–E13 находятся в `docs/reports/`; решения и ограничения — в `docs/research/EXPERIMENT_LEDGER_RU.md` и `NEXT_RESEARCH_PLAN_RU.md`.

