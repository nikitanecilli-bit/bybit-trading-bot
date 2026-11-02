# Текущий аудит расхождения веток и исследовательских результатов — 2026-11-02

## Точный снимок Git

Репозиторий: `nikitanecilli-bit/bybit-trading-bot`

- `main`: `e86b1bfd6d086684c32e395e0dc383802665d59f`
- `research/market-regime-v1-main`: `df3b1ed1c37b5895aadb3636c088123e963bec73`
- merge-base: `ae599a2f3279e15fe27360662f94f0e7ef8db5be`
- GitHub Compare (`main...research`): status `diverged`, research ahead 705, behind 13.
- Pull Request #4: open, draft, not merged, `mergeable=false`, `mergeable_state=dirty`; head is current research HEAD.
- PR reports 161 changed files, +17,196 / -116 lines.

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
