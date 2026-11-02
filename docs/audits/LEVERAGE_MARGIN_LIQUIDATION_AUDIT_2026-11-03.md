# Аудит leverage, margin и liquidation model

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
