# ENG-EXEC-034 — Strict CSV quoting for public trade archives

Дата: 2026-11-04

## Воспроизводимый дефект

Python `csv.DictReader` по умолчанию использует `strict=False`. Проверка на синтетическом CSV показала, что незакрытая кавычка в последнем optional flag поле могла быть принята как обычное строковое значение (например, `"false\n`) и пройти boolean parsing после trimming. Такой malformed CSV row не обязан приводить к ошибке ширины/обязательных полей.

## Исправление

- Основной `iter_public_trades()` использует `csv.DictReader(stream, strict=True)`.
- Trade inspector выделил `validated_trade_csv_reader()`, который использует strict mode и сохраняет прежние header/row-width checks.
- Добавлены регрессии для незакрытой кавычки в optional RPI поле в обоих parser paths.
- Синтетическая проверка Python CSV parser подтверждает: strict mode поднимает `csv.Error: unexpected end of data` для этих fixtures.

## Коммиты

- Trade inspector: `d78720991bf6a72efa05310b878505dcd5bf1123`.
- Core replay parser: `81f58d0b48705ed1e5f2db36ba80ca42c0feb50a`.
- Core regression: `13f32dbc2db3e686549866a14998a0c31cf659a6`, fixture newline correction `5f6c245de6bbd82cd280d4db750b8e3d1434c867`.
- Inspector regression: `06544878931c0daa1117980c63eb01885c8e338e`, fixture newline correction `9302114d0199097d834fecf112f2c6d74ec931d7`.

## Проверка и gates

- Синтетический stdlib parser reproduction выполнен локально в изолированной проверке; это не заменяет CI.
- Combined commit status для последнего test commit пуст; полный Research CI не подтверждён.
- Не загружались market archives; network inspector workflow не запускался.
- Нет collectors, market PnL/backtests, private API, runner, paper/live orders. Maker execution gate закрыт; `main` не менялся, PR #4 не сливался.
