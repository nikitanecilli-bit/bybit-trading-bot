# H-B Mean Reversion — Synthetic Test Specification v0.1
**Дата:** 2026-11-05  
**Статус:** SPECIFICATION ONLY / SYNTHETIC-ONLY / NOT MARKET-PREREGISTERED / NOT MARKET-VALIDATED / NOT DEPLOYMENT-APPROVED

## 1. Назначение и границы

Документ задаёт детерминированный контракт для будущих offline synthetic tests H-B и регрессионных тестов существующих стратегий. Он не разрешает подключение биржи, получение архивов, private/account API, paper/live trading, расчёт рыночного PnL или parameter sweep.

Тесты должны доказывать механику и сохранение инвариантов, а не прибыльность/edge. Synthetic pass не открывает market-data, preregistration или deployment gate.

## 2. Неизменяемая гипотеза и временная семантика

- Таймфрейм H1, только long.
- Range regime gate вычисляется на закрытии бара t-1 и не использует shock bar t или последующие данные.
- Shock на close t: `close[t] <= close[t-24] - 2.0 * ATR[t-1]`.
- Требуются ровно 24 последовательных H1 бара до t; пропуск, дубликат, неверная длительность, invalid/non-positive ATR — fail closed.
- Stabilization на close t+1: строго `close[t+1] > high[t]`.
- Сигнал/сохранение pending — после закрытия t+1; вход — по `open[t+2]`, не по close t+1.
- Stop — абсолютный frozen `low[t]`.
- Target — арифметическое среднее ровно 24 pre-shock closes `close[t-24:t]`, включая t-24 и исключая t.
- Time stop — close 24-го H1 бара удержания; fill bar считается первым.
- Никаких partial exits, trailing, breakeven, averaging, повторного расчёта target/stop после рестарта.
- Policy version: `v0.1`.

## 3. Соглашения о синтетическом времени и данных

Использовать искусственные UTC timestamps на сетке ровно 3_600_000 ms. Fixtures должны задавать OHLC, ATR, range-gate labels и timestamps явно, без random seed и без обращения к внешним данным.

Минимальный fixture builder:
1. 24 последовательных pre-shock close с заранее вычислимым средним.
2. Предыдущий ATR положительный и конечный.
3. Shock bar t, удовлетворяющий точному порогу; отдельный граничный fixture с равенством.
4. Stabilization bar t+1 с close выше shock high; отдельный fixture с равенством, который обязан отклоняться.
5. Fill bar t+2 с независимо задаваемым open, включая gap-up/down случаи.

Каждый тест должен проверять не только итоговый статус, но и отсутствие нежелательных мутаций (pending, positions, risk manager, backup, journal). Для ошибок persistence предыдущий backup сравнивать byte-for-byte.

## 4. End-to-end happy path

Один детерминированный сквозной сценарий:
1. Построить валидную последовательность t-24…t+1 и проверить один H-B signal.
2. Проверить, что pending содержит strategy, direction, signal_ts, signal_origin_ts и все H-B metadata.
3. Сохранить pending и восстановить из Plan B backup.
4. На следующем H1 баре исполнить по фактическому open t+2.
5. Проверить геометрию `0 < shock_low < actual_fill < frozen_mean_target`.
6. Рассчитать shared risk sizing от actual fill до absolute shock-low stop; проверить risk_usdt, qty rounding и portfolio budget.
7. Создать H-B OpenPositionState: TP1/TP2 null; TP1 false; TP1 timestamp null; realized TP1 gross 0; remaining fraction 1; frozen shock/stop/target/policy.
8. Сохранить и восстановить открытую позицию.
9. Рассчитать intrabar и bar-close MTM, не обращаясь к TP1 price.
10. Проверить приоритет liquidation > kill-switch > protective stop > H-B mean target > time stop.
11. Закрыть H-B через каждый допустимый механизм в отдельных изолированных тестах.
12. Проверить TradeRecord, JSON journal и H-B-only report; проверить, что legacy strategy records не изменились.

## 5. Signal evaluator — позитивные и негативные проверки

| ID | Сценарий | Ожидание |
|---|---|---|
| SIG-01 | Валидный range gate t-1, shock и stabilization | Ровно один pending H-B |
| SIG-02 | Shock ровно на пороге | Условие проходит (`<= `) |
| SIG-03 | Shock на минимально меньшем отклонении | Сигнал отсутствует |
| SIG-04 | Stabilization close строго выше shock high | Условие проходит |
| SIG-05 | Stabilization close равен shock high | Сигнала нет (строгое `>`) |
| SIG-06 | Range gate false на t-1 | Сигнала нет |
| SIG-07 | Gate меняется на shock bar, но t-1 false | Сигнала нет |
| SIG-08 | Меньше 24 pre-shock closes | Fail closed |
| SIG-09 | Gap/duplicate/non-H1 timestamp в окне | Fail closed |
| SIG-10 | ATR отсутствует, NaN, Inf, zero или negative | Fail closed |
| SIG-11 | Неполный/невалидный OHLC | Fail closed |
| SIG-12 | Проверка lookahead: изменение t+1/t+2 не меняет уже вычисленный shock predicate | Нет lookahead |
| SIG-13 | Повторная обработка того же закрытого бара | Нет дублирующего pending |
| SIG-14 | Short/неизвестное направление | Не создаётся H-B сигнал |

