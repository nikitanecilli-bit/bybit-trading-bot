# ALT-SYSTEM-ACCOUNTING-CONTRACT-AUDIT-001 — static review

Дата: 2026-11-05  
Ветка: `research/market-regime-v1-main`  
Режим: read-only source/test/documentation review; никаких рыночных данных или PnL replay не использовано.

## Краткое решение

- **Подтверждённого нового profit-inflating дефекта в проверенных формулах не найдено.**
- **Instrument specs: кодовая валидация сильная, историческая effective-time полнота не доказана.**
- **Risk tiers: ladder/IM/MM формулы и structural checks согласованы, но historical completeness/effective-time не доказаны.**
- **Funding: cashflow sign/partial-close/boundary logic покрыты deterministic tests; settlement Mark остаётся H1 Mark-candle proxy, а расписание имеет неустранимую по текущим snapshot evidence неоднозначность при смене интервала.**
- **Portfolio: предыдущий audit и regressions закрывают ряд accounting invariants; это не account-wide Bybit UTA/cross-margin/liquidation model.**

Никакие статусы BLOCKED из readiness decision не снимаются.

## 1. Instrument specs

Проверено:
- `bybit_instrument_specs.py`
- `instrument_spec_history.py`
- `scripts/snapshot_bybit_instruments.py`
- `tests/test_bybit_instrument_specs.py`
- `tests/test_instrument_spec_history.py`

### Подтверждённые защитные свойства

- Decimal parsing отвергает missing/non-finite/non-positive обязательные значения.
- Поддерживается только linear category; обязательны symbol/category, priceFilter, lotSizeFilter; optional leverageFilter не подменяется дефолтами.
- Проверяются min/max price, qty limits, leverage bounds; limit price rounding направлено наружу (buy вниз, sell вверх), quantity округляется вниз.
- `validate_order` проверяет Trading status, min qty, max limit/market qty, min notional; limit price проверяется на price range и tick alignment.
- История отвергает duplicate timestamps, schema/source/category mismatch, duplicate symbols, malformed rows, invalid timezone/sub-ms timestamps и symbol identity reuse.
- As-of selection выбирает только последний snapshot, fetched_at которого не позже requested timestamp; staleness можно ограничить max_age.
- При наличии page observations проверяются последовательность страниц, status filters, continuation flags, row counts, collection window и соответствие символов.

### Остаточные ограничения

1. **fetched_at — время наблюдения/завершения сбора, не exchange effective_from.** As-of lookup корректно не использует будущий snapshot, но не доказывает, что изменённый tick/qty/minNotional/status вступил в силу ровно в fetched_at.
2. Сбор full universe — последовательность нескольких status-filter/page requests. Page evidence подтверждает ход сбора, но не создаёт атомарный биржевой snapshot; состояние инструмента может измениться в процессе обхода.
3. Runtime loader допускает legacy snapshot без `page_observations`. Такой файл может пройти structural checks, но сам по себе не имеет проверяемого page-completeness evidence. Для data acceptance его нельзя приравнивать к fully attested snapshot.
4. Возможное переименование symbol маркируется как `possible_rename_not_proven`; автоматического склеивания истории нет — это безопасное поведение.
5. Даже свежие snapshots не дают полноценного исторического effective-time журнала. Текущий data acceptance D5 остаётся PARTIAL/UNVERIFIED.

**Решение:** parser/rounding contract — статически согласован; историческая PIT спецификация и полное покрытие — BLOCKED.

## 2. Risk tiers и margin

Проверено:
- `bybit_risk_tiers.py`
- `scripts/snapshot_bybit_risk_limits.py`
- `tests/test_bybit_risk_tiers.py`
- `scripts/audit_instrument_snapshot_coverage.py` (joint instrument/risk state path)

### Подтверждённые защитные свойства

