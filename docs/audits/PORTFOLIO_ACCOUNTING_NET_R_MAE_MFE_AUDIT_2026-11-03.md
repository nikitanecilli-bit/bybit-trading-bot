# Аудит портфельной бухгалтерии, Net R и MAE/MFE

Дата: 2026-11-03
Статус: STATIC AUDIT COMPLETE — no confirmed profit-inflating accounting defect found; one conservative MTM/exit-cost asymmetry documented.
Объект: `Bybit_Trading_Engine_v14_research.py`, `tests/test_portfolio_accounting.py`, `tests/test_gap_execution.py`, `tests/test_funding_mark_to_market.py`.

## 1. Проверенные тождества

### Закрытая сделка

`gross_pnl = realized_tp1_gross + remaining_size * signed_price_change`.

`net_pnl = round_money(gross_pnl - fees - slippage - funding)`.

`net_R = net_pnl / initial_estimated_stop_risk`.

В журнал попадают gross/net PnL, комиссии, slippage, funding, risk_usdt, risk_pct, gross_R и net_R. Риск-делитель — сохранённый первоначальный денежный риск с учётом моделируемых затрат на стоп, а не стартовый капитал. Это согласуется с назначением R multiple. Нулевой/отрицательный риск не должен возникать на штатном пути: fill отклоняется при size_usdt <= 0 или risk_usdt <= 0.

### Частичный TP1

После TP1:
- реализуется 50% размера по TP1;
- remaining_fraction становится 0.5;
- gross PnL открытой позиции складывается из реализованной TP1-ноги и mark-to-market остатка;
- при закрытии итоговый gross PnL собирается из тех же двух частей;
- fees/slippage считаются по входу, TP1 и финальному выходу отдельно.

Найдены отдельные regression tests на TP1, последующий стоп, TP2, funding quantity и reconciliation закрытой сделки.

### Equity и просадка

Risk manager ведёт `current_equity = realized_equity + unrealized_pnl`. На синхронизированной сетке свечей portfolio replay предварительно рассчитывает adverse marks по всем символам до обработки каждого символа, чтобы внутрибарая просадка не зависела от порядка обхода. Закрытия с одинаковым exit timestamp группируются перед расчётом closed-trade drawdown. Итоговая просадка берёт максимум между closed-trade equity DD и intrabar MTM DD.

Это правильное направление реализации; оно не заменяет реальный тиковый equity path, которого в OHLC нет.

## 2. Найденная асимметрия: открытый MTM против фактического TP exit

В `_unrealized_pnl_at_marks()` оставшаяся позиция всегда получает оценку будущего выхода как taker:
`remaining_notional * (TAKER_FEE + TAKER_SLIP)`.

В `_close_position()` финальная нога при `exit_reason == "take_profit"` и `maker_exits == True` оценивается как maker без taker slippage.

Текущие константы:
- taker fee = 0.055%;
- maker fee = 0.020%;
- taker slippage = 0.0225%.

Поэтому открытый MTM на maker TP-сценарии занижает equity относительно соответствующего финального TP PnL на 0.0575% оставшегося notional. Например, на остатке $10,000 разница составляет $5.75.

Классификация: CONSERVATIVE MODEL ASYMMETRY, не подтверждённая ошибка закрытого PnL. Она может преждевременно сработать на daily stop / kill switch при близости к порогу. Это может снизить результат и число сделок, но само по себе не завышает прибыльность. Текущая консервативность может быть намеренной, однако её следует явно параметризовать/документировать и тестировать на пороговых сценариях.

Важно: не менять на maker MTM автоматически. OHLC touch не доказывает maker fill, а очередь/частичные исполнения неизвестны. До получения более реалистичной модели разумно оставить taker MTM как стресс-оценку, но не смешивать её с отчётным фактическим PnL.

## 3. MAE/MFE

MAE/MFE рассчитываются в ценовых R от initial_stop_dist, не от денежного risk_usdt после fees. Это нормальная excursion-метрика, но её нельзя смешивать с net_R.
- Fill-bar: благоприятный экстремум не засчитывается, поскольку он мог быть до входа; неблагоприятный экстремум учитывается консервативно.
- Stop-bar: благоприятный wick не засчитывается, MAE ограничивается моделируемой ценой stop fill, включая gap.
- На обычных последующих барах экстремумы накапливаются.
- TP1 не сбрасывает начальную базу R.
- Финализация использует накопленные экстремумы и последний общий close.

Найденные тесты покрывают long/short stop-bar, fill-bar, partial TP1 и trailing lifecycle. OHLC всё равно не позволяет восстановить фактический порядок high/low.

