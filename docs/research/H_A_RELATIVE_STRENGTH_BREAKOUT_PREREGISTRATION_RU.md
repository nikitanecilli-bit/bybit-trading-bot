# H-A — Relative Strength Breakout: preregistration

Дата фиксации: 2026-11-03  
Статус: hypothesis specified; no market PnL run  
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

## 4. Evaluation protocol

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

