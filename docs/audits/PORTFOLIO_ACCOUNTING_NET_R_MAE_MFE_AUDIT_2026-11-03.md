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

Это статическая проверка кода и перечня тестов. Я не утверждаю, что новый CI был запущен в этой сессии: доступного действия для dispatch workflow нет. Последний ранее подтверждённый полный Research CI — #41520724088; он предшествует этому аудиту.

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
