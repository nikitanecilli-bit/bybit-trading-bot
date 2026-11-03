# Матрица покрытия аудита и исследовательских гипотез

Статус относится к подтверждённым доступным материалам на 2026-11-03, а не к обещанию корректности. Для текущей интеграции exchange sizing/liquidation этот файл superseded by `docs/audits/EXECUTION_INTEGRATION_REAUDIT_2026-11-03.md`; для Net R/MAE/MFE/MTM — `docs/audits/PORTFOLIO_ACCOUNTING_NET_R_MAE_MFE_AUDIT_2026-11-03.md`. Ни зелёный CI, ни наличие моделей не подтверждают реальный Bybit PnL.

| Область | Статус | Что известно | Что требуется |
|---|---|---|---|
| Архитектура репозитория | PARTIAL | Найдены engine, downloader, scripts, workflows, reports, tests | Сверить все ветки и зависимости |
| Live execution / безопасность | PARTIAL | Research engine заявлен как simulator; 7 branch versions of `Bybit_Trading_Engine_v14_research.py` checked with no order mutation endpoint matches; ENG-SEC-001 private API preflight hardened (10 mocked tests) | Scoped scan is not a full historical/repository proof; continue checking remaining scripts/workflows; no live execution authorization |
| Bybit private API credential preflight | ACCEPT (code/fixtures only) | ENG-SEC-001: 10 tests passed; only official host allowlist, HTTPS, no redirects, integer `retCode=0` and integer `readOnly=1`; CI #41469608200 | No real key or API request used; actual key permissions remain unverified until manual read-only workflow run |
| Свечи и временные метки | TESTED / PARTIAL | `test_timeframe_validation.py` проверяет соответствие интервала конфигу; строгий H1 runner проверяет UTC-hour alignment, непрерывность и совпадение symbol с filename; CI #41678760487 | Корректность исходного exchange feed и внутрисвечной path всё равно не доказывается OHLCV |
| Session boundary semantics | PARTIAL | `scripts/audit_h1_entry_session_boundary.py` сравнивает signal-candle и next-entry-bar session; native `blocked_sessions_utc` использует timestamp сигнальной свечи, журнал — timestamp фактического fill | Не менять семантику без отдельной гипотезы; если цель — блокировать сессию входа, добавить отдельный entry-session gate и проверить shared-capital replay |
| Look-ahead | PARTIAL | Основной signal core использует только предыдущие бары для Donchian/ATR; полный аудит scripts/features/folds не завершён | Статический аудит всех сигналов/фич/выходов и fold construction |
| Stop/TP внутри свечи | PARTIAL | `test_gap_execution.py`: long/short stop-vs-TP1/TP2 collision, fill-bar stop, trailing-stop timing; `test_time_model.py`: kill-switch vs TP2 same-bar collision (ENG-KS-001) | OHLC не раскрывает реальный порядок high/low; проверить time-stop/TP collisions, multi-position risk-trigger sequencing и execution proxy |
| Market gap execution | PARTIAL | `test_gap_execution.py` и gap report существуют | Повторить тесты, проверить точное покрытие |
| Limit fills | PARTIAL / GAP-AWARE | `test_gap_execution.py`: marketable entry gaps and TP1/TP2 target gaps classify as taker; long/short target gaps covered; TP1 liquidity flag persists and is used by MTM + final close; CI #41720537099 SUCCESS 52/52. Current Bybit H1 runner: 20 bps offset, 5 bps penetration, 3 H1 bars TTL | No bid/ask, queue priority, partial fill, cancellation latency or adverse selection; non-gap maker touch remains optimistic proxy. Existing h1-limit-fill-stress uses Binance OHLCV + independent per-symbol capital, not Bybit shared-capital validation; a Bybit-native sensitivity remains queued behind Funding gate |
| Multi-bar pending limit wait in H1 portfolio harness | FIX IMPLEMENTED / TESTED (research harness only) | `multibar_limit_wait.py` + H1 wrapper adapt freshness guard on actual fill while retaining original signal time; `OpenPositionState.signal_ts_ms` and `TradeRecord.signal_ts_ms` now preserve origin through JSON journal; audit: `H1_LIMIT_WAIT_SCRIPT_AUDIT_2026-11-03.md`; CI #41684988411, portfolio accounting 46/46, state persistence 68/68 | OHLC penetration remains an optimistic fill proxy; no queue, spread, latency, partial-fill or adverse-selection model. No market PnL run is implied |
| Fees | CORRECTED / TESTED; GAP-AWARE TP LIQUIDITY | v14 charges entry, TP1 and final exit on each leg's execution notional; TP1/TP2 limit gaps through candle open now use taker fee + slippage, ordinary intrabar touches retain configured maker proxy; TP1 liquidity survives restore; CI #41720537099 SUCCESS 52/52 | VIP/region-specific fee rates remain fixed assumptions; non-gap maker fill/queue model remains optimistic; no L2, spread, partial fills or adverse selection |
| Slippage | PARTIAL | В движке есть модель slippage | Проверить применение к фактической цене и sizing |
| Funding | PARTIAL / PROXY; TP1 + ENTRY-BOUNDARY ALLOCATION CORRECTED; UTC GRID CHECK ADDED | Cumulative funding enters MTM/close PnL; exact entry-boundary payments charged and receipts excluded; after TP1, historical Funding is prorated to exact remaining quantity for isolated-margin health; stable dated fundingInterval snapshots now independently reconstruct expected UTC grid; unresolved observed interval changes fail closed; new manifest/downloader regressions and saturated-page chain fixture passed Research CI #41719390878 (52/52) | No Bybit funding/Mark archive; equal snapshots cannot rule out interval change/reversion between observations; live snapshot collector remains blocked by HTTP 403; settlement price uses timestamp-aligned Mark candle-open proxy; position-level model applies net Funding to position margin without account available-balance ledger (may overstate or understate liquidation risk depending on sign/balance); E11/E13 funding omitted |
| Position sizing / leverage | INTEGRATED / DATA-GATED | `_try_fill_pending()` selects dated instrument specs, validates leverage/risk tier and calls `size_to_exchange_constraints()`; exact contract qty, qtyStep, minQty/minNotional, TP1 floor and final reduce checks are stored; CI #41685190246 | Dated Bybit snapshots are not committed, so replay is fail-closed. Position-level isolated margin is not account-wide UTA/Cross/Portfolio Margin; see execution re-audit |
| State persistence / restore | PARTIAL / TESTED | ENG-STATE-003…018: fail-closed schemas, transactional restore, TP1 invariants, UTC metadata, strict JSON and fsync; 68 persistence tests. `signal_ts_ms` round-trips and older backups without the optional field restore as `None`; CI #41685190246 | Нет exchange reconciliation; нет proof restored pending signals match active exchange orders; no absolute hardware durability guarantee |
| Portfolio shared capital | TESTED / PARTIAL | Shared-capital replay preallocates bar-open risk/slots before symbol execution; simultaneous-entry permutation, same-bar freed-slot reservation, sparse/dense timeline and exit-timestamp drawdown regressions; CI #41685190246 | Historical PnL data still proxy/survivor-selected; OHLC cannot prove intrabar path or live fills |
| MTM maker-vs-taker exit-cost consistency | DOCUMENTED / TESTED | Open MTM reserves taker fee+slippage for remaining size while final modeled maker TP can use maker fee; exact delta and daily-stop threshold behavior are pinned by regressions; CI #41685190246, portfolio accounting 47/47 | Conservative stress proxy may trip risk gates earlier than a real maker fill; do not relax without queue/fill evidence |
| Leverage / margin / liquidation model | PARTIAL / POSITION-LEVEL ISOLATED | Dated risk-tier integration, entry IM/MM, exact remaining quantity, funding-aware Mark OHLC liquidation and bankruptcy settlement are integrated; CI #41685190246 | No partial liquidation ladder, shared collateral, Cross/Portfolio Margin, auto-add/manual margin or exact exchange rounding; real account mode remains unconfirmed |
| Linear exchange sizing integration | INTEGRATED / SNAPSHOT-DATA GATED | `_try_fill_pending()` uses as-of Linear instrument specs and exact Decimal contract sizing; TP1/final-leg quantity validation and position/TradeRecord provenance; CI #41685190246 | No historical Bybit snapshots committed; this integration cannot produce valid exchange-aware replay until data coverage gate is met |
| Concurrency / risk gates | TESTED / PARTIAL | Deterministic preallocation, simultaneous-entry order invariance, same-bar slot reservation, independent daily/kill latches and portfolio flattening tests; CI #41685190246 | Conservative policy leaves a slot unused for the bar if its pre-ranked limit candidate does not fill; not proven PnL-optimal |
| TradeRecord / journal provenance | TESTED / PARTIAL | `signal_ts_ms` survives delayed fills, state restore and `export_journal_for_dashboard()` JSON; exchange quantity/tier and TP1/remaining-leg provenance retained; sub-micro prices/stop distances preserve 12-decimal precision; CI #41685190246, portfolio accounting 47/47 | No exchange execution ID/fill ledger; journal is simulation provenance, not exchange reconciliation |
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