## 4. Текущее покрытие, подтверждённое по исходникам

В `tests/test_portfolio_accounting.py` есть тесты:
- equity = realized + unrealized;
- TP1 partial mark;
- long/short unrealized sign;
- closed trade PnL/fees/slippage/equity reconciliation;
- risk budget cap и zero budget rejection;
- simultaneous-entry order invariance;
- same-bar multi-symbol stop/order invariance;
- exit chronology drawdown;
- funding settlement boundary и TP1 remaining quantity.

В `tests/test_gap_execution.py` есть long/short gap, stop-vs-TP collision, fill-bar MAE/MFE, partial TP1 и per-leg fees/slippage cases. В `tests/test_funding_mark_to_market.py` есть accrued funding, settlement boundary, missing mark fail-closed и funding-triggered daily stop.

Это статическая проверка кода и перечня тестов. Последующая полная Research CI проверка #41542100415 завершилась SUCCESS на commit `0546f53a45bb4508d1f16ba06bbb310cdd69b1de`; compile и весь детерминированный suite, включая portfolio accounting, funding, exchange sizing и новые archive-audit tests, прошли. Этот CI не добавляет отдельного threshold-boundary теста для MTM maker-vs-taker asymmetry; этот конкретный пробел остаётся OPEN.

## 4A. Regression for conservative maker MTM asymmetry — 2026-11-03

Added `test_open_maker_take_profit_mtm_remains_conservative_vs_final_maker_close` to `tests/test_portfolio_accounting.py`. It pins the exact expected difference for a $1,000 limit-entry long whose modeled final TP exit is maker: open-position MTM stresses the remaining exit as taker fee + taker slippage, while the closed TP ledger uses maker fee. The test asserts the conservative MTM shortfall equals the modeled fee/slippage delta on the $1,100 exit notional.

Research CI [41676899254](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41676899254) completed SUCCESS on the test commit; portfolio accounting **40/40** passed, including the new regression. Added follow-up `test_conservative_maker_mtm_can_trip_daily_stop_before_modeled_maker_close`: it places the daily-stop threshold between the conservative open-position MTM and the corresponding modeled maker-close result, and confirms the conservative mark trips the latch while the maker-close comparison does not. Research CI [41677294943](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41677294943) completed SUCCESS on the follow-up test commit; portfolio accounting **41/41** passed. The asymmetry and its risk-gate consequence are now explicitly pinned. This confirms intended conservative behavior, not a profit-inflating accounting defect. No engine behavior or PnL replay was changed.

## 5. Открытые ограничения

- Intrabar path и очередь лимиток неизвестны из OHLC.
- MTM оценивает будущий выход консервативно taker, а TP target в закрытой записи может быть maker proxy.
- Liquidation, maintenance margin tiers и exchange margin accounting не моделируются полноценно.
- Funding/mark-price archive на Bybit пока не получен; существующие Binance-proxy прогоны не имеют исторического funding.
- Пороговые тесты для MTM maker-vs-taker асимметрии нужны отдельно.
- Нужен запуск актуального CI после будущего изменения тестов/кода; этот аудит сам по себе не является CI.

## Решение

`NO P0 ACCOUNTING DEFECT CONFIRMED`.
`P1 DOCUMENTED`: conservative MTM exit-cost asymmetry may trigger risk gates earlier than a maker TP close would.
Не менять движок и не запускать рыночные бэктесты на основании этого статического аудита. Следующий безопасный шаг — добавить детерминированные тесты на границе daily-stop/kill-switch и явно зафиксировать expected conservative behavior, затем продолжить аудит margin/liquidation and data alignment.


## Superseding finding — exit fee/slippage notional basis (2026-11-03)

The earlier audit verified that closed net PnL reconciled as gross PnL minus modeled fees, slippage and funding, but did not verify the notional basis used for each execution leg. A subsequent Bybit fee-formula audit found a confirmed defect: TP1/final exit fee and slippage were calculated from entry notional rather than actual modeled exit notional. This has now been corrected in v14; see `EXCHANGE_SIZING_INTEGRATION_AND_BYBIT_SCHEMA_2026-11-03.md` section 15.

The earlier reconciliation conclusion remains true algebraically, but the historical fee amounts and net PnL values produced by the old formula were not exchange-price accurate. The regression suite now checks long/short stops, gaps, TP1/TP2 and MTM with execution-price notionals. CI #41536540759 passed.



## E11/E13 artifact sensitivity — exit-notional fee correction (2026-11-03)

Downloaded and inspected the archived E11 artifact `13105661683` and E13 artifact `13105403824`. Both use market execution and a 2× cost multiplier; E13 baseline reproduces E11 baseline. The trade CSVs retain gross PnL and the summary retains fold-level gross/net PnL.

