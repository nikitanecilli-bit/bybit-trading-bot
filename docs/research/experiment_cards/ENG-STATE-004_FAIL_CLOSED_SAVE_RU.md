# ENG-STATE-004 — fail-closed state save при ошибке записи

Статус до изменения: CONFIRMED SAFETY DEFECT / write exception is logged and swallowed.  
Дата: 2026-11-02.  
Тип: state persistence integrity; deterministic tests only.

## Наблюдаемая проблема

`PlanBStatePersistence.save_state()` при `enabled=True` пишет временный JSON и делает `os.replace()`, но при любой ошибке только логирует её и продолжает выполнение. Вызывающий торговый цикл не получает сигнал, что резервная копия не обновилась.

При последующем аварийном завершении восстановление может использовать старый backup и не отражать последние открытые позиции/pending orders.

## Предварительное решение

- При `enabled=False` сохранить no-op.
- При `enabled=True` ошибка сериализации/записи/атомарной замены должна выбрасывать явный `RuntimeError`; не маскировать неуспешное сохранение.
- Удалять только временный файл, созданный текущей неудачной попыткой (best effort).
- Не менять payload/schema и торговые параметры.

## Критерии проверки

1. Disabled persistence — no-op.
2. Успешный save создаёт валидный JSON.
3. Ошибка atomic replace поднимает RuntimeError.
4. При ошибке не остаётся временного файла.
5. Existing persistence, engine and CI tests pass.

## Границы

Это заставляет вызывающий код увидеть неудачную запись, но не гарантирует durability при отключении питания: fsync каталога/файла и remote backup отдельно не реализованы. Также не заменяет Bybit reconciliation.

## Решение

OPEN до regression tests и CI. Рыночные backtests не нужны.
