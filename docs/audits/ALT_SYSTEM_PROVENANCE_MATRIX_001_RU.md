# ALT-SYSTEM-RESEARCH-001 — provenance matrix (P1, read-only)

Дата: 2026-11-05  
Ветка: `research/market-regime-v1-main`  
Статус: PARTIAL — historical ledger cross-referenced; missing provenance explicitly retained as gaps.  
Scope: existing repository documents and already-published GitHub Actions metadata only. No workflow reruns, artifact downloads, backtests, PnL recalculation, API calls or data acquisition.

## Правила интерпретации

- Workflow success confirms execution of that workflow, not strategy profitability.
- An artifact link/ID recorded in the ledger is not equivalent to re-verifying its current availability or contents.
- A run's source commit, script, dataset hash, complete universe, fold boundaries and cost assumptions must be independently tied together before two results can be compared.
- "Not recorded in the reviewed ledger" means unknown, not absent.
- PnL values below are historical reported results, not recalculated in this audit.

## Strategy experiment matrix

| ID | Run / artifact recorded in ledger | Code commit / script | Data, universe and design | Reported result / admissible conclusion | Provenance gaps / status |
|---|---|---|---|---|---|
| E01 | Run 40578394090 | Not recorded in summary ledger | H1, 50 symbols, 3 chronological folds, per-symbol independent tests | Long+short market -16,911.93; long-only market +1,056.65; long+short limit -261.36; long-only limit +9,823.41 USDT | Dataset identity/hash, exact folds, script/config and source commit not tied in summary. Preliminary; limit fill optimistic; not shared capital. |
| E02 | Run 40578394009 | Not recorded in summary ledger | 15m and H1 walk-forward execution policy comparison | 15m -11,470.98 vs market -24,039.44; H1 -5,999.65 vs -16,911.93; H1 median PF 0.92 | Exact artifacts/config/data hash and source commit not recorded in summary. Aggregate remains negative. |
| E03 | Run 40578393971 | Not recorded in summary ledger | 50 independent symbols, H1; limit offsets and expiry variants | Market -5,923.64; tested limit variants +457.46 to +3,143.13; 15m variants negative | Dataset hash, exact fold ranges, script/config/commit not recorded in summary. Strong optimistic-fill risk; not portfolio evidence. |
| E04 | Run 40588753444 | Not recorded in summary ledger | 5 selected symbols plus 50-symbol market context, 3 folds | Chase 1.5–3% +3,400.55 to +4,899.37; unrestricted +1,428.39 | Binance OHLCV proxy noted; selected five symbols, fold-3 concentration. Exact artifact/hash/config/commit not recorded in summary. Selection-biased diagnostic. |
| E05 | Run 40541270994 | Not recorded in summary ledger | Fresh Bybit data / holdout acquisition check | HTTP 403; no confirmed holdout | No data package produced. Operational blocker, not a strategy result. |
| E06 | Run 40587243295 | Not recorded in summary ledger | H1 signal and market-context diagnostics; fold dates corrected during development | Diagnostics artifacts reported; no isolated independent PnL effect | Artifact identity, data hash, exact script/config/commit and final fold manifest not tied in summary. Diagnostic only. |
| E07 | Run 40566687595 | Not recorded in summary ledger | Shared-capital, 5 selected symbols, 3 folds, 108 filter/cost combinations | Example selected configuration sums +3,947.32 USDT across separately restarted folds | Binance proxy, multiple-testing/selection bias, limit touch treated as fill without queue/spread/partial fills. Exact selected configuration's selection path and artifact provenance need forensic confirmation. Not independent edge. |
| E08 | Run 40650477230; artifact 12799089180 | Commit 17c31df587e802da7c74d3c8e2f53a656a632668; `scripts/run_e08...` path not stated in ledger | Binance OHLCV proxy; H1; RAY/PUMP/TAO/AAVE/CAKE; three folds; ×2 costs; 10k initial capital; 1% risk; max 5 positions | Limit variants +3,400.55 to +4,899.37; market -436.83. 2,160 trades and 10,120 signals | Artifact SHA and exact script path/config not recorded in this E08 section. Not a clean body-vs-gap factorial; market/limit semantics differ; funding omitted; maker fill optimistic. |
| E09 | Run 41355171678; artifact 13103031404 | Commit 483278f51d99d402215a1f26a690ea2661e28939; `scripts/run_e09_h1_gate_factorial.py` | Binance proxy; same 5 symbols, H1, 3 folds; 24 cells; ×2 costs; fixed 2% gap gate | Market body gate OFF -436.83 / ON +2,272.91; limit OFF +1,428.39 / ON +4,030.24. Gap gate changed no trades | Artifact SHA 503aa4ef...; detailed folds and configuration in ledger. Five selected symbols; funding absent; limit fill optimistic. First attempt and zero-test attempt explicitly excluded; final workflow ran 18/18 gap tests. Diagnostic only. |
| E10 | Run 41360728294; artifact 13104981517 | Commit 483278f51d99d402215a1f26a690ea2661e28939; `scripts/run_e10_h1_body_gate_replication.py` | Binance proxy + six CryptoFetch archives; 50 discovered, 47 included; H1; 282 symbol-fold independent runs | Sum independent net OFF -22,857.66 / ON -15,912.54; still negative; 2,422 vs 1,797 trades | Artifact SHA 64832db9...; per-symbol archive SHA/coverage in artifact manifest, not reproduced here. Not shared-capital PnL; not blind holdout; funding absent. |
| E11 | Run 41361376448; artifact 13105661683 | Commit ae6f7b4c99b79cbe31fdfeded8780a058b118049; `scripts/run_e11_h1_shared_capital_replay.py` | Binance proxy; 47 symbols; common 4,321 H1 bars (2026-04-29 to 2026-10-26 UTC); 3 folds; shared 10k account per fold; market; ×2 costs | Body OFF -3,178.61 / ON -2,774.00 summed across separate folds; still negative; no robust edge | Artifact SHA 441e518a...; exact archive-by-symbol manifest in artifact. Fold restarts; funding absent; not blind holdout. |
| E12 | Run 41361856404; artifact 13105721458 | Commit 4100d800761983d9de148f368d2402280b3dc6be; `scripts/run_e12_h1_market_context_diagnostics.py` | Completed-bar context on 4,249 timestamps; fixed 47-symbol E11 universe; no backtest | Descriptive market breadth, returns, efficiency, ATR and dispersion; fold 2 weaker/choppier | Artifact SHA 5ac82041...; not a PnL test or validated regime classifier. |
| E13 | Run 41362217727; artifact 13105403824 | Commit f4da3cca0c0dc79cee86350ba6a680fc461e47fc; `scripts/run_e13_h1_compression_gate_replay.py` | Binance proxy; 47 aligned symbols; H1; causal expanding-q25 compression rule; shared 10k account per fold; market; ×2 costs | Compression ON -2,741.72 vs baseline -3,178.61; still negative; fold 2 materially negative and fold 3 profit reduced | Artifact SHA 9930d6f3...; same fold restarts; funding absent; not blind holdout. |

