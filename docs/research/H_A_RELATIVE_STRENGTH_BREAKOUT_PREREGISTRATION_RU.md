# H-A — Relative Strength Breakout: preregistration

Дата фиксации: 2026-11-03  
Статус: preregistered replay completed; H-A rejected after negative net results in all three reused folds  
Цель: проверить, добавляет ли cross-sectional relative strength информацию к H1 Donchian breakout после консервативных execution costs.

## 1. Universe and availability

- Input: только существующие audited CryptoFetch H1 OHLCV archives.
- Universe: все непустые H1 symbol histories, без отбора по будущему PnL.
- Replay: `run_simulation_pass(..., allow_sparse_data=True)`; только реальные свечи, без forward-fill.
- Symbol eligible at timestamp только после 72 полных H1 lookback bars и при наличии текущей свечи.
- Cross-sectional distribution строится только по eligible symbols, реально доступным на текущем timestamp.
- Минимум 5 eligible symbols для любого cross-sectional rank decision.
- Общая конечная граница — earliest last timestamp среди включённых histories.
- Отсутствующая свеча для открытой позиции или pending order = fail-closed.
- Исторический point-in-time Bybit listing/delisting universe в архиве отсутствует; результат будет CryptoFetch-available-universe proxy, не полным Bybit universe.

## 2. Frozen signal definition

На закрытии H1 бара для каждого eligible symbol:

- (r_{24}=Close_t/Close_{t-24}-1).
- (r_{72}=Close_t/Close_{t-72}-1).
- (ATR_{14}) рассчитывается по предыдущим 14 завершённым барам до текущего сигнального бара; (ATR% = ATR_{14}/Close_t).
- Strength score: (S=(0.5r_{24}+0.5r_{72})/ATR%).
- Cross-sectional percentile rank — midrank среди eligible symbols на этом же timestamp; ties получают средний ранг.
- Long gate: rank (ge 0.80). Short gate: rank (le 0.20).
- Trigger: close выше предыдущего Donchian(20) high для long либо ниже предыдущего Donchian(20) low для short. Текущая свеча не входит в Donchian window.
- Long/short симметричны; никаких дополнительных volume, ADX, broad-market или regime filters в первом тесте.
- Для дефицита портфельных слотов приоритет — (|S|), затем symbol name как стабильный tie-break.
- Никакого постоянного top-5 по будущему PnL.

## 3. Execution and risk

- Signal known only at H1 close; market entry at next H1 open, with existing max-chase and gap semantics.
- Existing engine stop/TP/partial-TP lifecycle and portfolio risk controls; параметры не подгоняются по результатам H-A.
- Conservative taker entry/exit cost model and existing slippage assumptions; no maker-fill credit in the first H-A run.
- Funding and mark-price histories are absent from these archives. Any OHLCV-only net result must explicitly state funding omitted and must not be presented as complete Bybit net PnL.
- Shared-capital replay only; no independent per-symbol equity summation.

## 4. Evaluation protocol (зафиксировано до replay)

- First run corrected-engine frozen baseline on exactly the same sparse universe, date boundary, folds, costs and capital settings.
- Then run this single frozen H-A definition once. No parameter sweep.
- Report total portfolio net PnL, PF, expectancy/trade, max DD, recovery, monthly returns, turnover, trade count, symbol/fold attribution, exposure, and costs.
- Report active universe size over time and eligible cross-sectional count distribution.
- Compare chronological windows separately. Folds previously used in E01–E13 are already researched, not blind holdout.
- Do not select instruments based on H-A in-sample PnL; any later shortlist must be retested on a separate chronological holdout.
- A positive aggregate result alone is insufficient: require positive net expectancy and no single fold/month dominating the result.

## 5. Gates before market PnL

