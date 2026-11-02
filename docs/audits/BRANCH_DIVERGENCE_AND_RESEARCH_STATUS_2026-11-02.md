# Текущий аудит расхождения веток и исследовательских результатов — 2026-11-02

## Точный снимок Git

Репозиторий: `nikitanecilli-bit/bybit-trading-bot`

- `main`: `e86b1bfd6d086684c32e395e0dc383802665d59f`
- `research/market-regime-v1-main`: `df3b1ed1c37b5895aadb3636c088123e963bec73`
- merge-base: `ae599a2f3279e15fe27360662f94f0e7ef8db5be`
- GitHub Compare (`main...research`): status `diverged`, research ahead 715, behind 13.
- Pull Request #4: open, draft, not merged, `mergeable=false`, `mergeable_state=dirty`; head is current research HEAD.
- PR reports 163 changed files, +17,558 / -116 lines.

**Interpretation:** 705 commits is not 705 independent strategy changes; the branch has a long divergent history since the common ancestor. The count is a graph relationship, not a measure of code quality. The PR is not safe to merge as-is.

## The 13 commits on main after the merge base

The current main-only commit sequence (newest first) is:

1. `e86b1bfd` — Add files via upload.
2. `f4767bd0` — revert accidental research-only file on main.
3. `68f90736` — revert accidental research-only file on main.
4. `f432b8e0` — CI: add H1 filter exit attribution workflow.
5. `1cd0cb42` — research: add H1 filter exit attribution.
6. `9d39488c` — Add files via upload.
7. `99ea5d4f` — expose read-only Bybit API check from default branch.
8. `94eef682` — link repository navigation from README.
9. `1a1b8b5f` — separate technical checks from manual market backtests.
10. `fb628169` — organize main repository structure.
11. `9c103e63` — add repository branch navigation.
12. `813805ab` — merge Audit PR.
13. `426ac3b4` — Add files via upload.

### Main-side changes relevant to the research branch

- README and repository navigation were reorganized; current main README explicitly documents research safety and Binance OHLCV proxy limitations.
- Technical CI and manual historical market backtests were separated on main.
- A default-branch manual read-only Bybit credential workflow was added. It checks out `research/market-regime-v1-main` with `persist-credentials: false`, then runs the read-only credential preflight. It requires BYBIT_API_KEY / BYBIT_API_SECRET repository secrets and an explicit manual dispatch; it has not been run as part of this audit.
- Main added standalone dashboard/legacy quant research files and copies of older audit materials. These are not evidence of current strategy performance.
- `scripts/run_uploaded_dataset_backtests.py` has only a small path-root refactor between main and research; the simulation configuration and trade calculation body are materially the same in the inspected versions.
- The branch's current research-checks workflow is broader than main's minimal baseline and targets the research branch. Do not replace it with main's smaller workflow.

## Merge / maintenance decision

- Do not merge PR #4.
- Do not rebase, reset, force-push, or delete any research branch.
- Do not merge main into the research branch merely to reduce the behind count. First preserve both heads and inspect conflicts, especially workflow paths, root-vs-`docs/` report moves, README, dashboard/archive renames and research artifacts.
- Treat PR #4 as a historical integration container, not a merge-ready deliverable. A later integration should use small, reviewed cherry-picks or a fresh integration branch from current main, with tests and artifact provenance.
- Keep main unchanged.

## Research result synthesis: E09–E13

### E09: fold differences

E09 describes the five-symbol exploratory sample. Fold 2 had weaker broad-market breadth and 24–72h momentum despite similar local volume/breakout signal characteristics. Market execution fold-2 gross edge (+265.70 USDT) did not cover fees/slippage (623.55 USDT), leaving -357.85 USDT. The result is descriptive and based on only five preselected symbols, not a causal regime proof.

### E10: cross-sectional body-gate replication

47 symbols, per-symbol isolated 10k USDT runs; 2,422 trades OFF vs 1,797 ON. Sum of independent net PnL improved from -22,857.66 to -15,912.54, but remained deeply negative. Median symbol-fold PF moved 0.81 to 0.78. Fold 1 worsened, folds 2/3 improved. This is not a shared-capital portfolio result.