## Additional hypotheses recorded outside E01–E13

| Hypothesis | Existing evidence in reviewed audit | Provenance status | Decision |
|---|---|---|---|
| H-A relative strength | Shared-capital aggregate -6,135.26 vs baseline -5,635.98 USDT; worse by 499.28; all three folds negative | Run ID, artifact ID/hash, source commit, script/config, exact data manifest and fold dates not identified in reviewed STRATEGY-REFOCUS audit | Reject this tested configuration; do not tune on same folds. |
| H-C post-break invalidation | Proxy net -2,880.12 vs baseline -2,720.47; more trades/costs; PF below 1 | Run ID, artifact ID/hash, source commit, script/config, exact data manifest and fold dates not identified in reviewed STRATEGY-REFOCUS audit | Reject as profitable in tested configuration; do not tune on same window. |

## Cross-cutting findings

1. The ledger explicitly warns that net-PnL entries using v14 `_close_position()` before the exit fee/slippage-by-execution-notional correction are provisional pending provenance-level engine-version checks. This must be applied per experiment, not blanket-assumed for every E-ID.
2. E01–E07 summary rows do not provide sufficient exact commit/script/config/data-hash/fold linkage for a reproducibility claim.
3. E08–E13 have stronger recorded run/artifact/commit/script lineage, but the exact per-symbol archive manifest, artifact contents and complete runtime provenance still need independent verification before replay or comparison.
4. E01–E04/E06 contain per-symbol or selected-symbol designs; E07 and E11/E13 are shared-capital by fold. These results are not directly comparable.
5. E10's large independent-symbol aggregate improvement is not portfolio evidence; E11 shows a much smaller shared-capital improvement and remains negative.
6. H-A/H-C have summary conclusions but incomplete provenance in the reviewed audit; preserve their rejection as configuration-specific and do not invent missing run metadata.
7. No prior result establishes a positive, robust edge for an autonomous altcoin portfolio. Bybit-native market history, complete point-in-time universe, dated contract specifications, full funding and realistic execution remain unresolved gates.

