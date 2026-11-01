# Bybit Trading Bot — research repository

Private repository for strategy research, historical backtests, data tooling, regression checks and reports.

## Start here

- [Agent/developer instructions](AGENTS.md)
- [Project working rules](PROJECT_WORKING_RULES_RU.md)
- [Documentation index](docs/README_RU.md)
- [Repository map](docs/REPOSITORY_MAP_RU.md)
- [Technical audit](docs/audits/PROJECT_AUDIT_RU.md)
- [Experiment ledger](docs/research/EXPERIMENT_LEDGER_RU.md)
- [Coverage matrix](docs/research/TEST_COVERAGE_MATRIX_RU.md)
- [Next research plan](docs/research/NEXT_RESEARCH_PLAN_RU.md)

## Safety and interpretation

- `Bybit_Trading_Engine_v14_research.py` is a research simulator, not a live order executor.
- Historical CryptoFetch archives contain Binance OHLCV; these are market-data proxies, not Bybit execution replay.
- OHLC limit-touch fills are optimistic without queue, spread, partial-fill and adverse-selection modelling.
- Never add live API keys, place real orders, or enable live trading as part of research.
- Preserve raw datasets, holdout data, experiment outputs and historical reports.

## Repository layout

```text
.github/workflows/       technical CI and manual research workflows
data/archives/           immutable source datasets
dashboards/v15/          dashboard exports and instructions
docs/audits/             technical and branch audits
docs/reports/            historical backtest and diagnostic reports
docs/research/           experiment ledger, coverage matrix and next plan
research/config/         research universe/configuration data
scripts/                 experiment runners and utilities
tests/                   deterministic regression tests
root                     engine, downloader, agent rules and README
```

The engine and downloader remain at repository root because existing runners import them directly.

## Environment

Python 3.11 is used in CI. The downloader requires `requests`.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install requests
```

Never commit `.env`; the research engine does not require real exchange credentials.

## Tests

Run deterministic checks individually:

```bash
python tests/test_gap_execution.py
python tests/test_time_model.py
python tests/test_funding_accounting.py
python tests/test_bybit_instrument_specs.py
python scripts/scan_secrets.py .
```

The technical workflow does not run market backtests. Market experiments remain separate, manually dispatched workflows and require a ledger entry and explicit data/method review.

Read [AGENTS.md](AGENTS.md) before changing code. A successful technical CI run is not evidence of strategy profitability.
