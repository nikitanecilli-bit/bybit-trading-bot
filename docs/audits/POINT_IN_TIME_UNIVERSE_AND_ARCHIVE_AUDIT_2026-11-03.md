# Аудит архива данных и point-in-time universe

Дата: 2026-11-03  
Ветка: `research/market-regime-v1-main`  
Статус: STATIC AUDIT — DATA PROVENANCE PARTIAL / SURVIVORSHIP CONTROL INSUFFICIENT

## Краткий вывод

Исторические результаты E01–E13 воспроизводимы по ряду workflow/artifact checks, но текущий набор данных не является point-in-time universe Bybit. Доступные ZIP содержат Binance-style OHLCV proxy; funding history, mark-price history и dated Bybit instrument/risk-tier snapshots в репозитории отсутствуют.

Для E11/E13 дополнительно подтверждён selection/survivorship limitation: общий universe строится из инструментов, для которых уже имеются достаточные данные во всех трёх заданных folds. Это полезно для сопоставимого replay на фиксированной выборке, но исключает инструменты без полной истории и не восстанавливает состав рынка, доступный на каждую историческую дату.

## 1. Что фактически хранится в репозитории

В `data/archives/cryptofetch/` находятся шесть ZIP-архивов:

- три архива с диапазоном в имени 2025-10-27 — 2026-10-27;
- три архива с диапазоном 2026-04-29 — 2026-10-26.

В исследовательском отчёте CryptoFetch зафиксированы 67 CSV entries в этих архивах. Схемы распознаны как Binance-style OHLCV. Отдельных funding-history CSV и mark-price datasets в проверенном архиве не обнаружено. В дереве текущей ветки нет сохранённых файлов в `data/funding/`, `data/mark_price/`, `data/instrument_specs/` или архиве risk tiers; каталог `data/` содержит только CryptoFetch ZIP.

Источники:
- `docs/research/CRYPTOFETCH_PER_SYMBOL_BACKTEST_2026-11-02.md`
- `scripts/audit_cryptofetch_archives.py`
- `scripts/run_uploaded_dataset_backtests.py`
- `scripts/archive_bybit_market_history.py`

## 2. Проверки целостности OHLCV

`read_zip_datasets()` в `scripts/run_uploaded_dataset_backtests.py` выполняет для CSV:
- проверку обязательных колонок;
- числовую проверку timestamp/OHLCV и положительных цен;
- проверку OHLC ordering и неотрицательного volume;
- сортировку по timestamp;
- отказ при дубликатах timestamp;
- проверку равномерного шага свечей для timeframe;
- выбор самого длинного валидного файла на пару symbol/timeframe.

Это полезные проверки структурной целостности выбранного файла. Однако выбор самого длинного файла не является доказательством, что он исторически репрезентативен или что universe не имеет survivorship bias. При нескольких версиях одного symbol/timeframe остальные файлы не объединяются; выбирается один кандидат, а решение зависит от числа строк и имени архива.

Отдельный `scripts/audit_cryptofetch_archives.py` — только инвентаризатор: считает строки, определяет schema/kind и first/last timestamp. Сам по себе он не проверяет duplicate timestamps, missing intervals, OHLC invariants или cross-archive consistency. Для этих проверок используется loader backtest-скрипта, но не отдельный архивный отчёт.

## 3. Неравномерность истории

В CryptoFetch per-symbol report отмечены:
- часть H1 инструментов имеет примерно годовую историю;
- многие инструменты покрывают только 2026-04-29 — 2026-10-26;
- GRAM начинается 2026-07-02;
- HYPE содержит только 758 H1 bars за 2026-09-24 — 2026-10-26;
- пустые DAIUSDT, MATICUSDT и XMRUSDT файлы пропущены;
- 15m выборка ограничена восемью инструментами.

Следствие: количество сделок, PF и net PnL нельзя напрямую сравнивать между символами без учёта разных окон, листингов, ликвидности и числа наблюдений. Короткая история и малое число сделок делают положительные оценки особенно нестабильными.

## 4. E11/E13: подтверждённый selection bias механизма формирования universe

В `scripts/run_e11_h1_shared_capital_replay.py`:
1. выбираются H1 datasets с не менее чем 500 bars;
2. для каждого символа считаются бары в трёх фиксированных folds;
3. символ включается только если в каждом fold есть не менее 100 bars;
4. затем строится пересечение timestamp sets всех включённых символов;
5. портфельный replay запускается только на этом общем синхронизированном окне.