### E11: shared-capital replay

47 symbols compete for one 10k USDT account per fold, max five concurrent positions. Body gate OFF/ON summed independent fold net: -3,178.61 / -2,774.00 USDT. PF 0.859 / 0.862. Costs increased by 386.03 USDT despite fewer trades. Fold 1 and 2 remain negative; fold 3 modestly positive. This is the stricter portfolio evidence.

### E12: causal context diagnostics

Fold 2 had the lowest breadth, 72h momentum, ATR and cross-sectional dispersion. Fold 1 winners were often observed under weak broad-market context, while fold 3 winners aligned more with broad trend expansion. Fold 2 winners and losers were barely separable by these broad context features. The evidence argues against a universal one-sided market-trend veto.

### E13: frozen compression gate

One causal rule was tested: broad median ATR% and cross-sectional IQR72 both below expanding q25 of prior completed observations, with 336h warm-up. Shared-capital summed fold net improved from -3,178.61 to -2,741.72 USDT; PF 0.859 to 0.870. Fold 1 improved (-617.62 to -294.93), fold 2 remained strongly negative (-2,970.05 to -2,614.55), fold 3 profit fell (+409.06 to +167.76). Gate is promising but unproven, not production-ready and not an untouched holdout.

All E09–E13 runs use Binance OHLCV proxy, modelled fees/slippage, omit funding, and lack Bybit order-book/queue/partial-fill/mark-price liquidation realism. Fold data were already inspected; they are not blind holdout.

## Data / exchange blockers still open

1. Public Bybit instrument-info snapshot workflow received HTTP 403; no dated snapshot is available. Do not infer an empty universe or substitute unverified specs.
2. Read-only private API check has not been manually run with user's GitHub Secrets; no API-key identity/read-only permission is verified.
3. Reconciliation collector and comparator have fixture/CI coverage only. No real exchange snapshot exists; comparator correctly remains fail-closed.
4. Funding helper and exchange sizing helper exist, but exact dated instrument specs and historical mark/funding coverage are not established for the backtest universe.
5. Initial/maintenance margin, risk tiers, liquidation price/fees and actual exchange liquidation remain unmodelled in v14.
6. OHLC maker fills do not model spread, queue priority, partial fills, latency or adverse selection.

## CI evidence freshness

The latest passing research-checks workflow observed during this audit was run `41470373006`, commit `01bd6409bc3b2712db889aa94b234fb95448256e`. It passed the technical test job. The two subsequent commits on current research HEAD (`95b87b32`, `df3b1ed1`) only update audit documentation. Do not describe the latest HEAD itself as having a fresh workflow run unless a new run is observed.

The separate instrument snapshot run `41468304134` failed on HTTP 403; that failure is external fetch availability, not a unit-test failure.

## Next safe actions

1. Keep the current rule and all E09–E13 outputs frozen; no threshold sweep or strategy selection on these same folds.
2. Complete E01–E09 provenance reconciliation (run SHA, code SHA, config, dataset/archive hash, exact folds, cost model, artifact hash). Missing evidence is UNVERIFIED.
3. Audit the data archive inventory and per-symbol point-in-time coverage, including delisted/renamed symbols and survivorship bias.
4. Finish deterministic engine lifecycle checks (pending expiry, stop/TP collision, fill-bar stop timing, trailing timing, long/short symmetry, shared-capital event ordering).
5. Do not claim exchange-executable profitability until dated Bybit specs, funding/mark coverage, realistic execution costs and margin/liquidation are addressed.
6. Use a genuinely later untouched period for the next strategy validation; if none exists, remain in diagnostic/code-audit mode.

## Final status

The research branch has passed deterministic technical CI, but the strategy is not profitable by demonstrated shared-capital evidence and the execution model is not exchange-complete. E13 reduces historical losses modestly but does not produce a robust positive edge. Main and research histories are diverged; PR #4 is draft/dirty and must not be merged automatically.


## E01–E09 primary workflow provenance cross-check

Run metadata was re-read from GitHub Actions and compared with the experiment ledger. All successful artifact runs below still have non-expired artifacts as of this audit.