1. Pure feature/rank unit tests: lookback indexing, timestamp causality, ties, minimum breadth, no future bars.
2. Sparse replay integration tests: late listings, missing open/pending candle fail-closed, terminal boundary, order invariance.
3. Independent accounting reconciliation: entry/exit fees, slippage, partial TP1, funding boundaries, equity path.
4. Verify the H-A runner loads the audited archive manifest and the corrected engine commit.
5. Run corrected-engine frozen baseline, then one H-A replay. No Bybit API, runner, new exchange data, or live orders.

## 6. Frozen replay parameters and chronology

Для baseline и H-A одинаковы:
- стартовый капитал 10,000 USDT; риск на сделку 0.5%; общий stop-risk cap портфеля 2%; максимум 5 одновременных позиций; leverage setting 5x;
- daily stop 5%, emergency kill-switch 30%;
- Donchian 20, ATR 14; stop 2.5 ATR; TP1 2R, TP2 5R; ATR trail 3.0; max hold 32 H1 bars;
- market entry/exit; max-chase 1.5%; maker fills не засчитываются;
- taker fee и slippage модели умножаются на 2.0 относительно текущих констант движка;
- baseline — текущий H1 Donchian + volume gate (min volume ratio 1.6); H-A — только замена signal evaluator на правила раздела 2. Остальные execution/risk settings идентичны.
- В каждом fold используется общий капитал 10,000 USDT с независимым reset; до начала signal window бары служат только для warm-up, сигналы до границы запрещены.

Фиксированные исследовательские окна (UTC):
1. 2026-04-27 12:00 — 2026-06-21 05:00
2. 2026-06-21 06:00 — 2026-08-14 23:00
3. 2026-08-15 00:00 — 2026-10-27 00:00

Это повторно исследованные E11/E13 окна, не holdout. Если архив заканчивается раньше requested end, используется фактический общий последний H1 бар и это явно отражается в отчёте.

Реализация: `scripts/run_h_a_relative_strength_replay.py`. По умолчанию скрипт выполняет только archive audit/prepare; для PnL требуется явный `--execute`. Он сравнивает baseline и H-A на одинаковом dynamic universe, сохраняет архивный manifest, fold summary, trade ledger, monthly equity и portfolio equity path. Это CryptoFetch/Binance-style OHLCV proxy: funding не загружен, поэтому funding в отчёте равен нулю и итог не является полным Bybit net PnL.

### 7. Фактическая подготовка архива — CI run 41632126319

Режим prepare-only успешно обработал все существующие ZIP без рыночного replay:
- 50 из 50 непустых H1 символов включены в sparse universe;
- 6 дублирующихся symbol/timeframe групп, 6 pairwise comparisons;
- 0 конфликтующих OHLCV overlap bars;
- 0 случаев, когда выбранный longest archive не покрывает timestamps другого дубликата;
- все 50 символов имеют общий terminal H1 bar `2026-10-26T00:00:00Z`;
- распределение первого доступного бара: 25 символов с `2025-10-27`, 22 с `2026-04-29`, 1 с `2026-07-02`, 1 с `2026-07-17`, 1 с `2026-09-24`.

Следствие: fold 3 физически заканчивается `2026-10-26T00:00:00Z`, а не requested `2026-10-27T00:00:00Z`; runner обязан показывать фактическую границу. Поздние символы допускаются в cross-section только после своего фактического старта и 72h warm-up. Архивный manifest с SHA-256 сохранён в artifact `h-a-archive-preparation` run 41632126319.

Это подтверждает пригодность существующих файлов для динамического OHLCV replay, но не доказывает Bybit listing history, не устраняет survivorship bias в исходном наборе символов и не добавляет funding/mark-price.

## 8. Фактический результат preregistered replay — 2026-11-03

CI run: 41633199418, commit 3ac4bb0c20c48e31e0264df7fe39235cb5c8a658, conclusion success. Артефакт: h-a-preregistered-ohlcv-results (fold_summary.csv, results.json, archive_manifest.json).

