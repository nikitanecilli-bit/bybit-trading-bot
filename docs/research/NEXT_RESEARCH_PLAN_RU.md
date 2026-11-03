# План аудита и исследований (без новых рыночных тестов)

## Фаза 0 — организация
- [x] Создать единый вход `docs/README_RU.md`.
- [x] Создать `AGENTS.md` с правилами работы.
- [x] Создать первичную матрицу покрытия и аудит-реестр.
- [ ] Проверить ссылки, workflow path dependencies и secret hygiene.

## Фаза 1 — воспроизводимость экспериментов
1. Собрать для E01–E09: run ID, workflow, commit SHA, dataset, конфиг, folds, costs, artifacts.
2. Сопоставить run SHA с версиями скрипта и движка.
3. Проверить завершение каждого job, ошибки, тестовые counts, artifact contents.
4. Пометить старые результаты без первичных данных как UNVERIFIED.
5. Выявить дублирующие эксперименты и причинно зависимые результаты.

## Фаза 2 — аудит движка
Проверять в таком порядке:
1. Candle/time model и отсутствие look-ahead.
2. Сигналы, warm-up, индикаторы и контекст.
3. Pending orders и fills.
4. Stops, targets, trailing, break-even и intra-bar collision.
5. Fees/slippage/funding.
6. Sizing, leverage, margin и liquidation.
7. Portfolio shared capital, risk gates, concurrency.
8. Trade journal и метрики.

Для каждого дефекта: severity, file/function, минимальный reproduction, влияние на результаты, regression test. Не менять поведение без теста и записи.

## Фаза 3 — качество данных
- Инвентаризировать все ZIP и внутренние CSV: symbols, timeframe, date range, row count, duplicate/missing candles.
- Определить источник данных и стабильность формата.
- Проверить Bybit vs Binance proxy; не заявлять Bybit holdout при HTTP 403.
- Проверить universe survivorship и исключённые инструменты.

## Фаза 4 — исследовательские выводы
- Пересчитать только то, что нужно для проверки целостности существующих результатов; новые сетки параметров запрещены до закрытия аудита.
- Отдельно оценить устойчивость по fold и symbol, concentration, drawdown, trade count.
- Не подгонять стратегию по holdout.
- Вернуться к market-regime / false-breakout / maker execution только после устранения критических методологических рисков.

## Критерий завершения аудита
Аудит завершён, когда у каждого исторического эксперимента есть воспроизводимая ссылка на commit/run/artifact либо явная метка UNVERIFIED; ключевые торговые механики движка покрыты проверками; критические ограничения исполнения и данных документированы; следующий тест отвечает на новый вопрос и не дублирует предыдущий.


## Обновление 2026-11-02 — автономный аудит

Завершено:
- Timeframe CSV validation исправлена и regression-tested.
- Portfolio MTM, TP1 partial mark, risk sizing budget и close PnL/fee/slippage reconciliation покрыты deterministic tests.
- Подтверждённая зависимость одновременного распределения риска от порядка symbols исправлена пакетным распределением: equal risk share among eligible signals; slot priority = vol_ratio descending, symbol tie-break.
- Технический CI отделён от рыночных backtests; market experiment workflows переведены на ручной запуск.
- Static scan не нашёл live order endpoints в Python engine copies и active research scripts.

Следующие задачи (без новых market backtests):
1. Полный audit lifecycle: pending-order expiry/retry, stop/TP collision, trailing-stop update timing, same-bar fills.
2. Margin/leverage/liquidation approximation and exchange quantity/tick constraints.
3. Funding integration review and timestamp semantics.
4. Проверка journal metrics: net R denominator, MAE/MFE, drawdown and per-period aggregation.
5. Reconcile E01–E09: run SHA, script SHA, config, data manifest, folds, costs, artifacts. Missing evidence => UNVERIFIED.
6. Check archive/CSV integrity and data provenance.
7. Только после закрытия этих пунктов — решить, какие исторические результаты нужно воспроизвести на исправленном engine. Не начинать parameter search.

Последний подтверждённый технический CI: [41356881313](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41356881313), commit `3246eb1df4b9d4cfbd109fa6e6a6316e44710200` — success.


## Обновление 2026-11-02 — lifecycle review

Завершён первичный статический просмотр `step_candle` / `_try_fill_pending` / `_manage_position`:
- Pending сигнал живёт одну следующую свечу; no-touch, chase reject и risk reject удаляют его без retry.
- Limit touch fill не моделирует очередь, спред, partial fill или adverse selection.
- Stop имеет приоритет над TP при неоднозначном OHLC same-bar событии.
- Fill-bar stop может учитывать экстремум, который был до фактического входа; favourable excursion на fill bar исключён.
- Trailing stop, рассчитанный по текущей свече, применяется только к последующим свечам.

Следующий безопасный порядок:
1. Добавить тесты, фиксирующие фактические one-bar pending semantics и fill-bar/trailing timing (без изменения поведения).
2. Проверить, одинаково ли runners интерпретируют лимитную заявку и TTL; расхождения описать, не исправляя молча.
3. Продолжить аудит TP/stop/trailing и portfolio event ordering; отдельно проверить long/short симметрию.
4. Затем margin/leverage/quantity-tick и funding timestamp semantics.
5. Только после завершения аудита — воспроизводимость E01–E09 и data archive integrity. Новые market backtests и parameter search пока запрещены.


## 2026-11-02 — exchange realism gate before profitability claims

Static review confirms that v14 sizing is a notional approximation, not a Bybit margin/contract execution model:
- no quantity conversion to `qtyStep` / `minOrderQty` / `minNotionalValue`;
- no price tick rounding;
- no initial/maintenance margin, risk tiers or liquidation;
- historical funding files can be downloaded, but funding cashflows are not charged;
- mark/index/premium datasets can be downloaded, but mark-price liquidation and basis effects are not modeled.

Do not treat old H1 PnL as exchange-executable net performance until these are implemented. **Completed as isolated groundwork:** `bybit_instrument_specs.py` parses Decimal tick/lot/min-notional constraints (including separate max market/limit quantity caps); `instrument_spec_history.py` selects the latest complete snapshot at or before a backtest timestamp and fails closed on future/stale/missing specs. Tests cover rounding, boundaries and as-of selection. Neither is yet wired into v14; no historical snapshots have been confirmed in the archive. Next: verify CI, add date-versioned instrument-spec collection, then funding cashflow accounting; margin/liquidation follows once the spec/data schema is stable.


## Completed groundwork — dated specs and pure funding accounting

- `scripts/snapshot_bybit_instruments.py` archives raw Bybit V5 instrument-info responses with UTC timestamped filenames and pagination/duplicate guards; a dedicated Actions workflow is configured to populate `data/instrument_specs/linear/`.
- `funding_accounting.py` provides a single cumulative as-of calculation with timestamp-aligned hourly mark-candle-open proxies (not guaranteed to equal the exchange settlement mark) and conservative TP1 boundary semantics; offline tests cover long/short sign, settlement inclusivity, missing marks, duplicates and partial TP1.
- The instrument collector is not yet confirmed to have produced its first artifact. Funding helper is now wired into v14 mark-to-market and final close; do not claim exchange-realistic PnL until CI passes and funding/mark data coverage is validated for every symbol and settlement.

## Funding integration — first isolated pass implemented

В активной ветке добавлен `funding_accounting.py` и подключён к v14 через один cumulative as-of helper:
- `_unrealized_pnl_at_marks(as_of_ts)` вычитает accrued funding с открытых позиций до проверки daily stop / kill-switch;
- `_close_position()` использует тот же helper на `exit_ts` и вычитает funding из realized net PnL;
- `TradeRecord.funding_cost_usdt` и summary `total_costs`/`funding_cost_usdt` сохраняют раздельную видимость funding;
- `OpenPositionState.tp1_ts_ms` фиксирует консервативную границу закрытия TP1; settlement на этой границе относится к полному исходному notional, более поздние settlements — к оставшемуся объёму;
- CLI принимает `--funding-dir` и `--mark-price-dir`; оба аргумента обязательны парой, missing CSV/timestamp-aligned mark-candle proxy завершаются ошибкой, а не молча исключаются.

Добавлены тесты pure helper, realized close, mark-to-market risk и mark-price loader. Это первый интеграционный этап; перед любыми PnL-выводами требуется фактический CI run и отдельная проверка funding coverage/mark timestamp alignment для каждого инструмента. Funding не добавляет mark-price OHLC intrabar liquidation model. Добавлен preflight `scripts/validate_funding_coverage.py`, который проверяет для каждого символа наличие funding/mark CSV, уникальность timestamp и полное совпадение funding settlements с timestamp mark-candle open. Запуск перед funding-adjusted backtest: `python scripts/validate_funding_coverage.py --funding-dir data/funding --mark-dir data/mark_price --symbols BTCUSDT,ETHUSDT,...`. Если coverage неполный, скрипт завершается с ошибкой; не запускать PnL-анализ на неполном архиве.


