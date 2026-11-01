# Технический аудит проекта — рабочий документ

Дата начала: 2026-11-02  
Ветка: `research/market-regime-v1-main`  
Базовый HEAD при инвентаризации: `9271b0e4eac3d05db700f09cced255e25eb8f776`  
Текущий HEAD после организации документации: `2fae0948bab853f0161b7c983d35927ab2d13d29`

## 1. Инвентаризация
В репозитории 7 веток: `main`, `Audit`, `research/bybit-funding-data-v1`, `research/data-adapter-v1`, `research/market-regime-v1-main`, `research/market-regime-v1`, `research/v15-donchian-signal`.

В текущей ветке есть один основной v14 research engine, downloader, research scripts, workflows, root-level tests, отчёты и архивы cryptofetch. Физическое перемещение файлов отложено до проверки imports/workflow paths.

## 2. Проверки CI, которые удалось подтвердить
Run `41355263006` на commit `9271b0e4eac3d05db700f09cced255e25eb8f776` завершился success. Лог job подтверждает:
- py_compile прошёл;
- secret scanner сообщил: no obvious secret patterns found (это эвристика, не гарантия);
- 18/18 gap execution tests прошли;
- 37/37 time model tests прошли;
- завершились также несколько backtest/walk-forward/regime steps и выгрузка артефактов.

Отдельно E09 run `41355171678` на commit `a11606b2e37c750b3b39ab6fb7201916a554efac`: factorial завершён, pytest gap suite выполнен, три CSV выгружены. Этот run не соответствует текущему HEAD, но commit SHA фиксирует версию кода для исторического результата.

## 3. Подтверждённые выводы по движку
Подробности и ссылки на строки — в [ENGINE_AUDIT_FINDINGS_RU.md](ENGINE_AUDIT_FINDINGS_RU.md).
- Сигнал рассчитывает Donchian/ATR на предыдущих свечах; текущая свеча подтверждает breakout/volume; вход переносится на следующую свечу.
- Stop имеет приоритет над TP, если оба уровня попали в одну OHLC-свечу.
- Лимитный fill по касанию high/low не моделирует очередь, спред, частичные исполнения, latency и adverse selection.
- **P1:** CSV interval не сверяется с `cfg.timeframe`, хотя временные границы движка вычисляются из конфига. Это может неверно трактовать все свечные времена и длительности.
- Session/hour/weekday фильтры применяются к open timestamp сигнальной свечи, хотя сигнал известен на close; семантику требуется закрепить.
- **Подтверждён P1:** распределение портфельного риск-бюджета между одновременными сигналами зависит от порядка symbols. Тест `test_simultaneous_entry_selection_is_order_dependent_under_binding_risk_cap` воспроизводит разные наборы открытых инструментов при перестановке списка. CI 41356762102 passed; см. `ENGINE_AUDIT_FINDINGS_RU.md`.

## 4. Методологические ограничения
- Binance OHLCV proxy не доказывает качество Bybit исполнения; запрос Bybit data ранее вернул HTTP 403.
- Funding не моделировался в ряде прогонов.
- Maker fills optimistic OHLC touch.
- Selection/multiple testing: E07/E08/E09 выбраны на пяти инструментах и имеют зависимые итерации; результаты не являются независимыми подтверждениями.
- Технические проверки отделены от рыночных экспериментов: `research-checks.yml` запускает только compile, secret scan и deterministic tests; рыночные workflow переведены на `workflow_dispatch`.

## 5. Статус
- [x] Инвентаризация веток и дерева текущей ветки.
- [x] Добавлена структура документации и AGENTS.md.
- [x] Проверены логи основного CI run и E09 workflow metadata.
- [x] Первичный просмотр trade lifecycle и ключевых функций движка.
- [ ] Сверить E01–E09 commit/run/artifact в полном объёме.
- [ ] Аудит всех scripts/workflows на повторные прогоны, look-ahead и временные границы.
- [ ] Проверить все ветки на live order endpoints и расхождение engine versions.
- [ ] Добавить regression tests для timeframe mismatch и symbol order invariance (после подтверждения спецификации).
- [ ] Независимая арифметическая сверка PnL/equity/risk.
- [ ] Проверка архивов данных и checksum.
- [ ] Финальный перечень P0/P1/P2 и разрешение на следующий этап.

Новые рыночные эксперименты не запускать до завершения аудита. Разрешены проверки кода, воспроизводимости и корректности расчётов.

## Обновление аудита 2026-11-02

- P1 timeframe mismatch исправлен и покрыт regression tests; CI run 41356694461 passed.
- Добавлен `test_portfolio_accounting.py`: MTM equity identity, TP1 partial mark, risk budget, long/short PnL signs, closed trade fee/slippage/net PnL reconciliation. CI run 41356694461 passed.
- Изменение CI: исследовательские рыночные workflow теперь ручные; технический CI запускается при изменениях движка и тестов, не выполняя рыночные backtests.
- Остаточный риск: последовательное распределение ограниченного портфельного бюджета между одновременными сигналами может зависеть от порядка symbols. Не меняли без согласованной спецификации; нужно сначала формализовать приоритет или pro-rata allocation.
- Проверки реального funding, Bybit fill quality, liquidation/margin tiers, full symbol permutation and full portfolio event reconciliation остаются открытыми.

- CI run [41356762102](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41356762102) passed after adding a regression test that confirms the P1 symbol-order allocation defect. No behavior change has been made pending a documented batch-allocation policy.