| Fold | Variant | Trades | Net USDT | PF | Expectancy R | Max DD |
|---|---|---:|---:|---:|---:|---:|
| 1 | Baseline | 320 | -2,278.63 | 0.66 | -0.193 | 24.01% |
| 1 | H-A | 306 | -1,601.57 | 0.74 | -0.140 | 17.79% |
| 2 | Baseline | 306 | -2,371.50 | 0.62 | -0.199 | 24.59% |
| 2 | H-A | 322 | -2,225.91 | 0.66 | -0.194 | 23.26% |
| 3 | Baseline | 396 | -985.85 | 0.88 | -0.034 | 15.04% |
| 3 | H-A | 405 | -2,307.78 | 0.74 | -0.136 | 30.01% |

По трём независимым reset-folds:
- Baseline: 1,022 trades; gross +587.02; fees 4,416.37; slippage 1,806.63; net -5,635.98 USDT.
- H-A: 1,033 trades; gross +29.53; fees 4,375.03; slippage 1,789.76; net -6,135.26 USDT.
- H-A хуже baseline на 499.28 USDT суммарно; это сумма трёх независимых прогонов с reset капитала, не единая непрерывная equity curve.
- H-A лучше baseline в fold 1 на 677.06 USDT и в fold 2 на 145.59 USDT, но хуже в fold 3 на 1,321.93 USDT. Преимущество не переносится между периодами.
- H-A net отрицателен во всех folds; PF ниже 1, expectancy отрицательна во всех folds. В fold 3 активировался 30% emergency kill-switch.
- H-A gross суммарно лишь +29.53 USDT до 6,164.79 USDT modeled fees+slippage. Baseline gross +587.02 до 6,223.00 USDT costs.
- Monthly path H-A: fold 1 May -12.38%, June -3.51%; fold 2 July -12.04%, August -11.03%; fold 3 September -14.16%, October -11.82%. Августовская частичная прибыль в начале fold 3 не удержалась.
- В H-A были отдельные символы с положительным net в нескольких folds (например ETC, ICP, ZEC), но их результаты малы относительно портфельного убытка и это post-hoc attribution на уже использованных периодах. Нельзя превращать их в shortlist без нового независимого хронологического теста.

### Вывод и решение

H-A отклонена как текущий кандидат: не показала положительного net expectancy, не покрыла расходы, а fold 3 показал существенное ухудшение и kill-switch. Не делать parameter tuning или отбора монет по этим же folds — это усилит selection bias. Не переходить к API/runner/live.

Следующий исследовательский шаг — не «подкрутить пороги H-A», а разобраться, почему у baseline/H-A столь большая доля gross edge поглощается costs и почему fold 3 ломает относительную силу: разложить сделки по turnover/holding time, entry/exit fee, adverse excursion, exit reason, long/short и режиму рынка. После этого решить, есть ли основание для отдельной preregistered гипотезы с меньшей частотой сделок. Текущие folds остаются использованными, не holdout. Funding не включён; это не Bybit net PnL.

## 9. Post-run trade-ledger attribution (без нового replay)

Агрегация уже сохранённого trade ledger из artifact run 41633199418:

**Направление H-A**
- Fold 1: long 156 сделок / -1,588.79 USDT; short 150 / -12.78 USDT. Убыток почти полностью пришёл от long.
- Fold 2: long 163 / -981.39; short 159 / -1,244.52 USDT. Оба направления отрицательны.
- Fold 3: long 227 / -409.85; short 178 / -1,897.93 USDT. Основной ущерб пришёл от short.
- Нет устойчиво лучшего направления: в разных folds меняется сторона, которая создаёт основную просадку.

**Причины закрытия H-A**
- Fold 1: stop_loss 153 сделки / -5,947.88 USDT; time_stop 104 / +2,283.68; trailing_stop 42 / +1,914.93; take_profit 2 / +172.69.
- Fold 2: stop_loss 167 / -6,221.34; time_stop 107 / +2,022.83; trailing_stop 41 / +1,762.95; take_profit 3 / +191.99.
- Fold 3: stop_loss 208 / -8,125.58; time_stop 114 / +1,499.03; trailing_stop 65 / +3,143.12; take_profit 13 / +1,253.01; kill_switch 5 / -77.36.
- Stop-loss cohort losses materially exceed gains from time/trailing/TP exits in each fold.

