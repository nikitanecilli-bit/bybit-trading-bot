# Bybit Trading Bot — research repository

Private repository for strategy research, historical backtests, data tooling, regression checks and reports.

## Start here

- **[Agent/developer instructions](AGENTS.md)** — mandatory rules before changing code or running workflows.
- **[Project working rules](PROJECT_WORKING_RULES_RU.md)** — autonomy, safety and research standards.
- **[Documentation index](docs/README_RU.md)** — repository navigation.
- **[Repository map](docs/REPOSITORY_MAP_RU.md)** — purpose of directories and key files.
- **[Technical audit](PROJECT_AUDIT_RU.md)** — audit status and confirmed limitations.
- **[Experiment registry](EXPERIMENT_LEDGER_RU.md)** — historical experiment record.
- **[Coverage matrix](TEST_COVERAGE_MATRIX_RU.md)** — tested, partial and unverified areas.
- **[Next research plan](NEXT_RESEARCH_PLAN_RU.md)** — audit-first plan; no duplicate experiments.

## Important status

- `Bybit_Trading_Engine_v14_research.py` is a research/backtest simulator, not a live order execution bot. Its source header states that it has no Bybit order connection.
- Several historical experiments used Binance OHLCV as a proxy; they do not prove Bybit execution profitability.
- OHLC limit-touch fills are optimistic unless queue position, spread, partial fills and adverse selection are modelled.
- Real-money trading is not enabled by this research scaffold. Never connect live API keys or enable live trading as part of research setup.

## Main components

- `Bybit_Trading_Engine_v14_research.py` — research engine.
- `bybit_downloader.py` — public market-data downloader.
- `scripts/` — experiment runners, diagnostics and utilities.
- `.github/workflows/` — reproducible CI/research workflows.
- `test_*.py` — existing regression tests (currently in repository root).
- `cryptofetch_*.zip` — archived datasets; do not overwrite or delete.
- Markdown reports and dashboard exports — historical documentation/artifacts.

Files are intentionally not being moved during the audit: workflow paths, imports and historical references must be checked first.

## Environment setup

Python 3.10+ is recommended. The research engine primarily uses the standard library. The downloader requires `requests`.

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
python -m pip install requests
```

Never commit `.env`. The current research engine does not need real exchange credentials.

## Tests

```bash
python test_gap_execution.py
python test_time_model.py
python scripts/scan_secrets.py .
```

Read [AGENTS.md](AGENTS.md) before editing. Review staged changes manually; do not blindly run `git add .`. A successful workflow is not proof of a profitable strategy.
