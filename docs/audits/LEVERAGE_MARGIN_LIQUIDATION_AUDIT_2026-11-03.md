# Аудит leverage, margin и liquidation model

> **Актуальный статус на 2026-11-03:** исходный статический аудит предшествовал интеграции ENG-EXEC-010/011 и Mark OHLC liquidation path. Dated risk tiers, entry-time position IM/MM и isolated USDT position-level Mark liquidation теперь реализованы и покрыты CI. Поэтому формулировки ниже об отсутствии любой liquidation-модели, exact contract quantity или risk-tier lookup являются историческими и superseded. Это **не** полный Bybit account engine: Cross/Portfolio Margin, shared collateral, partial-liquidation ladder и подтверждение реального account mode остаются вне модели. См. [Execution integration re-audit](EXECUTION_INTEGRATION_REAUDIT_2026-11-03.md).


Дата: 2026-11-03
Статус: CONFIRMED MODEL LIMITATION / EXECUTION GATE BLOCKED
Scope: `Bybit_Trading_Engine_v14_research.py`, `exchange_order_sizing.py`, `bybit_instrument_specs.py`, `tests/test_portfolio_accounting.py`, `docs/audits/EXECUTION_REALISM_READINESS_RU.md`.

## 1. Что реально моделирует движок

В `AdaptiveRiskManager.calculate_position_size()`:
- рассчитывается stop loss risk budget с fee/slippage;
- notional = risk budget / estimated loss rate;
- применяется верхний предел `equity * leverage_val / max_concurrent_positions * 0.95`;
- округление notional вниз до центов;
- возвращается `size_usdt` и `risk_usdt`.

Позиция `OpenPositionState` хранит `size_usdt` (notional proxy), но не contract qty, initial margin, maintenance margin, margin mode, positionIdx или liquidation price. Сайзинг не вызывает `exchange_order_sizing.size_to_exchange_constraints()`; этот helper существует отдельно и не участвует в текущем engine lifecycle.

## 2. Подтверждённые отсутствующие механики

В движке не обнаружена реализация:
- расчёта initial margin / maintenance margin по symbol risk tier;
- liquidation price и ликвидационного события;
- maintenance-margin tier transitions при изменении notional;
- cross/isolated margin accounting и shared collateral effects;
- exchange liquidation fee / bankruptcy price;
- mark-price liquidation trigger distinct from candle close / stop trigger;
- exchange qtyStep/tickSize/minNotional integration in entry, partial exit and funding quantity.

Поиск по полному engine source не обнаружил `liquidation_price`, `maintenance_margin` или liquidation calculation. В тестах portfolio accounting есть проверка leverage-based notional cap, но нет liquidation/margin test suite. Это не утверждение о дефекте формулы stop PnL; это подтверждённая неполнота модели.

## 3. Что означает существующий leverage cap

Текущий предел `equity * leverage / max_concurrent_positions * 0.95` — грубый allocation cap на одну позицию. Он не является расчётом фактической маржи Bybit и не моделирует риск ликвидации. Его нельзя трактовать как доказательство, что позиция выдержит заданный adverse move или что stop исполнится до liquidation.

Также `risk_usdt` оценивает плановый убыток на stop с базовыми комиссиями и slippage. Он не является maximum loss: gap, mark/index divergence, maintenance tier, funding, ликвидационная комиссия и невозможность исполнения стопа могут увеличить фактический убыток.

## 4. Существующие тесты и пробелы

Есть тест `test_portfolio_risk_budget_caps_new_position_size`, который проверяет, что risk sizing уважает заданный risk budget, и тесты распределения портфельного risk budget между одновременными сигналами. Они не проверяют:
- корректное вычисление margin/notional по точному qty;
- liquidation price для long и short;
- cross/isolated collateral;
- maintenance tier lookup и переходы;
- stop gap vs liquidation ordering;
- mark-price liquidation при отличии от last/trade candle;
- funding и fee impact на liquidation equity.

## 5. Решение

`NO CONFIRMED SIZING FORMULA BUG` в пределах проверенного кода.
`P0/P1 EXECUTION REALISM GATE: BLOCKED` для любых выводов о реальной ликвидационной устойчивости и live readiness.

Не добавлять выдуманную liquidation formula и не использовать произвольный maintenance rate. До реализации необходимы датированные официальные Bybit linear instrument/risk-tier snapshots, точный exchange qty и account margin mode. Затем pure deterministic margin calculator + fixtures из реальных risk tiers, отдельно cross/isolated, mark-price trigger, funding/fees, partial fills и stop-vs-liquidation stress cases.

