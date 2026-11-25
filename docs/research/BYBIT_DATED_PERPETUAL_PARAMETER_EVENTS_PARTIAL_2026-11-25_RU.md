> **Superseded:** This was the initial partial extraction. The expanded review found additional official notices and more symbol/event rows. Use [BYBIT_DATED_PERPETUAL_PARAMETER_EVENTS_EXPANDED_PARTIAL_2026-11-25_RU.md](BYBIT_DATED_PERPETUAL_PARAMETER_EVENTS_EXPANDED_PARTIAL_2026-11-25_RU.md) as the current broader inventory. This document remains as an audit trail for the first extraction; its D5 NOT ACCEPTED decision still applies.

# Bybit Dated Perpetual Parameter Events — Partial Manual Extraction

**Date of review:** 2026-11-25  
**Source artifact:** `bybit-public-announcement-inventory`, workflow [45586354775](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45586354775)  
**Review method:** manually inspected structured article body text from the captured official HTML; raw body SHA-256 retained below.  
**Status:** partial source-backed extraction; **D5 remains NOT ACCEPTED**.

## 1. Tick-size changes

All values below are copied from official announcement tables. Values are decimal price increments, not price precision guesses.

### Effective 2026-08-11 08:30 UTC

Published: `2026-08-06T10:36:56Z`  
Official source: https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-aug-11-2026--art4f47b6648755/  
Captured body SHA-256: `5ec21a6cad43af5b75a78b68928656d169a80d778eefd3feaa36021ae47bfbce`

| Symbol | Old tick size | New tick size |
|---|---:|---:|
| ATOMUSDT | 0.0001 | 0.001 |
| CAKEUSDT | 0.0001 | 0.001 |
| MORPHOUSDT | 0.0001 | 0.001 |
| NEARUSDT | 0.0001 | 0.001 |
| RENDERUSDT | 0.0001 | 0.001 |
| TRXUSDT | 0.00001 | 0.0001 |
| XLMUSDT | 0.00001 | 0.0001 |

The announcement says the adjustment is effective by 08:30 UTC and that existing orders remain in the book with their original tick size.

### Effective 2026-10-12 07:30 UTC

Published: `2026-10-08T03:09:14Z`  
Official source: https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-oct-12-2026--art5c4a8b8eef37/  
Captured body SHA-256: `7783748c07f10d7bd9a7e07ce927ed74c5e7b1f52445066bcfe7feaf2f58c592`

| Symbol | Old tick size | New tick size |
|---|---:|---:|
| BCHUSDT | 0.1 | 0.01 |
| BNBUSDT | 0.1 | 0.01 |
| PAXGUSDT | 0.1 | 0.01 |
| CAKEUSDT | 0.001 | 0.0001 |
| MORPHOUSDT | 0.001 | 0.0001 |

The announcement says the adjustment is effective by 07:30 UTC and that existing orders remain in the book with their original tick size.

## 2. Maximum order-size changes

These are maximum market/limit order quantities in coins. They are not lot-size/qty-step values and must not be substituted for min order quantity, qty step, notional limits, or risk tiers.

### Effective 2026-10-13 07:30 UTC

Published: `2026-10-12T07:04:46Z`  
Official source: https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-oct-13-2026--art0d130e93d1dc/  
Captured body SHA-256: `1e7111c8de041b6aa6ae282d0f8f23c822ae2c4a5fdae56f61612fec97b34f33`

| Symbol | Market max before | Market max after | Limit max before | Limit max after |
|---|---:|---:|---:|---:|
| SUIUSDT | 66,000 | 290,000 | 330,000 | 1,160,000 |
| ADAUSDT | 590,000 | 1,480,000 | 1,500,000 | 5,920,000 |
| ENAUSDT | 700,000 | 1,290,000 | 3,500,000 | 5,160,000 |
| UNIUSDT | 11,000 | 15,600 | 32,000 | 62,400 |
| XLMUSDT | 260,000 | 980,000 | 730,000 | 3,920,000 |
| AAVEUSDT | 460 | 1,150 | 1,200 | 4,600 |

The article also contains INJUSDT, which is outside the 47-symbol proxy set used in this inventory.

### Effective 2026-11-05 05:31 UTC

Published: `2026-11-04T08:01:56Z`  
Official source: https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-nov-5-2026--artff0e2f730786/  
Captured body SHA-256: `233e01289ff4a39e7062ed8b9f23a8242062df7a6470ec1983098571fc09ece1`

| Symbol | Market max before | Market max after | Limit max before | Limit max after |
|---|---:|---:|---:|---:|
| WLDUSDT | 370,000 | 700,000 | 1,850,000 | 2,800,000 |

## 3. Interpretation and restrictions

- These **19 symbol/event rows** (12 tick-size rows + 7 order-size rows; CAKEUSDT and MORPHOUSDT occur in both tick-size events) are a **partial dated parameter history** from four official announcements.
- `effective_from` is taken from the announcement's stated UTC effective time, not inferred from the publication timestamp.
- The captured source HTML hashes identify the exact raw bodies used for transcription.
- This is not a complete historical specification database and does not establish historical qty step, min quantity, min notional, max leverage, fee schedule, or all order constraints.
- Do not extrapolate values to symbols absent from these notices.
- Current `instruments-info` data must not be backfilled into earlier periods.
- The collector's separate five empty-content articles remain unresolved; none of those pages was used for the tables above.

## 4. Gate decision

**D5 — NOT ACCEPTED.** The extracted notices provide useful, dated evidence for tick-size and maximum-order-size changes, but the history is incomplete across symbols and time, and has not been reconciled against independently dated instrument snapshots.

**D6 — NOT ACCEPTED.** Maximum leverage notices and risk-limit announcement leads are not equivalent to a complete historical risk-tier ladder. No tier schedule should be inferred from these tables.
