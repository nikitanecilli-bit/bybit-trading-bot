# Bybit Dated Perpetual Parameter Events — Expanded Partial Extraction

**Review date:** 2026-11-25  
**Source artifact:** workflow [45586354775](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45586354775), artifact `bybit-public-announcement-inventory`  
**Method:** manually checked official article title, publication timestamp, article body/table, effective-time text and raw HTML SHA-256. Tables were read from rendered HTML or the Contentstack rich-text JSON table nodes.  
**Universe:** only rows intersecting the 47-symbol research proxy set are shown. This set is Binance-style, survivor-biased, and is not a Bybit point-in-time universe.

## 1. Coverage summary

| Parameter event type | Official notices with proxy hits | Symbol/event rows | Distinct proxy symbols |
|---|---:|---:|---:|
| Tick-size changes | 7 | 19 | 14 |
| Maximum market/limit order-size changes | 8 | 29 | 31 |

These are positive records found in the selected four-category archive capture. They are not percentages of complete Bybit history. The same symbol may appear in multiple events.

## 2. Tick-size changes

Values are price increments. `Current ticksize` and `New ticksize` are transcribed from the official table.

### Effective 2026-01-06 06:30 UTC

Published: `2026-01-05T11:41:40+08:00`  
[Official notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-jan-6-2026-bltb7bba7e6015daf73/)  
Raw body SHA-256: `490fddaac236d970cec2713bfa25e735e3366467f782673e897c824f90bd4f72`

| Symbol | Old tick | New tick |
|---|---:|---:|
| APTUSDT | 0.001 | 0.0001 |
| CAKEUSDT | 0.001 | 0.0001 |

### Effective 2026-01-09 09:00 UTC

Published: `2026-01-08T12:34:30+08:00`  
[Official notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-jan-9-2026-blt7060901c04757924/)  
Raw body SHA-256: `8cd7a8448ee7ea8ba391b39914114a9307e211af5ae8ac52f36d29b8aa882a73`

| Symbol | Old tick | New tick |
|---|---:|---:|
| JSTUSDT | 0.00001 | 0.000001 |

### Effective 2026-01-15 02:30 UTC

Published: `2026-01-13T17:32:10+08:00`  
[Official notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-jan-15-2026-blt09e1c3f9de2d23e2/)  
Raw body SHA-256: `bc0ed642e5b7f09480dd7fdf1b1224c63728e5e5e5109d09b7f0ad50fd383e17`

| Symbol | Old tick | New tick |
|---|---:|---:|
| ARBUSDT | 0.0001 | 0.00001 |

### Effective 2026-01-22 06:00 UTC

Published: `2026-01-21T10:13:00+08:00`  
[Official notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-jan-22-2026-blt4e4b8ca4bef94d2d/)  
Raw body SHA-256: `23a6cf7ffb514379617cdc17551ea704b73b7e1c8c12caa2d45ff2fd4869d53c`

| Symbol | Old tick | New tick |
|---|---:|---:|
| ENAUSDT | 0.0001 | 0.00001 |
| ATOMUSDT | 0.001 | 0.0001 |

### Effective 2026-05-07 02:30 UTC

Published: `2026-05-06T10:12:40+08:00`  
[Official notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-may-7-2026-blt8cc849b9222b4f54/)  
Raw body SHA-256: `9845a8f108b116ed47ee75f2a6fa03affcabadf59bf0e3ca03f0d36077926352`

| Symbol | Old tick | New tick |
|---|---:|---:|
| JSTUSDT | 0.000001 | 0.00001 |

### Effective 2026-08-11 08:30 UTC

Published: `2026-08-06T10:36:56Z`  
[Official notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-aug-11-2026--art4f47b6648755/)  
Raw body SHA-256: `5ec21a6cad43af5b75a78b68928656d169a80d778eefd3feaa36021ae47bfbce`

| Symbol | Old tick | New tick |
|---|---:|---:|
| ATOMUSDT | 0.0001 | 0.001 |
| CAKEUSDT | 0.0001 | 0.001 |
| MORPHOUSDT | 0.0001 | 0.001 |
| NEARUSDT | 0.0001 | 0.001 |
| RENDERUSDT | 0.0001 | 0.001 |
| TRXUSDT | 0.00001 | 0.0001 |
| XLMUSDT | 0.00001 | 0.0001 |