Текущие Binance-proxy OHLCV backtests не могут подтвердить Bybit liquidation safety. Рыночные PnL sweeps и live deployment остаются заблокированы до закрытия execution-data gate.


## 6. Official formula and account-mode boundary (verified 2026-11-03)

Current Bybit documentation confirms:
- The V5 `GET /v5/market/risk-limit` response supplies per-symbol tier ID, riskLimitValue, maintenanceMargin, initialMargin, maxLeverage and mmDeduction; linear returns a paginated universe. See [official API schema](https://bybit-exchange.github.io/docs/v5/market/risk-limit).
- For USDT contracts, position value is contract quantity × mark price. Maintenance margin is tier-based; `MM = positionValue × MMR − mmDeduction`. Tier transitions can occur as mark price changes. The documented deduction recurrence is `MMDeduction[n] = riskLimit[n−1] × (MMR[n] − MMR[n−1]) + MMDeduction[n−1]`. See [Bybit Maintenance Margin (USDT)](https://www.bybit.com/en/help-center/article/Maintenance-Margin-USDT-Contract), last updated 2026-04-16.
- Bybit's isolated liquidation formula is account/product-mode specific. The current UTA isolated USDT formula includes entry price, quantity, leverage, extra margin, MMR, mmDeduction and taker close-fee adjustment. Cross margin instead depends on shared account equity/MMR; Portfolio Margin uses account-level stress risk. See [Bybit isolated liquidation calculation](https://www.bybit.kz/en-KAZ/help-center/article/Liquidation-Price-Calculation-under-Isolated-Mode-Unified-Trading-Account) and [Bybit liquidation rules](https://www.bybit-global.com/en/help-center/article/UTA-Trading-Rules).

The risk-tier snapshot collector now validates each symbol's tier sequence before saving: unique lowest-tier flag, strictly increasing risk limits, non-decreasing maintenance/initial margin rates, non-increasing max leverage, and the documented mmDeduction recurrence. These are data-integrity checks, not a liquidation model.

**Implementation decision:** do not wire a single liquidation formula into the engine yet. The config string `ISOLATED_5X` indicates intended leverage/mode but does not establish whether the actual account is Classic isolated or Unified Trading Account isolated, nor extra-margin/auto-add-margin settings. The current official UTA formula cannot safely be assumed to match a Classic account. Implement isolated UTA only as an explicitly selected model after account mode is known; keep Cross and Portfolio Margin out of scope until their account-level inputs are available. The mark-price trigger must remain distinct from trade/last-price OHLC.

No live account or private API was queried for this decision.


## 7. Risk-tier sequence validation and CI evidence

The risk-limit collector now validates complete per-symbol tier groups before accepting a snapshot:
- exactly one `isLowestRisk=1`, on the lowest tier;
- strictly increasing `riskLimitValue`;
- non-decreasing maintenance and initial margin rates;
- non-increasing max leverage;
- `mmDeduction` recurrence per Bybit's published USDT maintenance-margin formula.

Research CI [#41543899344](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41543899344) completed **SUCCESS** on commit `93d6dca3fde3b59d1c8d9e9727af660623b5d3b4`; all 12 risk-tier collector tests and the complete Research suite passed.

The push-triggered official risk-tier snapshot attempt [#41543899223](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41543899223) failed at the API download step with HTTP 403; no snapshot was written. This is an external data-access blocker, not a parser/test failure. The snapshot collector remains ready but no current or historical Bybit risk-tier values are available in the repository.

Official references checked:
- [Bybit V5 Get Risk Limit](https://bybit-exchange.github.io/docs/v5/market/risk-limit): linear endpoint pagination and fields `riskLimitValue`, `maintenanceMargin`, `initialMargin`, `maxLeverage`, `mmDeduction`.
- [Bybit Maintenance Margin — USDT contracts](https://www.bybit.com/en/help-center/article/Maintenance-Margin-USDT-Contract), last updated 2026-04-16: tier-based maintenance margin, live mark-price tier changes, and deduction recurrence.
- [Bybit Isolated Liquidation — UTA](https://www.bybit.kz/en-KAZ/help-center/article/Liquidation-Price-Calculation-under-Isolated-Mode-Unified-Trading-Account): UTA isolated long/short formulas and close-fee adjustments.

The collector's sequence checks are now covered by tests; the liquidation calculator itself remains deliberately unimplemented until account mode and dated risk-tier snapshots are known.