**Удержание и оборот**
- Median holding time: 19–20 H1 bars; p90 and maximum: 32 bars (configured max hold).
- H-A made 1,033 trades; total modeled fees + slippage = 6,164.79 USDT, about 5.97 USDT/trade on average. Aggregate gross PnL was only +29.53 USDT, about +0.03 USDT/trade. These are portfolio totals divided by trade count, not per-trade normalized expectancy.
- Ledger reconciliation is exact at reported precision: gross − fees − slippage − funding = net for each fold; funding is 0 because unavailable, not because actual funding would be zero.

**Research implication:** do not simply block long or short globally; the failing side flips by fold. The strongest diagnostic target is the stop-loss cohort versus profitable time/trailing exits, with entry quality and subsequent adverse/favourable excursion. Any next experiment must be a new preregistered hypothesis, not an optimized threshold or direction filter fitted to these already-used folds.

## 10. Независимая проверка сохранённого artifact и ограничений trade ledger

Artifact h-a-preregistered-ohlcv-results повторно скачан и прочитан как ZIP; проверены results.json, fold_summary.csv, archive_manifest.json. Это повторная проверка уже существующего результата, не новый рыночный replay.

### Покрытие фактического universe

- Manifest: 50 включённых H1 symbols, 6 duplicate symbol/timeframe groups, 6 pairwise comparisons, 0 conflicting overlap bars, 0 longest-file-not-superset pairs.
- По folds: 47 symbols в fold 1, 49 в fold 2, 50 в fold 3. Внутри fold активный universe менялся: fold 1 — 25–47 (median 47), fold 2 — 47–49 (median 49), fold 3 — 49–50 (median 49).
- Исторические начала файлов неоднородны: earliest 2025-10-27, median first timestamp 2026-01-27, latest first timestamp 2026-09-24. Поэтому число 50 — количество файлов/symbols, а не 50 одновременно торгуемых инструментов на всём периоде. Состав и breadth меняются во времени.
- Это по-прежнему CryptoFetch Binance-style proxy; manifest не доказывает, что каждый инструмент был доступен на Bybit в соответствующий момент, и не содержит delisted instruments отсутствующих в архиве.

### Важное ограничение уже использованного H-A ledger

Сохранённый artifact был создан до расширения export в runner. В его trades_ledger присутствуют symbol, direction, entry/exit dates/prices, size, gross, fees, slippage, funding, net, R и exit_reason, но **нет MAE, MFE, risk_usdt, gross_R, session и order_type**. Следовательно, предыдущая attribution по направлениям и причинам закрытия подтверждается исходным ledger, но MAE/MFE-разбор по этому artifact выполнить нельзя. Новые поля добавлены в runner для будущих диагностических запусков, однако пока не проверены новым CI/replay; нельзя ретроспективно приписывать их старому artifact.

### Интерпретация MAE/MFE в движке

Текущие TradeRecord.mae / .mfe хранят excursion в R до модельного выхода, а не независимую полную внутрисвечную траекторию цены. При стоп-срабатывании adverse extreme ограничивается модельной ценой stop fill (или gap open); неоднозначный wick за stop не включается. На fill bar favourable extreme не обновляется, поскольку OHLC не показывает, был ли экстремум до или после входа. Это консервативное правило исполнения, но оно цензурирует MAE stop-out сделок примерно на уровне исполнения стопа. Поэтому нельзя сравнивать MAE stop-loss trades с winners как полную меру «насколько цена шла против сделки». Для будущей диагностики это нужно обозначать как execution-bounded MAE; если понадобится анализ полного OHLC диапазона stop-bar, он должен быть отдельной метрикой с явной оговоркой о неизвестном порядке high/low.

### Обновлённый статус

- Ledger direction/exit attribution — подтверждена повторным чтением artifact.
- MAE/MFE attribution H-A — не выполнена; данных в сохранённом artifact нет.
- Dynamic universe breadth — измерен из сохранённого artifact; 50 symbols не были активны одновременно на всём горизонте.
- Никакой новый PnL replay не запускался.