Added `test_bybit_instrument_specs.py` for versioned snapshot parsing, Decimal buy/sell tick rounding, quantity step flooring, min/max quantity, min notional, tick alignment, zero-rounded price, and missing required fields. `research-checks.yml` now compiles the helper/test and runs the dedicated test file. Full Research checks now verify the helper and test suite; latest full run #41468327832 passed. No dated live instrument snapshot has been captured. No v14 execution path imports the helper yet.

## 2026-11-02 — instrument snapshot and funding helper tests

- `test_snapshot_bybit_instruments.py`: pagination, sorted universe, duplicate handling, cursor-loop rejection, page cap, strict retCode, official host allowlist, non-Bybit host rejection, provenance and atomic JSON write.
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

| Bybit public instrument snapshot collector | ACCEPT (code/fixtures only) | ENG-DATA-001: 13 deterministic tests; official-host allowlist, no redirects, strict retCode, cursor validation and page cap; full CI #41468736376 | Live public API capture remains BLOCKED: regional endpoint run #41468304134 returned HTTP 403; no dated snapshot archived |
| Bybit V5 reconciliation parsing | PARTIAL | ENG-RECON-002: pure positions/orders/executions parsers; pagination chain, identity checks and optional position TP/SL fields; 16 fixture tests | Exact local qty/positionIdx/order IDs/execution ledger still absent; overall reconciliation BLOCKED |
| Bybit V5 read-only snapshot collector | ACCEPT (code/fixtures only) | ENG-RECON-003/006: 15 mocked collector tests passed in Actions #41470373006; host allowlist, redirect refusal, positions, active orders, historical orders, executions, server-time bounds and 7-day cursor windows and explicit USDT execution filter | No real Bybit snapshot/API call; historical orders are partial under documented 24h/7d retention rules; exact local qty/positionIdx/order IDs/execution ledger absent |
| Bybit V5 report-only comparator | ACCEPT (diagnostic only) | ENG-RECON-004/006: 17 tests passed in Actions #41470373006; verifies raw hash, parser/count integrity, UTC chronology, interval continuity, historical-order IDs/statuses, symbol/direction and stop-protection diagnostics | Always returns BLOCKED; historical order API is not a complete journal; no real Bybit snapshot; exact local qty/positionIdx/order IDs and execution ledger absent; no live resume |