## 6. Pending persistence — schema и fail-closed

H-B pending должен содержать все H-B поля: `h_b_shock_ts_ms`, `h_b_stop_price`, `h_b_target_price`, `h_b_exit_policy_version`, а также `signal_origin_ts`. Strategy строго `H-B-mean-reversion`, direction строго `long`. Shock timestamp положительный integer и строго раньше signal_ts; signal_origin_ts положительный integer, не позже signal_ts и backup saved_at_utc. Stop/target finite positive, stop < target; policy version строго `v0.1`.

| ID | Сценарий | Ожидание |
|---|---|---|
| PEN-01 | Валидный H-B pending save → load | Полный round-trip без изменения значений |
| PEN-02 | По очереди отсутствует каждый H-B key | Save/load reject |
| PEN-03 | H-B key присутствует у legacy strategy | Reject |
| PEN-04 | Unknown key | Reject |
| PEN-05 | bool/string/zero/negative/future timestamp | Reject |
| PEN-06 | signal_origin_ts > signal_ts | Reject |
| PEN-07 | shock_ts >= signal_ts | Reject |
| PEN-08 | NaN/Inf/zero/negative stop или target | Reject |
| PEN-09 | stop >= target | Reject |
| PEN-10 | policy version != v0.1 | Reject |
| PEN-11 | Save candidate не проходит тот же reader, что load | Save reject, старый backup byte-identical |
| PEN-12 | Legacy pending без H-B metadata | Старое поведение сохраняется |
| PEN-13 | H-B signal provenance с timestamp вне backup boundary | Reject |

Не ослаблять глобальный unknown-field rejection и не менять legacy schema без необходимости.

## 7. Fill adapter и sizing

Fill допускается только на непосредственно следующем H1 баре после signal_ts. Fill price — actual `curr.open`. Проверки выполняются до создания позиции и до изменения risk manager.

| ID | Сценарий | Ожидание |
|---|---|---|
| FIL-01 | Actual fill между frozen stop и target | Fill разрешён |
| FIL-02 | Fill <= shock-low stop | Pending отклонён, позиция не создана |
| FIL-03 | Target <= actual fill | Pending отклонён |
| FIL-04 | Gap-up при неизменном абсолютном stop | Stop не пересчитывается от close t+1 |
| FIL-05 | Actual fill-to-stop distance | Используется для shared sizing и initial_stop_dist |
| FIL-06 | Sizing от signal close вместо actual fill | Regression test должен выявить расхождение |
| FIL-07 | После lot/qty rounding risk/budget/geometry нарушены | Reject, stop не двигается |
| FIL-08 | Stale pending или пропущен immediate next bar | Pending не исполняется |
| FIL-09 | H-B bypass chase guard | Только H-B; legacy chase guard unchanged |
| FIL-10 | Invalid spec/risk tier/minQty/minNotional | Reject по общим правилам |
| FIL-11 | Legacy signal без H-B metadata | Старый fill path семантически неизменен |

## 8. OpenPositionState, restore и TP-null lifecycle

H-B TP1/TP2 являются `None`, не sentinel numbers. Сохранить constructor compatibility для legacy; nullable TP fields валидировать strategy-aware. Для H-B требуется согласованное состояние: `tp1_hit=False`, `tp1_ts_ms=None`, `realized_tp1_gross_usdt=0`, `remaining_fraction=1.0`. Запрещено частичное состояние.

| ID | Сценарий | Ожидание |
|---|---|---|
| POS-01 | H-B position save/load | Все frozen metadata round-trip exact |
| POS-02 | H-B null TP1/TP2 | Restore разрешён |
| POS-03 | Legacy long/short с числовыми TP | Старые проверки/поведение unchanged |
| POS-04 | H-B с любым non-null TP | Reject |
| POS-05 | H-B TP1 hit/partial fraction/TP1 timestamp | Reject |
| POS-06 | initial_stop_dist != entry - frozen stop | Reject с документированным tolerance |
| POS-07 | stop_price != frozen H-B stop | Reject |
| POS-08 | missing/invalid policy, shock ts, target | Reject |
| POS-09 | H-B exchange-sized minNotional | Проверяется по frozen stop/mean target, не TP2 |
| POS-10 | H-B restore не должен сбрасывать kill-switch latch | Latch сохраняется |
| POS-11 | Unknown position field | Reject |
| POS-12 | Старый backup без H-B полей | Legacy restore unchanged |