- Collector валидирует source response, cursor type/repetition, duplicate/conflicting tier rows, positive numeric values, lowest-tier marker, monotonic risk limits/MMR/IMR/max leverage и mmDeduction recurrence.
- Runtime loader повторно валидирует tier ladder, timestamp/schema/source/category, tier ids, duplicate limits, exactly one lowest tier и recurrence.
- При наличии page observations сверяются последовательность страниц, request chronology, continuation flags, symbol coverage и total tier count.
- As-of lookup не использует future snapshot; max_age поддерживается.
- Tier выбирается как первый riskLimitValue, покрывающий position value; max leverage проверяется для выбранного tier.
- Position-level формулы соответствуют задокументированной модели: IM = position value / configured leverage; MM = position value × MMR − mmDeduction.
- Отдельный `get_tiers` возвращает полную ladder без entry leverage rejection, чтобы уже открытая позиция могла быть проверена на maintenance shortfall, если позднее tier max leverage снизился.

### Остаточные ограничения

1. Как и для instrument specs, `fetched_at` — observation timestamp, не точная дата вступления изменения risk tier в силу.
2. Runtime loader допускает snapshots без `page_observations`; `tier_count == len(rows)` подтверждает только внутреннее соответствие файла, не полноту API pagination. Production collector формирует page observations, но старые/ручные snapshots требуют отдельного attestation.
3. Точность position-level IM/MM зависит от исторической полноты и соответствия ladder на момент позиции; текущие snapshots не заменяют dated history.
4. Это **не** account-wide cross-margin/UTA solvency model: нет полного account collateral, offsets, portfolio margin, insurance/ADL или exchange liquidation engine. Maintenance margin result не следует называть точной liquidation price.
5. Нельзя считать один instrument snapshot и один risk snapshot синхронным состоянием без проверки их временного skew и покрытия. Наличие joint audit helper не создаёт отсутствующие исторические данные.

**Решение:** tier arithmetic/ladder checks — статически согласованы; PIT completeness и account-level liquidation — BLOCKED.

## 3. Funding arithmetic и settlement evidence

Проверено:
- `funding_accounting.py`
- `funding_archive_manifest.py`
- `scripts/validate_funding_coverage.py`
- `tests/test_funding_accounting.py`
- `tests/test_funding_archive_manifest.py`
- `tests/test_funding_coverage.py`
- `docs/audits/FUNDING_ARCHIVE_COMPLETENESS_AUDIT_2026-11-03.md`

### Арифметические инварианты

Для линейной USDT позиции знак cashflow формируется как direction sign × contract quantity × mark × funding rate:
- long платит при положительной ставке и получает при отрицательной;
- short — наоборот.
- exact contract quantity предпочтительнее реконструкции quantity из entry notional / entry price.
- duplicate settlement timestamps, missing exact mark proxy и invalid rate/mark fail closed.
- Partial TP1 allocation различает full trade-lifecycle funding и share, остающуюся в открытой части позиции. После TP1 remaining-margin helper распределяет накопленные cashflows по точному remaining contract ratio, включая settlements до TP1.
- Entry/funding и TP1/funding совпадающие границы обрабатываются консервативно; same-boundary receipts могут быть отложены, чтобы не маскировать adverse risk mark.
- Final-close boundary не зачисляет потенциальную receipt после возможного закрытия позиции.

Тесты покрывают long/short sign, partial close, exact quantity, missing mark, duplicate timestamp, entry/TP1/exit boundaries и deferred receipts.

### Внешний trust boundary

- В движке settlement mark для исторического funding берётся как Mark candle open на exact funding timestamp — это **proxy**, не доказанная точная Bybit settlement mark.
- Schedule sidecar строит UTC grid из dated instruments-info snapshots и проверяет хеши snapshot bytes, но snapshot fetched_at не доказывает effective boundary изменения fundingInterval.
- При наблюдаемом изменении интервала код fail-closed; однако snapshot observations не могут исключить смену и возврат между двумя наблюдениями.
- Funding archive validator стал существенно сильнее: hash/row count, query-page coverage, saturated-page handling, independent UTC-grid reconstruction и duplicate timestamp rejection. Но эти проверки зависят от полноты и временной достоверности schedule evidence.
- Наличие Mark свечи на timestamp не доказывает, что Funding CSV содержит все settlement events; именно поэтому прежний простой coverage validator не является самостоятельным доказательством completeness.