## v15 execution-ablation coverage

Multi-bar pending logic в `research_v15/backtest.py` при статической проверке сохраняет заявку, если лимитка не исполнилась; предыдущая гипотеза об unconditional deletion отозвана. Добавить end-to-end тест `backtest_symbol()` с лимиткой, не затронутой на первой допустимой свече, но исполненной на второй, и тест expiry после N валидных свечей. Это пробел тестового покрытия, не подтверждённый дефект. Не менять реализацию без failing test.


## Operational caveats — branch and snapshot automation

- `research/market-regime-v1-main` is currently diverged from `main`: 3 commits behind and more than 200 research commits ahead. Do not merge/rebase automatically; first review the three incoming main commits and branch-wide workflow changes.
- The snapshot workflow has push/manual triggers on the research branch. Its daily cron is only activated by GitHub after the workflow file is present on the repository's default branch; until then, the daily schedule is dormant. The first committed snapshot is not yet verified.
- GitHub connector status lookup returned no check statuses for recent push commits; this is **unverified**, not a passing CI result.


## Exchange quantity sizing groundwork

`exchange_order_sizing.py` now converts target notional into Bybit-valid quantity using the spec helper, tick-rounds limit prices, floors quantity, enforces separate market/limit max quantity and min constraints, and scales estimated risk down with actual rounded notional. It is tested but not wired into v14. Next integration must store actual qty in each position and use the same qty for PnL/funding; no order splitting is modeled. Wait for verified timestamped specs before applying this to historical bars.


## 2026-11-02 — E10/E11 update and next research action

### Completed
- E10 broad cross-sectional replication: 47 H1 symbols, per-symbol independent accounts, body gate OFF/2%, market execution. Gate reduced the summed independent loss but did not create positive expectancy; fold 1 worsened, folds 2/3 improved. See `docs/reports/E10_H1_BODY_GATE_CROSS_SECTIONAL_RU.md`.
- E11 shared-capital replay: same 47-symbol universe, one 10,000 USDT account per fold, max 5 concurrent positions. Body gate changed summed fold net from -3,178.61 to -2,774.00 USDT only; PF 0.859 -> 0.862. It reduced trade count but increased total fees+slippage. Strategy remains negative in folds 1 and 2. See `docs/reports/E11_H1_SHARED_CAPITAL_PORTFOLIO_RU.md`.
- Body gate 2% is NOT approved for production. No threshold sweep.

### Next action — regime-context diagnostics, no threshold optimization

Use the E11 shared-capital signal/trade timestamps and calculate only causal, completed-bar market context at each signal:
1. broad-universe positive breadth over 24h and 72h;
2. broad-universe median 24h/72h return;
3. broad-universe median 24h path efficiency;
4. BTC/ETH 24h/72h returns and efficiency as secondary context.

Stratify the existing shared-capital results by these features and by fold. First ask whether losing trades in fold 2, and replacement trades that helped/hurt body gate, were distinguishable before entry. Do not choose thresholds from the same PnL sample. If context separation is stable across symbols and folds, freeze one simple regime rule and test it once in the same shared-capital replay; retain a later untouched period for holdout.

### Guardrails
- No more body threshold sweeps.
- Do not sum per-symbol independent PnL and call it portfolio return.
- Keep one shared-capital replay as the decision metric.
- Preserve the three historical folds for diagnosis only; they are not blind holdout.
- Binance OHLCV proxy, funding omission, and Bybit execution-model limitations must remain explicit.
- No real orders.


### E12 diagnostic result — 2026-11-02

The fixed 47-symbol completed-bar context snapshot distinguishes three historical states:
- Fold 1: weak/mixed broad market, but winners often occurred at lower broad breadth/72h momentum than losers.
- Fold 2: lowest signal-time breadth, 72h median return, ATR and cross-sectional dispersion; winners/losers barely separated and all 72h-return terciles remained negative.
- Fold 3: broad trend expansion; winners clustered with higher breadth and positive 72h momentum.

Do not use a one-sided broad-market trend filter: it risks rejecting fold-1 winners. Next define a single causal compression classifier using rolling ATR + cross-sectional dispersion; keep local opportunities available in weak broad markets. No threshold sweep and no PnL replay until the rule is frozen. Full diagnostic: `docs/reports/E12_BROAD_MARKET_CONTEXT_DIAGNOSTICS_RU.md`.



### E13 compression gate result — 2026-11-02

A single causal rule (both broad median ATR% and cross-sectional IQR72 below expanding q25 of all prior completed hours; 336h warm-up) improved the sum of separate shared-capital folds from -3,178.61 to -2,741.72 USDT. Fold 1 and 2 improved; fold 3 lost part of its profit. PF 0.859 -> 0.870. The strategy remains negative in folds 1 and 2; this is not production-ready and not an untouched holdout.

Next:
1. Keep this exact rule frozen; do not sweep percentiles/window lengths.
2. Verify it on a genuinely later, untouched data period when available.
3. In parallel, audit execution realism (Bybit-specific spread/slippage/funding and instrument qty) before interpreting the modest PnL change.
4. Do not deploy or alter production configuration based on E13.

Full report: `docs/reports/E13_CAUSAL_COMPRESSION_GATE_RU.md`.



## Execution realism gate — audit 2026-11-02

Before any further strategy optimization, close the execution-data gaps documented in `docs/audits/EXECUTION_REALISM_READINESS_RU.md`.

Confirmed blockers:
- No dated `data/instrument_specs/linear` snapshot exists. GitHub Actions received HTTP 403 from all six tested Bybit regional API hosts, including after adding `--base-url` fallback.
- `exchange_order_sizing.py` and `instrument_spec_history.py` are not integrated into the research engine; engine positions store notional, not exchange-valid contract qty.
- Funding uses `size_usdt / entry_price` and timestamp-aligned mark-candle open proxy; E13 has funding disabled.
- Fee/slippage are constants stressed ×2, not measured symbol/time/size-specific spread or market impact. No order-book queue/partial-fill model.
- Bybit recent-data validation has no successful run in the available Actions history; E11/E13 use Binance OHLCV proxy.

Decision: do not launch another PnL sweep or promote E13. Next step is to obtain one dated full linear instrument snapshot and Bybit H1/mark/funding dataset through an accessible public-data route, validate coverage and hashes, then integrate exact qty into a research-only execution model. No API trading credentials are needed or should be used.

The snapshot collector now supports regional `--base-url` fallback; current runner access remains blocked (HTTP 403). No market data or snapshots were written.



## 2026-11-02 — переход к непрерывному улучшению

Принят обязательный [протокол непрерывного улучшения](CONTINUOUS_IMPROVEMENT_PROTOCOL_RU.md) и добавлен [шаблон предварительной карточки эксперимента](EXPERIMENT_CARD_TEMPLATE_RU.md).

Применение с этого момента:
- не искать один универсальный фильтр; измерять вклад каждого слоя системы и его взаимодействие с остальными;
- до любого рыночного теста фиксировать baseline, гипотезу, один изменяемый фактор, метрики, защитные ограничения и решение ACCEPT/REJECT/INCONCLUSIVE;
- сохранять все результаты и не использовать holdout для подбора параметров;
- не объявлять улучшение по aggregate PnL без разрезов по символам, периодам, направлениям, режимам, концентрации и общему капиталу;
- не запускать новые parameter sweeps и market PnL backtests до прохождения execution/data gate из `EXECUTION_REALISM_READINESS_RU.md`;
- продолжать безопасные deterministic tests, аудит lifecycle, сверку происхождения данных и восстановление воспроизводимости старых экспериментов.

Текущий приоритет не изменён: получить проверяемые Bybit данные и dated instrument specs, закрыть точный exchange sizing/funding/execution gaps, затем выполнить один заранее зафиксированный execution-aware replay без оптимизации параметров.


## 2026-11-02 — lifecycle/execution audit follow-up

