# ENG-STATE-017 — durable atomic backup write

Статус: ACCEPT — fsync durability regression и CI прошли.  
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

Решение: ACCEPT для повышения локальной crash-durability.

- Engine commit: `3f2df9b78b9149e9f820dfc8d67140dbff7ba866`.
- Test commit: `dd808b3cb83e1308a26490f16582d26498fe0709`.
- CI: [Research engine checks #41447862710](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41447569454), SUCCESS.
- `tests/test_state_persistence.py`: 54/54; verifies file + parent-directory fsync on POSIX, and previous backup preservation when file fsync fails.
- Compile, configured deterministic suites and secret scan passed.

No market backtest, parameter sweep, production deployment or live order.

Boundary: fsync requests OS/filesystem durability but cannot guarantee survival against every storage controller, filesystem, virtualization layer or hardware failure. Directory fsync is performed on POSIX; Windows uses file fsync only.