**Решение:** cashflow arithmetic — deterministic-testable; settlement Mark precision и complete historical schedule — BLOCKED.

## 4. Portfolio accounting

Предыдущий `PORTFOLIO_ACCOUNTING_NET_R_MAE_MFE_AUDIT_2026-11-03.md` и последующие записи фиксируют:
- closed PnL decomposition gross − fees − slippage − funding;
- partial TP1 lifecycle и per-leg fee/slippage;
- realized + unrealized equity;
- same-bar/multi-symbol order invariance и shared-capital risk budget;
- conservative taker MTM exit cost vs maker-proxy final TP, включая threshold regressions;
- UTC daily baseline ordering, price journal precision, funding allocation after TP1 и corrected execution-notional fee basis.

Это подтверждает внутренние accounting invariants в тестируемой модели. Это не снимает ограничений OHLC intrabar path, optimistic limit touch, funding mark proxy, отсутствующих Bybit archives и неполного account-level margin/liquidation.

## 5. Статус доказательств

| Контур | Code/fixture contract | Historical source completeness | Решение |
|---|---|---|---|
| Instrument specs | Strong static validation | No complete effective-time PIT archive | BLOCKED |
| Risk tiers | Strong ladder and position-level formula checks | No complete effective-time PIT archive | BLOCKED |
| Funding cashflow | Arithmetic regressions present | Settlement mark/schedule not fully authoritative | BLOCKED |
| Portfolio accounting | Several deterministic CI-backed invariants | OHLC/market/account-level realism incomplete | BLOCKED |
| Strategy PnL | Existing negative/provisional proxy evidence | No accepted Bybit-native dataset | BLOCKED |

Не заявлять, что текущий code review заменяет CI. В этом аудите тесты не запускались; все утверждения о тестовом покрытии основаны на статическом чтении исходников, тестов и ранее зафиксированных CI run records.

## 6. Разрешённые следующие шаги

- read-only аудит вызывающих участков, которые связывают instrument history, risk-tier history и portfolio engine; проверить, что они fail closed при отсутствующих snapshots, stale snapshots и несогласованном временном skew;
- при обнаружении конкретного воспроизводимого дефекта — добавить только synthetic fixture regression и прогнать deterministic research CI;
- обновлять acceptance/readiness документы, не повышая статусы без реальных источников и доказательств.

Не запускать Bybit API, collectors, архивы, PnL replay, paper/live, parameter sweeps или self-hosted runner. Не менять `main`, не сливать PR #4/#13.


## 7. Follow-up integration audit — explicit snapshot-skew budget (P1, fixed)

Static caller tracing found a real integration defect after the contract review:

- `bybit_market_state.get_linear_market_state()` requires `max_snapshot_skew_ms` to be a non-negative integer and rejects `None`.
- `UnifiedQuantEngine` defaults `max_market_state_skew_ms=None`; the strict H1 runner passes the value returned by `resolve_market_state_skew_budget()`.
- Before this fix, the resolver returned `None` when `BYBIT_MAX_MARKET_STATE_SKEW_MS` was absent, and the H1 workflow did not pass that environment variable. Consequently, the strict joined instrument/risk path rejected entries (the `ValueError` was caught as a fail-closed entry rejection); restored positions could fail during market-state revalidation.
- A portfolio accounting test asserted the mocked join received `None`, unintentionally pinning the unusable default rather than exercising the real helper contract.

Correction:
- `resolve_market_state_skew_budget()` now fails immediately with a clear error if the environment variable is missing/blank; it still accepts explicit zero and positive integer milliseconds and rejects non-integers/negative values.
- H1 workflow_dispatch now requires `max_market_state_skew_ms` and passes it to `BYBIT_MAX_MARKET_STATE_SKEW_MS`.
- The runner regression now asserts missing/blank values fail before replay.

