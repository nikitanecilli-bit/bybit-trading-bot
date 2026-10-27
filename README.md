# Bybit Trading Bot — research repository

Private repository for the existing Bybit strategy research/backtest engine, tests, market-data downloader, and research reports.

## Important status

- `Bybit_Trading_Engine_v14_research.py` is a **research/backtest simulator**, not a live order execution bot. Its source header states that it has no Bybit order connection.
- Synthetic-candle results do not establish a profitable trading edge. Use validated historical data and include fees, slippage, funding, and realistic execution assumptions.
- Real-money trading is not enabled by this repository scaffold. Do not connect real API keys or enable live trading as part of setup.

## Files

- `Bybit_Trading_Engine_v14_research.py` — current research engine.
- `bybit_downloader.py` — public market-data downloader; its documented workflow does not require API keys.
- `test_time_model.py`, `test_gap_execution.py` — focused regression tests.
- Research and audit notes are stored in Markdown report files.

Older duplicate engine versions, archives, raw market-data dumps, local state, logs, and credential files are intentionally not included in this initial import. They can be added later after their role and contents are reviewed.

## Environment setup

Python 3.10+ is recommended. The research engine primarily uses the Python standard library. The downloader requires `requests`:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
python -m pip install requests
```

The current research engine does not read the example environment variables. Never commit `.env`.

## Tests

Run the focused regression scripts:

```bash
python test_gap_execution.py
python test_time_model.py
```

If a test fails, record the traceback and investigate before relying on the affected behavior.

## Secret checks before commits

```bash
git status --short
git check-ignore -v .env
python scripts/scan_secrets.py .
```

The scanner is heuristic and is not a guarantee. Review staged changes manually before every push.

## Safe workflow

1. Keep this repository private.
2. Review every file in a proposed commit.
3. Do not use `git add .` without checking `git status`.
4. Never commit real API keys, tokens, passwords, private keys, live journals, runtime state, or raw personal data.
5. If a credential was ever pushed, revoke/rotate it first; `.gitignore` does not erase Git history.