## Next read-only actions

- Resolve E01–E07 run metadata and artifact manifests from existing Actions records, where still available.
- Verify E08–E13 artifact availability and hashes without downloading/extracting archive datasets; if an artifact cannot be verified, mark it unavailable rather than infer its contents.
- Locate H-A/H-C primary reports and exact run references; otherwise keep them as summary-only records.
- Map each engine commit against the accounting corrections and label results provisional/impacted/unknown.
- Only after these checks, publish the data acceptance checklist and missing-input list for P2.


## Проверка наличия опубликованных Actions artifacts (metadata only)

Проверены metadata artifacts для исторических run IDs; содержимое архивов/artifacts не скачивалось и не распаковывалось.

| Run | Artifact metadata | Вывод |
|---|---|---|
| 40578394090 | `h1-direction-execution-ablation`, ID `12768870777`, 13,732 bytes, not expired | Artifact зарегистрирован и доступен по metadata. |
| 40578394009 | `execution-policy-walk-forward`, ID `12767913281`, 6,453 bytes, not expired | Artifact зарегистрирован и доступен по metadata. |
| 40578393971 | `execution-cost-ablation-report`, ID `12768457441`, 20,664 bytes, not expired | Artifact зарегистрирован и доступен по metadata. |
| 40588753444 | `h1-chase-limit-ablation`, ID `12773465436`, 1,106,266 bytes, not expired | Artifact зарегистрирован и доступен по metadata. |
| 40541270994 | No artifacts returned | Нет сохранённого Actions artifact в проверенной выдаче. |
| 40587243295 | `h1-signal-trade-diagnostics`, ID `12772483348`, 1,107,852 bytes, not expired | Artifact зарегистрирован и доступен по metadata. |
| 40566687595 | `h1-selected-primary`, ID `12764160379`, 13,704 bytes; `h1-selected-reserve`, ID `12764110430`, 13,929 bytes; both not expired | Два artifacts зарегистрированы и доступны по metadata. |
| 40650477230 | `h1-chase-gate-decoupling`, ID `12799089180`, 2,266,093 bytes, not expired | Совпадает с ledger. |
| 41355171678 | `e09-h1-gate-factorial`, ID `13103031404`, 1,808,245 bytes, not expired | Совпадает с ledger. |
| 41360728294 | `e10-h1-body-gate-cross-sectional`, ID `13104981517`, 2,539,639 bytes, not expired | Совпадает с ledger. |
| 41361376448 | `e11-h1-shared-capital-portfolio`, ID `13105661683`, 2,298,582 bytes, not expired | Совпадает с ledger. |
| 41361856404 | `e12-h1-market-context-diagnostics`, ID `13105721458`, 701,749 bytes, not expired | Совпадает с ledger. |
| 41362217727 | `e13-h1-compression-gate-shared-capital`, ID `13105403824`, 3,071,521 bytes, not expired | Совпадает с ledger. |

Artifact metadata availability does not validate the artifact's internal contents, hashes, dataset identity or completeness. E01–E07 source commit/script/config lineage remains incomplete; this check only closes the existence/ID field for the artifacts above. H-A/H-C exact run references remain unresolved.

## Safety and scope

