# Bybit Risk-Limit Change Notices — Partial Dated Event Inventory

**Review date:** 2026-11-25  
**Source artifact:** workflow [45586354775](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45586354775), artifact `bybit-public-announcement-inventory`  
**Method:** manually checked article title, publication timestamp, article body, affected-symbol table/list and raw HTML SHA-256. Body text was extracted from `content_html` or, where that field is empty, from `content.json`.  
**Scope limitation:** four announcement categories and a 47-symbol proxy universe; not a complete Bybit announcement history or a verified historical Bybit universe.

## 1. Coverage result

- 63 article titles in the captured inventory were candidates for risk-limit / position-tier / maximum-leverage review.
- 9 notices contained at least one match to the 47-symbol proxy universe.
- Those 9 notices cover 32 distinct proxy symbols.
- The 47-symbol proxy is survivor-biased and does not establish that these were the only Bybit-listed symbols at the relevant dates.

## 2. Source-backed events intersecting the proxy universe

| Published (source timestamp) | Effective UTC | Buffer end UTC | Matched proxy symbols | Source |
|---|---|---|---|---|
| 2026-08-18 15:12:52Z | 2026-08-20 08:00 | Not stated in article | ALGO, AVAX, BCH, BNB, BTC, DASH, DOT, ETC, ETH, HBAR, ICP, JST, LINK, LTC, NEAR, QNT, UNI, XLM, ZEC | [Official notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-aug-20-2026--artd5e4344ee603/) |
| 2026-09-02 04:35:23Z | 2026-09-04 07:30 | 2026-09-21 07:30 | ALGO, AVAX, BCH, DASH, DOT, ETC, ICP, JST, LTC, QNT, UNI, XLM | [Official notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-avaxusdt-xlmusdt-sep-4-2026--art453915b9e8fd/) |
| 2026-07-07 07:22:18Z | 2026-07-08 07:30 | 2026-07-25 07:30 | CAKE, DASH, RENDER | [Official notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-blurusdt-fartcoinusdt-jul-8-2026--blt22544b85ab5016cf/) |
| 2026-10-15 08:28:58Z | 2026-10-16 07:30 | 2026-11-02 07:30 | APT, ARB, ENA, ONDO, SUI, TAO, WLD | [Official notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-enausdt-suiusdt-oct-16-2026--artd87870c45c1f/) |
| 2026-06-29 11:53:30+08:00 | 2026-06-30 07:30 | 2026-07-17 07:30 | HBAR, MINA | [Official notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-hbarusdt-roseusdt-jun-30-2026--bltbb2dede6bad434bf/) |
| 2026-01-21 22:06:30+08:00 | 2026-01-23 02:30 | 2026-02-09 08:30 | QNT | [Official notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-ontusdt-qntusdt-jan-23-2026--blt830c7d7efc375824/) |
| 2026-06-11 15:00:50+08:00 | 2026-06-12 07:30 | 2026-06-29 07:30 | PAXG | [Official notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-paxgusdt-galausdt-jun-12-2026--blt366cf2f185d6d505/) |
| 2026-04-27 19:12:10+08:00 | 2026-04-28 09:30 | 2026-05-15 09:30 | ALGO, ICP, MINA, ONDO, POL | [Official notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-polusdt-algousdt-apr-28-2026--blt57993cb6d157988e/) |
| 2026-04-01 20:20:10+08:00 | 2026-04-02 09:30 | 2026-04-19 09:30 | PAXG, XRP | [Official notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-xrpusdt-xagusdt-apr-2-2026--blt6cc1c68b38638ad0/) |

## 3. Raw evidence identities

The following SHA-256 values identify the exact captured article HTML bodies in the source artifact, in the same row order as the table above:

1. `21e66fac4807297fb2c89ba79d491705882425a7343dcad3c8a8698c953e0a0d`
2. `58278d5091173a9b0e31dc6b27f154080f0cd6abcd3c9157aa92bb8a81dc3628`
3. `450c0489c38b671a18d2fea10c3dac2e36b6b27bbfbedd8393ae5f52557bd9b1`
4. `749966673a586b161d797074e282cc5a958dd7a25f904825e0e84f083672bbd0`
5. `60fb043647255f4dacca93eb1cabf0fe376c76097c9632572ea0d7984dbce55a`
6. `68cf36088690ac689f010377dea366e8c6dd3f987a5da6e687d9223d1fdacf73`
7. `464a8b90878e3b5df0a10805d4ed1fcb6e62d4e655c2eb1d969e9d7263780079`
8. `facbc01dceadfc70c7f63cbefb7dd4483f35ea357805105271cdbbc7f20397da`
9. `1e1cd8d11a9d55faf7f80a4b8cec8aff2c845f3a39eae0ea4fb0c2886a0aec61`

## 4. Interpretation

These announcements establish that Bybit published dated risk-parameter change notices, the stated effective times, and in eight cases explicit buffer-period end times. They also identify affected instruments.

They do **not** provide a complete historical risk-limit tier ladder. In particular, this inventory does not establish, for each affected symbol and effective date:
- tier-by-tier notional thresholds;
- maintenance-margin rates;
- initial-margin rates;
- maximum position size per tier;
- exact historical liquidation parameters.

One separate notice dated 2026-08-20 contains a maximum-leverage table; it is documented separately in `BYBIT_DATED_MAX_LEVERAGE_NOTICE_PARTIAL_2026-11-25_RU.md`. Maximum leverage is not a substitute for maintenance-margin tiers.

## 5. Gate decision

**D6 — NOT ACCEPTED.** The nine notices improve dated event coverage for 32 proxy symbols, but they do not supply the actual tier ladder values needed to reproduce historical margin and liquidation constraints.

Next useful source path: recover dated historical versions of Bybit's margin-parameters tables or source spreadsheets referenced by these notices. Current live parameters must not be backfilled into historical periods.
