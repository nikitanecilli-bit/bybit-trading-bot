# ENG-EXEC-015 — legacy TP1 maker-fee fallback consistency between MTM and close

Статус: ACCEPT — test-first regression reproduced the mismatch; fix passed full Research CI.  
Дата: 2026-11-03.  
Тип: deterministic execution-cost/accounting regression; не рыночный эксперимент.

## Наблюдаемый дефект

В _close_position() maker_exits разрешался с fallback:
- если pos.maker_exits is None, использовать pos.order_type == "limit";
- иначе использовать явное pos.maker_exits.

В _unrealized_pnl_at_marks() TP1 fee/slippage рассчитывались напрямую от truthiness pos.maker_exits. Для старой или восстановленной limit-позиции с maker_exits=None это означало:
- final close accounting: TP1 трактуется как maker;
- mark-to-market: TP1 трактуется как taker.

Из-за этого unrealized equity было ниже согласованного close accounting на TP1 notional × (taker fee + taker slippage − maker fee). Это могло раньше времени вызвать daily stop/kill-switch и нарушало согласованность бухгалтерии. Для текущего H1 validation preset maker_tp1_and_target=False; этот конкретный fallback там не используется. Дефект относился к legacy/restored positions и другим конфигурациям с None.

## Test-first доказательство

- Добавлен regression test_legacy_limit_position_mtm_uses_same_tp1_fee_fallback_as_close.
- CI до исправления: [#41705641423](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41705641423) — FAILED именно на новой регрессии; остальные уже завершившиеся шаги не показали дополнительных failures.
- Fixture: limit entry, TP1 already hit, maker_exits=None. Ожидаемая модель использует maker fee на entry/TP1 и taker fee+slippage на оставшуюся потенциальную exit leg. Старый MTM начислял taker fee+slippage также на TP1.

## Исправление

В _unrealized_pnl_at_marks() добавлено то же разрешение maker_exits, что и в _close_position():
- None → fallback по order_type;
- явный True/False → сохраняет заданную политику.

Никакие сигналы, стопы, цели, размер позиции, комиссии-константы или execution mode не менялись.

## Проверка

- Engine fix commit: f6a3910024cd84543c22998a0b28885ba9ff094b.
- Regression test commit: c5e566a60855419d6597a694fbe2ae682322a56a.
- Full Research CI: [#41705849389](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41705849389) — SUCCESS.
- Additional boundary coverage: `test_legacy_limit_position_uses_maker_tp1_fee_fallback_in_mtm` verifies the legacy `None → order_type` maker fallback numerically; `test_explicit_taker_tp1_override_is_preserved_in_mtm` verifies explicit `False` is not overridden. Test commit `6d00db961c510c3e2bca3e93f459947d83e3a332`; [CI #41707011122](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41707011122) SUCCESS, 50/50 steps; `test_funding_mark_to_market.py` passed 8/8.
- Portfolio accounting suite passed, including the legacy-limit TP1 regression.

## Ограничения и решение

- ACCEPT для внутренней согласованности MTM/close accounting.
- Это не PnL strategy experiment и не измеряет влияние на historical strategy returns.
- Это не устраняет ограничения OHLC maker-fill proxy, отсутствия L2 queue/partial-fill/adverse-selection, fixed fee/slippage assumptions и отсутствия реальных Bybit archives.
- Никаких market PnL runs, API account calls или live orders не выполнялось.