Completed deterministic corrections:
- **ENG-KS-001:** kill-switch now overrides TP1/TP2/time-stop once the portfolio kill-switch has latched before position management. Regression test covers adverse intrabar mark and simultaneous TP2 touch. CI run 41431556111 passed; `test_time_model.py` 38/38.
- **ENG-EXEC-002:** marketable limit gap-through entries are classified as taker for sizing, MTM and journal entry costs; ordinary OHLC limit touch remains maker proxy. CI run 41431923590 passed; `test_gap_execution.py` 25/25 and `test_time_model.py` 38/38.
- Session-boundary audit 41428755424 recorded a semantic distinction: `blocked_sessions_utc` blocks based on signal-candle timestamp, while journal session uses actual fill-candle timestamp. No policy change is made; signal-time and entry-time gates must remain separate hypotheses.

Remaining execution/lifecycle limitations:
1. OHLC intrabar limit touch is not proof of maker fill; no spread, queue, partial fill, cancel latency or adverse selection.
2. Exact Bybit instrument specs and contract quantity are still not wired into the engine.
3. Funding uses proxy quantity/mark assumptions; Bybit data retrieval remains blocked on current Actions runner.
4. Session-block semantics must be explicitly selected before any future strategy test; do not silently reinterpret the existing `blocked_sessions_utc` setting.
5. Continue deterministic lifecycle tests and source audit; do not run new market PnL sweeps until the execution/data gate is closed.

No production/live changes and no market backtests were performed in these corrections.


## 2026-11-02 — state restore and leverage/margin audit

- **ENG-STATE-003 accepted:** existing but unreadable/incompatible Plan B backup now raises a fatal `RuntimeError`; only a genuinely missing file is treated as clean cold start. CI #41432693641 passed; `tests/test_state_persistence.py` 4/4.
- Important boundary: this is local file integrity only. There is still no reconciliation of restored positions/pending orders against Bybit open positions and active orders. A valid backup can be stale; do not treat this as permission for live resume.
- **Funding coverage matrix corrected:** the current research engine does support optional funding inputs via `--funding-dir` and `--mark-price-dir`; cumulative funding is included in MTM and close PnL when supplied. However quantity is still a notional/entry-price proxy and hourly mark candle open is not verified settlement mark. Historical E11/E13 results without these inputs remain unadjusted.
- **Leverage/margin remains unverified:** `calculate_position_size()` applies a notional ceiling of `current_equity * leverage / max_concurrent_positions * 0.95` per new position. The Bybit Decimal sizing helper is not wired into the engine. There is no aggregate margin ledger, maintenance-margin tier model, liquidation price/fee simulation, or exchange quantity in `OpenPositionState`. Do not interpret the leverage cap as a liquidation model.
- Next P0/P1: (1) exchange position/order reconciliation before any restore/live-resume; (2) exact exchange quantity integrated consistently into position gross PnL, fees, funding and risk; (3) isolated margin/maintenance tier and liquidation simulation using dated Bybit specs. These require verified point-in-time snapshots and must remain deterministic tests before any market backtest.
- No market backtest or parameter search was run in this audit cycle.


- **ENG-STATE-004 accepted:** when persistence is enabled, failed JSON write/atomic replace now raises `RuntimeError` and cleans up the current temporary file best-effort. CI #41432914403 passed; state persistence tests 6/6. A caller must stop rather than proceed with a stale recovery point.
- Durability remains incomplete: no explicit fsync of file/directory, remote backup, or exchange reconciliation. Do not equate atomic rename with guaranteed survival of power loss.


- **ENG-STATE-005 accepted:** restore now stages risk state in a temporary manager and validates root, positions, pending orders and trade sequence before mutating the caller's risk manager. Malformed backups leave the original risk state unchanged. CI #41433598794 passed; state persistence tests 9/9.
- Remaining persistence P0: compare restored local positions and active orders with Bybit before any resume; define stale-backup detection/schema versioning; fsync/remote durability. Transactional in-memory restore alone is not sufficient for live recovery.


- **ENG-STATE-006 accepted:** restored pending signals are now validated for required fields, symbol identity, direction, order type, strategy and finite numeric values. Malformed `pending_orders: []` / null containers are no longer silently converted to empty dicts. CI #41433992368 passed; state persistence tests 14/14.
- This closes local nested-payload validation only. Pending signals are not exchange orders; reconciliation with Bybit active orders remains a separate P0 before any resume.


- **ENG-STATE-006 accepted:** nested pending signal payloads are validated (required keys, direction, order type, finite prices/distances) before state commit. CI #41434308834 passed.
- **ENG-STATE-007 accepted:** restored positions reject unknown fields and invalid required/optional values rather than relying on dataclass annotations. CI #41434308834 passed; combined persistence suite 18/18.
- The state persistence matrix now tracks both pending and open-position schema validation. Remaining hard blocker is still exchange reconciliation and backup freshness; local JSON validity is not proof of exchange state.


- **ENG-STATE-018 accepted:** risk-manager restore now rejects unknown keys, NaN/infinity, non-positive equity, invalid drawdown range, malformed date and non-boolean flags before committing staged state. CI #41434930478 passed; persistence suite 23/23.
- Local backup schema now has separate validation for positions, pending signals and risk-manager fields. This still does not provide exchange reconciliation, backup freshness or crash durability; keep live-resume blocked until those are implemented and verified.


- **ENG-STATE-008 accepted:** restored position validation now checks TP1/TP2 directional ordering and cross-field consistency of TP1 flag, remaining quantity and realized TP1 PnL. Persistence regression suite 29/29; CI #41435897233 passed.
- Remaining hard blockers before any live recovery: exchange reconciliation, stale-backup policy/schema migration, and durability semantics. Local JSON/state invariants alone do not establish safe restart.


- **ENG-STATE-009 accepted:** restore rejects symbols present in both open positions and pending signals, and rejects duplicate trade IDs. Persistence tests 31/31; CI #41436083033 passed.
- The next persistence priority is required-field completeness and backup freshness. A syntactically valid but incomplete JSON object must not be mistaken for a valid empty portfolio snapshot.


- **ENG-STATE-010 accepted:** backup restore now requires complete envelope keys and complete known risk snapshot. Incomplete valid JSON can no longer silently become an empty portfolio or reset missing protective flags. Persistence suite 33/33; CI #41436427155 passed.
- Compatibility consequence: older backups missing current fields fail closed. Do not add silent defaults; implement explicit, versioned migration only after collecting actual legacy backup schemas.


- **ENG-STATE-011 accepted:** backup serialization now uses strict JSON (`allow_nan=False`); NaN/Infinity cannot replace a previously valid backup. Persistence tests 35/35; CI #41436653943 passed.
- Remaining persistence priorities: explicit legacy schema migration, freshness/reconciliation policy, and durability guarantees beyond atomic rename.


- **ENG-STATE-012 accepted:** risk restore checks cross-field identities (current = realized + unrealized, peak >= current, max drawdown covers implied drawdown). Persistence tests 39/39; CI #41444495022 passed. Keep historical max drawdown values above current drawdown; do not "normalize" them down.
- Next persistence work: validate timestamps/identity semantics and decide explicit versioned migration/freshness/reconciliation. Local consistency still does not prove Bybit state.


- **ENG-STATE-013 accepted:** backup restore now validates required `saved_at_utc` (ISO-8601, explicit UTC) and non-empty `bot_version`. Persistence tests 40/40; CI #41445058006 passed.
- Important boundary: this validates metadata shape, not backup age. A stale but correctly timestamped backup can still restore; define a freshness threshold and exchange reconciliation before any live resume.


- **ENG-STATE-014 accepted:** TP1-hit state requires a positive event timestamp no earlier than entry; untouched TP1 must not carry a TP1 timestamp. Persistence tests 43/43; CI #41445386482 passed.


- **ENG-STATE-015 accepted:** restored pending signals now require a valid signal-candle timestamp and can fill only on the immediately following configured-timeframe candle. Stale/gapped signals are discarded, not delayed. Persistence tests 48/48; gap-execution/time-model suites and CI #41446661723 passed.
- Next temporal integrity check: ensure restored event timestamps (entry, TP1, pending signal) cannot lie after the backup's own `saved_at_utc`. Keep freshness/age policy separate from this internal chronology check.


- **ENG-STATE-016 accepted:** restored position entry, TP1 and pending signal timestamps cannot be later than the backup's own UTC save timestamp. Persistence tests 51/51; CI #41447112303 passed.
- This is internal chronology only. Still define a conservative maximum backup age and reconcile against Bybit before any restart can be considered safe.


- **ENG-STATE-017 accepted:** enabled backup writes now flush/fsync the temp file before atomic replace and fsync the parent directory on POSIX. Persistence tests 53/53; CI #41447569454 passed. This improves crash durability but is not an absolute hardware guarantee.