| ID | Workflow run | Result | Run commit | Artifact |
|---|---:|---|---|---|
| E01 | [40578394090](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578394090) | success | `4e27b6adf8c3199ce78446d33703984394c94152` | `12768870777`, h1-direction-execution-ablation |
| E02 | [40578394009](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578394009) | success | `4e27b6adf8c3199ce78446d33703984394c94152` | `12767913281`, execution-policy-walk-forward |
| E03 | [40578393971](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578393971) | success | `4e27b6adf8c3199ce78446d33703984394c94152` | `12768457441`, execution-cost-ablation-report |
| E04 | [40588753444](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40588753444) | success | `4b291265976d66f77b692d057a921d170be865da` | `12773465436`, h1-chase-limit-ablation |
| E05 | [40541270994](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40541270994) | failure | `c0b61c2e87c46b347179d811c1410a6ad84478b0` | none |
| E06 | [40587243295](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40587243295) | success | `9601f4d855f69d58e7353655a0c62060f519de13` | `12772483348`, h1-signal-trade-diagnostics |
| E07 | [40566687595](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40566687595) | success | `a5a9851622544b4d16a0aec7f9ccab7d612cc608` | `12764160379` primary; `12764110430` reserve |
| E08 | [40650477230](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40650477230) | success | `17c31df587e802da7c74d3c8e2f53a656a632668` | `12799089180`, h1-chase-gate-decoupling |
| E09 | [41355171678](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41355171678) | success | `a11606b2e37c750b3b39ab6fb7201916a554efac` | `13103031404`, e09-h1-gate-factorial |

### What this establishes and what it does not

- E01–E03 were run from the same code commit; they are distinct workflows/experiments, not three code revisions.
- E04, E06, E07, E08 and E09 have separate recorded run commits and retrievable artifacts.
- E05 is an actual failed Bybit recent-data validation run with no artifact. It is not a successful market holdout.
- E08's ledger explicitly identifies a confound: for limit mode the chase parameter also gates signal candle body; for market mode it is applied to next-open gap. Its market/limit table is not a clean causal body-vs-gap comparison. E09 was designed to separate those factors.
- E09's gap gate at 2% did not change any trades in its sample; body gate was the active factor. This does not prove all gap protection is useless, only that this threshold never fired in those data.
- Artifact existence and run success establish reproducibility inputs, not profitability or correctness of the execution model. Artifact SHA-256 is recorded in the E09–E13 reports where available; older E01–E08 report entries do not consistently include hashes or a complete dataset manifest.
- This cross-check is run-level provenance only. It does not yet verify that every artifact's embedded CSV/config hashes match the report's numbers. That remains the next artifact-level audit.


### Artifact-level verification completed for E01–E09

Downloaded the eight available E01–E04/E06–E08 artifacts plus E09. ZIP hashes below were calculated from the downloaded bytes; E09's computed hash exactly matches the SHA-256 already recorded in its report.

| Experiment | Artifact ID | SHA-256 of downloaded ZIP | Content-level check |
|---|---:|---|---|
| E01 | 12768870777 | `a61dfb45f41792ae4dbfb2e0f09975b389e6b0aa1c6d89c64824087065823ebc` | 600 rows; aggregate H1 variants reproduce ledger totals exactly |
| E02 | 12767913281 | `66483e95ece78e773dd47494bbbdfd8bd2a738f7f6be1e28958463d622122c83` | 174 rows; H1 and 15m selected-policy sums reproduce ledger exactly |
| E03 | 12768457441 | `880e4408f2d8ee2bd3e054ef76b43f06d089843da7086a2282999858645bfd66` | 754 rows; H1/15m execution-cost variants reproduce ledger totals exactly |
| E04 | 12773465436 | `e4061b3f49637e725730fe966bad000dc4a4f80d67733f8beca8fe5e15a206f7` | 15 rows; 1.5/2.0/2.5/3.0/100% chase totals reproduce ledger exactly |
| E06 | 12772483348 | `d52b42bc8e39f00f088f2d43d08647aabf9408789d4e92c6008271691e2dad27` | 5,060 signal rows, 910 trade rows, 21 market-context rows; diagnostic artifact |
| E07 primary | 12764160379 | `28b0275b4feee893b77f3b37ef66ba9fa07dde58ebcc2f431c7b216f5c41ccc7` | 108 shared-capital configurations; ledger example vol1.6 / breakoutATR0.25 / cost×1.5 matches all three fold values |
| E07 reserve | 12764110430 | `ae6f71dec3923f692cf98ac0a35fb1ebbcb97bf61fff7734db4e9cbe1e67b494` | Reserve artifact downloaded; separate universe output, not merged with primary |
| E08 | 12799089180 | `05e8aaa9b18c4509059c7db8eb2114fb1da6e76da1d3c9850832bbf669496c5b` | 30 summary rows, 2,160 trades, 10,120 signals; totals reproduce ledger and expose body/chase confound |
| E09 | 13103031404 | `503aa4ef24f6f7ef5adef0a63297e0deeeb7298c55b4d3254df1be7dd274416f` | 24 summary rows; exact hash match to E09 report; gap gate ON/OFF rows are identical in all cells |