Это обеспечивает сравнимую сетку и синхронный общий капитал. Но это не point-in-time universe:
- активы с короткой историей или поздним появлением в архиве исключаются;
- исключённые активы не участвуют в оценке доходности соответствующего исторического периода;
- состав universe формируется из доступности данных в собранном архиве, а не из исторического списка торгуемых Bybit linear contracts на каждый timestamp;
- delisted/renamed instruments не представлены как гарантированно полная историческая выборка.

Дополнительно `scripts/h1_symbol_universes.json` сообщает, что primary/reserve shortlist ранжировался по прежним результатам H1 signal-quality ablation на тех же архивах. Поэтому этот shortlist — отобранная исследовательская выборка, а не независимый набор для подтверждения преимущества. E11/E13 folds уже использовались для анализа и не являются blind holdout.

**Классификация:** подтверждённое ограничение дизайна и отбора выборки; не доказательство арифметической ошибки в E11/E13.

## 5. Bybit-native data gate остаётся закрытым

В репозитории есть сборщик `scripts/archive_bybit_market_history.py` для:
- trade OHLCV H1 через `/v5/market/kline`;
- mark-price H1 через `/v5/market/mark-price-kline`;
- funding settlements через `/v5/market/funding/history`.

Также есть collectors dated instrument specifications и risk-limit tiers. Их offline tests подтверждают обработку ответов, но это не равно наличию реального архива. В журнале указаны HTTP 403 на публичных Bybit endpoints из GitHub Actions, и текущий tree не содержит полученных Bybit snapshots. Обход региональных ограничений не предпринимался.

Следовательно, E01–E13 остаются Binance OHLCV proxy experiments. Funding в этих результатах не подтверждён; mark-price liquidation, точные instrument specs, maintenance tiers и exchange-valid contract quantity не представлены.

## 6. Статус старых PnL

Все исторические net PnL, полученные через v14 `_close_position()` до исправления exit fee/slippage notional basis, помечены в журнале как provisional. Ошибка расчёта exit costs была исправлена позднее, но E01–E13 не пересчитаны на исправленном коде. Даже после пересчёта Binance OHLCV proxy и optimistic OHLC limit fills не станут Bybit execution replay.

Старый результат CryptoFetch (14/50 H1 symbols positive; 0/8 15m positive) — только исторический screening snapshot. Число 14/50 и список символов нельзя использовать как актуальный рейтинг кандидатов до повторного расчёта на исправленном движке и общего капитала.

## 7. Что необходимо для честного point-in-time validation

До следующего рыночного PnL replay:
1. Получить разрешённым способом исторический список Bybit linear instruments с датами листинга/делистинга или другой проверяемый point-in-time universe source.
2. Для каждого timestamp формировать universe только из инструментов, которые были доступны на эту дату; сохранять и исключённые инструменты с точной причиной отсутствия.
3. Сохранить immutable manifest: источник, archive filename, SHA-256, symbol, timeframe, first/last timestamp, count, duplicate count, missing intervals, schema version.
4. Не выбирать между дублирующими архивами только по максимальному числу строк без объяснения различий; сравнивать overlapping rows и фиксировать правило разрешения конфликтов.
5. Получить Bybit-native trade OHLCV, mark-price candles, funding settlements и dated instrument/risk-tier snapshots с полным coverage.
6. Только после этого интегрировать exact exchange quantity, fees/funding, spread/slippage and margin/liquidation assumptions.
7. Отделить universe selection period от validation period; сохранить будущий untouched holdout, который не участвует ни в выборе символов, ни в настройке стратегии.

## Решение

- Не запускать новые market backtests и parameter sweeps на текущих данных.
- Не продвигать E13 compression gate и старый top-symbol shortlist.
- Сохранить E01–E13 как исторические диагностические результаты с ограничениями.
- Следующий безопасный этап — point-in-time universe/data provenance; если источник исторических Bybit listings недоступен, это остаётся явным blocker, а не поводом подменять его сегодняшним списком инструментов.


## ENG-DATA-006 — point-in-time linear universe collector (2026-11-03)