A fixed-trade, cost-only sensitivity can be calculated without changing trade sequence:

- For each completed position, total exit notional across all exit legs equals entry notional plus gross PnL for linear USDT quantity accounting.
- Old exit costs used entry notional; corrected exit costs use execution notional.
- For all-taker exits with the same rate on every leg, aggregate exit-cost delta = gross PnL × 2 × (0.055% taker fee + 0.0225% taker slippage).
- Therefore adjusted net for the *same historical trades* = old net − gross PnL × 0.00155.

| Replay | Old sum of fold net | Cost-only adjusted estimate | Fold sums remain |
|---|---:|---:|---|
| E11 body gate OFF | -3,178.61 | -3,181.69 | -618.82 / -2,967.89 / +405.02 |
| E11 body gate ON | -2,774.00 | -2,778.31 | -1,228.07 / -2,558.93 / +1,008.69 |
| E13 compression OFF | -3,178.61 | -3,181.69 | -618.82 / -2,967.89 / +405.02 |
| E13 compression ON | -2,741.72 | -2,744.98 | -296.65 / -2,612.60 / +164.27 |

The cost-only correction changes the E11 body-gate improvement from +404.61 to approximately +403.38 USDT, and the E13 compression-gate improvement from +436.89 to approximately +436.71 USDT. Both variants remain materially negative, especially fold 2.

**Important scope limitation:** this is not a rerun on the corrected engine. It holds the archived fills, sizes, and trade sequence fixed and estimates only the exit-notional cost delta from rounded aggregate gross PnL. The fee fix also changes stop-risk cost estimates used by position sizing; changed position sizes can affect portfolio capacity, fills and subsequent trade sequence. Per-leg cent rounding can also create small differences. Thus the table is a sensitivity estimate, not replacement ledger PnL and not a profitability claim.

Source artifacts and commits:
- E11 run 41361376448, artifact 13105661683, commit `ae6f7b4c99b79cbe31fdfeded8780a058b118049`.
- E13 run 41362217727, artifact 13105403824, commit `f4da3cca0c0dc79cee86350ba6a680fc461e47fc`.
- Fee correction CI run 41536540759, commit `4eb9a2e7d7fc6a198937ef028dec32a5f723e22d`.

Decision: keep E11/E13 historical PnL marked provisional. No strategy conclusion changes; no market backtest or parameter sweep was run.


## E11/E13 directional scope check

A direct read of the archived trade CSVs confirms all 1,452 E11 trade rows and all 1,496 E13 trade rows have `direction=long`; both experiment runners explicitly discard non-long signals. Therefore:
- the fixed-trade exit-notional sensitivity formula above is directionally valid for these artifacts (long gross PnL equals total exit-notional change);
- E11/E13 do not provide evidence about short-side breakout expectancy, costs, or portfolio interaction;
- any future two-sided strategy validation must treat short-side testing as a separate experiment, not infer it from these long-only results.

This is a scope limitation, not a newly discovered defect in the portfolio engine.


## Superseding update — UTC risk boundary and journal price precision (2026-11-03)

После исходного статического аудита найдены и исправлены два дополнительных дефекта, не завышавших PnL, но влиявших на риск-контроль и воспроизводимость журнала:
1. **UTC daily baseline timing (P1):** новый дневной baseline фиксировался до обновления mark equity на границе UTC-даты. Исправлено; first-mark initialization сохранена. Регрессии daily rollover и independent daily/kill latches: Research CI #41682730056 SUCCESS; portfolio accounting 45/45.
2. **TradeRecord price precision (P1 reporting):** entry/exit prices округлялись до 6 знаков, price levels/distances — до 8; для low-priced assets это теряло точность, хотя PnL считался по исходным значениям. Все price/distance fields переведены на 12 знаков; regression подтверждает восстановление gross PnL и stop distance. Research CI #41685190246 SUCCESS; portfolio accounting 47/47.

Также добавлены отдельные проверки same-bar slot reservation, simultaneous daily-stop/kill-switch latches и funding-adjusted bankruptcy reconciliation. Ни один из этих тестов не запускает рыночный PnL replay.

**Текущий вывод:** confirmed profit-inflating accounting defect в проверенном lifecycle не найден. Исправленные UTC/journal defects закрыты регрессиями. Консервативная taker-MTM vs maker-TP asymmetry остаётся намеренной и протестированной. Liquidation остаётся isolated position-level approximation; account-wide cross-margin/UTA не моделируется. Bybit-native archive отсутствует, поэтому PnL validity/exchange execution остаются data-gated.
