# Bybit public API smoke test — 2026-11-25

## Result

GitHub Actions run: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45577858899

Branch: `research/bybit-public-api-smoke-test`  
Commit: `bd7ddd8911c641342ac8511e7e466bde8adc496a`  
Runner: GitHub-hosted `ubuntu-latest`, Azure region `eastus3`  
Workflow: `.github/workflows/bybit-public-api-smoke-test.yml`

All three public GET requests to `https://api.bybit.com` returned HTTP 403:

- `/v5/market/kline?category=linear&symbol=BTCUSDT&interval=60&limit=3`
- `/v5/market/mark-price-kline?category=linear&symbol=BTCUSDT&interval=60&limit=3`
- `/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=3`

Response body from CloudFront:

```text
The Amazon CloudFront distribution is configured to block access from your country
```

## Interpretation

This is a geography-based denial from the network location of the GitHub-hosted runner. The runner was in Azure East US 3. It does **not** establish that Bybit blocks Russian residential IP addresses or Russian residents.

The test only establishes that these three public endpoints were not reachable from this particular cloud-runner geography at the time of the test. No API keys, private endpoints, account endpoints, or orders were used.

## Next evidence required

To answer the user's actual question, test the same public market-data URL from an ordinary internet connection physically located in Russia, without VPN, proxy, mirror, or other location-masking mechanism. A successful browser response would establish public market-data reachability from that connection only; it would not prove account KYC eligibility, derivatives permissions, or private trading API access.

Do not attempt to bypass the CloudFront restriction by routing the GitHub runner through another region.