| Bybit V5 position TP/SL visibility | ACCEPT (field coverage only) | ENG-RECON-005: parser preserves takeProfit/stopLoss/trailingStop/tpslMode; comparator distinguishes configured, absent and unknown stop fields; CI #41468736376 | No real position snapshot; does not prove conditional-order health or trigger execution; reconciliation remains BLOCKED |

| Bybit V5 historical order capture | ACCEPT (partial API coverage only) | ENG-RECON-006: 15 collector tests + 17 comparator tests passed in #41470373006; cursor pagination, orderId deduplication, retention metadata | API omits cancelled/rejected/deactivated orders beyond 24h and only exposes filled orders beyond 7d; endpoint may be delayed; not a complete outage journal |

- Bybit public snapshot acquisition: BLOCKED / HTTP 403. Instrument snapshot workflow runs #7–#10 failed during API download; decoded logs show HTTP 403. Host list corrected; branch-scoped runs #41533728951 (instrument) and #41533743884 (risk tiers) failed with HTTP 403 from every official regional host. No dated instrument/risk-tier archive committed. Schedule/dispatch remain dormant until workflow files are on default branch. Schedule/dispatch are dormant until workflow files are on default branch. See `EXCHANGE_SIZING_INTEGRATION_AND_BYBIT_SCHEMA_2026-11-03.md`.

- Execution-notional fee correction: CI #41536540759 passed. Prior per-symbol H1/15m net-PnL results are provisional until rerun because old exits used entry notional for exit fees/slippage. See `EXCHANGE_SIZING_INTEGRATION_AND_BYBIT_SCHEMA_2026-11-03.md`.


| Directional H1 scope | LONG-ONLY RESEARCH VARIANT | Current H1 shared-capital runner filters non-long signals; Top-5 selector reuses the same runner, so selection is long-only. Historical E01 direction ablation is proxy / independent-symbol only. Audit: H1_DIRECTIONAL_SCOPE_AUDIT_2026-11-03.md | No Bybit-native shared-capital long-only vs short-only vs both comparison; do not generalize current H1 results to two-sided strategy. Directional ablation is queued behind Funding completeness gate |
