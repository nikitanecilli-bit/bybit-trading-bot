# ENG-RISK-001 — mark-to-market immediately after a new position fills

Статус: ACCEPT — confirmed defect fixed; regression tests and technical CI passed.
Дата: 2026-11-02.
Тип: deterministic portfolio-risk accounting regression; не рыночный эксперимент.

## Наблюдаемая проблема

В run_simulation_pass() перед обработкой символов вызываются _prepare_portfolio_intrabar_marks() и _update_mark_to_market() для позиций, которые уже были открыты до текущего бара.

В step_candle():
1. текущая свеча сначала оценивается до входа;
2. затем _try_fill_pending() может открыть новую позицию;
3. при успешном fill вызывается _manage_position();
4. между fill и завершением шага нет обновления _intrabar_risk_marks[symbol] и повторного _update_mark_to_market().

До входа для символа без позиции _intrabar_risk_marks[symbol] содержит curr.close. После входа новая позиция может получить неблагоприятный экстремум текущей свечи в max_adverse_px, но portfolio MTM остаётся рассчитанным по старому mark. На следующем баре прежний экстремум уже не входит в текущий adverse mark. Поэтому daily stop / kill-switch могут не увидеть drawdown новой позиции на баре входа.

## Предварительная гипотеза

После успешного fill движок должен:
- рассчитать adverse risk mark для только что открытой позиции через _risk_mark_for_position(pos, curr);
- обновить _intrabar_risk_marks[symbol];
- повторно вызвать _update_mark_to_market(bar_close_ts) до дальнейшего управления позицией.

Это должно применяться к long и short. Для limit fill OHLC не раскрывает, случился ли экстремум до или после фактического intrabar fill; использование полного adverse экстремума является консервативной политикой и согласуется с текущим учётом MAE. Для market fill по open текущий бар целиком следует после открытия, поэтому пропуск adverse excursion особенно проблематичен.

Если новый mark включает kill-switch, _manage_position() должен увидеть уже активированный kill-switch и использовать существующий приоритет принудительного выхода.

## Критерии проверки

- Regression test проходит через step_candle() с pending market entry.
- До fill mark-to-market не учитывает новую позицию.
- После fill adverse low для long / adverse high для short включается в portfolio unrealized PnL на том же bar-close timestamp.
- Настроенный test threshold подтверждает, что kill-switch срабатывает на fill bar, а не ждёт следующей свечи.
- Проверить long и short симметрию.
- Существующие tests на kill-switch, stop/TP collision, gap execution, portfolio risk, funding MTM и persistence остаются зелёными.
- Никаких market backtests, параметрических оптимизаций или production/live изменений.

## Риски и границы

- OHLC не раскрывает путь цены внутри свечи. Для intrabar limit fills adverse mark по полному low/high консервативен и может переоценить фактическую просадку, если экстремум был до fill.
- Это корректность симуляции риск-ограничений, не доказательство торгового edge.
- Повторный MTM должен выполняться только после успешного fill; не менять порядок signal generation и sizing без отдельного обоснования.

## Решение

Решение: ACCEPT для исследовательского движка.

- Regression tests were committed first: `bf0b556f7cb0b88620c62af22634b6d95612dfc9`.
- The test-only CI run [#41475914811](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41475914811) failed exactly at the new long fill-bar test: observed only the pre-fill MTM call `[(0, bar_close_ts)]`; the test expected a second adverse mark `-100`.
- Fix commit: `f65c08bec78b179a9a89832ce31b574740f4dce3` updates the adverse mark after a successful fill and calls MTM again before position management.
- Passing CI: [#41475941543](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41475941543), SUCCESS. Compile, secret scan, all 27 gap-execution tests, 38 time-model tests, portfolio risk tests and 54 persistence tests passed; all other workflow steps completed successfully.
- Both long and short fill-bar regression tests passed and confirm the kill-switch sees the adverse entry-bar excursion at the same bar-close timestamp.

Рыночные backtests запрещены для этого engineering task. ACCEPT означает исправление риск-учёта в исследовательском движке, не доказательство доходности стратегии и не live/production approval.