- ENG-STATE-017 follow-up: POSIX parent-directory fsync failure after rename is explicitly tested; save raises even though the replacement file may be visible. Persistence suite now 54/54; CI #41447862710 passed.


## Exchange reconciliation — hard blocker

- Read [EXCHANGE_RECONCILIATION_READINESS_RU.md](../audits/EXCHANGE_RECONCILIATION_READINESS_RU.md). Current verdict: `UNSUPPORTED_LOCAL_MODEL / BLOCKED`.
- The engine lacks exact exchange contract qty, `positionIdx`, order IDs/link IDs and execution ledger; `size_usdt / entry_price` is not exact qty. Read-only API key verification alone is insufficient.
- Next safe implementation: pure response parser + fixture tests for V5 positions, active orders, executions and order history; pagination completeness and fail-closed handling first. Then report-only comparator. No mutation endpoints.


- **ENG-RECON-002 accepted:** pure Bybit V5 parser added; 12/12 fixture tests and CI #41448536690 passed. It validates caller-supplied pages only, not live collection.
- Next: read-only collector with explicit cursor loop, server-time/capture coherence and fail-closed errors. Do not wire restore or trading until exact local qty, positionIdx, exchange IDs and execution ledger exist.

- Parser hardening: only integer `retCode=0` counts as success; boolean false is rejected. Parser tests 13/13; CI #41448898597 passed.


## ENG-RECON-003 — read-only collector (2026-11-02, code/fixture ACCEPT)

- `scripts/bybit_reconciliation_snapshot.py`: only GET; API key must be explicitly read-only; official host allowlist is enforced before credentials are sent; redirects are refused; complete cursor pagination; server-time bounds; execution windows <= 7 days; SHA-256 raw capture and atomic fsync write.
- 12 mocked tests passed; full configured workflow #41459486381 SUCCESS. No live API call or real snapshot.
- Do not add credentials to CI or infer a successful exchange capture from fixture tests.

## ENG-RECON-004 — report-only comparator (2026-11-02)