- Official Bybit API Explorer documents status filters `PreLaunch`, `Trading`, `Settling`, `Delivering`, and `Closed`; linear records include `launchTime` and `deliveryTime`. The default response is documented as `Trading` + `PendingOpen`, so the collector captures the default response plus all four non-default status filters.
- Added `scripts/snapshot_bybit_linear_universe.py` to paginate each response, validate status/symbol/launch/delivery fields, reject conflicting duplicate symbols, and save an immutable timestamped snapshot under `data/universe_history/linear/`.
- Added `is_linear_usdt_perpetual_within_lifecycle_at()` as a deterministic lifecycle-bound predicate: only LinearPerpetual USDT-settled records, after launch and before nonzero delivery; PreLaunch/PendingOpen are excluded and Closed/Settling/Delivering rows without a delivery timestamp fail closed. This does not prove temporary exchange trading availability.
- Extended the existing instrument-spec collector's request helper with an optional validated status parameter; its default behavior is unchanged.
- Added offline tests and Research CI wiring. The capture workflow is manual-only; a push does not call Bybit.
- Limitations: current status plus launch/delivery bounds do not prove full historical trading availability or temporary suspension history. Closed-status retention and API access must be confirmed from a real capture. Previous Bybit requests from Actions returned HTTP 403; no real snapshot is claimed. Cross-check captured records against official listing/delisting announcements before calling the universe complete.


## Verification record

- Research CI run [41540392254](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41540392254) completed SUCCESS on code/test commit `041b7eb2f26d65ff26242e56163529174de538df`; 33/33 job steps passed, including the new point-in-time universe test.
- Existing instrument-spec workflow run [41540268697](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41540268697) attempted a public request to `https://api.bybit.com` and received HTTP 403. No data snapshot was written. Its push trigger has been removed to prevent ordinary collector-code pushes from making network requests.
- The new universe archive workflow is manual-only. It has not been dispatched; the collector's actual Bybit response, especially `status=Closed`, remains unverified.


## ENG-DATA-007 — duplicate archive selection is not yet proven safe

Static source inspection confirmed that `read_zip_datasets()` in `scripts/run_uploaded_dataset_backtests.py` selects the candidate ZIP member with the greatest row count (then archive path as tie-breaker). It does not check whether:
- overlapping timestamps have identical OHLCV values;
- the selected longest file is a superset of timestamps from other candidates;
- shorter files contain complementary timestamps missing from the selected file.

This is a confirmed provenance/selection limitation, not proof that historical E01–E13 rows are corrupted. Added a read-only audit utility and CI scan; it reports per-archive SHA-256, time coverage, gaps, pairwise overlap equality, and longest-file superset status. The scan must complete before choosing whether to retain the legacy winner, reject conflicts, or build a non-conflicting union. No old experiment input is modified.


## ENG-DATA-007 — full archive scan result

The dedicated CryptoFetch audit workflow completed successfully:
- Audit run [41542079766](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41542079766), artifact [13187466159](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41542079766/artifacts/13187466159).
- Research CI [41542100415](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41542100415) passed compile and deterministic unit tests.
- 67 CSV members inspected: 67 structurally valid; 64 meet the legacy 200-bar loader floor; 3 are empty (DAIUSDT, MATICUSDT, XMRUSDT) and are skipped by the existing loader; 0 malformed members.
- Six duplicate symbol/timeframe groups and six pairwise comparisons: zero conflicting overlapping OHLCV candles, zero cases where the legacy longest-file winner omits timestamps present in its comparison partner. All 67 members have zero irregular/missing hourly/15m intervals.
- AAVEUSDT, DOTUSDT, TAOUSDT each have a 4,321-bar subset exactly matching the same timestamps in an 8,761-bar archive. ENAUSDT, ONDOUSDT, QNTUSDT each have two identical 8,761-bar copies.
- All six ZIP SHA-256 hashes in the E11 and E13 artifacts match the current checked-in archive hashes. Thus the scan covers the exact archive bytes used in those experiments.
- Conclusion: no current duplicate-selection corruption or coverage loss was found in E11/E13 source archives. This resolves the present duplicate-archive concern for these exact inputs only. It does not resolve the separate Binance-vs-Bybit market-data gap, historical listing availability, funding, spread, or execution fidelity.

## ENG-DATA-008 — current status is not historical tradability (2026-11-04)

Static audit of `scripts/snapshot_bybit_linear_universe.py`, `instrument_spec_history.py`, and their offline tests found an important distinction:

