# План аудита и исследований (без новых рыночных тестов)

## Фаза 0 — организация
- [x] Создать единый вход `docs/README_RU.md`.
- [x] Создать `AGENTS.md` с правилами работы.
- [x] Создать первичную матрицу покрытия и аудит-реестр.
- [ ] Проверить ссылки, workflow path dependencies и secret hygiene.

## Фаза 1 — воспроизводимость экспериментов
1. Собрать для E01–E09: run ID, workflow, commit SHA, dataset, конфиг, folds, costs, artifacts.
2. Сопоставить run SHA с версиями скрипта и движка.
3. Проверить завершение каждого job, ошибки, тестовые counts, artifact contents.
4. Пометить старые результаты без первичных данных как UNVERIFIED.
5. Выявить дублирующие эксперименты и причинно зависимые результаты.

## Фаза 2 — аудит движка
Проверять в таком порядке:
1. Candle/time model и отсутствие look-ahead.
2. Сигналы, warm-up, индикаторы и контекст.
3. Pending orders и fills.
4. Stops, targets, trailing, break-even и intra-bar collision.
5. Fees/slippage/funding.
6. Sizing, leverage, margin и liquidation.
7. Portfolio shared capital, risk gates, concurrency.
8. Trade journal и метрики.

Для каждого дефекта: severity, file/function, минимальный reproduction, влияние на результаты, regression test. Не менять поведение без теста и записи.

## Фаза 3 — качество данных
- Инвентаризировать все ZIP и внутренние CSV: symbols, timeframe, date range, row count, duplicate/missing candles.
- Определить источник данных и стабильность формата.
- Проверить Bybit vs Binance proxy; не заявлять Bybit holdout при HTTP 403.
- Проверить universe survivorship и исключённые инструменты.

## Фаза 4 — исследовательские выводы
- Пересчитать только то, что нужно для проверки целостности существующих результатов; новые сетки параметров запрещены до закрытия аудита.
- Отдельно оценить устойчивость по fold и symbol, concentration, drawdown, trade count.
- Не подгонять стратегию по holdout.
- Вернуться к market-regime / false-breakout / maker execution только после устранения критических методологических рисков.

## Критерий завершения аудита
Аудит завершён, когда у каждого исторического эксперимента есть воспроизводимая ссылка на commit/run/artifact либо явная метка UNVERIFIED; ключевые торговые механики движка покрыты проверками; критические ограничения исполнения и данных документированы; следующий тест отвечает на новый вопрос и не дублирует предыдущий.
