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
