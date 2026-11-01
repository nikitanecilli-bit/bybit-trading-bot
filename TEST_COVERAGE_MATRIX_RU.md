# Матрица покрытия аудита и исследовательских гипотез

Статус относится к подтверждённым доступным материалам на 2026-11-02, а не к обещанию корректности.

| Область | Статус | Что известно | Что требуется |
|---|---|---|---|
| Архитектура репозитория | PARTIAL | Найдены engine, downloader, scripts, workflows, reports, tests | Сверить все ветки и зависимости |
| Live execution / безопасность | PARTIAL | README утверждает, что v14 research engine не отправляет ордера | Проверить весь репозиторий/ветки на API order endpoints |
| Свечи и временные метки | PARTIAL / P1 | Есть `test_time_model.py`; обнаружено, что CSV равномерность проверяет, но интервал не сравнивает с `cfg.timeframe` | Добавить тесты mismatch и уточнить open/close timestamp semantics |
| Look-ahead | PARTIAL | Основной signal core использует только предыдущие бары для Donchian/ATR; полный аудит scripts/features/folds не завершён | Статический аудит всех сигналов/фич/выходов и fold construction |
| Stop/TP внутри свечи | NOT_TESTED | Есть общие тесты времени и гэпов | Проверить collision и OHLC path assumptions |
| Market gap execution | PARTIAL | `test_gap_execution.py` и gap report существуют | Повторить тесты, проверить точное покрытие |
| Limit fills | PARTIAL | E03/E07/E09 моделируют лимитное касание | Нет queue/partial fill/spread/adverse selection |
| Fees | PARTIAL | В v14 есть maker/taker fees per leg; в v15 отдельная модель fee/slippage | Сопоставить тарифы, maker/taker по каждой ноге и rounding |
| Slippage | PARTIAL | В движке есть модель slippage | Проверить применение к фактической цене и sizing |
| Funding | PARTIAL / UNVERIFIED IN CURRENT BRANCH | В отдельной diverged ветке есть downloader, mark-price loader, funding cashflow и synthetic tests; текущая ветка это не использует | Проверить exact mark price, settlement semantics и интегрировать отдельным патчем; старые результаты не funding-adjusted |
| Position sizing / leverage | NOT_TESTED | Есть параметры риска и плеча в движке | Проверить формулы, округления, margin/liquidation |
| Portfolio shared capital | PARTIAL | E07 портфельный тест | Проверить event ordering, simultaneous signals и capital accounting |
| Concurrency / risk gates | PARTIAL | E07/E09 учитывают max positions и risk gates | Проверить последовательность символов и зависимость результата от порядка |
| Market regimes | PARTIAL | Есть regime scripts/reports и E06 diagnostics | Внешняя независимая проверка, стабильность по периодам |
| False breakout classifier | NOT_TESTED | Гипотеза описана в проектном контексте | Формализовать признаки без leakage и проверить out-of-sample |
| Universe screening | PARTIAL | E01/E02/holdout отчёты | Survivorship, delisted symbols, point-in-time universe |
| Holdout integrity | PARTIAL | Holdout report существует; Bybit 403 noted | Проверить даты/данные и факт отсутствия повторного подбора |
| Multiple testing / DSR/PBO | PARTIAL | В отчётах есть caveats | Текущие упрощённые расчёты не считать валидированными |
| Reproducibility | PARTIAL | Есть GitHub workflows/artifacts; ветки diverged и несколько движков | Сверить E01–E09 SHA/artifacts и закрепить dataset hashes/manifests |
| E09 factorial | PARTIAL | 24 клетки заявлены в журнале | Сверить run commit SHA, job logs, 3 CSV и фактические различия факторов |

## Ключевые непроверенные риски
1. Корректность порядка исполнения входа/выхода на одной OHLC-свече.
2. Влияние funding и реальных Bybit комиссий.
3. Реалистичность maker fills.
4. Look-ahead и leakage через market context / universe.
5. Влияние порядка обработки символов на общий портфель.
6. Реальная устойчивость edge по каждому fold, инструменту и независимому периоду.

