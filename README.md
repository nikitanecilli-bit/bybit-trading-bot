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

## Real-data adapter (research/data-adapter-v1)

The downloader and engine use different CSV schemas. Convert downloader kline files before running the engine:

```bash
python bybit_downloader.py --symbols BTCUSDT ETHUSDT SOLUSDT --intervals 15 --datasets kline --category linear --start 2023-01-01 --out data
python -m unittest test_data_adapter.py
python scripts/adapt_bybit_klines.py --symbols BTCUSDT ETHUSDT SOLUSDT --category linear --interval 15 --input-dir data --output-dir engine_data
```

Then set `active_trading_pool` in a research config to exactly the same symbols and run:

```bash
python Bybit_Trading_Engine_v14_research.py --mode backtest --config path/to/research_config.json --data-dir engine_data --journal research_journal.json
```

The adapter deliberately fails on duplicate candles, invalid OHLCV, missing/irregular bars, or fewer than two common timestamps. It writes all selected symbols on the exact common timestamp intersection because the engine requires aligned bars. This may shorten the usable period to the overlap between listings; check the printed excluded-bar counts before interpreting results.

**Research caveat:** this is only the format/validation bridge. It does not yet provide an unbiased historical universe (current symbols can create survivorship bias), nor does the engine currently consume the downloaded funding-history CSVs. Do not describe this pass as funding-adjusted or as a complete survivorship-bias audit. Validate fees/slippage settings and add funding accounting before treating the result as a realistic net return.

