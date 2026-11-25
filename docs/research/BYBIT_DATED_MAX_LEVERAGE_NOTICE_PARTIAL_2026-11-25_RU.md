# Bybit Dated Maximum-Leverage Notice — Partial Extraction

**Review date:** 2026-11-25  
**Official article:** https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-aug-20-2026--artd5e4344ee603/  
**Published:** `2026-08-18T15:12:52Z`  
**Effective:** `2026-08-20T08:00:00Z` (announcement wording: takes effect at 8AM UTC)  
**Captured raw article SHA-256:** `21e66fac4807297fb2c89ba79d491705882425a7343dcad3c8a8698c953e0a0d`

## Extracted rows

The official article contains a table headed “Symbol / Current Maximum Leverage / Maximum Leverage After Adjustment”. The following 19 rows intersect the 47-symbol research proxy universe.

| Symbol | Previous maximum leverage | New maximum leverage |
|---|---:|---:|
| BTCUSDT | 100x | 150x |
| ETHUSDT | 100x | 150x |
| BNBUSDT | 50x | 75x |
| AVAXUSDT | 50x | 75x |
| LINKUSDT | 50x | 75x |
| XLMUSDT | 50x | 75x |
| LTCUSDT | 50x | 75x |
| NEARUSDT | 50x | 75x |
| BCHUSDT | 50x | 75x |
| DOTUSDT | 50x | 75x |
| UNIUSDT | 50x | 75x |
| ETCUSDT | 50x | 75x |
| HBARUSDT | 50x | 75x |
| ZECUSDT | 50x | 75x |
| DASHUSDT | 50x | 75x |
| ICPUSDT | 50x | 75x |
| ALGOUSDT | 50x | 75x |
| QNTUSDT | 25x | 75x |
| JSTUSDT | 25x | 75x |

## Interpretation

This is an official, dated **maximum leverage** notice. It is not a full risk-limit tier schedule:
- it does not provide maintenance-margin rates by notional tier;
- it does not provide risk-limit values / notional thresholds for each tier;
- it does not establish historical account-specific leverage availability;
- it must not be used to infer liquidation prices or maintenance margin without the corresponding tier ladder.

The notice is useful as a dated maximum-leverage constraint and a pointer to the separate margin-parameters source. The raw body is retained in the workflow artifact, so the hash above identifies the exact captured source.

**Gate:** D6 remains **NOT ACCEPTED**. This extraction adds one dated maximum-leverage event, not complete historical risk tiers.