## 9. MTM, manager, exit ordering

Все common protective layers сохраняются. После liquidation, kill-switch и protective stop менеджер должен иметь отдельную H-B ветку до любых TP1/TP2/trailing/breakout calculations, затем return. TP1 quantity/notional вычислять только если TP1 действительно hit; H-B не вызывает `_apply_tp1()`.

| ID | Сценарий | Ожидание |
|---|---|---|
| MGR-01 | Intrabar MTM H-B с null TP | Нет исключения; нет TP1 fee leg |
| MGR-02 | Bar-close MTM H-B с null TP | Нет исключения |
| MGR-03 | H-B manager проходит target | Полное закрытие на frozen target |
| MGR-04 | Stop и target в одной свече | Stop first |
| MGR-05 | Long stop gap ниже stop | Исполнение по min(stop, candle.open) |
| MGR-06 | Target gap выше target | Без price improvement, фиксированный target |
| MGR-07 | Target/time condition на fill bar | Не закрывать discretionary exit на fill bar; stop active |
| MGR-08 | Time stop | На close 24-го бара удержания, fill bar = bar 1 |
| MGR-09 | Trailing/TP1/TP2 legacy условия одновременно истинны | H-B не вызывает breakout exits |
| MGR-10 | Liquidation + stop/target | Liquidation first |
| MGR-11 | Kill-switch latched + target/time | Kill-switch first |
| MGR-12 | H-B target/time не меняют frozen metadata | Frozen values неизменны |
| MGR-13 | Restart перед target/stop/time | Поведение после restore идентично uninterrupted path |

## 10. Close/accounting/provenance

Все close paths должны вызывать общую accounting semantics без TP1 partial leg. H-B остаётся full-size: remaining fraction 1.0; exchange-sized final quantity равен полной оставшейся позиции. Nullable TP serialisation должна быть безопасной.

| ID | Сценарий | Ожидание |
|---|---|---|
| CLS-01 | Close by stop | PnL/fees/slippage/funding корректны, provenance complete |
| CLS-02 | Close by mean target | Полное закрытие, target policy сохраняется |
| CLS-03 | Close by time stop | Полное закрытие, причина exit однозначна |
| CLS-04 | Liquidation close | Provenance сохранён; liquidation accounting path не заменён ordinary reduce validation |
| CLS-05 | Kill-switch flatten | Все H-B позиции закрыты exactly once с provenance |
| CLS-06 | Replay finalization | Administrative close, не маскировать как H-B target/time |
| CLS-07 | H-B TP fields в TradeRecord | null; round() не применяется к None |
| CLS-08 | TP1 fee/slippage/gross leg | Ноль/отсутствует |
| CLS-09 | initial_stop_price | Равен frozen shock-low |
| CLS-10 | Journal JSON | H-B fields и null сохраняются, `json.dumps(..., allow_nan=False)` проходит |
| CLS-11 | Non-H-B TradeRecord | Новые H-B provenance поля null; legacy JSON semantics unchanged |
| CLS-12 | Двойной close/re-entry | Нет повторного PnL, дублирующей записи или повторного удаления позиции |

## 11. Portfolio risk and report isolation

- Проверить, что общие liquidation/kill-switch/portfolio budget правила действуют на H-B без отдельного обхода.
- Проверить batch-close order independence для одинакового exit timestamp и aggregate drawdown/kill-switch evaluation после полного batch snapshot.
- Portfolio risk может объединять стратегии, но strategy edge attribution и readiness должны фильтровать точное `strategy == "H-B-mean-reversion"`.
- Generic `MaintenanceGateAuditor.all_ok` запрещено отображать как H-B readiness.
- Synthetic report не выводит market return/PF/monthly return/profitability/edge и не может иметь green readiness.

| ID | Сценарий | Ожидание |
|---|---|---|
| RPT-01 | Mixed legacy + H-B TradeRecords | H-B attribution включает только H-B |
| RPT-02 | Portfolio risk aggregation | Включает обе стратегии и помечает scope=portfolio |
| RPT-03 | Generic all_ok=true | Не открывает H-B market/deployment gate |
| RPT-04 | Synthetic report | Только mechanical pass/fail и coverage |
| RPT-05 | Provenance missing | Report fails closed / incomplete, не выдаёт validated |
| RPT-06 | Unknown external journal consumers | Compatibility status = unknown, не assumed compatible |
| RPT-07 | Same-time multi-symbol closes reordered | Aggregated result invariant to list order |

## 12. Legacy non-regression matrix