Verification:
- Research CI [#41928296140](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41928296140) completed SUCCESS on commit `6dffae15ac9d7525b329273b0de66a8a124c550b`.
- Compile and deterministic test suite passed; H1 runner execution-gate tests and portfolio accounting/risk-budget tests passed. No market PnL runner was dispatched.

Scope: this fixes a configuration/integration failure, not the historical snapshot effective-time limitation. No default skew was invented; the operator must choose and supply an explicit budget. Data and strategy readiness remain BLOCKED.


### Constructor-level fail-fast follow-up

The engine constructor now also rejects configuration that enables both dated instrument and risk-tier histories while omitting `max_market_state_skew_ms`. This moves the failure from first entry/restored-position validation to initialization, where the configuration error is immediately visible. The joined-entry accounting regression now supplies an explicit zero-ms fixture budget, and a new constructor regression verifies missing-budget rejection.

Research CI [#41928557280](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41928557280) completed SUCCESS on commit `8fa1685db728a051f37bb59921a3048446d269b1`; engine compile, H1 runner gate, portfolio accounting/risk budget and the full deterministic suite passed. This remains offline fixture/CI verification only.


## 8. Liquidation/Mark integration follow-up (2026-11-05)

Static caller review covered `mark_price_liquidation.py`, engine Mark OHLC loader, `_liquidation_exit_price`, portfolio intrabar marks, `_manage_position`, `_close_position`, TP1 quantity transitions, funding allocation and both liquidation test modules.

### Confirmed model behavior

- Mark OHLC is loaded separately from Last/Trade OHLC; liquidation-aware mode requires full Mark OHLC and exact timestamp match for every open symbol.
- Mark adverse low/high drives position-level margin health; Last/Trade OHLC continues to drive stop execution. If both are crossed in one candle, liquidation takes priority because OHLC cannot establish event order.
- Entry LP uses entry-time tier; current MM uses the tier selected at adverse Mark notional. A dynamic tier transition can therefore trigger margin shortfall before fixed LP is touched.
- For exchange-sized positions, liquidation quantity uses exact remaining contract quantity after TP1. Legacy notional-proxy positions reconstruct quantity from entry notional and remaining fraction.
- Funding allocated to remaining margin uses the remaining share of pre-TP1 settlements and full post-TP1 settlements on the reduced quantity; same-boundary receipts are deferred.
- Liquidation close path is distinguished from ordinary exit fee/slippage treatment in the close accounting tests.

### Confirmed limitations (not defects)

1. Full-candle adverse Mark extreme is used without tick sequence. Same-candle liquidation-before-stop is a deliberate conservative ordering assumption, not event reconstruction.
2. `evaluate_isolated_margin_health` always applies the supplied net funding cost directly to position margin. Official Bybit funding cash-routing can first debit/credit available balance; exact margin effect depends on wallet balance and account mode. Existing audit section 9 records this mismatch. Current engine is a position-level stress approximation, not wallet/account simulation.
3. Extra margin / auto-add-margin is not persisted in the engine position lifecycle; pure calculator supports an explicit extra-margin input, but engine integration does not claim to model manual margin changes.
4. Partial realized PnL is not implicitly transferred into remaining position margin. Cross/Portfolio Margin, collateral offsets, active-order tier aggregation, partial-liquidation ladder, AMR, insurance/ADL and exchange liquidation execution remain out of scope.
5. Historical Mark OHLC, risk-tier and instrument snapshots are not complete/authoritative; fetched_at is observation time, not effective_from. No empirical liquidation-safety claim is possible.

No new confirmed arithmetic defect was established in this static pass. No liquidation formulas or trading logic were changed.

### Test fixture correction and CI

One integration regression still encoded the old invalid `None` skew-budget behavior. Updated `tests/test_mark_price_engine_integration.py` to pass an explicit `0` ms fixture budget and assert the join receives `0`. The existing mocked join failure still tests fail-closed behavior; constructor and runner tests separately test missing-budget rejection.

Research CI [#41928978081](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41928978081) completed **SUCCESS** on commit `08afcdd6c16e6c32fa33198e2ff56c66023ce585`. All 58 workflow steps passed, including engine compile, isolated liquidation formulas, Mark OHLC integration, funding, instrument/risk snapshots, portfolio accounting and the full deterministic research suite.

**Scope disclosure:** the repository's normal research-checks workflow also ran its existing read-only CryptoFetch archive integrity/overlap audit and H-A preparation-manifest step against archives already present in the repository. The workflow did not download new archives or extract files to disk; the audit opened ZIP members and streamed their contents for integrity/overlap analysis. No PnL replay, market PnL test, API call, collector, private account query, paper/live action or parameter sweep was run.

The liquidation/data/strategy/paper/live readiness gates remain BLOCKED.


## 9. Portfolio PnL / isolated margin funding allocation — follow-up (2026-11-05)

Static trace completed from `_apply_tp1` through `_unrealized_pnl_at_marks`, `_close_position`, `accrued_funding_cost`, `accrued_funding_cost_for_remaining_margin`, and `AdaptiveRiskManager` equity updates.

### Confirmed ledger invariants

- TP1 gross PnL is carried once in `realized_tp1_gross_usdt`; remaining gross is calculated from exact remaining contract quantity for exchange-sized positions (legacy fallback uses remaining fraction).
- Entry, TP1 and final-exit fee/slippage legs are independently calculated on their execution notionals. Final trade net is gross less fee, slippage and full lifecycle funding.
- Open-position MTM combines the realized TP1 leg and remaining marked leg, subtracts the same entry/TP1 cost legs and a conservative taker estimate for the remaining exit, and includes full lifecycle funding cashflows. The taker-MTM vs maker-target-close difference is already documented and regression-tested as a deliberate conservative stress asymmetry.
- At final close, the position is removed before remaining open positions are re-marked; the closed trade net is added once to realized equity. Equity remains `realized_equity + unrealized_pnl`.
- Remaining isolated margin uses exact remaining contract ratio for all accrued funding history after TP1, while final closed-trade PnL retains the full lifecycle funding. This is the intended split between trade PnL and the open leg's allocated share.
- Existing deterministic tests cover TP1/full-close lifecycle, funding boundaries, exchange-sized quantities, MTM/final-close reconciliation, same-timestamp close ordering and shared-capital equity reconciliation.

### Confirmed limitation: no wallet-level funding routing

`evaluate_isolated_margin_health` subtracts net funding allocated to the open position directly from that position's margin balance. Bybit funding cash routing can debit/credit available balance first and only affect position margin under account-specific conditions. The engine has no available-balance ledger, wallet funding movements or account-mode-specific routing state.

This is **not uniformly conservative**:
- a funding payment covered by available balance may be charged against position margin too early, overstating liquidation risk;
- a funding receipt credited to available balance may be applied to position margin, understating liquidation risk for that isolated position;
- direction/magnitude depends on cashflow sign and wallet state.

A correct repair requires a separately modelled wallet/available-balance ledger, explicit account mode and a documented rule for allocating funding/realized partial-close proceeds to isolated position margin. Do not patch by simply removing funding from margin or assuming every funding event hits the position: either shortcut can reverse the error. No such account-level behavior is claimed by the current model.

### Partial-close realized PnL and margin

Realized TP1 PnL is included in portfolio realized equity, but is not automatically transferred into the remaining position's isolated margin. That is a deliberate boundary of the current position-level approximation, not a verified Bybit wallet-routing implementation. The same applies to manual extra margin and auto-add-margin.

### Conclusion

No new confirmed double-counting or sign defect was established in the deterministic portfolio/funding lifecycle. The remaining wallet-routing and partial-close margin treatment are **account-model gaps**, not safely repairable from the present position-only state. Do not infer exchange-exact liquidation safety or PnL from this code path. Data, strategy and account-level liquidation readiness remain BLOCKED.

No production code or trading formulas changed in this follow-up; existing CI-backed tests remain the evidence for the current deterministic contracts.