## 11. Диагностический повтор с расширенным trade ledger — 2026-11-03

CI run [41670116033](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41670116033), commit `3f762a4bf9fa3f53a61ff0912e2deaf411ead4b8`, conclusion SUCCESS. Artifact: `h-a-preregistered-ohlcv-results`, artifact ID 13247672222.

Цель повторного запуска — не повторный поиск edge, а проверка расширенных диагностических полей `mae_r`, `mfe_r`, `risk_usdt`, `risk_pct`, `gross_r_multiple`, `session`, `order_type`. Сигналы, параметры, cost multiplier, folds и universe не менялись. Финансовые метрики всех шести variant/fold комбинаций совпали с предыдущим artifact на опубликованной точности. Следовательно, расширение ledger не изменило исполнение или PnL.

Поля trade ledger проверены отдельным deterministic regression в Research CI [41670688299](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41670688299), commit `952cb7cdceea91622bb560be4d462eba29d9d681`; полный workflow SUCCESS.

### Stop-loss cohort

По H-A суммарно:
- 1,033 сделки; 528 stop-loss (51.1%).
- Stop-loss net PnL: -20,294.80 USDT, в среднем -38.44 USDT на сделку.
- Средний MFE stop-loss cohort: 0.447R; median 0.31R.
- 37.7% stop-loss trades имели MFE не ниже 0.5R; 13.8% — не ниже 1R; 3.2% — не ниже 1.5R.
- Средняя длительность stop-loss trades: около 11.6 H1 bars.
- Fold stability: средний MFE stop-loss cohort = 0.463R / 0.430R / 0.448R в folds 1/2/3; доля MFE >=0.5R = 38.6% / 38.3% / 36.5%.

Сравнение с frozen baseline:
- Baseline: 523 stop-loss из 1,022 сделок (51.2%); stop-loss net -20,112.73 USDT; average stop-loss MFE 0.449R.
- H-A практически не изменила частоту stop-loss или их MFE profile. Relative-strength rank не улучшил качество этой когорты в измеряемом смысле.

### Другие exit cohorts H-A

| Exit reason | Trades | Net PnL total | Avg net/trade | Avg MFE |
|---|---:|---:|---:|---:|
| Stop-loss | 528 | -20,294.80 | -38.44 | 0.447R |
| Time-stop | 325 | +5,805.54 | +17.86 | 1.509R |
| Trailing-stop | 148 | +6,821.00 | +46.09 | 2.779R |
| Take-profit | 18 | +1,617.69 | +89.87 | 5.687R |
| Kill-switch | 5 | -77.36 | -15.47 | 0.780R |
| End-of-test | 9 | -7.33 | -0.81 | 0.949R |

Stop-loss MAE averages exactly 1R by construction: `_manage_position()` caps the adverse extreme at the modeled stop fill and excludes the ambiguous post-stop wick. MFE on stop bars is also conservative because the favorable extreme on the stop candle is not counted when OHLC cannot establish intrabar order. These values are execution-bounded, not full path extrema.

### Session and direction stability

Session net attribution changes by fold; no UTC session is consistently profitable. The long/short loss contribution also changes by fold, consistent with the earlier ledger analysis. Do not add a global session, long-only or short-only gate based on this artifact.

### Interpretation

The relative-strength hypothesis did not reduce stop-loss frequency (51.2% baseline vs 51.1% H-A), nor improve the stop-loss MFE profile (0.449R vs 0.447R). H-A's aggregate gross PnL fell by 557.49 USDT while modeled fees+slippage fell by only 58.21 USDT; net therefore deteriorated by 499.28 USDT.

A simple breakeven-at-0.5R or stop widening rule is not justified by these summaries. MFE/MAE do not preserve the sequence of intrabar price touches; changing a stop can also cut time-stop/trailing winners. Any stop-management hypothesis needs a separately preregistered path-aware replay, and must not be tuned on these already-used folds.