### Effective 2026-10-12 07:30 UTC

Published: `2026-10-08T03:09:14Z`  
[Official notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-oct-12-2026--art5c4a8b8eef37/)  
Raw body SHA-256: `7783748c07f10d7bd9a7e07ce927ed74c5e7b1f52445066bcfe7feaf2f58c592`

| Symbol | Old tick | New tick |
|---|---:|---:|
| BCHUSDT | 0.1 | 0.01 |
| BNBUSDT | 0.1 | 0.01 |
| PAXGUSDT | 0.1 | 0.01 |
| CAKEUSDT | 0.001 | 0.0001 |
| MORPHOUSDT | 0.001 | 0.0001 |

## 3. Maximum order-size changes

All values below are maximum quantities in coins. These are not `qtyStep`, minimum order quantity, minimum notional, or risk-limit tiers.

### Date conflict: title 2026-01-20; article body 2025-01-20

Published: `2026-01-19T08:49:55Z`  
[Official notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-jan-20-2026-blteec5937787d92295/)  
Raw body SHA-256: `0901e7b1c65e331df36aee4aaae4dbb152fbd7ea6d1c857472e421eefc746370`

The title and publication timestamp indicate a 2026 notice, but the article body states `Jan 20, 2025, 9:00AM UTC`. This conflict is preserved rather than silently corrected. The row is quarantined from a dated 2026 parameter timeline until independently resolved.

| Symbol | Market max before | Market max after | Limit max before | Limit max after |
|---|---:|---:|---:|---:|
| WLFIUSDT | 160,000 | 2,400,000 | 450,000 | 12,000,000 |

### Date conflict: title 2026-01-23; article body 2025-01-23

Published: `2026-01-22T07:07:12Z`  
[Official notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-jan-23-2026-bltb03cc69400553b65/)  
Raw body SHA-256: `5229f894a29f2fe6520fd31c7ff499fdde127ff105e7e539a18621628b73d5fc`

The title and publication timestamp indicate a 2026 notice, but the article body states `Jan 23, 2025, 7:00AM UTC`. These rows are also quarantined from a dated 2026 timeline.

| Symbol | Market max before | Market max after | Limit max before | Limit max after |
|---|---:|---:|---:|---:|
| ZECUSDT | 100 | 1,100 | 500 | 5,500 |
| BCHUSDT | 130 | 1,300 | 340 | 6,500 |
| ENAUSDT | 100,000 | 700,000 | 500,000 | 3,500,000 |
| TAOUSDT | 305 | 980 | 700 | 4,900 |

### Effective 2026-01-30 07:00 UTC

Published: `2026-01-29T06:50:37Z`  
[Official notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-jan-30-2026-bltd40e4a78b9678660/)  
Raw body SHA-256: `a270df43c5d1ad0dde288f1ac099a129f6128dd2524ad0645a624be07ba1f7f7`

| Symbol | Market max before | Market max after | Limit max before | Limit max after |
|---|---:|---:|---:|---:|
| AVAXUSDT | 10,950 | 22,000 | 64,690 | 110,000 |
| DASHUSDT | 208 | 1,600 | 1,040 | 8,000 |
| ETHUSDT | 724 | 1,600 | 7,240 | 8,000 |
| GMXUSDT | 300 | 2,900 | 1,500 | 14,500 |

### Effective 2026-02-25 06:30 UTC

Published: `2026-02-25T11:31:00+08:00`  
[Official notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-feb-25-2026-blt832d22d1227daf31/)  
Raw body SHA-256: `e219f152d64fd18c3066f1ddeea893ab25c835502848dedb42b05a5796d2133d`

| Symbol | Market max before | Market max after | Limit max before | Limit max after |
|---|---:|---:|---:|---:|
| ARBUSDT | 283,360 | 4,300,000 | 1,799,900 | 21,500,000 |
| QNTUSDT | 91 | 1,300 | 380 | 6,500 |
| ONDOUSDT | 72,300 | 900,000 | 723,000 | 4,500,000 |
| WLDUSDT | 34,020 | 370,000 | 287,290 | 1,850,000 |
| APTUSDT | 15,408 | 160,000 | 154,080 | 800,000 |

### Effective 2026-04-10 08:30 UTC

