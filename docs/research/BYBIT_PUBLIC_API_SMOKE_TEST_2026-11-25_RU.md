# Bybit public API smoke test — 2026-11-25

## Result

GitHub Actions run: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45577858899

Branch: `research/bybit-public-api-smoke-test`  
Workflow: `.github/workflows/bybit-public-api-smoke-test.yml`

### Cloud-runner test

The GitHub-hosted `ubuntu-latest` runner in Azure region `eastus3` received HTTP 403 for all three public GET requests:

- `/v5/market/kline?category=linear&symbol=BTCUSDT&interval=60&limit=3`
- `/v5/market/mark-price-kline?category=linear&symbol=BTCUSDT&interval=60&limit=3`
- `/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=3`

CloudFront response:

```text
The Amazon CloudFront distribution is configured to block access from your country
```

This establishes a geography-based denial for that cloud-runner network location only. It does not establish a block on Russian residential IPs or Russian residents.

### User-network browser test

On 2026-11-25, the user opened all three public URLs from their own network/browser and supplied the JSON responses in the conversation. Each returned `retCode: 0`, `retMsg: "OK"`.

| Endpoint | User-supplied result | Fields returned |
|---|---|---|
| `/v5/market/kline` | PASS | BTCUSDT Linear H1 OHLCV, 3 candles |
| `/v5/market/mark-price-kline` | PASS | BTCUSDT Linear H1 Mark Price, 3 candles |
| `/v5/market/funding/history` | PASS | BTCUSDT Linear funding rate, 3 events |

The supplied funding records include rates `0.00000255`, `0.00003905`, and `0.00003371` with their event timestamps.

**Evidence classification:** user-supplied browser responses, not independently captured or hashed by the repository workflow. The exact physical country/network route was not independently verified. Therefore record this as successful reachability from the user's tested connection, not as proof of Russian-resident eligibility.

## Interpretation and limits

- The three public market-data endpoints are reachable from the network used for the user's browser test.
- This does not establish account KYC eligibility, availability of BTCUSDT Perpetual to a particular account, private/account API access, or permission to trade.
- It does not validate historical completeness, pagination, timestamp continuity, raw-data provenance, or any research data gate. Three-row smoke tests are connectivity checks only.
- The GitHub-hosted runner's HTTP 403 remains a separate result for its Azure East US 3 network location.

No API keys, private endpoints, account endpoints, orders, proxies, mirrors, VPN-based routing, or location-masking mechanisms were used. No archives were collected and no PnL/backtest was run.