Существующие тесты остаются нормативными; новые H-B ветки не должны ослаблять assertions:
- legacy long и short TP ordering;
- TP1 partial lifecycle, timestamp, realized gross и remaining fraction;
- legacy pending save/load, freshness и immediate-next-bar fill;
- unknown position/pending field rejection;
- atomic save, fsync/replace failure и сохранение предыдущего backup;
- legacy exchange-sized minNotional и remaining qty checks;
- старые TradeRecord JSON числовые TP значения;
- liquidation/kill-switch/close accounting;
- существующие strategy signal fixtures и отчёты.

Требование: для одинаковых legacy fixtures результаты до/после H-B должны совпадать по TradeRecord economic fields, journal fields и risk state, кроме заранее утверждённых additive schema metadata. Никаких скрытых изменений defaults.

## 13. Рекомендуемая структура будущих тестов

Добавить отдельный модуль, например `tests/test_h_b_mean_reversion_synthetic.py`, с независимыми fixture helpers. Не перегружать существующие тестовые модули H-B-specific conditions. Переиспользовать реальные классы/методы движка; не писать mock-движок, который дублирует production logic.

Группы тестов:
1. `TestHBSignalMechanics`
2. `TestHBPendingPersistence`
3. `TestHBFillAndSizing`
4. `TestHBPositionRestore`
5. `TestHBMarkToMarket`
6. `TestHBExitManager`
7. `TestHBCloseAccounting`
8. `TestHBJournalAndReporting`
9. `TestHBLegacyParity`

Предлагаемый порядок реализации и запуска:
1. Dataclass + persistence + strict validation.
2. Fill adapter + actual-fill sizing + legacy parity.
3. MTM null-safety + H-B manager branch.
4. Close/forced-close provenance + journal export.
5. Report isolation and manifest.
6. Targeted H-B tests.
7. Existing accounting and persistence regression suites.
8. Full offline test suite.
9. CI result inspection and rerun after sanctioned fixes.

Команды ниже — будущий offline test plan, не утверждение, что тесты запускались:
```bash
python -m pytest -q tests/test_h_b_mean_reversion_synthetic.py
python -m pytest -q tests/test_portfolio_accounting.py tests/test_state_persistence.py
python -m pytest -q
```

## 14. Release gates

| Gate | Required evidence | What it does NOT authorize |
|---|---|---|
| G0 — Spec frozen | Review of this contract and implementation plan | No code correctness claim |
| G1 — Synthetic mechanics | All deterministic H-B tests pass | No market edge/PnL claim |
| G2 — Legacy parity | Existing relevant suites pass; no economic regression | No market validation |
| G3 — Offline integration | Full offline suite + CI green; immutable code/test artifacts | No market validation or trading |
| G4 — Market research authorization | Separate explicit user authorization and data protocol | No deployment |
| G5 — Market validation | Frozen preregistration, provenance, independent data/periods, cost/risk analysis | No live/paper trading |
| G6 — Deployment approval | Separate explicit review of exchange/account execution and operational controls | No implicit live permission |

## 15. Known unresolved questions

1. Exact H-B field names/types/defaults in `OpenPositionState` and `TradeRecord` require implementation review.
2. Tolerance for comparing `initial_stop_dist` to `entry - frozen_stop` must be specified in code-level numeric units and must not hide material drift.
3. External consumers of engine journal JSON have not been identified; compatibility remains unknown.
4. Dashboard consumers of nullable TP fields are not evidenced by the inspected standalone Dashboard v15.
5. Isolated liquidation model does not establish account-level/cross-margin liquidation correctness.
6. The current H1 validation manifest is breakout-specific and must not be repurposed as H-B manifest.
7. Test module imports, test framework conventions and CI discovery should be confirmed at implementation time.

## 16. Current evidence statement

This document remains the broader lifecycle design specification derived from read-only source inspection and prior H-B contracts. As of 2026-11-24, a deliberately narrower pure signal predicate has been added separately in `h_b_signal.py`, with 10 deterministic tests in `tests/test_h_b_signal.py` on branch `research/hb-signal-contract` (PR #16). These tests cover only the causal signal predicate through t+1; they do not implement or validate pending/fill lifecycle, sizing, persistence, position management, exits, accounting, reporting or legacy parity.

No trading-engine production path was changed. The exact repository test suite ran as part of Research CI [45463406898](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45463406898) on commit `582ccedf943ed7d4a5a60db0436bbb63d4f5741c`; the H-B step completed with `Ran 10 tests` / `OK`, and the workflow concluded SUCCESS. The first attempt failed before assertions because pytest was unavailable; the tests were converted to standard-library unittest. This is synthetic mechanics evidence only, not market validation or profitability. No market data, exchange APIs, archives, private/account APIs, PnL backtests, parameter sweeps, paper trading or live trading were used.
