# OKX public market-data pilot — runbook

## Purpose

This is a bounded, read-only data-source pilot for `BTC-USDT-SWAP`. It downloads public H1 trade candles, H1 mark-price candles, funding history, and one current instrument-specification response. It does not call account/private endpoints, place orders, run a strategy, or calculate PnL.

The downloader is deliberately restricted to one instrument and the official `https://www.okx.com` host. It does not use proxies, mirrors, API keys, or alternate domains. If direct access fails from the machine running it, stop and report the error; do not try to route around regional/network restrictions.

## Run once

From the repository root, with Python 3.11+ and no third-party packages:

```bash
python scripts/okx_public_data_archive.py --days 365
```

This downloads the latest 365 complete UTC days (H1 boundaries) into:

```text
data/archives/okx/BTC-USDT-SWAP/
```

To select an exact range, use timezone-aware UTC hour boundaries; `--end` is exclusive:

```bash
python scripts/okx_public_data_archive.py \
  --start 2026-10-01T00:00:00Z \
  --end 2026-11-01T00:00:00Z
```

The output directory must be empty or absent. The script refuses to overwrite prior captures. Use a new output directory for a separate capture, for example `--output data/archives/okx/BTC-USDT-SWAP-2026-11-25`.

## Outputs

- `candles_h1.csv`: last-trade OHLCV candles, with the exchange `confirm` flag.
- `mark_price_h1.csv`: mark-price OHLC candles. These are reference/valuation prices, not executable fills.
- `funding_history.csv`: funding timestamps, rates, and formula metadata exactly as returned. **OKX documents this endpoint as covering up to three months**, so a 365-day OHLCV request will not imply 365 days of funding history. The manifest records the oldest raw funding event and whether pagination reached the requested start.
- `instrument_current.json`: current contract metadata only; it is not a historical specification archive.
- `raw/`: exact response bodies for every API page.
- `manifest.json`: requested range, exact request URLs, capture times, row counts, SHA-256 hashes, hourly-grid checks, and limitations.

Exit code `0` means both H1 series have complete hourly timestamp coverage and no unfinished candles in the requested interval. Exit code `2` means the archive was saved but hourly coverage is incomplete or contains unfinished candles. Exit code `1` means collection failed; any partial raw responses and a failure manifest are retained.

## What this does not prove

- A complete H1 grid does not prove that every historical contract rule, fee tier, risk tier, or funding formula regime has been reconstructed.
- Funding history endpoint retention is documented as up to three months. Older funding data may therefore be unavailable from this endpoint even when H1 candles/mark history extend further.
- Funding rows are not assumed to occur every eight hours. The received events are preserved; expected settlement completeness requires a separate schedule/effective-time audit.
- The instrument endpoint is current-state metadata. Historical tick size, lot size, contract value, lifecycle, and risk tiers remain separate acceptance gates.
- A successful download is data-source evidence, not a trading edge or permission to run a backtest. Do not start market-PnL work until the existing research authorization and data/provenance gates are explicitly reviewed.

## API references

- OKX official API guide: history candles and pagination, maximum 100 records per page; `after` returns older records and excludes the cursor timestamp.
- `GET /api/v5/market/history-mark-price-candles`
- `GET /api/v5/public/funding-rate-history`
- `GET /api/v5/public/instruments`
