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


## Обновление 2026-11-02 — автономный аудит

Завершено:
- Timeframe CSV validation исправлена и regression-tested.
- Portfolio MTM, TP1 partial mark, risk sizing budget и close PnL/fee/slippage reconciliation покрыты deterministic tests.
- Подтверждённая зависимость одновременного распределения риска от порядка symbols исправлена пакетным распределением: equal risk share among eligible signals; slot priority = vol_ratio descending, symbol tie-break.
- Технический CI отделён от рыночных backtests; market experiment workflows переведены на ручной запуск.
- Static scan не нашёл live order endpoints в Python engine copies и active research scripts.

Следующие задачи (без новых market backtests):
1. Полный audit lifecycle: pending-order expiry/retry, stop/TP collision, trailing-stop update timing, same-bar fills.
2. Margin/leverage/liquidation approximation and exchange quantity/tick constraints.
3. Funding integration review and timestamp semantics.
4. Проверка journal metrics: net R denominator, MAE/MFE, drawdown and per-period aggregation.
5. Reconcile E01–E09: run SHA, script SHA, config, data manifest, folds, costs, artifacts. Missing evidence => UNVERIFIED.
6. Check archive/CSV integrity and data provenance.
7. Только после закрытия этих пунктов — решить, какие исторические результаты нужно воспроизвести на исправленном engine. Не начинать parameter search.

Последний подтверждённый технический CI: [41356881313](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41356881313), commit `3246eb1df4b9d4cfbd109fa6e6a6316e44710200` — success.


## Обновление 2026-11-02 — lifecycle review

Завершён первичный статический просмотр `step_candle` / `_try_fill_pending` / `_manage_position`:
- Pending сигнал живёт одну следующую свечу; no-touch, chase reject и risk reject удаляют его без retry.
- Limit touch fill не моделирует очередь, спред, partial fill или adverse selection.
- Stop имеет приоритет над TP при неоднозначном OHLC same-bar событии.
- Fill-bar stop может учитывать экстремум, который был до фактического входа; favourable excursion на fill bar исключён.
- Trailing stop, рассчитанный по текущей свече, применяется только к последующим свечам.

Следующий безопасный порядок:
1. Добавить тесты, фиксирующие фактические one-bar pending semantics и fill-bar/trailing timing (без изменения поведения).
2. Проверить, одинаково ли runners интерпретируют лимитную заявку и TTL; расхождения описать, не исправляя молча.
3. Продолжить аудит TP/stop/trailing и portfolio event ordering; отдельно проверить long/short симметрию.
4. Затем margin/leverage/quantity-tick и funding timestamp semantics.
5. Только после завершения аудита — воспроизводимость E01–E09 и data archive integrity. Новые market backtests и parameter search пока запрещены.


## 2026-11-02 — exchange realism gate before profitability claims

Static review confirms that v14 sizing is a notional approximation, not a Bybit margin/contract execution model:
- no quantity conversion to `qtyStep` / `minOrderQty` / `minNotionalValue`;
- no price tick rounding;
- no initial/maintenance margin, risk tiers or liquidation;
- historical funding files can be downloaded, but funding cashflows are not charged;
- mark/index/premium datasets can be downloaded, but mark-price liquidation and basis effects are not modeled.

Do not treat old H1 PnL as exchange-executable net performance until these are implemented. **Completed as isolated groundwork:** `bybit_instrument_specs.py` parses Decimal tick/lot/min-notional constraints (including separate max market/limit quantity caps); `instrument_spec_history.py` selects the latest complete snapshot at or before a backtest timestamp and fails closed on future/stale/missing specs. Tests cover rounding, boundaries and as-of selection. Neither is yet wired into v14; no historical snapshots have been confirmed in the archive. Next: verify CI, add date-versioned instrument-spec collection, then funding cashflow accounting; margin/liquidation follows once the spec/data schema is stable.


## Completed groundwork — dated specs and pure funding accounting

- `scripts/snapshot_bybit_instruments.py` archives raw Bybit V5 instrument-info responses with UTC timestamped filenames and pagination/duplicate guards; a dedicated Actions workflow is configured to populate `data/instrument_specs/linear/`.
- `funding_accounting.py` provides a single cumulative as-of calculation with timestamp-aligned hourly mark-candle-open proxies (not guaranteed to equal the exchange settlement mark) and conservative TP1 boundary semantics; offline tests cover long/short sign, settlement inclusivity, missing marks, duplicates and partial TP1.
- The instrument collector is not yet confirmed to have produced its first artifact. Funding helper is now wired into v14 mark-to-market and final close; do not claim exchange-realistic PnL until CI passes and funding/mark data coverage is validated for every symbol and settlement.

## Funding integration — first isolated pass implemented

В активной ветке добавлен `funding_accounting.py` и подключён к v14 через один cumulative as-of helper:
- `_unrealized_pnl_at_marks(as_of_ts)` вычитает accrued funding с открытых позиций до проверки daily stop / kill-switch;
- `_close_position()` использует тот же helper на `exit_ts` и вычитает funding из realized net PnL;
- `TradeRecord.funding_cost_usdt` и summary `total_costs`/`funding_cost_usdt` сохраняют раздельную видимость funding;
- `OpenPositionState.tp1_ts_ms` фиксирует консервативную границу закрытия TP1; settlement на этой границе относится к полному исходному notional, более поздние settlements — к оставшемуся объёму;
- CLI принимает `--funding-dir` и `--mark-price-dir`; оба аргумента обязательны парой, missing CSV/timestamp-aligned mark-candle proxy завершаются ошибкой, а не молча исключаются.

Добавлены тесты pure helper, realized close, mark-to-market risk и mark-price loader. Это первый интеграционный этап; перед любыми PnL-выводами требуется фактический CI run и отдельная проверка funding coverage/mark timestamp alignment для каждого инструмента. Funding не добавляет mark-price OHLC intrabar liquidation model. Добавлен preflight `scripts/validate_funding_coverage.py`, который проверяет для каждого символа наличие funding/mark CSV, уникальность timestamp и полное совпадение funding settlements с timestamp mark-candle open. Запуск перед funding-adjusted backtest: `python scripts/validate_funding_coverage.py --funding-dir data/funding --mark-dir data/mark_price --symbols BTCUSDT,ETHUSDT,...`. Если coverage неполный, скрипт завершается с ошибкой; не запускать PnL-анализ на неполном архиве.


## v15 execution-ablation coverage

Multi-bar pending logic в `research_v15/backtest.py` при статической проверке сохраняет заявку, если лимитка не исполнилась; предыдущая гипотеза об unconditional deletion отозвана. Добавить end-to-end тест `backtest_symbol()` с лимиткой, не затронутой на первой допустимой свече, но исполненной на второй, и тест expiry после N валидных свечей. Это пробел тестового покрытия, не подтверждённый дефект. Не менять реализацию без failing test.


## Operational caveats — branch and snapshot automation

- `research/market-regime-v1-main` is currently diverged from `main`: 3 commits behind and more than 200 research commits ahead. Do not merge/rebase automatically; first review the three incoming main commits and branch-wide workflow changes.
- The snapshot workflow has push/manual triggers on the research branch. Its daily cron is only activated by GitHub after the workflow file is present on the repository's default branch; until then, the daily schedule is dormant. The first committed snapshot is not yet verified.
- GitHub connector status lookup returned no check statuses for recent push commits; this is **unverified**, not a passing CI result.