### Artifact reconciliation findings

- E01 independently recomputed H1 sums: both_market -16,911.93 (2,699 trades), long_market +1,056.65 (1,458), both_limit20 -261.36 (2,395), long_limit20 +9,823.41 (1,308). This matches the ledger.
- E02 recomputed selected-policy totals: 1h -5,999.65 vs market -16,911.93; 15m -11,470.98 vs market -24,039.44. This matches the ledger.
- E03 recomputed 1h market -5,923.64, limit 5bps/3 bars +457.46, 10bps/3 +1,204.81, 10bps/5 +1,565.78, 20bps/3 +3,143.13; all 15m tested variants remain negative. This matches the ledger.
- E04 recomputed sums by chase cap: +3,799.40 / +4,030.24 / +4,899.37 / +3,400.55 / +1,428.39 USDT for 1.5 / 2.0 / 2.5 / 3.0 / 100%. This matches the ledger.
- E07 selected example recomputed exactly: fold 1 +984.67, fold 2 +262.97, fold 3 +2,699.68. This is one selected row family from a 36-configuration × 3-fold search, so it is subject to selection bias.
- E08 recomputed limit totals match the ledger (+3,799.40 to +4,899.37 for 1.5–2.5% caps); market result is -436.83 at every cap because market mode does not apply that same body gate. This confirms the ledger's warning that E08 is not a clean one-factor causal comparison.
- E09 summary reproduces the report. At 2% gap threshold, all gap ON/OFF pairs are identical; the threshold never fired in this sample.

E01–E04/E06–E08 did not have artifact ZIP SHA-256 values consistently recorded in their original reports; the hashes above now provide a downloaded-byte identity for these archived files. This verifies artifact identity and report arithmetic, not the underlying data's exchange provenance or fill realism.


### E10–E13 artifact identity and baseline integrity

Downloaded the later cross-sectional/shared-capital artifacts and checked the SHA-256 of the ZIP bytes against the reports:

| Experiment | Artifact ID | Computed ZIP SHA-256 | Report match |
|---|---:|---|---|
| E10 | 13104981517 | `64832db93e5912c877debcfd4548cbf9a6fb2beb71ca647c39762e1321b963fa` | exact |
| E11 | 13105661683 | `441e518a683435e47327cb85bb741c8fcb24e734ded1ab720722dc50dd588765` | exact |
| E12 | 13105721458 | `5ac82041680ea6bcbb90561a6da11687c15c171885dd66034db321ce63bd8854` | exact |
| E13 | 13105403824 | `9930d6f3651305ef9dcf254c85bc0b50b24cb098b6b367accbaaae4bbad6f601` | exact |

E11 and E13 both embed the same six source-archive SHA-256 values in their manifests. The E13 compression-OFF baseline reproduces E11 body-gate-OFF per-fold metrics exactly:
- Fold 1: -617.62 USDT, 207 trades.
- Fold 2: -2,970.05 USDT, 227 trades.
- Fold 3: +409.06 USDT, 338 trades.

This is a meaningful internal reproducibility check: the E13 replay's baseline has no observed drift from E11. It does not prove correctness of the simulator or Bybit execution realism.