### Next diagnostic target

Investigate signal-candle and pre-break structure for stop-loss vs time/trailing winners: body/range relative to ATR, close location, upper/lower wick, volume ratio and trajectory, distance beyond prior Donchian boundary, and pre-break compression. Reconstruct only from bars available at signal close; use the previous H1 candle for next-bar entry and preserve the same shared-capital ledger. This is diagnostic attribution, not evidence of causality or a new profitable strategy.

## 12. Signal-candle and post-break attribution — 2026-11-03

Read-only artifact: workflow [41671977224](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41671977224), artifact ID 13248093501. It contains 2,055 trade rows across baseline and H-A, 41 cohort summaries, and a matching source archive SHA manifest. No PnL was recomputed; no signal or execution rule was changed.

### Pre-entry signal-candle features

Stop-loss vs profitable exit cohorts show weak separation from the signal candle alone. H-A in-sample rank AUC (higher feature value as a stop-loss score):

| Feature | AUC |
|---|---:|
| Signal range / ATR | 0.540 |
| Signal body / ATR | 0.546 |
| Signal volume / prior 20-bar mean | 0.515 |
| Directional close location | 0.516 |
| Breakout close clearance / ATR | 0.524 |
| Pre-break 6-bar range / 20-bar range | 0.477 |
| Previous close distance to Donchian boundary | 0.550 |

Fold-level direction and strength are not stable. The small take-profit cohort (18 H-A trades) has visibly larger impulse/volume, but is too small to justify a threshold. Do not introduce a signal-candle size, volume, wick or compression filter from this result.

### Post-entry follow-through and channel retest

For this analysis, the signal bar is the completed H1 candle immediately before the next-bar entry. Post-entry features use only completed H1 bars before exit. The exit candle is excluded for intrabar stop/trailing/TP/kill-switch exits; it is included only for close-based time-stop/end-of-test exits. No OHLC intrabar order is inferred.

H-A results:
- 3-bar close return in R: stop-loss cohort mean -0.104R (451 eligible trades), profitable exit cohort mean +0.222R (486 eligible trades). Rank AUC for a lower return indicating stop-loss is approximately 0.700.
- 6-bar close return in R: stop-loss mean -0.118R (353 eligible), profitable cohort mean +0.313R (475 eligible). Rank AUC for a lower return indicating stop-loss is approximately 0.734.
- Close back inside the prior Donchian boundary at least once within 3 completed bars: 61.6% of eligible stop-loss trades vs 41.6% of profitable exit trades; AUC 0.600.
- Same retest within 6 completed bars: 73.1% vs 50.5%; AUC 0.613.

The 3-bar retest association is directionally consistent in all folds:
- Fold 1: retest cohort net -1,206.64 USDT; no-retest cohort +589.12.
- Fold 2: retest cohort -2,540.07; no-retest +1,102.86.
- Fold 3: retest cohort -2,917.66; no-retest +1,397.25.

Baseline shows a similar pattern: 3-bar retest cohort net -5,604.54 USDT vs +3,588.59 USDT without retest. This suggests the observation is not unique to the H-A relative-strength rank.

These are eventual realized outcomes conditioned on a future path event, not counterfactual results of exiting at the retest. The eligible cohorts also exclude trades that exit before the requested horizon. This is not proof that an early exit rule would improve PnL.

### Research interpretation

The evidence currently favours post-entry continuation / early invalidation research over a pre-entry candle-shape classifier:
- Signal-candle shape, volume and pre-break compression have AUC close to 0.5.
- Directional close return after 3–6 completed H1 bars has materially stronger separation.
- A close back inside the prior breakout boundary is more common among stop-loss outcomes and has consistent fold-level association.

This is the most promising descriptive pattern found so far, but the folds are already used and are not holdout. Do not select an exact 1/3/6-bar threshold, optimize a retest rule, or claim profitability from this attribution. A future preregistered H-C should define the confirmation/invalidation timing and conservative execution before any new unseen data is tested.