No workflow reruns, artifact downloads, archive downloads/extraction, collectors, exchange API calls, market PnL recalculation, parameter sweeps, paper/live trading, private/account API or changes to `main`. PR #4 and PR #13 remain untouched.


## 2026-11-05 — P1: восстановлена точная привязка H-A / H-C к Actions artifacts

Read-only проверены первичные result reports, preregistration docs и метаданные workflow jobs/artifacts. Содержимое ZIP artifacts не скачивалось.

### H-A — Relative Strength Breakout

**Финальный отчётный run:** [#41670116033](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41670116033)
- Job `replay`: completed / success.
- Artifact: `h-a-preregistered-ohlcv-results`, ID `13247672222`, 372,438 bytes, не expired на момент проверки; создан 2026-11-03 16:03:58 UTC.
- Frozen strategy/report: H-A relative-strength rank + Donchian(20) против frozen H1 Donchian + volume baseline.
- Source: существующие CryptoFetch H1 OHLCV ZIP; dynamic archive-available universe; shared capital 10,000 USDT на каждый из трёх независимых folds; max 5 positions; 0.5% risk/trade; 2% portfolio risk cap; market entries/exits; costs ×2; funding omitted.
- Reported net: baseline −5,635.98 USDT; H-A −6,135.26 USDT; H-A хуже на 499.28 USDT. Все три folds отрицательны у обеих версий; fold 3 — основное относительное ухудшение.
- **Code SHA для финального run #41670116033 не восстановлен из проверенных report/metadata; оставить unknown, не переносить SHA другого run.**
- В preregistration также описан более ранний successful replay run [#41633199418](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41633199418): job `replay` success; artifact `h-a-preregistered-ohlcv-results`, ID `13228658700`, 313,595 bytes, not expired. В preregistration указан commit `3ac4bb0c20c48e31e0264df7fe39235cb5c8a658` для этого run. Не смешивать его artifact/commit с финальным run #41670116033 без отдельного подтверждения.
- Primary documents: `docs/reports/H_A_RELATIVE_STRENGTH_BREAKOUT_RESULTS_2026-11-03_RU.md` and `docs/research/H_A_RELATIVE_STRENGTH_BREAKOUT_PREREGISTRATION_RU.md`.

### H-C — post-break invalidation reverse-time robustness

**Run:** [#41722545731](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41722545731)
- Job `reverse-time-proxy`: completed / success.
- Artifact: `h-c-reverse-time-cryptofetch-proxy`, ID `13272957989`, 211,799 bytes, не expired на момент проверки; создан 2026-11-03 21:31:48 UTC.
- Research commit указан в первичном отчёте: `a5e7e1799f472db4cc00824dfcc774b40058165e`.
- Protocol: `H-C-RT-CRYPTOFETCH-2026-11-04-v1`; 25 frozen symbols; 2025-10-30 00:00 — 2026-04-26 23:00 UTC; 72 H1 warmup bars; shared capital 10,000 USDT per variant; market execution; fees/slippage ×2; funding and mark-price liquidation omitted.
- Baseline 313 trades, proxy net before funding −2,720.47 USDT, PF 0.63; H-C 610 trades, proxy net before funding −2,880.12 USDT, PF 0.72. H-C worse than baseline by 159.65 USDT; both variants hit 30% kill switch.
- The run is reverse-time robustness on previously examined CryptoFetch history, not forward OOS or Bybit-native PnL.
- Primary documents: `docs/reports/H_C_REVERSE_TIME_RESULTS_2026-11-04_RU.md` and `docs/research/H_C_POST_BREAK_INVALIDATION_PREREGISTRATION_RU.md`.

### Provenance conclusion

- H-A and H-C now have explicit primary report → workflow run → artifact ID/size → job conclusion links.
- H-A final run code SHA remains unresolved; earlier H-A run SHA must not be misattributed.
- Artifact metadata confirms existence and retention only; no artifact contents, hashes, or data completeness were re-verified in this step.
- H-A and H-C remain rejected in their tested configurations. No tuning, replay, artifact download, archive download, PnL calculation, API call, or order was performed.


## 2026-11-05 — P1: E01–E07 run SHA, script blob SHA и artifact ZIP digests

Проверены Actions job logs для семи исторических runs. Из checkout logs извлечён точный research commit, реально использованный каждым workflow; из upload logs — SHA-256 именно загруженного artifact ZIP (это **не** checksum исходных dataset ZIP). Артефакты не скачивались.

| Experiment | Run / job conclusion | Checked-out research commit | Script(s) at that commit — blob SHA | Artifact metadata and uploaded ZIP SHA-256 |
|---|---|---|---|---|
| E01 | [40578394090](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578394090) — `ablation: success` | `4e27b6adf8c3199ce78446d33703984394c94152` | `scripts/run_h1_direction_execution_ablation.py` — `7178fa588cf43ef67fd748037f04643be5cf21e6` | Artifact `h1-direction-execution-ablation`, ID `12768870777`, 13,732 bytes; ZIP SHA-256 `a61dfb45f41792ae4dbfb2e0f09975b389e6b0aa1c6d89c64824087065823ebc` |
| E02 | [40578394009](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578394009) — `walk-forward: success` | `4e27b6adf8c3199ce78446d33703984394c94152` | `scripts/run_execution_walk_forward.py` — `127aa4e7c9290dab80bb99dd479454cf4ce4c6c6` | Artifact `execution-policy-walk-forward`, ID `12767913281`, 6,453 bytes; ZIP SHA-256 `66483e95ece78e773dd47494bbbdfd8bd2a738f7f6be1e28958463d622122c83` |
| E03 | [40578393971](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578393971) — `execution-cost-ablation: success` | `4e27b6adf8c3199ce78446d33703984394c94152` | `scripts/run_execution_cost_ablation.py` — `682929a660339ec0d2708697b12625bfd7e10a59` | Artifact `execution-cost-ablation-report`, ID `12768457441`, 20,664 bytes; ZIP SHA-256 `880e4408f2d8ee2bd3e054ef76b43f06d089843da7086a2282999858645bfd66` |
| E04 | [40588753444](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40588753444) — `ablation: success` | `4b291265976d66f77b692d057a921d170be865da` | `scripts/run_h1_chase_limit_ablation.py` — `7e1fd655628fa42f712e391664d3ef648d37684b` | Artifact `h1-chase-limit-ablation`, ID `12773465436`, 1,106,266 bytes; ZIP SHA-256 `e4061b3f49637e725730fe966bad000dc4a4f80d67733f8beca8fe5e15a206f7` |
| E05 | [40541270994](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40541270994) — `bybit-h1-validation: failure` | `c0b61c2e87c46b347179d811c1410a6ad84478b0` | `scripts/run_bybit_h1_long_only_holdout.py` — `f032b411ed31139e05c83f794d097a7da4092de7` | No artifact. Job log records six HTTP 403 responses across the attempted public Bybit hosts; failure occurred in the download step before holdout script execution. |
| E06 | [40587243295](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40587243295) — `diagnostics: success` | `9601f4d855f69d58e7353655a0c62060f519de13` | `scripts/run_h1_signal_trade_diagnostics.py` — `3937413c38eb9fb086992e13483a12c37db610fc`; `scripts/run_h1_market_context_diagnostics.py` — `bf0db50b7871ff1b1bac4f744a5f730adcc53413` | Artifact `h1-signal-trade-diagnostics`, ID `12772483348`, 1,107,852 bytes; ZIP SHA-256 `d52b42bc8e39f00f088f2d43d08647aabf9408789d4e92c6008271691e2dad27` |
| E07 | [40566687595](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40566687595) — primary and reserve matrix jobs both success | `a5a9851622544b4d16a0aec7f9ccab7d612cc608` | `scripts/run_h1_shared_capital_portfolio_validation.py` — `bee1708cf94bd4ee53fdaf09aa9dc6b127f79c8f` | Primary artifact ID `12764160379`, 13,704 bytes; ZIP SHA-256 `28b0275b4feee893b77f3b37ef66ba9fa07dde58ebcc2f431c7b216f5c41ccc7`. Reserve artifact ID `12764110430`, 13,929 bytes; ZIP SHA-256 `ae6f71dec3923f692cf98ac0a35fb1ebbcb97bf61fff7734db4e9cbe1e67b494`. |

### Frozen script configuration recovered from those exact commits

- **E01:** 50%/65%, 65%/80%, 80%/100% chronological test folds; four fixed variants (both directions/long-only × market/limit 20 bps); Donchian 20, ATR 14, volume ratio 1.6, stop 2.5 ATR, TP1 2R, TP2 5R, trail 3 ATR, max hold 32; 10,000 USDT and one concurrent position **per symbol-run**. The summary explicitly aggregates independent symbol runs, not portfolio equity. Limit touch is credited from OHLC.
- **E02:** three same fractional folds; fixed candidate set market, limit 5/10/20 bps with three-bar wait; train prefix selects a policy per symbol/fold, next non-overlapping segment evaluates it; 10,000 USDT and one concurrent position per symbol-run. Still independent per-symbol results, not shared-capital portfolio.
- **E03:** per-symbol 70%/30% chronological split; market plus limit offsets 0/5/10/20 bps and wait 1/3/5 bars; Donchian 20, ATR 14, volume ratio 1.6, stop 2.5 ATR, TP1 2R, TP2 5R, trail 3 ATR, max hold 32; 10,000 USDT and one concurrent position per symbol-run. All exits forced taker to isolate entry policy. OHLC touch/fixed-price resting limit remains optimistic.
- **E04:** five selected trading symbols (RAY, PUMP, TAO, AAVE, CAKE), BTC/ETH context plus broad available-symbol context; three fixed UTC folds; volume ratio ≥1.6, breakout clearance ≥0.25 ATR, limit offset 20 bps, penetration 5 bps, wait 3 bars, costs ×2; chase thresholds 1.5/2/2.5/3/100%. This is a selected-symbol diagnostic, not broad-universe shared-capital proof.
- **E05:** attempted 180 days of H1 kline, mark and funding for 11 frozen candidates across the configured public Bybit hostnames. Six 403 responses; no dataset package and no holdout result. The failure is a data-access outcome, not a strategy result.
- **E06:** ran both signal/trade diagnostics and BTC/ETH + altcoin market-context diagnostics. The exact script defaults reuse the five selected symbols, three fixed H1 folds, Donchian 20, ATR 14, volume ratio 1.6, breakout clearance 0.25 ATR, 20 bps entry offset, 5 bps penetration, 3-bar wait and 2× costs. These are diagnostic exports, not a separately isolated filter PnL test.
- **E07:** five-symbol primary and five-symbol reserve matrix jobs; 3 chronological folds; shared 10,000 USDT portfolio per fold, max 5 positions; volume thresholds 1.2/1.6/2.0/2.5, breakout thresholds 0/0.10/0.25 ATR, cost multipliers 1/1.5/2; limit offset 20 bps, penetration 5 bps, wait 3 bars; Donchian 20, ATR 14, stop 2.5 ATR, TP1 2R, TP2 5R, trail 3 ATR, max hold 32. This is 4×3×3 = 36 configurations per fold, 108 fold/config runs. The positive example was selected from this grid and is exposed to multiple-testing bias.

### Remaining provenance gaps after this pass

- The artifact ZIP digests above are not hashes of CryptoFetch input archives. E01–E04/E06/E07 scripts record source archive filenames in result rows but do not emit a complete immutable input archive manifest with exact input file SHA-256 for each run. Exact dataset-byte provenance therefore remains incomplete.
- E01–E03 shared code commit is known, but their runs still lack independent Bybit-native data and shared-capital design. E04/E06/E07 use selected-symbol context and proxy archives; their exact source dataset hashes remain unknown.
- E05's exact failure commit and attempted scope are known; it produced no result artifact.
- The E07 workflow generated separate primary/reserve artifacts; the headline +3,947.32 USDT example must not be treated as a clean untouched holdout or combined primary+reserve portfolio.
- No artifacts were downloaded, no ZIP inputs were opened, and no tests, PnL, collectors, API calls or orders were executed during this provenance pass.


## 2026-11-05 — P1: historical accounting-version impact for E01–E07

### Confirmed version boundary

Static comparison of `Bybit_Trading_Engine_v14_research.py` at each experiment's exact checked-out commit against the later corrected engine establishes:

- E01–E03 (commit `4e27b6adf8c3199ce78446d33703984394c94152`): engine blob `e4501bd3666d7fe25ae8c1a10a9813da89b535dd`; old exit-cost basis.
- E04 (commit `4b291265976d66f77b692d057a921d170be865da`): same engine blob `e4501bd3666d7fe25ae8c1a10a9813da89b535dd`; old exit-cost basis.
- E06 (commit `9601f4d855f69d58e7353655a0c62060f519de13`): same engine blob `e4501bd3666d7fe25ae8c1a10a9813da89b535dd`; diagnostic trade/cost exports use old exit-cost basis.
- E07 (commit `a5a9851622544b4d16a0aec7f9ccab7d612cc608`): engine blob `c47caac76de0a9a38da1a839462495bfd14fa3af`; its `_close_position()` still uses the old entry-notional formula for TP1 and final exit fees/slippage.
- E05 (commit `c0b61c2e87c46b347179d811c1410a6ad84478b0`): failed at public-data download with HTTP 403 before holdout script execution; no PnL result to classify.

The old formula used `pos.size_usdt * TP1_FRACTION` for TP1 costs and `pos.size_usdt * remaining_fraction` for final exit costs. The corrected implementation, verified present in engine blob `b91c40f142ddbbe65703eb6e84f24ce4fd05dc26` at commit `4eb9a2e7d7fc6a198937ef028dec32a5f723e22d`, uses proxy quantity `size_usdt / entry_price` multiplied by the relevant TP1/final execution price and leg fraction. Entry costs remain based on entry notional; stop-risk cost estimates are also adjusted to the stop execution price.

### Direction of historical bias

For a profitable exit, the old entry-notional basis understates exit fees/slippage when exit notional is above entry notional? More precisely:
- if the total exit execution notional is greater than entry notional (aggregate profitable position), old exit costs are understated and old net PnL is overstated;
- if total exit execution notional is lower than entry notional (aggregate losing position), old exit costs are overstated and old net PnL is understated.

This direction follows the linear USDT quantity identity: total exit notional across all legs = entry notional + gross PnL, assuming unchanged quantity apart from recorded partial exits. It does **not** determine the net effect on a multi-trade experiment without its per-leg fills and execution classifications.

### Impact classification

| Experiment | Old fee/slippage formula present? | Classification |
|---|---|---|
| E01 | Yes | **PROVISIONAL — PnL and possibly position sizing affected.** Contains both market and OHLC-limit variants; no aggregate correction can be inferred from the published summary alone. |
| E02 | Yes | **PROVISIONAL — PnL and policy-selection scores affected.** The train-only policy selection itself may choose different candidates after corrected costs; fixed-trade adjustment is insufficient. |
| E03 | Yes | **PROVISIONAL — PnL and entry-policy comparisons affected.** Exit legs are taker by design, but limit-entry variants still have maker/taker entry classification; exact per-leg cost correction not reconstructed. |
| E04 | Yes | **PROVISIONAL — PnL and risk sizing affected.** Selected five-symbol diagnostic with OHLC limit fills and 2× cost assumptions; fold-level aggregate is not enough for a corrected ledger. |
| E05 | No PnL executed | **NOT APPLICABLE** — data-access failure only. |
| E06 | Yes | **DIAGNOSTIC COST FIELDS PROVISIONAL.** It is not an independent strategy PnL test; any trade-level cost attribution inherits the old engine formula. |
| E07 | Yes | **PROVISIONAL — shared-capital PnL and portfolio path affected.** Corrected stop-cost reserves can change position sizes, slot competition and subsequent trades; the selected grid result cannot be repaired by a scalar adjustment. |

### What is and is not concluded

- The code-version mismatch is confirmed by exact run checkout SHA and exact engine blob at those commits.
- The correction was present and tested by Research CI #41536540759 on commit `4eb9a2e7d7fc6a198937ef028dec32a5f723e22d`; the engine file at that commit contains price-specific TP1/final notional formulas.
- This is a classification of historical evidence, not a claim that every old result is numerically wrong in the same direction.
- No historical PnL was recalculated, no fixed-trade sensitivity was applied to E01–E07, no artifacts were downloaded, and no backtest or parameter sweep was run.
- Preserve original reported figures as historical outputs, but do not use them as corrected-engine profitability evidence. Any future rerun would require the separate user/data/execution gates to be explicitly reopened.


## 2026-11-05 — P1: accounting-version cross-check extended to E08–E13 and H-A/H-C

Exact engine file blobs were fetched at each recorded experiment commit and the `_close_position()` execution-cost formula was inspected. This is static code provenance; no PnL was recomputed.

| Experiment | Run commit | Engine blob at run commit | Exit-cost basis | PnL impact classification |
|---|---|---|---|---|
| E08 | `17c31df587e802da7c74d3c8e2f53a656a632668` | `e4501bd3666d7fe25ae8c1a10a9813da89b535dd` | Old entry-notional basis | **PROVISIONAL** — limit/maker proxy results affected; no scalar correction. |
| E09 | `483278f51d99d402215a1f26a690ea2661e28939` | `1a19ae8c3a321cf1efcba85223c2aded13da5868` | Old entry-notional basis | **PROVISIONAL** — market and limit factorial results affected; cost correction can also change risk sizing. |
| E10 | `483278f51d99d402215a1f26a690ea2661e28939` | `1a19ae8c3a321cf1efcba85223c2aded13da5868` | Old entry-notional basis | **PROVISIONAL** — per-symbol PnL sums and selection of the body gate affected. |
| E11 | `ae6f7b4c99b79cbe31fdfeded8780a058b118049` | `1a19ae8c3a321cf1efcba85223c2aded13da5868` | Old entry-notional basis | **PROVISIONAL** — shared-capital portfolio path affected. Existing cost-only sensitivity is explicitly not a corrected-engine rerun and does not capture changed stop-risk sizing/portfolio sequence. |
| E12 | `4100d800761983d9de148f368d2402280b3dc6be` | `1a19ae8c3a321cf1efcba85223c2aded13da5868` | Old engine present, but workflow is diagnostics-only | **NOT A PnL RESULT** — diagnostic values are not a strategy net-PnL estimate; no independent profitability claim. |
| E13 | `f4da3cca0c0dc79cee86350ba6a680fc461e47fc` | `1a19ae8c3a321cf1efcba85223c2aded13da5868` | Old entry-notional basis | **PROVISIONAL** — shared-capital portfolio path affected. Existing cost-only sensitivity does not capture changed sizing or trade sequence. |
| H-A final report run #41670116033 | Checkout SHA `3f762a4bf9fa3f53a61ff0912e2deaf411ead4b8` recovered from job log | `cc390a1f4c7345040e125ee64c1943ab944ed4be` | Correct execution-price TP1/final notional | **Fee-basis correction present.** Final report run code SHA is now resolved; do not apply the E01–E07 old-formula caveat to this run. |
| H-C reverse-time run #41722545731 | `a5e7e1799f472db4cc00824dfcc774b40058165e` | `4f2b101379cab11a351ecf4ce3ec18d01872d8a6` | Correct execution-price TP1/final notional | **Fee-basis correction present.** Remaining blockers are proxy universe, reverse-time design, omitted funding/mark and lack of forward OOS—not the old exit-notional formula. |

### Interpretation

- The accounting correction boundary is now materially clearer: E01–E11 and E13 used the old exit-notional formula; E12 is diagnostics-only; H-A final run and H-C run used the corrected execution-price fee formula.
- H-A final run checkout SHA `3f762a4bf9fa3f53a61ff0912e2deaf411ead4b8` was recovered from workflow job #126035908527. The exact engine blob at that SHA confirms TP1 and final exit costs use their execution prices. This resolves the previously unknown H-A final-run SHA.
- E11/E13 cost-only sensitivity values already documented elsewhere remain sensitivity estimates on fixed historical trades, not corrected engine portfolio runs. Since stop-risk cost estimates also changed, the trade sizes and later portfolio path could differ.
- H-C's corrected accounting does not make its negative proxy result a Bybit-native or forward-OOS result.
- No artifact contents were downloaded; no historical PnL, cost sensitivity or replay was recalculated in this pass.