- `is_linear_usdt_perpetual_within_lifecycle_at()` deliberately checks only launch/delivery bounds. Its test accepts a `Closed` instrument for a timestamp before its recorded `deliveryTime`. This is not a claim that the instrument was continuously `Trading`; the helper's docstring explicitly says it does not check current tradability.
- The universe snapshot stores the status observed in each completed collection. `InstrumentSpecHistory.get_spec()` selects the newest completed snapshot at or before `as_of_ts`, and with its default `require_trading=True` requires that snapshot's observed status to equal `Trading`. It does not retroactively apply today's status to earlier timestamps.
- A symbol absent from the latest full-universe snapshot fails closed. This avoids silently carrying a previously observed spec forward after disappearance.
- However, a snapshot is a point observation, not a status-transition log. Between snapshots, temporary suspensions, delisting/status changes and newly listed instruments cannot be reconstructed. `max_age_ms` is optional and defaults to no age limit; even a freshness bound limits staleness but cannot prove there was no intrainterval status change.
- The collector queries default (Trading/PendingOpen) plus PreLaunch, Settling, Delivering and Closed statuses, but the actual Bybit capture remains unverified because the manual-only collector workflow has not been run and prior public API access returned HTTP 403.

**Finding:** no demonstrated code path was found that intentionally uses a present-day status as the historical status for an earlier `as_of_ts`; the dated-snapshot selector is directionally correct. But neither lifecycle eligibility nor a stale status snapshot proves continuous historical tradability. The current collector/history design is insufficient to certify an exact historical tradable universe without sufficiently frequent archived status observations or authoritative status-transition evidence.

**Decision:** do not change the lifecycle predicate to exclude every `Closed` row before delivery: that would conflate contractual lifecycle with observed trading status and discard useful lifecycle evidence. Do not invent a default freshness interval. Keep point-in-time tradability and strategy-PnL gates blocked until dated status coverage and its sampling gaps can be measured. No market tests, collector runs, API requests or archive downloads were performed for this audit.

## ENG-DATA-009 — temporal coverage is not yet measurable (2026-11-04)

A workflow/source audit found:
- `.github/workflows/bybit-linear-universe-history.yml`, `bybit-instrument-snapshots.yml`, and `bybit-risk-limit-snapshots.yml` are all `workflow_dispatch` only; there is no scheduled cadence.
- No committed snapshots exist in `data/universe_history/linear/` or `data/instrument_specs/linear/`. The prior documented public Bybit request failed HTTP 403, and no later successful capture is recorded.
- Each collector requests multiple statuses/pages sequentially. `collection_started_at` and `fetched_at` bound the total collection interval, but rows do not carry individual observation timestamps. A complete file is therefore not an atomic market-wide observation; status transitions during collection can be missed or produce a mixed-time view.
- The history loader's conservative completion-time selection avoids using a snapshot before the entire collection finished, but does not make each row's status valid at exactly `fetched_at`.

Added `scripts/audit_instrument_snapshot_coverage.py` and deterministic tests. The offline tool reports per-source snapshot counts and date span, collection-duration distribution, inter-snapshot gaps (completion-to-start where available, otherwise completion-to-completion), overlapping collection windows, symbols added/removed, and observed status changes. It has no built-in freshness threshold; optional gap/duration thresholds must be supplied explicitly. It fails closed on malformed files, duplicate timestamps and overlapping collection windows. Empty archive directories are reported as `NO_DATA`, not as zero-gap coverage.

**Decision:** no automatic schedule or live capture was enabled. First obtain an approved public-data capture path and enough dated snapshots to measure actual cadence, collection durations and gaps. Even a measured cadence cannot prove absence of intrainterval status transitions; use authoritative status-change events if exact historical tradability is required. Keep point-in-time tradability and strategy-PnL gates blocked. No API requests, collectors, archive downloads or market tests were run for this work.

## ENG-DATA-010 — per-page request timing provenance (2026-11-04)

Both Bybit snapshot collectors now attach optional `page_observations` metadata to newly generated snapshots:
- `status_filter` and sequential `page_index`;
- `request_started_at` and `request_completed_at` (UTC, millisecond precision);
- `row_count`, sorted `symbols`, and `has_next_page`.

`request_completed_at` is recorded after `_request_page` returns, including JSON parsing and response-shape/retCode validation. It is a conservative client-side completion bound, not an exchange-side event timestamp or exact socket-receipt timestamp. Raw opaque pagination cursors are deliberately not persisted.

Snapshot builders validate each observation window, global chronological ordering, sequential page indices per status filter, collection start/fetch bounds, and exact union of observed symbols versus the final snapshot universe. Older schema-v1 snapshots without this optional field remain readable.

The offline coverage auditor now validates the page metadata and reports per-snapshot page counts, per-status request windows and row counts, and request-duration distributions. It rejects malformed timing, out-of-order pages, duplicate symbols, and incomplete symbol coverage.

