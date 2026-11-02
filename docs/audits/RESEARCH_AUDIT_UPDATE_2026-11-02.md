# Актуализация аудита исследовательской ветки — 2026-11-02

## Область и воспроизводимость

- Репозиторий: `nikitanecilli-bit/bybit-trading-bot`
- Ветка: `research/market-regime-v1-main`
- Проверенный HEAD на момент аудита: `dcb48cf5faf6c94347be938c8f4ed3451348e256`
- Проверенный workflow: `.github/workflows/research-checks.yml`
- Workflow run: [41470373006](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41470373006)
- Run head SHA: `01bd6409bc3b2712db889aa94b234fb95448256e` (PR merge/test ref); PR head SHA: `dcb48cf5faf6c94347be938c8f4ed3451348e256`
- Итог job `tests`: `success`; все 26 основных шагов после setup завершились успешно.
- Artifacts: отсутствуют. Это технический regression workflow, не рыночный backtest.

## Что подтверждено текущим CI

Успешно выполнены:
1. py_compile движка, research helpers и тестов;
2. Bybit instrument specs / Decimal rounding;
3. dated instrument snapshot collector;
4. as-of instrument spec history;
5. exchange-valid quantity sizing;
6. cumulative funding accounting;
7. realized funding PnL;
8. funding mark-to-market;
9. funding/mark coverage preflight;
10. Bybit private API signature/read-only checks;
11. V5 reconciliation parser;
12. fail-closed read-only snapshot collector;
13. fail-closed report-only comparator;
14. secret scan;
15. causal regime classifier;
16. trend/breakout filters;
17. regime analysis helpers;
18. frozen regime gate;
19. gap execution;
20. time model;
21. configured candle timeframe validation;
22. portfolio accounting/risk budget;
23. fail-closed state persistence.

Workflow не запускает исследовательские рыночные backtests: это разделено намеренно. Успешный CI не означает прибыльность стратегии, реальное качество исполнения или успешный запрос к аккаунту.

## Проверка read-only Bybit reconciliation

### Подтверждено кодом

- `scripts/bybit_reconciliation_snapshot.py` использует только GET-запросы к:
  - `/v5/user/query-api`;
  - `/v5/market/time`;
  - `/v5/position/list`;
  - `/v5/order/realtime`;
  - `/v5/order/history`;
  - `/v5/execution/list`.
- До чтения состояния аккаунта требуется совпадение API-key identity и явный `readOnly == 1`.
- Разрешён только HTTPS и allowlist официальных Bybit API hostnames; redirect запрещён.
- Запросы ограничены `category=linear` и `settleCoin=USDT`.
- История executions разбивается на окна максимум 7 дней; страницы проверяются на целостность cursor chain.
- Снимок сохраняет исходные страницы и SHA-256 digest.
- Парсер отклоняет неполные страницы, дубли идентификаторов/неоднозначные записи и невалидные retCode.
- Comparator работает report-only и fail-closed; он не выдаёт разрешение на возобновление торговли.

### Важные ограничения, явно отражённые в реализации

- Снимок имеет статус `CAPTURED_READ_ONLY_NOT_RECONCILED`, а не reconciliation pass.
- Bybit order history не является полным event journal для произвольного outage window: отменённые/отклонённые/деактивированные заявки доступны ограниченное время; старше 7 дней доступны только заявки с fills.
- Наличие текущей позиции или stopLoss в exchange snapshot само по себе не доказывает полную историю ордеров/исполнений.
- Comparator намеренно блокирует live resume при отсутствии локальной модели с точной биржевой quantity/order/execution identity.
- Реальный API-снимок в рамках этого аудита не получен. Mocked tests не подтверждают доступность аккаунта, валидность ключа или IP allowlist.

## Исправления статусов в прежней документации

В старых разделах `docs/audits/ENGINE_AUDIT_FINDINGS_RU.md` и `docs/research/TEST_COVERAGE_MATRIX_RU.md` есть исторические статусы, которые нельзя читать как текущие:

- Timeframe mismatch: ранее P1; regression `test_timeframe_validation.py` теперь включён в текущий workflow и прошёл.
- Portfolio accounting / simultaneous-entry order dependence: позднее покрыто тестом с детерминированной политикой распределения общего risk budget; актуальная матрица содержит статус FIXED / TESTED. Старые формулировки «не доказано» относятся к состоянию до соответствующего исправления.
- Текущий workflow run 41470373006 подтверждает выполнение этих тестов.
- Это не снимает риски exchange margin/liquidation, funding input quality, real fills и cross-symbol event sequencing за пределами тестовых fixtures.

## Остаточные риски по финансовой модели

| Область | Текущий статус | Почему не закрыто |
|---|---|---|
| Exchange quantity/tick integration в engine | PARTIAL | Decimal sizing helper и тесты есть, но активный v14 execution path не использует его как источник фактической exchange quantity |
| Initial/maintenance margin и liquidation | NOT MODELED | Нет полноценной модели risk tiers, cross/isolated collateral, liquidation price и liquidation fee |
| Funding | PROXY / OPTIONAL | Интеграция существует, но отключена без funding/mark inputs; mark series proxy не эквивалентна точному settlement mark |
| Maker execution | OHLC PROXY | Нет bid/ask, queue priority, partial fills, latency, cancellation и adverse selection |
| Exchange fees | MODELED CONSTANTS | Не подтверждены реальным тарифом аккаунта и фактической maker/taker классификацией каждого fill |
| Bybit reconciliation | IMPLEMENTED / NOT RUN AGAINST ACCOUNT | Read-only workflow требует пользовательские GitHub Secrets и реальный запуск; этот аудит их не запрашивал |
| Historical order journal completeness | LIMITED BY EXCHANGE API | Endpoint history не покрывает произвольный outage window без ограничений |

## Рыночные результаты: запрет на переобучение

Существующие H1 отчёты остаются отрицательным/неподтверждающим свидетельством:

- Двухпериодный экран: 25 непрерывных символов; 9/25 net-positive в screening и 6/25 в forward; сумма независимых тестов forward `-14,789.82 USDT`.
- Это суммы независимых per-symbol симуляций, не общий shared-capital portfolio PnL.
- US-session exclusion улучшает forward baseline, но оставляет `-5,341.50 USDT` в exit-attribution run; alignment + US exclusion оставляет `-2,819.98 USDT`.
- Ни один из этих фильтров не является подтверждённой стратегией; исследованные окна уже использовались для диагностики и не могут считаться untouched holdout.
- Нельзя выбирать top-5 по этим же forward данным и объявлять их устойчивыми.

## Следующие безопасные шаги

1. Сверить все отчёты E01–E09 с первичными workflow run IDs, commit SHA, конфигами, датасетами и artifact hashes.
2. Проверить, что historical datasets и universe point-in-time корректны, включая делистинги и survivorship bias.
3. Подготовить end-to-end deterministic fixtures для нескольких одновременно открытых позиций, partial TP, funding settlement, gap stop и equity reconciliation.
4. Спроектировать exchange-aware position model только после фиксации Bybit instrument snapshots и источников funding/mark data.
5. Не запускать новые оптимизационные переборы на уже просмотренных окнах. Следующий рыночный тест должен иметь заранее зафиксированную гипотезу и новый untouched период.

## Решение

Технический CI текущей исследовательской ветки зелёный. Это означает, что детерминированные проверки прошли, но финансовая модель ещё не exchange-complete. Read-only reconciliation pipeline реализован fail-closed, однако реальная сверка аккаунта не выполнена. Никакая стратегия или фильтр не одобрены для live торговли.