E13 compression-ON rows from the artifact reproduce the report:
- Fold 1: -294.93 USDT, 211 trades, 65 candidate signals blocked.
- Fold 2: -2,614.55 USDT, 197 trades, 137 blocked.
- Fold 3: +167.76 USDT, 316 trades, 89 blocked.

The compression gate improves the sum by +436.89 USDT, but gated fold 1 and fold 2 remain negative; gated fold 3 remains positive but is reduced from +409.06 to +167.76. No claim of positive overall expectancy is justified.


### E10/E11/E13 universe and source-manifest equivalence

A direct row-by-row comparison of the downloaded E10, E11 and E13 universe manifests found exact equality across all 50 symbol rows and all manifest columns:
- same 50 discovered symbols;
- same 47 included symbols;
- same three exclusions (AERO, GRAM, HYPE) and exclusion reasons;
- same per-symbol bars, start/end timestamps, per-fold bar counts and source archive names.

The six source ZIP SHA-256 values embedded in E10, E11 and E13 are also identical. Thus the E10 vs E11 difference is not explained by a different symbol list or different per-symbol bar coverage in the manifests: it is primarily the accounting/simulation design difference (independent 10k accounts per symbol versus one shared-capital portfolio, plus synchronized event ordering). This makes E11 the more relevant portfolio result.

Caveat remains: the 50-symbol CryptoFetch archive is a fixed uploaded universe, not a verified point-in-time historical Bybit listing universe. New listings with insufficient first-fold history were excluded; delisted, renamed or unavailable historical instruments may be absent. Survivorship/universe-selection bias is therefore not fully ruled out.


## ENG-RISK-001 — fill-bar portfolio mark-to-market gap (confirmed and fixed)

### Confirmed defect

The pre-entry mark was calculated while the symbol had no open position, so its intrabar risk mark was the candle close. A successful pending fill then opened a position, but the engine did not refresh that symbol's adverse mark or rerun portfolio MTM before managing the new position. The entry-bar adverse wick could be recorded in trade MAE while being omitted from portfolio equity, daily-stop and kill-switch evaluation. The next bar replaced the old mark, so the excursion could be permanently missed by portfolio drawdown tracking.

### Evidence and correction

- Preregistered card: [ENG-RISK-001](../research/experiment_cards/ENG-RISK-001_FILL_BAR_MTM_RU.md).
- Regression tests committed first: `bf0b556f7cb0b88620c62af22634b6d95612dfc9`.
- Test-only CI [#41475914811](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41475914811) failed at the new long test with only one pre-fill mark observed: `[(0, bar_close_ts)]`, instead of the expected pre-fill and post-fill marks.
- Fix commit: `f65c08bec78b179a9a89832ce31b574740f4dce3`. After successful fill, engine now calculates `_risk_mark_for_position(new_position, curr)`, updates `_intrabar_risk_marks[symbol]`, and calls `_update_mark_to_market(bar_close_ts)` before position management.
- Passing CI [#41475941543](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41475941543): SUCCESS. New long and short cases pass; gap execution suite 27/27, time model 38/38, persistence 54/54; compile, portfolio-risk suite and secret scan pass. All workflow steps completed successfully.
- Card status: ACCEPT for research-engine risk accounting only.

### Remaining boundary

For intrabar limit fills, OHLC cannot prove whether the adverse extreme happened before or after the fill. The full adverse wick is intentionally conservative and consistent with the existing fill-bar MAE convention. This fix makes risk accounting safer; it does not make OHLC execution realistic or establish profitability. No market backtests were run.


### Latest Git snapshot after ENG-RISK-001 (15:54 UTC)

- Research HEAD has since advanced through documentation-only audit commits; the latest code-changing commit remains `f65c08bec78b179a9a89832ce31b574740f4dce3`.
- Compare status remains `diverged`: 715 commits ahead, 13 behind main.
- PR #4 now reports 163 changed files, +17,558 / -116 lines; it remains open and unmerged. GitHub's mergeability field is currently unknown, so do not treat it as merge-ready.
- Latest code-changing commit `f65c08bec78b179a9a89832ce31b574740f4dce3` passed Research engine checks #41475941543. The two commits after it update documentation only; the current docs HEAD does not have a separate new CI run.
