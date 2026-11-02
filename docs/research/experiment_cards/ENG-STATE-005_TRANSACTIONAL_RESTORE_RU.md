# ENG-STATE-005 — transactional state restore

Статус: ACCEPT — transactional restore regression и CI прошли.  
Дата: 2026-11-02.  
Тип: state restore atomicity; deterministic tests only.

## Наблюдаемая проблема

`PlanBStatePersistence.load_state()` сначала вызывает `risk_mgr.from_dict()`, а затем восстанавливает позиции и pending orders. Если позднее восстановление позиции/ордера падает, метод выбрасывает RuntimeError (после ENG-STATE-003), но переданный risk manager уже частично изменён данными из backup.

Для вызывающего кода, который повторно использует объект после ошибки, это нарушает fail-closed гарантию: операция восстановления завершилась неуспешно, но часть состояния уже применена.

## Решение

Восстанавливать risk state во временный AdaptiveRiskManager, валидировать весь корневой объект, positions, pending и trade_seq, и только после успешного разбора всех частей переносить risk state в исходный менеджер.

Не менять формат backup и значения стратегии.

## Критерии проверки

1. Валидный backup сохраняет существующий round-trip.
2. Невалидная позиция не меняет исходный risk manager.
3. Невалидный pending payload не меняет исходный risk manager.
4. Невалидный root / trade sequence отклоняется.
5. Все deterministic tests и CI проходят.

## Границы

Это атомарность локального восстановления в памяти. Не заменяет Bybit reconciliation, backup freshness, schema migration или fsync.

## Решение

Решение: ACCEPT для исследовательского движка.

- Исправление: commit `ee191fb37711a2304b5a7a64752f629a7e0566d4`.
- Тесты: commit `481a71484579f700feef53930326bde50a4513d1`.
- CI: [Research engine checks #41433598794](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41433598794), SUCCESS.
- `tests/test_state_persistence.py`: 9/9; malformed positions, pending payload и trade sequence не изменяют исходный risk manager.
- Compile, все configured deterministic suites и secret scan прошли.

ACCEPT означает атомарность локального применения backup в памяти. Не заменяет exchange reconciliation, freshness/schema migration или durability.