## Межветочный аудит (2026-11-02)

- `research/bybit-funding-data-v1`: funding integration существует отдельно, не включена в текущую ветку; mark-price hourly open — proxy, не точный settlement tick.
- `research/data-adapter-v1`: adapter проверяет ожидаемый interval и общий timestamp intersection; кандидат на точечное исправление P1.
- `research/v15-donchian-signal`: isolated simulator и portfolio replay; replay overlay не является полноценной portfolio simulation.
- Подробности: `BRANCH_COMPARISON_AUDIT_RU.md`.


## Regression tests added — 2026-11-02

| Area | Status | Evidence | Limits |
|---|---|---|---|
| Configured candle timeframe | TESTED | `test_timeframe_validation.py`; CI 41356694461 | Does not validate exchange candle source correctness |
| Portfolio MTM equity identity | TESTED | `test_portfolio_accounting.py`; CI 41356694461 | Focused unit test, not full multi-event simulation |
| TP1 partial-position mark accounting | TESTED | `test_portfolio_accounting.py`; CI 41356694461 | Does not test every stop/trailing path |
| Risk-budget cap and zero-budget rejection | TESTED | `test_portfolio_accounting.py`; CI 41356694461 | Does not prove fair allocation across simultaneous symbols |
| Closed trade PnL/fees/slippage/equity reconciliation | TESTED | `test_portfolio_accounting.py`; CI 41356694461 | Uses deterministic fixture and modeled fee constants |
| Symbol-order invariance | FIXED / TESTED | `test_simultaneous_entries_share_risk_budget_independent_of_symbol_order`; CI 41356881313 | Equal risk split; scarce slots ranked by vol_ratio, symbol tie-break; same-bar freed risk not redistributed |
| Funding, margin tiers, liquidation | NOT_TESTED | No complete exchange model in active engine | Must not infer safety from backtest risk budget |

- Latest portfolio accounting CI: [41356762102](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41356762102), commit `36bd4b8f8a448207d9d74f439d39bdc345853624` — passed, including the test that reproduces symbol-order dependence.


| Stop-candle MAE/MFE | TESTED / FIXED | Long+short wick-order regression tests; CI 41357102546 | OHLC still cannot reconstruct the true intrabar path; favorable excursion on stop candle is intentionally not credited |


## 2026-11-02 — lifecycle regression additions

`test_gap_execution.py` now includes four additional deterministic cases:
- pending entry is removed when the risk gate rejects it;
- fill-bar stop handling for long and short does not count favorable wick as MFE and caps MAE at modeled stop fill;
- a newly calculated trailing stop is not applied retroactively to the same OHLC candle.

Commit: `c46178d624fa441ee2c5bd684beb42f5c5db3dbd`.
Workflow `research-checks.yml` is configured to run on pushes touching `test_*.py` in the active research branch. The available workflow-run lookup did not return a run for this push commit; therefore execution status is **pending/unverified**, not passed. Do not count these tests as CI evidence until a completed run is inspected.

## 2026-11-02 — exchange realism coverage gaps

Not yet modeled/tested in v14:
- instrument quantity/price tick constraints (`qtyStep`, `minOrderQty`, `minNotionalValue`, `tickSize`);
- initial/maintenance margin, risk tiers, liquidation price/fees;
- funding settlement cashflows;
- mark/index/premium price effects on PnL and liquidation.


## v15 multi-bar pending integration coverage

- Added end-to-end test: a pending limit order remains alive after the first untouched eligible bar and fills on the second valid bar.
- Added end-to-end test: an unfilled pending limit expires after the configured number of valid bars.
- Added focused workflow `.github/workflows/v15-unit-checks.yml` on `research/v15-donchian-signal` pushes touching v15 code/tests.
- Commits: test `4d9f6f4274d95ded88c67cb563e42cd73baa3c92`; workflow `0305c8229329b56f7c374adce33601ad08b803f5`.
- CI execution is not yet verified; do not treat tests as passed until run result is inspected.
