# ENG-STATE-004 — fail-closed state save при ошибке записи

Статус: ACCEPT — write-failure regression и CI прошли.  
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

Решение: ACCEPT для исследовательского движка.

- Исправление: commit `ac43d4aa23d2e797eae99d57e6c65c714642e120`.
- Тесты: commit `0b142dcf5393683844e8e73b7d3f2096525a7722`.
- CI: [Research engine checks #41432914403](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41432914403), SUCCESS.
- `tests/test_state_persistence.py`: 6/6; ошибка `os.replace` вызывает RuntimeError, временный файл очищается; disabled persistence остаётся no-op.
- Compile, все configured deterministic tests и secret scan прошли.

ACCEPT означает, что при включённом persistence ошибка записи больше не маскируется. Это не гарантия fsync/durability при отключении питания и не exchange reconciliation.