Regression tests cover valid page metadata, invalid/reversed windows, chronology, snapshot-time bounds, and symbol coverage. Research CI run [#41898947956](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41898947956) completed **SUCCESS** (59/59 steps), including collector tests, temporal audit tests and offline archive audit. An intermediate run failed because the linear-universe builder had not yet forwarded its page observations into the shared validator; fixed in commit `d2edd46`, then revalidated successfully in #41898525899 and #41898947956.

**Limit:** this narrows collection windows to individual page requests but does not reveal the exact instant at which Bybit's backend sampled the underlying instrument state, nor status transitions between page requests or between snapshots. The snapshot remains a sequentially collected observation, not an atomic exchange-side universe. No live/public/private API request, collector execution, archive download or PnL/market test was performed.

## ENG-DATA-011 — pagination and status-filter integrity (2026-11-04)

Page provenance validation now checks more than page numbering:
- Every page advertising `has_next_page=true` must be followed by the next page for that same status filter; the final page for each filter must have `false`.
- Status-filter groups must be contiguous and in the collector's expected order. The complete expected filter set must be present, including filters that returned an empty page.
- The dated instrument-spec collector rejects any row whose returned `status` does not equal the requested filter. This prevents an unexpected/misrouted response from being silently attributed to the wrong lifecycle bucket.
- The offline audit reports repeated symbol appearances across pages (`duplicate_symbol_observations`) rather than silently treating them as proof of a clean pagination boundary. Identical duplicates remain deduplicated by the collector for backward-compatible handling; conflicting duplicate rows are rejected. Duplicate appearances are a quality warning because moving exchange-side data during pagination can cause overlap and may also conceal omissions.

Regression coverage includes missing continuation pages, inconsistent final-page flags, omitted status filters, interleaved status groups, wrong-status rows, and repeated symbols. Research CI run [#41900677467](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41900677467) completed **SUCCESS** (59/59 steps). The prior successful baseline #41900428039 (59/59) validated the first pass; intermediate runs exposed fixture and validation-order issues, which were corrected before the final green run.

**Interpretation remains conservative:** the checks establish consistency of the client-side pagination record, not proof that Bybit's backend supplied a transactionally consistent universe. Repeated symbols are surfaced; absent server-side cursor snapshots or event timestamps, no algorithm can prove that no instrument was skipped during a changing multi-page result set.

## ENG-DATA-012 — contract identity continuity across snapshots (2026-11-04)

The linear instrument history loader no longer treats `symbol` as a sufficient contract identity. Every instrument row must now provide non-empty `contractType`, `baseCoin`, `quoteCoin`, and `settleCoin`. It records this tuple alongside the parsed trading constraints.

Across the full loaded history (not merely adjacent snapshots), reappearance of a symbol with a different identity tuple fails closed as symbol reuse/identity change. This catches reuse even if the symbol was absent from one or more intervening snapshots. Within one snapshot, two different symbols with the same identity tuple are rejected as ambiguous rather than silently joined.

When the identity tuple is unchanged but the symbol differs at its next observed appearance (including after one or more snapshots where that identity is absent), the loader exposes `possible_renames` entries classified `possible_rename_not_proven`. It does not merge aliases, rewrite history, or make the old symbol resolve to the new one. This is a candidate for manual review, not proof of an exchange rename. Trading-constraint changes (tick size, lot size, leverage limits) do not constitute a new identity and remain valid history revisions.

Regression tests cover symbol reuse, reuse after a gap where the symbol is absent, ambiguous duplicate identity, possible rename reporting without aliasing, missing identity fields, and ordinary constraint changes under stable identity. CI is pending at the time of this documentation update; final status will be recorded after the workflow completes.

**Limit:** Bybit's instrument-info response does not itself provide a globally immutable contract ID in the captured fields. The identity tuple is a conservative composite, not an exchange-guaranteed permanent identifier. Same tuple with changed symbol is therefore reported as a possible rename only; no automatic reconciliation is performed.

ENG-DATA-012 validation result: Research CI [#41901402434](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41901402434) completed **SUCCESS** (58/58 steps). The first three runs exposed a missing identity fixture in the existing collector-to-history round-trip test; the fixture was updated with Bybit contract identity fields and the full workflow passed. No live collector or API execution was involved.


ENG-DATA-012 follow-up: possible-rename detection now retains the last observed symbol per composite identity across the entire ordered history, so a gap in which the contract is absent does not hide a subsequent symbol change. A regression test covers this non-adjacent case. This remains a heuristic candidate only; no automatic aliasing or history rewrite occurs.
