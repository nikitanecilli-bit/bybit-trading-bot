# Матрица покрытия аудита и исследовательских гипотез

Статус относится к подтверждённым доступным материалам на 2026-11-02, а не к обещанию корректности.

| Область | Статус | Что известно | Что требуется |
|---|---|---|---|
| Архитектура репозитория | PARTIAL | Найдены engine, downloader, scripts, workflows, reports, tests | Сверить все ветки и зависимости |
| Live execution / безопасность | PARTIAL | README утверждает, что v14 research engine не отправляет ордера | Проверить весь репозиторий/ветки на API order endpoints |
| Свечи и временные метки | PARTIAL / P1 | Есть `test_time_model.py`; обнаружено, что CSV равномерность проверяет, но интервал не сравнивает с `cfg.timeframe` | Добавить тесты mismatch и уточнить open/close timestamp semantics |
| Session boundary semantics | PARTIAL | `scripts/audit_h1_entry_session_boundary.py` сравнивает signal-candle и next-entry-bar session; native `blocked_sessions_utc` использует timestamp сигнальной свечи, журнал — timestamp фактического fill | Не менять семантику без отдельной гипотезы; если цель — блокировать сессию входа, добавить отдельный entry-session gate и проверить shared-capital replay |
| Look-ahead | PARTIAL | Основной signal core использует только предыдущие бары для Donchian/ATR; полный аудит scripts/features/folds не завершён | Статический аудит всех сигналов/фич/выходов и fold construction |
| Stop/TP внутри свечи | PARTIAL | `test_gap_execution.py`: long/short stop-vs-TP1/TP2 collision, fill-bar stop, trailing-stop timing; `test_time_model.py`: kill-switch vs TP2 same-bar collision (ENG-KS-001) | OHLC не раскрывает реальный порядок high/low; проверить time-stop/TP collisions, multi-position risk-trigger sequencing и execution proxy |
| Market gap execution | PARTIAL | `test_gap_execution.py` и gap report существуют | Повторить тесты, проверить точное покрытие |
| Limit fills | PARTIAL | `test_gap_execution.py`: marketable gap-through long/short классифицируются как taker; обычный OHLC touch остаётся maker proxy; fees/slippage per leg проверяются | Нет bid/ask, queue priority, partial fill, cancellation latency и adverse selection; non-gap maker touch остаётся оптимистичным proxy |
| Fees | PARTIAL | В v14 есть maker/taker fees per leg; в v15 отдельная модель fee/slippage | Сопоставить тарифы, maker/taker по каждой ноге и rounding |
| Slippage | PARTIAL | В движке есть модель slippage | Проверить применение к фактической цене и sizing |
| Funding | PARTIAL / PROXY | В текущей ветке v14 есть optional `--funding-dir` + `--mark-price-dir`; cumulative funding входит в MTM и close PnL, есть tests на settlement boundary, TP1 quantity и missing marks | Funding отключён, если директории не заданы; qty derived from notional/entry price, hourly mark candle open — proxy, не подтверждённый settlement mark; старые E11/E13 результаты funding-adjustment не имеют |
| Position sizing / leverage | PARTIAL / MARGIN NOT MODELED | Есть risk-budget sizing и per-position notional cap `equity * leverage / max_concurrent_positions * 0.95`; отдельный Decimal helper переводит notional в Bybit qtyStep/min/max, но engine его не вызывает | Нет exchange qty в позиции, aggregate margin, maintenance-margin tiers, liquidation price/fees и isolated/cross reconciliation; нельзя трактовать leverage cap как модель ликвидации |
| State persistence / restore | PARTIAL | ENG-STATE-003/004: fail-closed load/save; ENG-STATE-005: transactional restore; ENG-STATE-006: pending schema; ENG-STATE-007: position schema; ENG-STATE-008: TP1 invariants; ENG-STATE-009: identity consistency; ENG-STATE-010: complete envelope and risk snapshot; 33 persistence regression tests | Нет Bybit reconciliation, explicit legacy backup migration, freshness policy, fsync/remote durability and proof restored pending signals match active exchange orders |
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
1. Оставшиеся OHLC path ambiguities для time-stop/TP и межсимвольной portfolio sequencing; текущие stop/TP collision cases имеют regression coverage.
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


## 2026-11-02 — instrument spec helper coverage

Added `test_bybit_instrument_specs.py` for versioned snapshot parsing, Decimal buy/sell tick rounding, quantity step flooring, min/max quantity, min notional, tick alignment, zero-rounded price, and missing required fields. `research-checks.yml` now compiles the helper/test and runs the dedicated test file. The workflow-run connector only exposes PR-triggered runs and returned no run for the relevant push; CI remains **unverified**. No v14 execution path imports the helper yet.

## 2026-11-02 — instrument snapshot and funding helper tests

- `test_snapshot_bybit_instruments.py`: pagination, sorted universe, duplicate handling, cursor-loop rejection, empty response, provenance and atomic JSON write.
- `test_funding_accounting.py`: cumulative as-of boundary, long/short sign, TP1 close-boundary quantity, missing exact marks, duplicate settlements and invalid position state.
- Both are included in `research-checks.yml`; workflow execution remains unverified because the available GitHub Actions connector does not expose push-triggered run listings.

## 2026-11-02 — funding integration regression coverage

- `test_funding_accounting.py`: pure cumulative helper, settlement inclusivity, long/short sign, partial TP1, missing mark and duplicate protection.
- `test_funding_pnl.py`: realized close net PnL, TP1 quantity boundary, exit boundary, missing mark, empty funding file, and exact Decimal preservation for funding rates/mark prices.
- `test_funding_mark_to_market.py`: accrued funding reduces open-position unrealized PnL before close, future settlements excluded, missing marks fail closed, TP1 timestamp captured.
- All three are added to `research-checks.yml`; CI status is **unverified** until a completed Actions run is inspected.

## 2026-11-02 — as-of instrument specification history

`test_instrument_spec_history.py` covers UTC as-of selection, refusal to use future snapshots, max-age enforcement, full-universe missing-symbol handling, non-Trading status, duplicate timestamps and invalid snapshots. `test_bybit_instrument_specs.py` additionally covers separate `maxOrderQty`/`maxMktOrderQty` and permits non-tick-aligned market reference prices while requiring tick alignment for limit prices. Added to `research-checks.yml`.

## 2026-11-02 — funding data coverage preflight

`test_funding_coverage.py` проверяет полное timestamp совпадение funding settlements с mark-candle opens, отсутствующие symbol-файлы, пустые события и дубликаты. Добавлен в `research-checks.yml`. Это проверка completeness/temporal alignment, не подтверждение того, что mark-candle open равен фактической settlement mark price.

## v15 multi-bar pending integration coverage

- Added end-to-end test: a pending limit order remains alive after the first untouched eligible bar and fills on the second valid bar.
- Added end-to-end test: an unfilled pending limit expires after the configured number of valid bars.
- Added focused workflow `.github/workflows/v15-unit-checks.yml` on `research/v15-donchian-signal` pushes touching v15 code/tests.
- Commits: test `4d9f6f4274d95ded88c67cb563e42cd73baa3c92`; workflow `0305c8229329b56f7c374adce33601ad08b803f5`.
- CI execution is not yet verified; do not treat tests as passed until run result is inspected.
