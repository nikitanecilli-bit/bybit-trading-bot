# Bybit H1 timestamp alignment audit

Date: 2026-11-25  
Branch: research/h1-volume-lookback-provenance-fix

## Finding

The public.bybit.com/kline_for_metatrader4 BTCUSDT H1 archive uses candle timestamps that are consistently 3 hours later than UTC trade timestamps in the sampled history.

This was detected by matching the sum of Bybit public linear trade sizes per UTC hour to the H1 candle volume. The comparison used 12 daily samples spanning 2020-04-01 through 2025-11-02, including both April and December/November samples to check for a seasonal offset.

Pre-normalization alignment result:
- Best candle timestamp offset relative to UTC trade hour: +3 hours.
- Matched hourly buckets: 288.
- Median absolute volume difference: 0%.
- 95th percentile absolute volume difference: 0.30278938%.
- Maximum absolute volume difference: 3.12529891%.

The +3 hour offset remained the best match across the pooled summer and winter sample. The small number of outlier hours require separate investigation; they do not alter the clear timestamp alignment result.

## Code correction

scripts/download_bybit_btcusdt_public_history.py now converts source timestamps to UTC by subtracting 3 hours before filtering and writing the H1 CSV. The manifest explicitly records:
- source_timestamp_offset_hours: 3
- normalized_timestamp_timezone: UTC
- the evidence basis for the conversion.

All H1-based research workflows are being rerun from the corrected normalized dataset. The chronological bar sequence and price/volume values are not changed; UTC labels and calendar-window selection are corrected. Any previously published calendar timestamps should be treated as provisional until the corrected runs are complete.

## Trade archive schema change: RPI

The sampled 2025-11-02 public trade archive contains an RPI column; the sampled earlier daily files did not. RPI executions must be tracked separately from visible-book order flow because Bybit's public orderbook API does not expose RPI liquidity.

scripts/validate_bybit_public_trade_archive.py now:
- keeps all trade volume for reconciliation against H1 volume;
- separately calculates RPI volume/count when the archive provides the flag;
- exposes non-RPI delta separately;
- reports per-day timestamp alignment, so a seasonal offset cannot be hidden by a pooled result.

Absence of an RPI column is recorded as missing metadata, not interpreted as proof that no RPI activity occurred.

## Reproduction

- Cross-season alignment run: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45670947701
- Normalized H1 and trade revalidation: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45671262874
- Updated loader: scripts/download_bybit_btcusdt_public_history.py
- Validation script: scripts/validate_bybit_public_trade_archive.py

## Consequence for strategy research

Do not use the old raw MT4 archive timestamps as UTC. Use only the normalized loader output. Re-run any analysis that joins candles to trades, book updates, funding, or fixed calendar windows. Index-based OHLCV return statistics are expected to be largely unchanged, but their reported UTC boundaries and any time-of-day/session analysis require corrected data.


## Post-correction revalidation

The corrected loader was then re-run against the same 12 daily trade samples:
- Best alignment after normalization: 0 hours.
- Matched hourly buckets: 288.
- Median absolute volume difference: 0%.
- p95 absolute difference: 0.30278938%.
- Maximum absolute difference: 3.12529891%.
- Per-day best alignment: 0 hours on all 12 dates, including December samples.

This confirms the loader now writes timestamps on the UTC clock and does not need a seasonal timezone rule.

The 2025-11-02 sample includes an RPI column. No rows in the sampled file were marked as RPI by the parser. Older sampled files do not contain that column, so absence of the flag is treated as unavailable metadata, not as evidence of zero RPI activity.
