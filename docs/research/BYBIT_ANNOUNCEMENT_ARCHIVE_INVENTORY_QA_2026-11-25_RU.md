# Bybit Public Announcement Archive — Inventory QA

**Дата сбора:** 2026-11-25  
**Workflow run:** [45586354775](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45586354775)  
**Commit:** `d1cb66be43870abea63df0defee932cbd405ba57`  
**Artifact:** `bybit-public-announcement-inventory` (21,115,419 bytes; GitHub artifact SHA-256 `2145c610aa4a5b963981fc7eee08f6f218ae4d067e80327cc40ed59ea6b694fe`)  
**Source:** https://announcements.bybit.com

## 1. Collection result

The workflow completed successfully. Offline parser/safety tests, public-page collection, and artifact upload all succeeded.

| Category | Observed page count | Retrieved | Result |
|---|---:|---:|---|
| `new_crypto` | 25 | 25 | complete |
| `delistings` | 11 | 11 | complete |
| `maintenance_updates` | 19 | 19 | complete |
| `latest_bybit_news` | 11 | 11 | complete |
| **Total** | **66** | **66** | **complete within selected scope** |

- Unique article URLs discovered: **1,275**.
- Article bodies captured: **1,275**.
- Collection failures: **0**.
- `inventory.json` reports `complete=true`.
- Publication timestamps present: **1,275/1,275**, spanning `2026-01-01T06:08:17Z` through `2026-11-25T09:02:44Z`.
- Every article was extracted from `__NEXT_DATA__.props.pageProps.articleDetail.content_html`.

### Independent artifact integrity check

Downloaded ZIP inspected independently:
- 1,341 body files: 66 category-page HTML + 1,275 article HTML.
- 1,341/1,341 body files found.
- 1,341/1,341 SHA-256 hashes match `inventory.json`.
- 1,341/1,341 byte sizes match `inventory.json`.
- No duplicate body-file paths.
- ZIP contains 1,342 entries including `inventory.json`.

This verifies byte integrity of the downloaded artifact against its own manifest. It does **not** independently authenticate the publisher's full archive or prove that the selected categories contain every historically relevant announcement.

## 2. Scope and limitations

The collector crawled four public announcement categories and all unique article links discovered on their selected pages, with a 100-page/category cap. The page counts above matched the counts observed when the collector was prepared (25/11/19/11). This is a bounded category inventory, not a guarantee of complete Bybit announcement history:
- other categories, languages, deleted/redirected articles, and announcements not linked from these category pages were not covered;
- the observed page totals can change over time;
- this is a current 2026 snapshot, not yet a dated multi-year event database;
- the 47-symbol set is a survivor-biased proxy universe, not a proven historical Bybit universe.

The collector made requests only to `announcements.bybit.com`; it did not call market endpoints or private/account APIs and did not place orders.

## 3. Candidate classifier output (not accepted evidence)

Across 1,275 articles, the title/body candidate labels were:
- `DELIST`: 324
- `LIST`: 317
- `HALT_RESUME_OR_ADJUSTMENT`: 122
- `RISK_LIMIT_CHANGE`: 72
- `ORDER_SIZE_CHANGE`: 22
- `TICK_CHANGE`: 16
- `FUNDING_RULE_CHANGE`: 11
- `OTHER`: 391

Product-class candidates:
- `unknown`: 508
- `perpetual_product_unknown`: 257
- `tradfi_candidate`: 222
- `linear_candidate`: 168
- `spot_or_token_candidate`: 117
- `inverse_candidate`: 3

These are heuristic labels from article title/body text. They are not verified event records. In particular, a `DELIST` candidate may concern Bybit Alpha, spot tokens, Convert, or another product rather than a USDT perpetual contract. Likewise `RISK_LIMIT_CHANGE` can refer to margin trading or institutional loans rather than the contract risk-limit ladder needed by the trading engine.

## 4. Target-proxy symbol matching

The 47-symbol proxy list was searched in article title/body:
- 42/47 proxy symbols had at least one match.
- No matches were found for `MINAUSDT`, `PEPEUSDT`, `PUMPUSDT`, `RAYUSDT`, `SHIBUSDT`.
- 42 matching symbols does not mean all their lifecycle/spec/risk events were found. No-match does not prove that no event occurred.

### Target-symbol event candidates for manual review

