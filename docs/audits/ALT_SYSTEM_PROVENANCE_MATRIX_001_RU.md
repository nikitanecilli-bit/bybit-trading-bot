# ALT-SYSTEM-RESEARCH-001 — provenance matrix (P1, read-only)

Дата: 2026-11-09  
Ветка: `research/market-regime-v1-main`  
Статус: PARTIAL — historical ledger cross-referenced; missing provenance explicitly retained as gaps; weekly read-only refresh added 2026-11-09.  
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


## 2026-11-09 — weekly P1/P2 refresh (read-only)

### 1. Branch, PR and CI snapshot

- Начальный HEAD read-only snapshot до этого weekly matrix update: `9e8ffb4c06acc4fcf7600b85206cdb30e95f95c2`, commit `docs(research): record offline regression harness inventory`, 2026-11-05 08:14:41 UTC ([commit](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/9e8ffb4c06acc4fcf7600b85206cdb30e95f95c2)). Сам weekly refresh меняет только этот audit-документ.
- Previous recorded snapshot was `17cfb27fb6999a0c22d809a6e882dad3e73eb146`. На начальном snapshot текущая ветка была его потомком на 55 commits, 0 behind. Diff за этот интервал затрагивал только четыре документа: `NEXT_STRATEGY_RESEARCH_PLAN_RU.md`, `H_B_MEAN_REVERSION_READINESS_2026-11-05_RU.md`, `H_B_SYNTHETIC_TEST_SPEC_2026-11-05_RU.md` и `NEW_INPUTS_REVIEW_2026-11-04_RU.md`. Weekly matrix refresh — отдельный docs-only commit. Ни исходный код, ни datasets, ни workflow за исследованный интервал не менялись.
- Latest Research CI remains [#41928978081](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41928978081): SUCCESS, 2026-11-04 22:52 UTC, tested code SHA `08afcdd6c16e6c32fa33198e2ff56c66023ce585`. Its job has 56 numbered work/test steps plus setup/checkout/cleanup, all successful. Scope includes deterministic tests, existing CryptoFetch archive integrity/overlap audit and H-A preparation-manifest generation; this is not a strategy PnL run.
- Compare от tested SHA `08afcdd6c16e6c32fa33198e2ff56c66023ce585` до начального HEAD: 68 commits ahead, 0 behind; все восемь изменённых путей — документация (accounting audit, continuation checkpoint, next strategy plan, H-B readiness/spec, new-input review и hypothesis-source index/input). Настоящий weekly refresh добавляет только provenance matrix. Исполняемый код не менялся относительно CI-tested snapshot; documentation commits CI не проходили.
- У начального HEAD не было combined status checks и PR-triggered workflow runs. В первых 100 branch workflow runs не найден run новее #419289; этот weekly update является документационным и не заявляется как CI-tested.
- Branch/main relationship на начальном snapshot: `main` оставался `c06af3aa084d3513a3c2d7b183f02dba312be230`; compare был `diverged`, 2,661 ahead / 40 behind. Этот refresh меняет только research-документацию; `main` не затрагивался. Не merge/rebase/fast-forward.
- PR #4 remains open Draft, unmerged; its head is current research HEAD and its base is `main`. PR #13 remains open, non-Draft, unmerged; its base is the research branch. PR #9 remains open and unmerged against `main`. No PR was changed or merged.

### 2. Actions artifacts — metadata only

| Run | Artifact | ID | Size | Metadata checked 2026-11-09 |
|---|---|---:|---:|---|
| [#41928978081](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41928978081) | `cryptofetch-archive-audit` | 13371450337 | 2,732 bytes | not expired; expires 2027-02-02 22:52:09 UTC |
| [#41928978081](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41928978081) | `h-a-archive-preparation` | 13370881028 | 1,649 bytes | not expired; expires 2027-02-02 22:52:09 UTC |
| [#41670116033](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41670116033) | `h-a-preregistered-ohlcv-results` | 13247672222 | 372,438 bytes | not expired; expires 2027-02-01 16:02:51 UTC |
| [#41722545731](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41722545731) | `h-c-reverse-time-cryptofetch-proxy` | 13272957989 | 211,799 bytes | not expired; expires 2026-12-03 21:31:48 UTC |

Only artifact metadata was queried. No artifact or source archive was downloaded or extracted; metadata existence does not validate artifact contents or input-dataset hashes.

### 3. New H-B design evidence — no experiment result

- Added H-B readiness assessment and synthetic-test specification dated 2026-11-05. H-B is still `DESIGN GAP REVIEW / NOT PREREGISTERED / NO PNL RUN`; it is not ready for implementation or market validation.
- Static review confirms that `market_regime.py` already contains a causal regime classifier, but it is research-only and not connected to trading signals, execution or sizing. Its thresholds are not yet frozen/justified for H-B.
- A candidate mechanics contract is outlined (long-only H1, completed-bar range gate, one oversold event, one stabilization rule, next-open entry), but it is not a frozen preregistration. Timeframe semantics, regime configuration, stop/target/time-stop, same-bar priority, sizing, validation folds, controls and `N_trials` must be resolved together. Do not treat the candidate thresholds as validated.
- The synthetic specification maps future persistence, fill/sizing, MTM, exit-manager, close-accounting, journal/reporting and legacy-parity tests. Existing accounting/persistence test modules were inventoried, not executed. No H-B production code or test module was added; no synthetic tests or CI pass are claimed.
- The H1 validation manifest is breakout-specific and must not be repurposed as an H-B manifest. H1/H4 empirical horizon comparison remains NOT READY; the candidate H1 mechanics design does not establish that H1 is superior to H4.

### 4. P1 — provenance state and historical accounting impact

- E01–E07 now have recovered run/check-out commits, script blob identities and uploaded artifact ZIP digests. The ZIP digests are not hashes of the original CryptoFetch market-data archives; exact input archive byte hashes/manifests remain unknown. E08–E13 lineage is stronger, but original source-data completeness and some artifact contents remain unverified.
- Accounting-version classification remains: E01–E11 and E13 used the old entry-notional basis for TP1/final exit fees and slippage; E12 is diagnostics-only. These PnL rows remain PROVISIONAL/IMPACTED. The correction can change cost reserves, risk sizing, slot competition and the later shared-capital trade sequence; it cannot be repaired by a scalar adjustment. No historical PnL was recalculated.
- H-A final run #41670116033 and H-C reverse-time run #41722545731 used the corrected execution-price fee basis. H-A still lost `6,135.26 USDT` versus baseline `5,635.98 USDT`; H-C proxy net before funding was `-2,880.12 USDT` versus baseline `-2,720.47 USDT`. Their remaining proxy/universe/holdout/funding/Mark limitations are unchanged.
- ENG-EXEC-041's positive-timestamp guard is a deterministic input-validation fix, not market evidence. No existing historical strategy result was replayed to quantify whether any invalid zero/negative timestamp row would be affected. Maker execution remains blocked: the stored AAVE sample lacks required BT/block-trade classification, and aggregate L2/CSV sequence and queue limitations remain.
- Wallet/accounting audit still finds no confirmed TP1/funding sign or double-counting defect in the tested position-level ledger, but wallet-level available-balance funding routing, funding-receipt destination, TP1 proceeds transfer, manual/auto margin and account-mode-specific liquidation remain unmodelled. This is an account-model gap, not a safe local formula patch.

### 5. P2 — Bybit data contract

The last audited acceptance state remains unchanged; no new Bybit data was acquired:

| Dataset gate | Status | Blocking fact |
|---|---|---|
| D1 Bybit-native H1 OHLCV | `missing` | No complete saved Bybit-native package for the research interval |
| D2 Mark OHLCV | `missing / unverified` | Historical coverage/package and settlement alignment unconfirmed |
| D3 Funding + settlements | `missing / unverified` | Complete PIT observations and authoritative settlement Mark not confirmed |
| D4 PIT universe/lifecycle | `partial / unverified` | Listing/delisting/suspension history and delisted-symbol coverage incomplete |
| D5 Effective-time instrument specs | `partial / unverified` | No complete dated spec history across the research interval |
| D6 Effective-time risk tiers | `partial / unverified` | Historical tier coverage/effective times not proven |
| D7 L2/trades | `partial` for one diagnostic AAVE day; `missing` for representative research | One day and four hypothetical orders are not a multi-symbol/multi-regime fill dataset |
| D8 Fees | `unverified` | Dated account/symbol-specific fee assumptions not established |

### 6. Readiness and next safe boundary

- Strategy readiness, Bybit-native PnL validation and maker execution remain BLOCKED. No reviewed configuration demonstrates reproducible positive net results on independent, complete Bybit-native data with validated shared-capital accounting and realistic execution.
- Shared-capital replay infrastructure and deterministic accounting regressions exist, but that does not close wallet-level funding routing or UTA liquidation semantics. A portfolio architecture comparison is therefore not ready for strategy selection or deployment.
- Empirical H1/H4 horizon selection is blocked by missing accepted Bybit-native OHLCV/Mark/Funding and PIT universe/spec/risk-tier packages. Acquiring them would require collector/API/archive actions that remain prohibited. Stop at this boundary; do not substitute CryptoFetch/Binance-style proxy data or current snapshots for historical Bybit facts.
- Next safe work is read-only: preserve this provenance state, resolve any remaining source-code/manifest identities from already-published repository and Actions metadata, and keep H-B as a design-only candidate until its contract and the existing data/accounting gates are independently satisfied. No new market run, sweep, collector, API call, artifact download or order is authorized by this refresh.

## 2026-11-16 — weekly P1/P2 refresh (read-only)

### 1. Branch, PR and CI snapshot

- Предыдущий weekly snapshot: `7e51ad5c17765a400e31831a21792940694bc0eb` (`docs(research): clarify weekly provenance snapshot boundary`, 2026-11-09 08:48:11 UTC). Начальный HEAD этого refresh: `866b9c018b69999854c69eaca607d51a7f20f95f` (`docs(research): refresh weekly provenance map 2026-11-16`, 2026-11-16 08:35:36 UTC); между snapshots добавлен один документационный commit, рыночных/кодовых изменений нет.
- `main` остаётся на `c06af3aa084d3513a3c2d7b183f02dba312be230`; сравнение веток на начальном HEAD: `diverged`, 2,664 ahead / 40 behind. Ни merge, ни rebase, ни fast-forward не выполнялись.
- PR #4 остаётся open / Draft / unmerged, head `866b9c018b69999854c69eaca607d51a7f20f95f`, base `main`. PR #13 остаётся open / non-Draft / unmerged, head `f2510136222f4e271ccb1293642a2bdba709b6f3`, base ref `research/market-regime-v1-main`; GitHub PR metadata сообщает base SHA `4c6d12d681fe97b03a43b48a4c0c462d2f0f7dd9`, отличный от текущего branch HEAD `866b9c018b69999854c69eaca607d51a7f20f95f`. Это расхождение метаданных зафиксировано; PR не ретаргетился и не сливался. PR #9 остаётся open / unmerged, base `main`. PR-состояния не менялись.
- Последний обнаруженный branch workflow остаётся [Research engine checks #41928978081](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41928978081): SUCCESS, 2026-11-04 22:52 UTC, tested code SHA `08afcdd6c16e6c32fa33198e2ff56c66023ce585`. Job содержит 59 шагов: 56 numbered work/test steps плюс setup/checkout/cleanup; все завершились успешно.
- Compare tested code SHA `08afcdd6c16e6c32fa33198e2ff56c66023ce585` → начальный HEAD этого refresh показывает 71 commit ahead, 0 behind и ровно 9 изменённых путей, все под `docs/`. Исполняемый код после CI-tested SHA не менялся; документационные изменения CI не проходили. У текущего HEAD нет опубликованных status entries или check-runs (0/0), это не следует интерпретировать как успешный CI.
- В branch-filtered Actions list нет более нового workflow run после #419289. Новых strategy PnL runs или новых experiment IDs за период не обнаружено.

### 2. Experiment ledger и гипотезы

- `docs/research/EXPERIMENT_LEDGER_RU.md` повторно прочитан (blob `1f5726777ac906d09855ad5f3dd3b0883931762f`, 1,310 строк). Последняя запись — ENG-EXEC-041 от 2026-11-04: положительный timestamp guard для normalized public trades, deterministic input-validation fix; указанный CI [#41891208250](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41891208250) успешен. Это не market/PnL evidence.
- Новых записей E-ID, новых strategy run IDs, рыночных результатов или изменений experiment design после предыдущего snapshot не найдено.
- H-B остаётся `DESIGN CANDIDATE v0.1 / NOT PREREGISTERED / DATA-BLOCKED`: реализация и synthetic tests отсутствуют, тесты не запускались. Дополнительные design blockers, уже описанные в [H-B readiness review](https://github.com/nikitanecilli-bit/bybit-trading-bot/blob/research/market-regime-v1-main/docs/research/hypotheses/H_B_MEAN_REVERSION_READINESS_2026-11-05_RU.md): абсолютный shock-low stop ещё не представлен общим entry/stop contract без адаптера; nullable TP1/TP2 конфликтуют с частью legacy restore/close/report paths; H-B provenance нужно сохранять в TradeRecord/journal и проверить consumers. Это статические design findings, не новые тестовые результаты.

### 3. Actions artifact metadata — повторная проверка 2026-11-16

Проверены только метаданные всех run/artifact references, перечисленных в этой матрице; ZIP bytes не скачивались и не открывались.

| Run | Artifact | ID | Size | Metadata 2026-11-16 | GitHub artifact ZIP digest (reported) |
|---|---|---:|---:|---|---|
| [#40578394090](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578394090) | `h1-direction-execution-ablation` | 12768870777 | 13,732 bytes | not expired; expires 2027-01-25 20:28:43 UTC | `sha256:a61dfb45f41792ae4dbfb2e0f09975b389e6b0aa1c6d89c64824087065823ebc` |
| [#40578394009](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578394009) | `execution-policy-walk-forward` | 12767913281 | 6,453 bytes | not expired; expires 2027-01-25 20:28:43 UTC | `sha256:66483e95ece78e773dd47494bbbdfd8bd2a738f7f6be1e28958463d622122c83` |
| [#40578393971](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578393971) | `execution-cost-ablation-report` | 12768457441 | 20,664 bytes | not expired; expires 2027-01-25 20:28:43 UTC | `sha256:880e4408f2d8ee2bd3e054ef76b43f06d089843da7086a2282999858645bfd66` |
| [#40588753444](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40588753444) | `h1-chase-limit-ablation` | 12773465436 | 1,106,266 bytes | not expired; expires 2027-01-25 21:40:36 UTC | `sha256:e4061b3f49637e725730fe966bad000dc4a4f80d67733f8beca8fe5e15a206f7` |
| [#40541270994](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40541270994) | none returned | — | — | no artifact metadata | — |
| [#40587243295](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40587243295) | `h1-signal-trade-diagnostics` | 12772483348 | 1,107,852 bytes | not expired; expires 2027-01-25 21:29:41 UTC | `sha256:d52b42bc8e39f00f088f2d43d08647aabf9408789d4e92c6008271691e2dad27` |
| [#40566687595](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40566687595) | `h1-selected-primary` / `h1-selected-reserve` | 12764160379 / 12764110430 | 13,704 / 13,929 bytes | both not expired; expires 2027-01-25 19:10:27 UTC | primary `sha256:28b0275b4feee893b77f3b37ef66ba9fa07dde58ebcc2f431c7b216f5c41ccc7`; reserve `sha256:ae6f71dec3923f692cf98ac0a35fb1ebbcb97bf61fff7734db4e9cbe1e67b494` |
| [#40650477230](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40650477230) | `h1-chase-gate-decoupling` | 12799089180 | 2,266,093 bytes | not expired; expires 2027-01-26 07:30:07 UTC | `sha256:05e8aaa9b18c4509059c7db8eb2114fb1da6e76da1d3c9850832bbf669496c5b` |
| [#41355171678](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41355171678) | `e09-h1-gate-factorial` | 13103031404 | 1,808,245 bytes | not expired; expires 2027-01-30 22:03:44 UTC | `sha256:503aa4ef24f6f7ef5adef0a63297e0deeeb7298c55b4d3254df1be7dd274416f` |
| [#41360728294](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41360728294) | `e10-h1-body-gate-cross-sectional` | 13104981517 | 2,539,639 bytes | not expired; expires 2027-01-30 23:09:46 UTC | `sha256:64832db93e5912c877debcfd4548cbf9a6fb2beb71ca647c39762e1321b963fa` |
| [#41361376448](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41361376448) | `e11-h1-shared-capital-portfolio` | 13105661683 | 2,298,582 bytes | not expired; expires 2027-01-30 23:17:27 UTC | `sha256:441e518a683435e47327cb85bb741c8fcb24e734ded1ab720722dc50dd588765` |
| [#41361856404](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41361856404) | `e12-h1-market-context-diagnostics` | 13105721458 | 701,749 bytes | not expired; expires 2027-01-30 23:23:13 UTC | `sha256:5ac82041680ea6bcbb90561a6da11687c15c171885dd66034db321ce63bd8854` |
| [#41362217727](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362217727) | `e13-h1-compression-gate-shared-capital` | 13105403824 | 3,071,521 bytes | not expired; expires 2027-01-30 23:27:47 UTC | `sha256:9930d6f3651305ef9dcf254c85bc0b50b24cb098b6b367accbaaae4bbad6f601` |
| [#41670116033](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41670116033) | `h-a-preregistered-ohlcv-results` | 13247672222 | 372,438 bytes | not expired; expires 2027-02-01 16:02:51 UTC | `sha256:d4e2178e537e22b08191df7df8caa3431bcdfdb9026f0244397021d4b63915af` |
| [#41722545731](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41722545731) | `h-c-reverse-time-cryptofetch-proxy` | 13272957989 | 211,799 bytes | not expired; expires 2026-12-03 21:31:48 UTC | `sha256:df2c0eb18d826e79e033a105bc62b1a995898db680b1c1ca6ef8a0b3d4928742` |
| [#41928978081](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41928978081) | `cryptofetch-archive-audit` / `h-a-archive-preparation` | 13371450337 / 13370881028 | 2,732 / 1,649 bytes | both not expired; expires 2027-02-02 22:52:09 UTC | audit `sha256:92293475279760ffa57d6e20288ea4ff262b97f92c2649dfab05281e6ebd1ca8`; H-A prep `sha256:4b9a4cf836d2ae2ffa8a2f4b089d221430671760f86cd6f75bf27cff2c455003` |

GitHub-reported digests above identify the Actions artifact ZIPs; they were not independently recomputed and are not hashes of the original input market-data archives. Metadata existence, size and retention do not prove artifact contents or dataset completeness. E05 (#40541270994) still has no artifact metadata. No artifact was downloaded or extracted.

### 4. P1 — accounting/execution impact

- Historical classification is unchanged: E01–E11 and E13 used the old entry-notional exit fee/slippage basis and remain `PROVISIONAL / IMPACTED`; E12 is diagnostics-only. The correction can affect exit costs, stop-risk reserves, sizing, slot competition and subsequent shared-capital path; no scalar adjustment is justified and no historical PnL was recalculated.
- H-A final run #41670116033 and H-C run #41722545731 used the corrected execution-price fee basis. Their reported proxy outcomes remain negative: H-A `-6,135.26 USDT` vs baseline `-5,635.98 USDT`; H-C `-2,880.12 USDT` vs baseline `-2,720.47 USDT` before funding. This does not validate Bybit-native profitability.
- E01–E07 exact run/script lineage is materially improved, but artifact ZIP SHA values are not hashes of original CryptoFetch input archives. Exact source archive byte hashes/manifests and full PIT dataset identity remain unknown; artifacts were not opened.
- Position-level accounting regressions do not close the wallet/UTA gap: available-balance funding debit waterfall, funding-receipt destination, TP1 proceeds transfer, manual/auto margin movements and account-mode-specific liquidation remain unmodelled. No new accounting/execution code fix or market replay occurred during this interval.

### 5. P2 — data contract and horizon/portfolio readiness

| Dataset gate | Status at 2026-11-16 | Blocking evidence |
|---|---|---|
| D1 Bybit-native H1 OHLCV | `missing` | No complete accepted Bybit-native package for the research interval |
| D2 Mark OHLCV | `missing / unverified` | Historical coverage and exact settlement Mark alignment not established |
| D3 Funding settlements | `missing / unverified` | PIT completeness and authoritative interval/settlement schedule evidence not established |
| D4 PIT universe incl. delisted/suspended instruments | `partial / unverified` | Historical lifecycle coverage is not proven; current proxy universe is survivorship/availability constrained |
| D5 Effective-time instrument specs | `partial / unverified` | Snapshot `fetched_at` is observation time, not exchange `effective_from`; full dated history missing |
| D6 Effective-time risk tiers | `partial / unverified` | Same effective-time and historical-coverage limitation |
| D7 L2/trades | `partial` for one diagnostic AAVE day; `missing` for representative research | No multi-symbol/multi-regime validated execution tape |
| D8 Fees | `unverified` | Dated account/symbol-specific fee schedule not established |

- H1/H4 empirical comparison remains NOT READY. The H-B candidate uses H1 mechanics only as a design choice; no paired H1/H4 preregistered comparison or accepted common data manifest exists.
- Shared-capital replay and deterministic accounting regressions are engineering capabilities, not proof of a selected portfolio architecture. Strategy selection remains BLOCKED by data acceptance, wallet accounting, realistic execution and independent validation gaps.
- No new Bybit data or external source was acquired. Closing D1–D6 requires an approved, auditable Bybit-native source package with H1 trade OHLCV, Mark/Funding and settlement evidence, PIT listing/delisting universe, dated specs/risk tiers and immutable source-byte manifests. Collectors, exchange/API access and archive downloads/extraction remain prohibited; stop at this boundary.

### 6. Scope of this refresh

Read-only GitHub repository, commit, PR, workflow, job, ledger and artifact-metadata inspection only. No source code, workflow, dataset or `main` changes; no workflow reruns, artifact/source downloads, archive extraction, collectors, exchange/private/account API, market PnL tests/recalculation, parameter sweeps, paper or live trading. This section records a metadata/documentation refresh, not CI verification or profitability evidence.


## 7. Weekly metadata refresh — 2026-11-23

### Branch, PR and CI snapshot

- Research branch HEAD: `a09295d25b89b32ca349c7bcd81c43b73cc1bdde`; unchanged from the 2026-11-16 snapshot. No new branch commit was found in this interval.
- `main`: `c06af3aa084d3513a3c2d7b183f02dba312be230`; unchanged. Compare remains `diverged`, 2,665 commits ahead / 40 behind, merge base `ae599a2f3279e15fe27360662f94f0e7ef8db5be`.
- PR #4 remains open, Draft, unmerged; its head SHA equals the research HEAD. PR #13 remains open, non-Draft, unmerged; GitHub reports base branch `research/market-regime-v1-main` with base SHA `4c6d12d681fe97b03a43b48a4c0c462d2f0f7dd9`, which differs from the current branch HEAD. Record this as metadata divergence; do not retarget or merge. PR #9 also remains open and unmerged.
- No commit statuses or check runs are published for current HEAD `a09295d...`.
- Latest discovered Research CI remains [#41928978081](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41928978081), SUCCESS on code SHA `08afcdd6c16e6c32fa33198e2ff56c66023ce585` (2026-11-04). Its `tests` job and all 56 numbered workflow steps completed successfully; cleanup steps also succeeded.
- Compare `08afcdd6...` → current HEAD reports 72 commits and only nine changed paths, all documentation: accounting audit, provenance matrix, continuation checkpoint, next strategy plan, H-B readiness/specification, new-input review, hypothesis index and preserved hypothesis source. No code, workflow, test or dataset path changed after the last verified code SHA. The documentation changes themselves have no CI result.
- The experiment ledger remains 1,310 lines; latest entry is ENG-EXEC-041 (2026-11-04). No later market-PnL experiment ID was found.

### ENG-EXEC-042 — instrument snapshot fail-closed validation

The branch contains an additional deterministic data-ingestion guardrail that was not separately represented in the previous matrix snapshot:

| Commit | Change | CI evidence |
|---|---|---|
| [b1fafc3](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/b1fafc3b69fe71cb5d97408689b2ee7403f8191f) | Require explicit non-empty string `category`; remove implicit `linear` default | [#41892075429](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41892075429) SUCCESS |
| [2c00abd](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/2c00abd10803030e6e4cc1536339afdbad544d05) | Reject missing, empty, numeric or boolean `symbol` values | [#41892392949](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41892392949) SUCCESS |
| [8c04cde](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/8c04cde99b20fc6a42908c620e1786bb0231a6f7) | Apply strict symbol validation in instrument snapshots | [#41893297801](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41893297801) FAILURE: one collector test expected error text `missing symbol`, while implementation raised `instrument row is missing or has invalid symbol`; the instrument-spec tests passed 15/15 |
| [f7ef140](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/f7ef1405013e0593f045b5c6f8de19fa9749c5d2) and [c9096a7](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/c9096a7ccb2fd9b3b3a48537a709907529ec3c62) | Update/add collector regression assertions for fail-closed symbol validation | Covered by subsequent successful CI |
| [ff7e5bb](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/ff7e5bbda19907ef11b70695e0109cf90958a19e) | Reject non-string symbols in linear-universe snapshots | No separate check run surfaced for this exact SHA; later full Research CI succeeded |
| [c069075](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/c06907551c4210ed09540f77115fd218778676a3) and [3025039](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/302503937f47277ab0ee7a83c2a0247bcf51a81c) | Read category from the validated snapshot envelope when row-level category is absent; reject contradictions; add as-of history regressions | [#41893435624](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41893435624) and [#41893443621](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41893443621) SUCCESS |
| [08afcdd](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/08afcdd6c16e6c32fa33198e2ff56c66023ce585) | Explicit timestamp-skew fixture in Mark/liquidation integration test | [#41928978081](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41928978081) SUCCESS; latest discovered full Research CI |

The ENG-EXEC-042 changes affect input parsing, snapshot provenance and fail-closed eligibility only. They do not change signal rules, sizing arithmetic, stops/targets, fee/slippage formulas or PnL accounting. Direct historical PnL impact is therefore not indicated by the changed code. An indirect effect is possible if malformed snapshots would previously have been admitted into an instrument universe; its actual magnitude is unknown and unmeasured. No Bybit-native historical PnL run exists to quantify it.

### Supplemental Actions artifact metadata checked 2026-11-23

Metadata was re-fetched for the following ENG-EXEC-042 validation runs. No artifact was downloaded or extracted.

| Run | Artifact | ID | Size | GitHub digest | Retention at check |
|---|---|---:|---:|---|---|
| [#41892075429](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41892075429) | `cryptofetch-archive-audit` | 13355115589 | 2,732 B | `805a01c55bb7626b57f8649b3c574b5643da826da853cdead9b4bbc257164bd7` | not expired; 2027-02-02 18:56:36 UTC |
| #41892075429 | `h-a-archive-preparation` | 13355035942 | 1,649 B | `13a8d2f147c748dcb16c355a70c37b76ae8a432f2fa5b584ca80db4dc9fe5218` | not expired; 2027-02-02 18:56:36 UTC |
| [#41892392949](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41892392949) | `h-a-archive-preparation` | 13355180705 | 1,649 B | `2282ef1173bba062a14e5d483473b4bf2370979b2b3fd044f0aa63c8d0baf6b1` | not expired; 2027-02-02 18:58:36 UTC |
| #41892392949 | `cryptofetch-archive-audit` | 13354127520 | 2,732 B | `1b26a22e1ff5fd9fedc384ff2e3fa8860a1f9801f84ba787e8305ae8c41e13af` | not expired; 2027-02-02 18:58:36 UTC |
| [#41893297801](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41893297801) | `cryptofetch-archive-audit` | 13355251398 | 2,732 B | `b2bf08168a3bcf29cc6dc0454d53734b0efb85833dd91aed7b81c14eb53d082a` | not expired; 2027-02-02 19:04:02 UTC |
| #41893297801 | `h-a-archive-preparation` | 13355151581 | 1,649 B | `7c8de50ef5bc1e42040b048a2776464f4fcd4c8421b37421dc14ddc4aadfdcba` | not expired; 2027-02-02 19:04:02 UTC |
| [#41893435624](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41893435624) | `cryptofetch-archive-audit` | 13354117822 | 2,732 B | `3b258e0a0f7e839a75b8dc726d03ab59e968cf16bccf184ad9b903a4923359fd` | not expired; 2027-02-02 19:04:50 UTC |
| #41893435624 | `h-a-archive-preparation` | 13353338959 | 1,649 B | `3eb645730acea8b2774ebe6958d7d6472fda08acb5e0c9dcbc7b0cb0b687f1c8` | not expired; 2027-02-02 19:04:50 UTC |
| [#41893443621](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41893443621) | `h-a-archive-preparation` | 13354512428 | 1,649 B | `38554703bb8350dab1a3bb0b0ee3895067b352d4bd0f842d28966b9c3fbca416` | not expired; 2027-02-02 19:04:53 UTC |
| #41893443621 | `cryptofetch-archive-audit` | 13353458760 | 2,732 B | `3b258e0a0f7e839a75b8dc726d03ab59e968cf16bccf184ad9b903a4923359fd` | not expired; 2027-02-02 19:04:53 UTC |

These are GitHub-reported SHA-256 digests of Actions artifact ZIPs, not independently recomputed hashes and not hashes of original market-data archives. Artifact metadata confirms registration/retention only, not artifact contents or Bybit dataset completeness.

### P1/P2 and research readiness — unchanged

- E01–E11 and E13 retain `PROVISIONAL / IMPACTED` classification for the prior exit-fee/slippage basis; no scalar correction or historical PnL recalculation is justified. H-A/H-C remain negative proxy outcomes on corrected fee basis.
- D1 Bybit-native H1 OHLCV: `missing`; D2 Mark: `missing / unverified`; D3 Funding/settlement: `missing / unverified`; D4 PIT universe incl. delisted/suspended: `partial / unverified`; D5/D6 effective-time specs/risk tiers: `partial / unverified`; D7 representative L2/trades: `missing` (one diagnostic AAVE day only); D8 dated account/symbol fee assumptions: `unverified`.
- H-B remains design-only, not preregistered and data-blocked. H1/H4 empirical comparison and portfolio-architecture selection remain NOT READY.
- The latest CI is deterministic code/data-integrity validation; its archive audit and H-A preparation steps are not market PnL runs.

### Scope of this refresh

Read-only inspection of existing GitHub files, commit metadata, PR metadata, CI jobs/logs and Actions artifact metadata; one documentation-only matrix update. No code, workflow, dataset or `main` changes; no workflow dispatch/rerun, artifact or archive download/extraction, collectors, exchange/private/account API, market PnL tests/recalculation, parameter sweeps, paper or live trading.