Published: `2026-04-09T11:34:10+08:00`  
[Official notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-apr-10-2026-blt5f98c3dc14f36458/)  
Raw body SHA-256: `1c3b6016bae4786a1d6abaa5de2c354208a9e57db8c68e32fdb8285c20fd2ba4`

| Symbol | Market max before | Market max after | Limit max before | Limit max after |
|---|---:|---:|---:|---:|
| BTCUSDT | 119 | 150 | 1,190 | 1,500 |
| ETHUSDT | 1,600 | 2,000 | 8,000 | 10,000 |
| SOLUSDT | 11,740 | 12,000 | 79,770 | 96,000 |
| XRPUSDT | 520,000 | 1,500,000 | 1,300,000 | 7,500,000 |
| RENDERUSDT | 10,000 | 100,000 | 50,000 | 500,000 |
| SKYUSDT | 170,000 | 1,700,000 | 470,000 | 8,500,000 |

### Effective 2026-05-08 06:30 UTC

Published: `2026-05-07T15:14:20+08:00`  
[Official notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-may-8-2026-blt6be62bc8018a1c9c/)  
Raw body SHA-256: `f03c3c74db40da0e2982d33b3ac04960b1f052d557c2d14d004a9ad6b989a1ca`

| Symbol | Market max before | Market max after | Limit max before | Limit max after |
|---|---:|---:|---:|---:|
| QNTUSDT | 1,300 | 520 | 6,500 | 2,600 |
| SKYUSDT | 1,700,000 | 680,000 | 8,500,000 | 3,400,000 |

### Effective 2026-10-13 07:30 UTC

Published: `2026-10-12T07:04:46Z`  
[Official notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-oct-13-2026--art0d130e93d1dc/)  
Raw body SHA-256: `1e7111c8de041b6aa6ae282d0f8f23c822ae2c4a5fdae56f61612fec97b34f33`

| Symbol | Market max before | Market max after | Limit max before | Limit max after |
|---|---:|---:|---:|---:|
| SUIUSDT | 66,000 | 290,000 | 330,000 | 1,160,000 |
| ADAUSDT | 590,000 | 1,480,000 | 1,500,000 | 5,920,000 |
| ENAUSDT | 700,000 | 1,290,000 | 3,500,000 | 5,160,000 |
| UNIUSDT | 11,000 | 15,600 | 32,000 | 62,400 |
| XLMUSDT | 260,000 | 980,000 | 730,000 | 3,920,000 |
| AAVEUSDT | 460 | 1,150 | 1,200 | 4,600 |

### Effective 2026-11-05 05:31 UTC

Published: `2026-11-04T08:01:56Z`  
[Official notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-nov-5-2026--artff0e2f730786/)  
Raw body SHA-256: `233e01289ff4a39e7062ed8b9f23a8242062df7a6470ec1983098571fc09ece1`

| Symbol | Market max before | Market max after | Limit max before | Limit max after |
|---|---:|---:|---:|---:|
| WLDUSDT | 370,000 | 700,000 | 1,850,000 | 2,800,000 |

## 4. Interpretation and limits

- These rows establish dated changes only for the symbols and parameters explicitly listed in each official notice.
- Maximum order quantity in coins is not a lot-size step, minimum quantity, minimum notional, or leverage tier.
- The two January max-order notices have an internal date conflict (title/publication in 2026; body says 2025). They are preserved but quarantined from a 2026 effective-time timeline.
- No values are inferred for symbols absent from these notices.
- Current `instruments-info` data must not be backfilled into earlier periods.
- The selected archive categories and 47-symbol proxy do not establish exhaustive Bybit history.

## 5. Gate decision

**D5 — NOT ACCEPTED.** The expanded extraction provides 7 dated tick-size notices (19 proxy symbol/event rows) and 8 maximum-order-size notices (29 proxy symbol/event rows), including two January notices with unresolved year conflicts. This is materially better evidence, but it is not a complete historical instrument-specification database. Historical `qtyStep`, `minOrderQty`, `minNotional`, all maximum-order changes, and dated leverage/fee schedules remain incomplete.

**D6 — NOT ACCEPTED.** Maximum order sizes and maximum leverage notices do not provide full risk-limit tier ladders or maintenance-margin rates.