The following 16 articles had both a target-proxy symbol hit and a potentially relevant candidate label. This is a review queue, not accepted D4/D5/D6 evidence.

| Published (UTC as supplied) | Candidate | Product class candidate | Matched proxy symbols | Official article |
|---|---|---|---|---|
| 2026-05-29T00:00:00.000Z | RISK_LIMIT_CHANGE | unknown | ASTERUSDT, CAKEUSDT, DASHUSDT, ENAUSDT, GMXUSDT, JSTUSDT, MORPHOUSDT, PAXGUSDT, POLUSDT, QNTUSDT, RENDERUSDT, SKYUSDT, SUIUSDT, WLDUSDT, WLFIUSDT | [Updates to contract leverage for Institutional Loans](https://announcements.bybit.com/en/article/-important-updates-to-contract-leverage-for-institutional-loans-blt0e3ddabb7c7afae1/) |
| 2026-08-06T10:36:56Z | TICK_CHANGE | linear_candidate | ATOMUSDT, CAKEUSDT, MORPHOUSDT, NEARUSDT, RENDERUSDT, TRXUSDT, XLMUSDT | [Change Tick Size for USDT Perpetual Contract Aug 11, 2026](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-aug-11-2026--art4f47b6648755/) |
| 2026-10-08T03:09:14Z | TICK_CHANGE | linear_candidate | BCHUSDT, BNBUSDT, CAKEUSDT, MORPHOUSDT, PAXGUSDT | [Change Tick Size for USDT Perpetual Contract Oct 12, 2026](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-oct-12-2026--art5c4a8b8eef37/) |
| 2026-11-04T08:01:56Z | ORDER_SIZE_CHANGE | linear_candidate | WLDUSDT | [Changes of Max. Order Size for USDT Perpetual Contracts Nov 5, 2026](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-nov-5-2026--artff0e2f730786/) |
| 2026-10-12T07:04:46Z | ORDER_SIZE_CHANGE | linear_candidate | AAVEUSDT, ADAUSDT, ENAUSDT, SUIUSDT, UNIUSDT, XLMUSDT | [Changes of Max. Order Size for USDT Perpetual Contracts Oct 13, 2026](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-oct-13-2026--art0d130e93d1dc/) |
| 2026-11-06T00:00:00.000Z | ORDER_SIZE_CHANGE | spot_or_token_candidate | JSTUSDT | [Notice on adjustment to maximum spot trade quantity](https://announcements.bybit.com/en/article/notice-on-adjustment-to-maximum-spot-trade-quantity--artd644d7914f10/) |
| 2026-08-18T15:12:52.000Z | RISK_LIMIT_CHANGE | perpetual_product_unknown | ALGOUSDT, AVAXUSDT, BCHUSDT, BNBUSDT, BTCUSDT, DASHUSDT, DOTUSDT, ETCUSDT, ETHUSDT, HBARUSDT, ICPUSDT, JSTUSDT, LINKUSDT, LTCUSDT, NEARUSDT, QNTUSDT, UNIUSDT, XLMUSDT, ZECUSDT | [Risk Limit Adjustment for Selected Perpetual Contracts (Aug 20, 2026)](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-aug-20-2026--artd5e4344ee603/) |
| 2026-09-02T04:35:23Z | RISK_LIMIT_CHANGE | perpetual_product_unknown | ALGOUSDT, AVAXUSDT, BCHUSDT, DASHUSDT, DOTUSDT, ETCUSDT, ICPUSDT, JSTUSDT, LTCUSDT, QNTUSDT, UNIUSDT, XLMUSDT | [Risk limit adjustment for selected Perpetual Contracts (Sep 4, 2026)](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-avaxusdt-xlmusdt-sep-4-2026--art453915b9e8fd/) |
| 2026-07-07T07:22:18Z | RISK_LIMIT_CHANGE | perpetual_product_unknown | CAKEUSDT, DASHUSDT, RENDERUSDT | [Risk limit adjustment for selected Perpetual Contracts (Jul 8, 2026)](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-blurusdt-fartcoinusdt-jul-8-2026--blt22544b85ab5016cf/) |
| 2026-10-15T08:28:58Z | RISK_LIMIT_CHANGE | perpetual_product_unknown | APTUSDT, ARBUSDT, ENAUSDT, ONDOUSDT, SUIUSDT, TAOUSDT, WLDUSDT | [Risk limit adjustment for selected Perpetual Contracts (Oct 16, 2026)](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-enausdt-suiusdt-oct-16-2026--artd87870c45c1f/) |
| 2026-06-29T11:53:30+08:00 | RISK_LIMIT_CHANGE | unknown | HBARUSDT | [Risk limit adjustment for selected Perpetual Contracts (Jun 30, 2026)](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-hbarusdt-roseusdt-jun-30-2026--bltbb2dede6bad434bf/) |
| 2026-01-21T22:06:30+08:00 | RISK_LIMIT_CHANGE | unknown | QNTUSDT | [Risk limit adjustment for selected Perpetual Contracts (Jan 23, 2026)](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-ontusdt-qntusdt-jan-23-2026--blt830c7d7efc375824/) |
| 2026-06-11T15:00:50+08:00 | RISK_LIMIT_CHANGE | unknown | PAXGUSDT | [Risk limit adjustment for selected Perpetual Contracts (Jun 12, 2026)](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-paxgusdt-galausdt-jun-12-2026--blt366cf2f185d6d505/) |
| 2026-04-27T19:12:10+08:00 | RISK_LIMIT_CHANGE | unknown | ALGOUSDT, POLUSDT | [Risk limit adjustment for selected Perpetual Contracts (Apr 28, 2026)](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-polusdt-algousdt-apr-28-2026--blt57993cb6d157988e/) |
| 2026-04-01T20:20:10+08:00 | RISK_LIMIT_CHANGE | unknown | XRPUSDT | [Risk limit adjustment for selected Perpetual Contracts (Apr 2, 2026)](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-xrpusdt-xagusdt-apr-2-2026--blt6cc1c68b38638ad0/) |
| 2026-11-19T00:00:00.000Z | FUNDING_RULE_CHANGE | unknown | ADAUSDT, ARBUSDT, ATOMUSDT, AVAXUSDT, LTCUSDT, NEARUSDT | [Update to Funding Rate Calculation Formula for Perpetual Contracts](https://announcements.bybit.com/en/article/update-to-funding-rate-calculation-formula-for-perpetual-contracts--art9f3b40f8766e/) |

### Important exclusions / false-positive examples

- `Notice on adjustment to maximum spot trade quantity` matched `JSTUSDT`, but is explicitly a spot quantity notice and must not be used as a perpetual max-order-size record.
- `[Important] Updates to contract leverage for Institutional Loans` matched multiple proxy symbols, but the title indicates institutional loans; it is not automatically a perpetual risk-limit tier change.
- Numerous `DELIST` candidates concern Bybit Alpha or token removals. Do not treat the classifier's `DELIST` label as a derivative delisting without checking product and effective time.
- The candidate symbol parser only records matches in extracted article title/body; the lack of a match is not a negative event assertion.

## 5. Gate status

| Gate | Result from this inventory |
|---|---|
| D4 — historical listing/delisting lifecycle | **NOT ACCEPTED**. No target-proxy symbol hit among the 324 generic `DELIST` candidates in this inventory. This is not proof of no delistings; category/product coverage is bounded. |
| D5 — dated contract specifications | **NOT ACCEPTED**. Two symbol-matched tick-size candidates and two linear max-order-size candidates are useful leads, but full symbol coverage, exact effective values/timestamps, and historical snapshots are not yet established. |
| D6 — dated risk-limit tiers | **NOT ACCEPTED**. Risk-limit candidate articles exist, including selected-perpetual notices, but full tier ladders and complete symbol/time coverage have not been independently extracted and reconciled. |
| D7 — L2/trades | Not in scope. |
| D8 — dated fees | Not in scope. |

## 6. Next work

1. Manually review the 16 symbol-matched candidate articles and extract structured fields: product, symbol, event type, `published_at`, `effective_from`, old/new values, units, and source URL.
2. Keep publication time separate from effective time. If an effective time/value is absent, record `unknown`; never infer it from the current API.
3. For each candidate, preserve the raw article body/hash and add an independently reviewed event record with reviewer/status.
4. Search the official announcement site for missing historical lifecycle/spec/risk notices outside these four categories; record search coverage and unresolved gaps.
5. Keep D4/D5/D6 gates closed until coverage and value-level validation are demonstrated.

**Conclusion:** the first complete, byte-verified bounded announcement inventory is now available. It materially improves the evidence base and creates a focused manual-review queue, but it does not yet justify accepting any historical lifecycle, contract-specification, or risk-tier gate.
