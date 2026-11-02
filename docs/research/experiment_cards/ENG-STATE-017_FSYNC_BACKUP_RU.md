# ENG-STATE-017 — durable atomic backup write

Статус до изменения: CONFIRMED DURABILITY GAP / atomic replace is not a durability barrier.  
Дата: 2026-11-02.  
Тип: local backup durability; deterministic tests only.

## Наблюдаемая проблема

The writer flushes JSON through Python's buffered file object and atomically replaces the target, but does not fsync the temporary file or its parent directory. A successful return therefore does not request persistence of file contents and directory entry across a crash/power loss.

## Решение

- Flush and `os.fsync(file.fileno())` before atomic replace.
- On POSIX, open the parent directory and fsync it after replace so the rename metadata is also requested durable.
- Keep Windows behavior portable: fsync the file, omit directory fsync where POSIX directory descriptors are unavailable.
- Any fsync failure raises through the existing fail-closed save path. If directory fsync fails after replace, the new file may already be visible; caller still stops because durability was not confirmed.

## Критерии проверки

1. Successful save fsyncs file and parent directory on POSIX.
2. File fsync failure preserves previous backup and cleans temporary file.
3. Existing atomic replace failure remains fail-closed.
4. Full deterministic CI passes.

No market backtest required.
