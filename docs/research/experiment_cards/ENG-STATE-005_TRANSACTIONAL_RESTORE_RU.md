# ENG-STATE-005 — transactional state restore

Статус до изменения: CONFIRMED SAFETY DEFECT / risk manager mutates before full backup validation.  
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

OPEN до regression tests и CI. Рыночные backtests не нужны.