- `scripts/bybit_reconciliation_report.py` validates backup/snapshot integrity, parser output, counts, UTC chronology and contiguous execution coverage; emits symbol/direction and protection diagnostics.
- 14/14 tests passed; full workflow [#41459486381](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41459486381) SUCCESS.
- Comparator never returns PASS and always sets `live_resume_allowed=false`. This remains intentional until local state has exact exchange qty, positionIdx, order IDs/link IDs and full execution ledger.

## ENG-RECON-005 — exchange-side position protection visibility (2026-11-02)

- Parser preserves Bybit position `takeProfit`, `stopLoss`, `trailingStop`, `tpslMode`; comparator distinguishes configured stop, absent stop and unknown fields.
- Parser 14/14, collector 12/12, comparator 14/14; full workflow #41459486381 SUCCESS.
- Position-level fields are not proof of conditional-order health or stop trigger execution. No real position snapshot was captured.

## ENG-RECON-006 — historical order capture (2026-11-02)

- Added paginated `GET /v5/order/history` capture in <=7-day windows, orderId deduplication and explicit partial-coverage metadata.
- 15 collector tests and 16 comparator tests passed; full configured workflow [#41460727701](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41460727701) SUCCESS.
- Bybit's documented history retention means the endpoint is not a complete event journal: Cancelled/Rejected/Deactivated statuses are queryable only within 24h; beyond 7 days only orders with fills are queryable; endpoint may be delayed.

## Next technical gates

1. Review and add conditional/TP/SL order identities from open orders and history where returned; position-level stop fields alone do not prove trigger-order health.
2. Design a complete local exchange execution ledger and state schema: exact exchange qty, positionIdx/account mode, orderId/orderLinkId, execId, partial fills, stop/TP identifiers and status.
3. Review account mode, margin mode and position-mode metadata needed to interpret positions and positionIdx; don't infer from row data alone.
4. Keep all network capture out of CI. Any live capture must use a Bybit-confirmed read-only key and remain a separately audited manual operation.
5. No PnL sweeps, live resume, order mutations or production deployment until execution/data gates are closed.

Do not infer exchange qty from `size_usdt / entry_price`.


## ENG-DATA-001 — instrument snapshot collector

- Hardened public metadata collector: official HTTPS host allowlist, redirects disabled, strict integer response code, cursor type validation and pagination safety cap.
- 13 mocked tests passed in full CI [#41468327832](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468327832).
- Live regional endpoint workflow [#41468304134](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468304134) returned HTTP 403. No dated snapshot was created; this is blocked access, not an empty instrument universe.
- Snapshot workflow is weekly/manual, not triggered by every code push. Do not substitute guessed instrument specs.
- Execution-aware sizing remains blocked until a real dated Bybit snapshot is archived and provenance/age validated.


## ENG-SEC-001 — private API preflight hardening

- Hardened `scripts/bybit_private_api_check.py`: official HTTPS host allowlist, no redirects, strict integer `retCode` and `readOnly`, suppressed response bodies.
- 10 mocked tests and secret scan passed in [Actions #41469608200](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41469608200).
- No real key or private API request was used. The manual workflow remains the only step that can verify an actual key's Bybit-reported read-only status.
- Continue full repository/branch audit for any order mutation endpoints before considering live execution; no live order or deployment.


## Продолжение автономного аудита — 2026-11-02

### Закрыто после предыдущей версии плана
- ENG-FUND-001: funding на точной границе TP1 учитывается консервативно для платежа/получения.
- ENG-FUND-002: funding на точной границе полного закрытия не начисляется на уже закрытый объём; payment/receipt semantics покрыты тестами.
- ENG-FUND-003: receipt на pre-exit MTM границе откладывается, чтобы не улучшать equity до разрешения выхода на этой свече.
- ENG-PERSIST-001/002/003: сохраняются risk-stop latches, post-TP1 MTM и lifecycle state, а также last marks всех открытых позиций; восстановление без валидных last marks отклоняется.
- Одновременные same-bar close events для двух символов проверены на независимость от порядка обхода; PnL/equity/closed-trade ledger сверяются.
- Проверены все 21 прямых `python tests/test_*.py` вызовов в `research-checks.yml`: каждый имеет `unittest.main()` или явный runner для plain functions. Неисполнявшиеся ранее suite получили runner.
- Подтверждено, что CLI `--mode watch` — это config-watch с повторным backtest replay, а не live loop. `--persist-state` не включает restore; отдельный exchange-reconciled live-resume path отсутствует в данном CLI. Read-only private API check не размещает заявки; order sizing helper не является execution adapter.

### Следующие задачи (по приоритету, без новых рыночных прогонов)
1. **Margin/leverage/exchange sizing:** проверить, как sizing cap соотносится с реальным initial margin, maintenance margin, risk tiers, contract qty, qtyStep/minQty/minNotional, tick size и market/limit maxQty. Не считать `leverage_val` доказательством корректной маржи: сейчас это только notional cap approximation.
2. **Pending/stop/trailing lifecycle:** дополнить тесты для обеих сторон и пограничных событий, где OHLC не раскрывает порядок исполнения; отдельно зафиксировать консервативные допущения и не превращать их в maker-fill доказательства.
3. **Persistence recovery freshness:** last marks сохраняются, но не имеют отдельных per-symbol timestamps. До live-resume нужна свежесть mark snapshots и fail-closed gate до получения/сверки актуальных биржевых цен и позиций. Не добавлять live-resume без согласованного протокола reconciliation.
4. **Journal/metrics:** проверить net-R denominator, MAE/MFE, daily/peak drawdown и агрегирование по периодам на синтетических контрольных примерах.
5. **Исторические эксперименты:** продолжить E01–E09 provenance reconciliation и пометить недоказанные результаты UNVERIFIED.

### Рыночные данные и holdout
- Доступный CryptoFetch архив заканчивается 2026-10-27 и является Binance OHLCV proxy; в ZIP нет исторических funding/mark-price CSV. Два уже изученных периода и все их производные фильтры не являются новым blind holdout.
- Не запускать новые parameter sweeps и не объявлять новый holdout на тех же уже просмотренных свечах. Следующий валидный рыночный тест требует нового заранее зафиксированного временного окна/набора данных либо nested walk-forward, явно маркированного как повторный model selection.
- Bybit public snapshot ранее получил HTTP 403; не обходить ограничение неофициальными прокси или непроверенными источниками.


## Дополнение: ENG-METRIC-001 (2026-11-02)
- Закрыт дефект порядка расчёта drawdown: `MaintenanceGateAuditor` теперь агрегирует net PnL по UTC timestamp закрытия и применяет группы хронологически. Тест-first CI #41512547727 воспроизвёл ошибку; full CI #41512721144 SUCCESS, portfolio accounting 24/24.
- Следующий инженерный блок: тесты метрик на контрольных equity paths — одновременные закрытия, out-of-order records, несколько UTC offsets, MTM drawdown vs realized curve, cost aggregation с funding receipts. Затем проверить корректность MAE/MFE при TP1 и финальном закрытии.
- Exchange sizing и margin tier integration пока не менять: достоверных версионированных Bybit instrument snapshots/risk tiers для исторических дат в репозитории нет; public snapshot endpoint ранее вернул 403. Не подставлять текущие параметры в прошлое и не использовать неофициальные обходы.


## Дополнение 2026-11-02 — prospective risk-tier archive
- Добавлен fail-closed collector `scripts/snapshot_bybit_risk_limits.py` и еженедельный/manual workflow `bybit-risk-limit-snapshots.yml`; 9/9 offline tests, CI #41518145630 SUCCESS.
- Это фиксирует текущие risk tiers с момента первого успешного захвата. Исторические tiers до даты первого архива остаются неизвестными; не подставлять сегодняшние `maintenanceMargin`, `initialMargin`, `mmDeduction` и `maxLeverage` в старые периоды.
- Следующий data task: после успешного доступа к официальному Bybit API архивировать historical funding settlements и mark-price klines по exact timestamps; отдельный preflight должен выявлять неполные страницы/символы/границы и не подменять отсутствующие значения last trade price.
- Risk-tier integration в PnL/ликвидационный симулятор отложена до получения версионированных tiers и точного определения account/position mode, isolated/cross margin и risk-limit transitions.


## Дополнение 2026-11-02 — funding/mark archive pipeline

- Реализован scripts/archive_bybit_market_history.py: официальные linear funding history + mark-price klines, bounded windows, проверка полноты H1 grid, атомарные CSV, fail-closed при 403/лимите/пропусках.
- Добавлен manual workflow bybit-market-history-archive.yml. Для каждого запуска отдельный каталог с временным диапазоном и run id; затем coverage preflight и commit в research branch.
- 11 offline tests прошли. Полный CI на кодовом commit 83af4e662e1f66a28a8dce5e064fbedb54347c0c прошёл тестовые шаги; окончательное состояние workflow проверяется.
- Следующий шаг: выполнить ручной архив на 1-2 ликвидных инструментах и небольшом диапазоне, подтвердить фактический API доступ/форматы/coverage. Только после этого расширять на полный 50-symbol universe и 180-day период.
- После получения реальных данных сверить funding timestamps против mark candle opens; помнить, что H1 open — proxy, не settlement mark. Не переписывать funding accounting или исторические результаты до отдельной проверки event-time semantics.
- Только после успешной data validation подключать funding + mark data к воспроизводимым shared-capital H1 backtests, затем отдельным этапом — исторические risk tiers и maintenance-margin/liquidation model.

- CI update: 12/12 tests for the Bybit history collector passed in Research CI #41518947460 (SUCCESS), including the guard against incomplete current H1 candles.


## Дополнение 2026-11-02 — Bybit-native OHLCV
- Архив Bybit теперь включает trade OHLCV /v5/market/kline, mark-price H1 и funding settlements. Для trade и mark свечей требуется полная H1 сетка, а coverage preflight сверяет их timestamp sets.
- Добавлены offline тесты парсинга и coverage. В CI на commit 9a94ee7d793e99cdbcc14da6a8eaffce0484dc6f тестовые шаги collector и coverage прошли; общий workflow ещё находился в cleanup.
- E01–E13 остаются Binance-proxy результатами и не меняются задним числом.
- После успешного официального API capture: загрузить BTCUSDT/ETHUSDT на коротком интервале, проверить реальные CSV, coverage и архивные SHA256; затем расширить на 50 символов/180 дней. Только после этого повторять shared-capital H1 folds на Bybit-native OHLCV + mark + funding.


## Дополнение 2026-11-02 — адаптивная пагинация funding
- Если Bybit возвращает полную страницу из 200 funding events, загрузчик автоматически делит временное окно пополам и повторяет запросы; если насыщение сохраняется на минимальном интервале, загрузка завершается ошибкой, а не принимает потенциально усечённые данные.
- Добавлены регрессионные тесты. Research CI #41520495668 завершился SUCCESS на commit 78a07cbbc5713b5e72874c231c3c53245aff999f; все 23 тестовых шага успешны.
- Реальный архив всё ещё не скачан: workflow требует ручного запуска, а подключение GitHub не предоставляет операцию workflow dispatch. `main` не изменён.


## Дополнение 2026-11-03 — multi-bar limit wait harness defect

- Статически подтверждён дефект в `scripts/run_h1_shared_capital_portfolio_validation.py`: при `WAIT_BARS=3` wrapper сохраняет исходный `signal_ts`, а затем на последующих свечах вызывает engine `_try_fill_pending`, который допускает только строго next-bar timestamp и удаляет более старый сигнал.
- Следствие: заявленный fill на второй/третьей свече не может пройти через текущий wrapper. Это дефект исследовательской обвязки, не базового engine.
- Скрипт и его multi-bar выводы запрещены к повторному использованию до отдельного исправления и регрессий для fill на 1/2/3-й свече, expiry, long/short, gap/taker и risk budget.
- Аудит: `docs/audits/H1_LIMIT_WAIT_SCRIPT_AUDIT_2026-11-03.md`. Матрица покрытия обновлена. Связь с E01–E13 не установлена; не аннулировать их без provenance.
- Следующая работа: продолжить независимый аудит метрик и портфельной бухгалтерии; не запускать рыночные прогоны до закрытия технического аудита. Базовый движок и торговая логика не менялись.


## Дополнение 2026-11-03 — аудит Net R / MAE-MFE / portfolio MTM

- Статически проверены `TradeRecord`, `_close_position`, `_manage_position`, `_apply_tp1`, `_unrealized_pnl_at_marks`, `AdaptiveRiskManager`, `MaintenanceGateAuditor` и regression test inventory.
- Подтверждённого дефекта, завышающего закрытый net PnL или Net R, не найдено. TP1 partial gross, per-leg costs, funding, realized/unrealized equity и chronology drawdown имеют отдельные regression tests.
- Обнаружена консервативная асимметрия: MTM всегда резервирует taker fee + taker slippage для оставшейся позиции, тогда как финальный TP close может быть maker. При maker TP это занижает открытое MTM equity на 0.0575% оставшегося notional при текущих ставках и может преждевременно активировать daily stop/kill switch. Это не завышение прибыли и не подтверждённый дефект закрытого PnL.
- Аудит: `docs/audits/PORTFOLIO_ACCOUNTING_NET_R_MAE_MFE_AUDIT_2026-11-03.md`; матрица покрытия обновлена.
- Следующий шаг: отдельные deterministic threshold-boundary tests для MTM cost asymmetry; затем продолжить margin/liquidation, dataset alignment и execution realism. Не менять текущую консервативную модель и не запускать рыночные бэктесты без тестов/CI.
- Полный CI #41520724088 — последнее ранее подтверждённое успешное выполнение; новый CI в этой сессии не dispatch-ился и не заявляется.


## Дополнение 2026-11-03 — leverage / margin / liquidation

- Проверены `AdaptiveRiskManager.calculate_position_size()`, `OpenPositionState`, entry lifecycle, exchange sizing helper и portfolio accounting tests.
- Подтверждено: текущий `leverage_val` используется только в грубом notional cap `equity * leverage / max_concurrent_positions * 0.95`. Это не Bybit margin model.
- В движке отсутствуют расчёт IM/MM по symbol risk tiers, liquidation price/event, cross/isolated collateral, maintenance tier transitions и mark-price liquidation trigger. Точный exchange qty также не участвует в sizing/funding/partial exits.
- Отдельный `exchange_order_sizing.py` не подключён к engine lifecycle; текущая позиция хранит notional proxy.
- Подтверждённого дефекта формулы stop-risk sizing не найдено, но ликвидационная устойчивость не моделируется. Это блокирующее ограничение execution realism, а не основание придумывать коэффициенты.
- Отчёт: `docs/audits/LEVERAGE_MARGIN_LIQUIDATION_AUDIT_2026-11-03.md`; матрица покрытия обновлена.
- Следующий шаг: получить датированные официальные Bybit instrument + risk-tier snapshots; после этого разработать pure margin calculator и deterministic fixtures для long/short, cross/isolated, tier transitions, mark-price trigger, fees/funding, partial fills и stop-vs-liquidation. Не запускать PnL sweeps и не делать выводов о liquidation safety до закрытия этого gate.


## Дополнение 2026-11-03 — exchange sizing integration / Bybit schema

- Проверка официальной документации уточнила, что поля `minNotionalValue`, `maxOrderQty`, `maxMktOrderQty` корректны для Linear/Inverse; Spot использует другую схему. Linear parser менять не нужно.
- Подтверждён integration gap: основной `_try_fill_pending()` использует `size_usdt` как notional proxy и не вызывает `size_to_exchange_constraints()`; OpenPositionState, TP1, funding и PnL не хранят/не используют точный contract qty.
- Отчёт: `docs/audits/EXCHANGE_SIZING_INTEGRATION_AND_BYBIT_SCHEMA_2026-11-03.md`.
- Официальный Bybit V5 risk-limit endpoint публикует `riskLimitValue`, `maintenanceMargin`, `initialMargin`, `maxLeverage`, `mmDeduction`, но свежие значения API в этой сессии не получены. Документация не заменяет архивный snapshot.
- Следующий этап: определить контрактную семантику qty и расширить position/trade records, versioned instrument/risk snapshots, затем подключить exact qty к TP1/remaining qty/funding/PnL. Изолированную liquidation формулу реализовывать только с настоящими tier fixtures и piecewise tier validation; cross/UTA требует account-level model и остаётся заблокирован.

- Дополнительная проверка показала, что weekly snapshot workflows и оба downloader script уже существуют. Ожидаемые output dirs `data/instrument_specs/linear` и `data/instrument_specs/risk_limits` на момент проверки отсутствуют (GitHub contents 404); свежий snapshot/run не подтверждён. Не создавать дублирующие workflow/scripts. Следующий шаг — получить результат уже существующего scheduled/manual workflow; dispatch через подключённые инструменты в этой сессии недоступен.

- Дополнительно скорректирован cron `.github/workflows/bybit-instrument-snapshots.yml`: теперь snapshot запускается 3-го и 17-го числа в 02:17 UTC, после указанного Bybit обновления лимитов в 08:00 UTC+8. Ручной dispatch сохранён. Commit `747862d`; сам workflow не запускался в этой сессии.


## Дополнение 2026-11-03 — fail-closed sizing и workflow evidence

- Повторная проверка InstrumentSpec выявила отсутствие `minPrice/maxPrice`, отсутствие запрета на явно не-linear category и отсутствие запрета на sizing инструмента в статусе `PendingOpen`/unknown. Внесено fail-closed исправление в `bybit_instrument_specs.py`, регрессионные тесты добавлены в parser/sizing tests. Коммиты: `924e7da`, `7e94b3d`, `95e74cc`.
- GitHub Actions #631/#632 были запущены push-ами автоматически. Результаты на момент записи ещё проверяются; не объявлять тесты успешными до completed conclusion.
- Через Actions REST удалось получить историю и логи Bybit instrument snapshot workflow #7–#10. Все три доступных run IDs (#7–#10) завершились failure на Download step; logs явно показывают HTTP 403 на API endpoints, после чего job exit code 1. Это сетевой/API access blocker. Не пробовать обходить гео/сетевые ограничения.
- Приоритет: дождаться CI новых fail-closed тестов; затем отдельно проверить risk-limit snapshot workflow runs и его job logs. Только после реального официального snapshot реализовывать margin/liquidation calculator. Exact qty engine integration остаётся отдельным P1/P0 execution realism blocker.

- Завершённая проверка CI: #41533273830, #41533575723, #41533598553 — все success. Новые тесты min/max price, Linear-only category, Trading status, исправленная as-of fixture и актуальные official/retired host allowlists проходят.
- Host cleanup: удалены retired `api.bybit.nl` и ошибочный `api.bybit-tr.com`; используется официальный `api.bybit.tr`. Добавлен branch-scoped push trigger для instrument/risk snapshot workflows, так как GitHub schedule и workflow_dispatch работают только если workflow находится в default branch; main не изменяли.
- Bybit Integration Guidance подтверждает 403 для IP из US/Mainland China. География egress GitHub runner не установлена; не обходить сетевые ограничения. Дождаться результата запуска instrument snapshot workflow #41533728951; risk-limit workflow пока не подтверждён как выполненный. Реальные датированные архивы пока отсутствуют.

- Финальные результаты branch-scoped snapshot validation: instrument run `41533728951` и risk-limit run `41533743884` завершились failure на download step; логи подтверждают HTTP 403 от каждого официального регионального host в исправленном списке. Snapshot commit steps не выполнялись. Это runner/network access blocker; больше не повторять те же запросы и не пытаться обходить географические ограничения. Требуется получение snapshot из официально разрешённой среды.

- Проверка root/scripts подтверждает, что текущий репозиторий — research-only: не найден live order submission adapter (`/v5/order/create`, `place_order`, `create_order`, pybit отсутствуют в engine). Не планировать интеграцию live orders до отдельного создания и аудита execution adapter. Текущий P1 — contract-accurate research sizing; production order lifecycle — отдельный этап.

- После проверки всех official regional hosts fallback-loop удалён: workflows используют один `BYBIT_API_BASE_URL` repository variable (default `https://api.bybit.com`), без перебора юрисдикций. Новый single-host run #41534141800 (instrument) и #41534156659 (risk-limit) также получил HTTP 403; архивы не созданы. При необходимости владелец задаёт variable на официальный host своего региона; не использовать cross-region fallback для обхода отказа.

- Дополнительно закрыт fail-open в parser: `maxOrderQty` и `maxMktOrderQty` больше не optional для Linear; оба обязательны. Тест удаления каждого поля проходит. CI #41534399745 и #41534426284 — success. Exact qty integration в engine остаётся не сделана.


## Дополнение 2026-11-03 — execution-notional fees

- Подтверждён и исправлен дефект: exit fee/slippage ранее считались от entry notional, а не от `qty × actual modeled exit price`. Исправлены TP1, final exit, MTM reserve и stop-risk sizing. Для linear proxy qty = `size_usdt / entry_price`; точный exchange qty всё ещё не wired.
- Regression coverage обновлено для long/short stops, gap stops, TP1/TP2 maker legs, TP1 + taker trailing stop, MTM and risk sizing. CI #41536540759 — success.
- Все старые H1/15m net-PnL rankings, включая 50-symbol screen 14/50 positive, считаются provisional до повторного прогона на исправленном engine. Точное изменение aggregate PnL не вычислено. Новые strategy backtests пока не запускать: отсутствуют датированные instrument/risk snapshots, engine exact qty, IM/MM/liquidation model; API workflow returns 403.
- Fixed rates remain assumptions: taker 0.055%, maker 0.020%, taker slippage 0.0225%. VIP/region-specific account fee schedule and maker queue/partial fills not modeled.

- Подготовлена карта интеграции точного qty без изменения кода: `_try_fill_pending` → immutable spec snapshot → exchange-valid qty → OpenPositionState → qtyStep-safe TP1/remaining qty → PnL/fees/funding → TradeRecord → persistence schema migration. Подробности и тест-gate в `EXCHANGE_SIZING_INTEGRATION_AND_BYBIT_SCHEMA_2026-11-03.md` section 16.

## Обновление 2026-11-03 — H-A rejection и execution data gate

Завершено:
- H-A frozen relative-strength breakout replay выполнен на трёх ранее исследованных fold; обе версии (baseline и H-A) отрицательны после costs во всех fold. H-A хуже baseline на 499.28 USDT суммарно; fold 3 ухудшен на 1,321.93 USDT и max DD вырос на 14.97 п.п. Подробности: `docs/reports/H_A_RELATIVE_STRENGTH_BREAKOUT_RESULTS_2026-11-03_RU.md`.
- E14 read-only post-break diagnostics completed: 3-bar/6-bar follow-through и retest связаны с последующим stop-loss outcome, но это post-entry association на уже просмотренных fold, не counterfactual PnL и не независимая проверка.
- H-C close-based post-break invalidation реализована за disabled-by-default H1 flag, ограничена baseline H1-momentum-breakout и покрыта синтетическим CI (9/9 H-C tests; state persistence 67/67). Рыночный PnL не запускался: старые folds запрещены для оценки H-C, нужен untouched period и полноценный execution data gate. Подробности: `docs/research/H_C_POST_BREAK_INVALIDATION_PREREGISTRATION_RU.md`.
- TradeRecord TP1/remaining-leg provenance перенесён в закрытую запись и проверен full Research CI #41673525597 SUCCESS на commit `69358a1f720e6b91046d2afaf7da8696f5958836`.
- Delayed multi-bar fill provenance исправлена: исходный signal timestamp теперь проходит через `signal_origin_ts` → `OpenPositionState.signal_ts_ms` → `TradeRecord.signal_ts_ms` → JSON journal; старые backups без поля совместимы. CI [#41684988411 SUCCESS](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41684988411): portfolio accounting 46/46, state persistence 68/68, gap execution 31/31.
- Для low-priced symbols устранено округление journal price/stop fields до 6/8 знаков: precision повышена до 12 знаков; тест реконструкции gross PnL и stop distance. CI [#41685190246 SUCCESS](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41685190246), portfolio accounting 47/47. Расчёт PnL не менялся, исправлена только точность закрытой записи.
- Старые sizing/liquidation audit notes получили supersession notices; текущий статус сосредоточен в `EXECUTION_INTEGRATION_REAUDIT_2026-11-03.md`.

Текущий блокер:
- В ветке по-прежнему отсутствуют `data/instrument_specs/`, `data/archives/bybit/` и архивы Bybit universe history. В наличии только CryptoFetch archives. Поэтому новый Bybit-native H1 market PnL replay не запускается.
- Bybit public endpoints блокировали GitHub-hosted egress (HTTP 403 для US/CN). Workflow архивирования готов, но требует настроенного self-hosted runner вне этих регионов. API secrets не нужны для публичных market-data endpoints.

Следующий порядок:
1. Не делать H-A threshold sweep и не переиспользовать старые fold для оценки H-C.
2. Проверить, настроен ли non-US/non-CN self-hosted runner; после его появления выполнить ручные dated instrument/risk-tier captures и Bybit H1/funding/Mark archive с проверкой coverage.
3. До появления архива продолжить только инженерный аудит: remaining journal metrics (Net R denominator, MAE/MFE, drawdown aggregation), H1 runner/data manifests, старые audit-note supersession и PR #4 file classification. Signal→fill timestamp provenance уже закрыт и regression-tested.
4. Разобрать PR #4 (211 changed files, 1,331 commits ahead / 18 behind current main; +17,482 / −164) по пакетам; не merge/rebase/force-push whole branch. Любая интеграция — отдельная чистая ветка от актуального main с небольшими проверяемыми патчами.
5. После закрытия data/account-mode gates — один frozen shared-capital Bybit-native validation. Никаких новых параметрических сеток на proxy данных.

## v15 dashboard safety disclosure — completed in main 2026-11-03

- PR #7 merged: [docs(dashboard): label v15 as unvalidated demo](https://github.com/nikitanecilli-bit/bybit-trading-bot/pull/7), main commit `fc2c16151a6f945a50f6f3b3907bbd8b286bace9`.
- HTML and its downloadable Markdown source now disclose the planted synthetic edge, independent per-symbol virtual capital, same-sample symbol selection, and synthetic fallback after API failure.
- Unsupported "pure profit" and 96% fee-savings claims were removed; dashboard remains a demo, not a Python engine result. PDF export remains an unreviewed archived artifact.
- Dashboard integrity CI and full Research engine checks both passed; see PR #7 for run links.


## Main repository organization — completed 2026-11-03

- PR #6 `chore(repo): organize main branch root artifacts` merged by squash into `main`.
- Main merge commit: `74bca15de1de0d33a7e019116acad856160bfc5e`.
- Two root HTML dashboards moved to `dashboards/quant_analytics/`; the cognitive protocol moved to `docs/operations/`; the obsolete validator prototype moved to `research/legacy_tools/` with a clear missing-dependencies warning.
- Engine, downloader, active scripts, tests, workflows and data archives were not moved or modified. Source blobs for moved artifacts were preserved.
- PR CI passed: [run 41674873356](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41674873356). Main tree paths were re-checked after merge.
- PR #4 remains Draft and must not be merged wholesale; current compare is 1,268 commits ahead / 15 behind, 210 files, mergeable=false.


## Обновление 2026-11-03 — shared-capital protective accounting audit

Завершён следующий блок проверки портфельного lifecycle без рыночных PnL прогонов:
- Исправлен UTC midnight baseline: mark на границе даты теперь сначала обновляет equity, затем задаёт baseline нового дня; первый mark после старта по-прежнему сравнивается со стартовым/restored equity.
- Проверено независимое срабатывание daily stop и emergency kill-switch; смена UTC-даты сбрасывает только daily latch, kill-switch остаётся latched.
- Добавлена регрессия, доказывающая, что pending entry не использует слот, освобождённый закрытием другой позиции позднее в том же баре. Предварительное распределение risk/slots уже блокировало этот путь; исправление движка для него не потребовалось.
- Проверено, что TP1 partial transition повторно маркирует portfolio MTM; существующие reconciliation и permutation tests покрывают одновременные TP1/stop и multiple closes.
- Funding-adjusted bankruptcy formula сверена с final net loss: funding сдвигает bankruptcy price, а отдельное вычитание funding cashflow приводит к одному учёту allocated margin loss, не к двойному списанию.

**CI evidence:** [#41682730056 — SUCCESS](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41682730056), portfolio accounting 45/45; [#41683684185 — SUCCESS](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41683684185), gap execution 31/31 и portfolio accounting 45/45; [#41684012791 — SUCCESS](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41684012791), isolated liquidation 16/16. Полные Research workflows завершились успешно.

**Не закрыто:** account-wide cross-margin/UTA liquidation, реальные exchange fills/queue, персональные fee tiers и историческая settlement mark price. Это остаётся явно ограниченной областью модели, не доказанной биржевой симуляцией.

**Data gate перепроверен по текущему Git tree:** `data/archives/` содержит только `cryptofetch/`; `data/archives/bybit/` и `data/instrument_specs/` отсутствуют. Архивный workflow уже реализован, но требует self-hosted GitHub runner вне США и материкового Китая; workflow dispatch из подключённых инструментов этой сессии недоступен. Не запускать Bybit PnL replay на proxy и не подменять исторические snapshots текущими.

**Следующий автономный шаг без пользователя:** продолжить аудит journal serialization/metrics, H1 runner manifest и file/workflow provenance; проверить отсутствие новых дублирующих экспериментов. Для Bybit-native market validation остаётся один внешний blocker: владелец репозитория должен один раз настроить разрешённый self-hosted runner и запустить уже готовые snapshot/archive workflows. После появления данных — только один frozen shared-capital validation, без параметрического sweep.


## Обновление 2026-11-03 — provenance gate для следующего H1 прогона

H1 validation runner дополнен отдельным JSON manifest рядом с CSV. Он фиксирует точный frozen symbol list, общий H1 timestamp grid, fold boundaries, все strategy/risk/execution параметры, hashes входных Bybit kline/funding/mark/spec/risk файлов и ключевых code/workflow files, Git commit, workflow run ID, result rows и SHA-256 выходного CSV. Добавлена проверка, что каждый выбранный kline-файл действительно находится в заявленной input directory. H1 workflow принимает optional comma-separated `symbols`, чтобы один и тот же top-5/reserve-5 universe можно было передавать без повторного dynamic selection; artifact upload очищен от stale filenames, которые runner не создаёт.

**CI:** [#41687904323 — SUCCESS](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41687904323), manifest tests 4/4. Никаких рыночных PnL прогонов не запускалось.

**Состояние веток:** `main` отдельно продвинулся с `2055cdd` до `fc2c161` коммитом `docs(dashboard): label v15 as unvalidated demo` (добавлены предупреждения и integrity CI для v15 dashboard). Этот коммит не является частью текущего research-изменения; merge не выполнялся. `docs/README_RU.md` менялся и на main, и в research branch — при будущем объединении нужно отдельно сверить этот файл. Все текущие изменения H1 manifest находятся в `research/market-regime-v1-main`.

**Следующий шаг:** продолжать статический аудит provenance/serialization и runner gates. Market PnL replay остаётся заблокирован до появления Bybit-native kline/funding/mark archives и dated execution snapshots через разрешённый self-hosted runner.


**Дополнительное закрытие state persistence gate:** writer теперь отклоняет `signal_ts_ms > entry_ts` до записи backup, симметрично строгому reader. Research CI #41687016004 SUCCESS; state persistence suite 69 tests passed. Это предотвращает создание заведомо невосстанавливаемого Plan B backup.


**Plan B writer/reader parity завершена:** serialized candidate теперь проверяется строгим reader до atomic replace. Невалидный position/pending/risk payload не может заменить предыдущий backup; temp удаляется. CI #41689536499 SUCCESS; state persistence suite 73 tests passed. Повреждённые-backup tests отделены от writer tests и мутируют уже валидный envelope после сохранения.


## Обновление 2026-11-03 — collector workflow dispatch доступен из main

- Три Bybit collector workflow выборочно опубликованы в default branch через PR #8: merge commit `a0ceb66d9b2cf818b3a24d723130d1125c8ca382`. В main добавлены только YAML-файлы instrument snapshots, risk-limit snapshots и market-history archive; Python scripts и торговый движок не переносились.
- Все три workflow checkout-ят `research/market-regime-v1-main`, запускают уже существующие collector scripts и коммитят только полученные snapshots/archives обратно в research branch.
- PR #8 CI run `41691250317` — SUCCESS: compile, secret scan, gap-execution tests и time-model tests.
- YAML-файлы остаются manual-only: `schedule/cron` отсутствует. Автоматическую периодичность не считать настроенной.
- Наличие зарегистрированного self-hosted runner с label `self-hosted` и egress вне US/CN пока не подтверждено. Через текущую GitHub-интеграцию список runners недоступен. Это единственный непосредственный внешний gate для первого запуска collectors.
- H1 validation workflow по-прежнему отсутствует в main; не запускать market PnL, пока не будет официального Bybit архива, датированных specs/risk snapshots и выборочно опубликованного H1 validation workflow.
- Runbook исправлен: `docs/research/BYBIT_DATA_ARCHIVE_RUNBOOK_RU.md`.


## Дополнительный аудит H1 validation runner — 2026-11-03

### Статус исполнения и воспроизводимости
- Shared-capital runner перебирает 3 временных fold × 4 volume thresholds × 3 breakout-ATR thresholds × 3 cost multipliers = **108 replay-конфигураций**.
- Это исследовательская сетка чувствительности, а не 108 независимых подтверждений. Если пороги выбираются по совокупным результатам этих fold, все три fold становятся validation/selection data; их нельзя после выбора продолжать называть независимым финальным OOS.
- До первого запуска необходимо заранее определить primary metric, правило выбора конфигурации и запретить повторный подбор на финальном holdout. После выбора — заморозить параметры/код/fees и оценить один следующий, временно более поздний, неиспользованный период.
- Временные fold: 50–65%, 65–80%, 80–100% общей синхронизированной истории. Это неперекрывающиеся scoring windows, но последний fold не является untouched holdout, если используется при выборе параметров.
- Cost multipliers 1.0/1.5/2.0 — стресс фиксированных engine fee/slippage assumptions, не калибровка реальных комиссий конкретного Bybit аккаунта. Нужны подтверждённые fee tier и реальные execution observations, когда появится read-only reconciliation.
- Maker fill модель требует OHLC penetration limit на 5 bps; она не моделирует очередь, спред, partial fills и adverse selection. Внутрисвечной касание не доказывает maker execution; marketable-at-open заявка правильно переводится движком в taker proxy, но optimistic maker assumption остаётся.
- Ликвидация — position-level isolated approximation; Bybit partial-liquidation ladder/account mode и полная account-level UTA/Classic semantics не подтверждены.

### Точность формулировок
- Три успешных collector test suites подтверждают локальные/mock сценарии, а не сетевой сбор архива.
- H1 PnL остаётся заблокированным до фактических Bybit H1 klines, funding/mark series и непрерывных point-in-time instrument/risk snapshots. Никакие PnL результаты не заявляются.
- Нельзя публиковать 108 результатов как независимые OOS доказательства и нельзя выбирать top-5 монет по одному и тому же отрезку, на котором затем заявляется подтверждение прибыльности.


## 2026-11-03 — защита финального H1 holdout

Подтверждён методологический дефект прежнего runner: он выполнял полную сетку 4 volume × 3 breakout-ATR × 3 cost stress на каждом из трёх fold, то есть последний временной fold участвовал в подборе.

Исправлено в исследовательской ветке:
- H1_VALIDATION_MODE=explore (default): 72 запуска — полная сетка только на fold 1 и 2 (50–80% общей истории). Fold 3 не читается как scoring window.
- H1_VALIDATION_MODE=confirm: только fold 3 (80–100%) и одна конфигурация из заранее зарегистрированной сетки. Требуются оба frozen inputs: H1_FROZEN_MIN_VOLUME_RATIO и H1_FROZEN_MIN_BREAKOUT_ATR; незарегистрированные значения отклоняются.
- Для замороженной конфигурации выводятся три заранее заданных cost stress (1.0/1.5/2.0); это сценарии затрат, а не дополнительные параметры стратегии.
- Manifest теперь фиксирует фактический validation mode, выбранные fold, frozen config и реально применённые сетки.
- Workflow H1 Shared-Capital Portfolio Validation получил ручной выбор explore/confirm и frozen threshold inputs. Значение по умолчанию — explore.
- Deterministic tests проверяют запрет scoring fold 3 в explore, единственную frozen-конфигурацию в confirm и отказ на отсутствующих/незарегистрированных параметрах.

Проверка: Research CI #41693438367 — SUCCESS (https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41693438367), test commit e598b59a401d5304c575ed07f81601b1d4444450; compile и все deterministic test steps прошли. Финальный branch head после обновления workflow: 0f82415289d578cd008f742ad65d6d9cce818ebb.

Ограничения:
- Это устраняет повторный подбор параметров на последнем fold, но не создаёт автоматически корректный top-5 universe. Top-5 должен быть отобран только по train-отрезку и зафиксирован до explore/confirm; список символов затем передаётся через H1_SYMBOL_ALLOWLIST.
- Нельзя запускать confirm после просмотра fold 3 или менять frozen inputs после получения результата: в таком случае fold 3 становится использованным и следующий подтверждающий holdout должен быть более поздним.
- Bybit data/execution gate всё ещё закрыт; PnL не запускался. CI подтверждает только код и deterministic tests.


Дополнение к защите holdout (после CI #41693921708): confirm mode теперь дополнительно требует ровно пять уникальных заранее выбранных символов в H1_SYMBOL_ALLOWLIST. Автоматический coverage-filtered universe в confirm запрещён. Frozen symbol list сохраняется в manifest. Это не выполняет отбор top-5 за нас: top-5 сначала нужно определить на train-периоде, затем неизменно передать в explore и confirm. Research CI #41693921708 завершился SUCCESS; все 49 job steps успешны. Финальный workflow-only commit `4482bc95fea19d025ccb9c2456a26bbc1c62cfdf` содержит эти изменения в активной ветке.


## 2026-11-03 — train-only top-5 selection protocol

Добавлен отдельный Bybit-native selector `scripts/select_h1_top5_train_only.py` и manual workflow `H1 Top-5 Train-Only Selection`.

Правила зафиксированы до получения данных:
- Universe берётся из официального Bybit linear lifecycle snapshot; допускаются только USDT-settled LinearPerpetual, активные по launch/delivery bounds на cutoff. Отсутствующие в snapshot инструменты исключаются и отражаются в manifest.
- Training cutoff — 50% span самой длинной H1 истории, с embargo в один H1 бар до validation. Используются только свечи не позже cutoff.
- На каждом кандидате выполняется один фиксированный long-only H1 replay: volume ratio 1.6, breakout clearance 0.10 ATR, 2x cost stress, существующие engine execution/risk settings. Никакого sweep и старого per-symbol PnL ranking.
- Требуется не менее 3,000 training H1 bars и 30 закрытых сделок; eligibility только при net PnL > 0, PF > 1 и expectancy R > 0.
- Ранжирование: expectancy R ↓, PF ↓, drawdown ↑, trades ↓, symbol ↑. Берутся top-5 primary и следующие 5 reserve. Если меньше пяти eligible либо у primary нет минимум 3,000 общих training bars — selector fail-closed, слабые монеты не подставляются.
- Manifest содержит cutoff, source hashes, code hashes, lifecycle snapshot, все кандидатные метрики/исключения, primary/reserve и правило ранжирования.
- Explore и confirm теперь оба требуют committed selection manifest и ровно тот же allowlist. Runner проверяет hash manifest, совпадение списка, отсутствие пересечения training cutoff с первым scored fold; итоговый validation manifest сохраняет provenance отбора.

Ограничения: Bybit lifecycle snapshot содержит launch/delivery bounds, но не гарантирует полный исторический retention delisted contracts и не отражает временные приостановки торгов. Поэтому universe completeness остаётся ограниченной, пока не накоплена/проверена историческая серия snapshots и официальные listing/delisting notices. Selector требует Bybit H1, funding, mark, dated specs/risk tiers; он не может быть исполнен на имеющихся CryptoFetch ZIP. Старый shortlist RAY/PUMP/TAO/AAVE/CAKE и reserve DASH/HBAR/ENA/GMX/ONDO не переиспользуется.
