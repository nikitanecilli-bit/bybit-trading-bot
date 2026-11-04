> **Актуализация 2026-11-03:** все записи, net-PnL которых рассчитан через v14 `_close_position()` до исправления exit fee/slippage по execution notional, считаются provisional до повторного прогона. Это не автоматически распространяется на эксперименты с другими engine versions: для каждого E-ID сначала сверить provenance/commit. Gross signal results и raw artifacts сохраняются как исторические. Подробности: `docs/audits/EXCHANGE_SIZING_INTEGRATION_AND_BYBIT_SCHEMA_2026-11-03.md`.

# Журнал экспериментов по торговой стратегии (2026-10-28)

Назначение: фиксировать результаты так, чтобы сравнения были воспроизводимыми и не смешивали разные версии движка, universe, периоды и модели исполнения.

## Правила чтения

- Успешный GitHub Actions run означает, что workflow завершился, а не то, что стратегия прибыльна.
- PnL ниже — результаты конкретных исследовательских прогонов. Если явно не указано иное, это **не единый портфель с общим капиталом**.
- Отдельно помечать наблюдаемую доходность и качество модели исполнения. OHLC-моделирование лимитных ордеров не доказывает, что такие исполнения были бы доступны в реальном стакане.
- Для сравнения стратегий сохранять commit SHA, датасет и его хэш, universe, точные границы fold, комиссии/funding/slippage, правила входа/выхода и артефакты. Исторический результат без этих метаданных считается предварительным.
- Bybit holdout на текущем этапе не подтверждён: отдельная проверка свежих данных получила HTTP 403; часть исследований использует Binance OHLCV как прокси.

## Сводка результатов

| ID | Эксперимент / run | Дизайн | Результат | Статус / ограничения |
|---|---|---|---|---|
| E01 | H1 Direction and Execution Ablation — [run 40578394090](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578394090) | H1, 50 символов, 3 хронологических fold, символы тестировались независимо | Long+short market: 2,699 сделок, −16,911.93 USDT; long-only market: 1,458 сделок, +1,056.65; long+short limit 20 bps: 2,395 сделок, −261.36; long-only limit 20 bps: 1,308 сделок, +9,823.41 | Предварительно. Не общий портфель; лимитное исполнение смоделировано и может быть оптимистичным. |
| E02 | Execution Policy Walk Forward — [run 40578394009](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578394009) | 15m и 1h; walk-forward; выбранная политика против market | 15m: −11,470.98 против −24,039.44; 1h: −5,999.65 против −16,911.93. Для H1 прибыльны 71 из 150 комбинаций инструмент-fold; медианный PF 0.92 | Выбранная политика улучшает результат относительно market, но агрегат остаётся отрицательным. |
| E03 | Execution Cost Ablation — [run 40578393971](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578393971) | 50 независимых символов, H1; разные лимитные отступы и сроки ожидания | Market: −5,923.64; limit 5 bps / 3 бара: +457.46; 10 bps / 3 бара: +1,204.81; 10 bps / 5 баров: +1,565.78; 20 bps / 3 бара: +3,143.13. Для 15m все проверенные варианты отрицательны; market baseline −12,562.42 | Высокий риск оптимистичной модели лимитных исполнений; требует fill-stress и портфельной проверки. |
| E04 | H1 Max-Chase Threshold Ablation — [run 40588753444](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40588753444) | 5 отобранных символов, 50 символов рыночного контекста, 3 хронологических fold | Chase 1.5%: +3,799.40; 2.0%: +4,030.24; 2.5%: +4,899.37; 3.0%: +3,400.55; практически без ограничения: +1,428.39 USDT | Самый многообещающий локальный результат — 2.0–2.5%, но выборка всего 5 отобранных символов; fold 3 даёт большую долю результата. Binance OHLCV proxy, моделируемые издержки/исполнение. Не доказательство преимущества. |
| E05 | Bybit fresh-data validation — [run 40541270994](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40541270994) | Проверка возможности получить свежие данные Bybit для holdout | HTTP 403 на запросах; подтверждённый holdout не получен | Блокирующее ограничение валидации. Не интерпретировать отсутствие holdout как положительный или отрицательный результат стратегии. |
| E06 | H1 Signal/Market Context Diagnostics — [run 40587243295](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40587243295) | Диагностика сигналов, причин пропуска сделок и рыночного контекста; синхронизация дат fold исправлялась в ходе разработки | Артефакты диагностики опубликованы; отдельный независимый PnL-эффект контекстных фильтров пока не доказан | Диагностика — не подтверждение прибыльности фильтра. |
| E07 | Shared-capital portfolio validation — [run 40566687595](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40566687595) | 5 основных символов: RAYUSDT, PUMPUSDT, TAOUSDT, AAVEUSDT, CAKEUSDT; 3 хронологических fold; общий портфель; 36 комбинаций фильтров × 3 множителя издержек = 108 прогонов | Пример одной конфигурации `vol>=1.6, breakoutATR>=0.25, cost×1.5`: fold 1 +984.67 USDT (44 сделки, PF 1.56, DD 6.37%); fold 2 +262.97 (42 сделки, PF 1.12, DD 9.45%); fold 3 +2,699.68 (49 сделок, PF 2.14, DD 9.20%). Сумма по fold +3,947.32 USDT, 135 сделок | Не считать независимым подтверждением: исследовалось много комбинаций, поэтому выбор конфигурации подвержен multiple-testing/selection bias; fold 3 даёт около 68% суммы. Binance OHLCV proxy, моделируемые издержки; касание лимита трактуется как исполнение без очереди/спреда/частичных fill. Не Bybit execution. |
| E08 | H1 chase-gate decoupling | Workflow добавлен в commit [794f5da](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/794f5da6c30569339fa434c73b6bb90adc6651bf) | На момент составления журнала отдельный завершённый диагностический run не подтверждён | Не путать успешную компиляцию/CI с результатом самого эксперимента. |

## Рабочие выводы (не финальные)

1. Market-entry baseline на широких H1/15m проверках отрицателен.
2. Направление сделки и исполнение сильно меняют результаты. Long-only и limit-варианты выглядят лучше, но ещё не прошли достаточную проверку реалистичности исполнения и общего капитала.
3. Ограничение chase около 2–2.5% выглядит перспективно в текущей маленькой выборке; нельзя закреплять параметр до проверки на более широком universe и независимом holdout.
4. Отдельный эффект market-context фильтров пока не изолирован надёжно.
5. Пока не получены свежие данные Bybit для holdout, вывод о реальном преимуществе остаётся неподтверждённым.

## Обязательные поля для новых запусков

- Run URL, дата/время UTC и локальное время
- commit SHA и ветка
- версия/хэш движка и исследовательского скрипта
- источник данных, период, таймфрейм, дата выгрузки и хэш датасета
- universe целиком, а также правило его отбора (чтобы исключить survivorship bias)
- train/validation/test и точные даты каждого fold
- сигнал, направление, вход/выход, stop/target, max-chase и другие параметры
- maker/taker fees, funding, spread/slippage и модель лимитного fill
- количество сделок, net PnL, expectancy, profit factor, max drawdown, turnover, доля прибыльных символов и fold
- портфельный результат с общим капиталом, лимитами риска и одновременными позициями
- ссылка на сырые CSV/логи и явные ограничения результата

## Следующий порядок работ

1. Проверить отдельный H1 chase-gate decoupling workflow и сохранить артефакты.
2. Зафиксировать один universe и три хронологических периода; сравнивать фильтры по одному изменению за раз.
3. Повторить проверку на полном universe, включая убыточные и исключённые инструменты, а не только пять заранее отобранных монет.
4. Зафиксировать выбранную конфигурацию до теста и не подбирать её по holdout; использовать независимый holdout после завершения разработки.
5. Только после подтверждения данных и реалистичности исполнения оценивать переход к paper trading. Реальные ордера этим журналом не запускаются.


### E08 — H1 candle-body / max-chase diagnostic (завершён)

- Workflow run: [40650477230](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40650477230)
- Commit исходного запуска: 17c31df587e802da7c74d3c8e2f53a656a632668
- Артефакт: [h1-chase-gate-decoupling](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40650477230/artifacts/12799089180)
- Данные: Binance OHLCV proxy; H1; RAYUSDT, PUMPUSDT, TAOUSDT, AAVEUSDT, CAKEUSDT; три периода:
  1. 2026-04-27 12:00 — 2026-06-21 05:00 UTC
  2. 2026-06-21 06:00 — 2026-08-14 23:00 UTC
  3. 2026-08-15 00:00 — 2026-10-27 00:00 UTC
- Фиксированные фильтры: volume ratio >= 1.6; breakout/ATR >= 0.25; моделируемые издержки ×2; 10,000 USDT начального капитала; риск 1% на сделку; максимум 5 позиций.
- Скрипт скомпилирован и завершился успешно; выгружено 30 строк summary, 2,160 сделок и 10,120 строк сигналов.
- Тесты в соседнем полном CI run 40650477119: 18/18 gap-execution tests и 37/37 time/engine tests прошли. PR-triggered run 40650487636 повторил тот же набор проверок и артефактов; это дублирующий CI, не независимая рыночная выборка.

| Модель из скрипта | Порог | Fold 1 net / PF / trades | Fold 2 | Fold 3 | Сумма net |
|---|---:|---:|---:|---:|---:|
| limit | 1.5% | +990.60 / 1.60 / 43 | +305.97 / 1.14 / 42 | +2,502.83 / 2.09 / 48 | +3,799.40 |
| limit | 2.0% | +878.13 / 1.50 / 51 | +742.75 / 1.36 / 48 | +2,409.36 / 1.82 / 64 | +4,030.24 |
| limit | 2.5% | +902.16 / 1.50 / 53 | +807.24 / 1.38 / 50 | +3,189.97 / 1.92 / 78 | +4,899.37 |
| limit | 3.0% | +294.00 / 1.14 / 58 | +832.94 / 1.38 / 51 | +2,273.61 / 1.56 / 88 | +3,400.55 |
| limit | 100% | +436.61 / 1.17 / 65 | +348.88 / 1.13 / 59 | +642.90 / 1.12 / 112 | +1,428.39 |
| market | 1.5–100% | +142.53 / 1.05 / 68 | −846.27 / 0.72 / 64 | +266.91 / 1.05 / 118 | −436.83 |

**Критически важная методологическая оговорка:** E08 не является чистым факторным экспериментом «candle-body gate против max-chase gate». В текущем скрипте execution_mode=limit одновременно включает maker-entry и проверку тела сигнальной свечи порогом chase_limit_pct; execution_mode=market отключает этот body-фильтр на генерации сигнала, но применяет тот же порог к гэпу следующего открытия. Поэтому таблица одновременно сравнивает разные типы исполнения и разные значения порога. Market-строки одинаковы для всех пяти порогов — ожидаемо, поскольку body-фильтр там отключён, а gap-порог применяется при заполнении. Это полезная диагностика, но она не позволяет причинно приписать разницу только одному из двух gate.

**Что можно утверждать:**
1. В рамках текущей maker-limit модели и пяти выбранных монет все три периода имеют положительный net при body cap 1.5–3%; fold 2 заметно слабее fold 1/3, но не отрицателен для limit-вариантов.
2. Снятие body cap до 100% снижает итог limit-модели с +3.8–4.9k до +1.43k, однако это не чистый эффект body gate из-за одновременно различающейся механики исполнения и ограничений fill.
3. Market-вариант отрицателен суммарно (−436.83), с PF 0.72 во втором периоде. Это согласуется с прежним наблюдением, что модель входа существенно влияет на результат.
4. Результаты нельзя переносить на Bybit без данных стакана/реальных maker fills; OHLC касание лимитной цены не моделирует очередь, спред, частичные исполнения и adverse selection. Funding в данном прогоне отдельно не отражён.

**Решение:** не менять production-порог и не объявлять 1.5–2.5% оптимальным. E08 завершён как диагностический тест, но его причинный вопрос остаётся OPEN.

**Следующий эксперимент (E09):** реализовать настоящий 2×2 факторный дизайн на одной и той же выборке сигналов и одинаковой механике исполнения: (A) body gate on/off × (B) next-open gap gate on/off. Отдельно повторить факторный дизайн для market и limit исполнения, не смешивая эффекты. До запуска проверить, что каждая ячейка отличается ровно одним фактором; сохранить полный signal funnel, причины отказов, attempted/filled/expired orders, стоимость и trade-level результаты. Для limit добавить стресс исполнения (минимум: adverse price/queue haircut или консервативное требование penetration), иначе вывод будет только о верхней границе OHLC fill-модели.


## E09 — факторное разделение body gate и next-open gap gate

**Статус:** выполнен, workflow успешен.  
**Workflow:** https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41355171678  
**Artifact:** `e09-h1-gate-factorial` (ID `13103031404`).  
**Код:** `scripts/run_e09_h1_gate_factorial.py`.  
**Конфигурация:** те же 5 символов (RAY, PUMP, TAO, AAVE, CAKE), H1, те же 3 хронологических fold, volume ratio >= 1.6, breakout/ATR >= 0.25, комиссии/проскальзывание ×2, 1% риска на сделку, максимум 5 позиций. Порог next-open gap зафиксирован на 2.0%. 24 ячейки: 2 execution modes × 2 body-gate states × 2 gap-gate states × 3 folds.

### Результаты

| Исполнение | Body gate | Gap gate | Сделки | Fold 1 net | Fold 2 net | Fold 3 net | Итого net |
|---|---:|---:|---:|---:|---:|---:|---:|
| Market | OFF | OFF | 250 | +142.53 | -846.27 | +266.91 | **-436.83** |
| Market | OFF | ON | 250 | +142.53 | -846.27 | +266.91 | **-436.83** |
| Market | ON | OFF | 173 | +614.96 | -357.85 | +2,015.80 | **+2,272.91** |
| Market | ON | ON | 173 | +614.96 | -357.85 | +2,015.80 | **+2,272.91** |
| Limit | OFF | OFF | 236 | +436.61 | +348.88 | +642.90 | **+1,428.39** |
| Limit | OFF | ON | 236 | +436.61 | +348.88 | +642.90 | **+1,428.39** |
| Limit | ON | OFF | 163 | +878.13 | +742.75 | +2,409.36 | **+4,030.24** |
| Limit | ON | ON | 163 | +878.13 | +742.75 | +2,409.36 | **+4,030.24** |

Net PnL in USDT. All 24 fold-cells are in `e09_gate_factorial_summary.csv`; trade-level and signal-level records are in the artifact.

### Что показал тест

1. **Body gate (absolute signal candle body <= 2.0%) materially changes results.** При market net улучшился на +2,709.74 USDT (с -436.83 до +2,272.91), число сделок снизилось с 250 до 173. При limit net улучшился на +2,601.85 USDT (с +1,428.39 до +4,030.24), число сделок снизилось с 236 до 163. Улучшение наблюдается во всех трёх fold, но market fold 2 всё ещё отрицательный (-357.85 USDT).
2. **Gap gate 2.0% не изменил ни одной сделки.** В диагностических сигналах максимальный наблюдавшийся next-open gap — около 0.178%; ни один сигнал не превысил 2%. Это не доказательство бесполезности gap gate вообще, а только отсутствие наблюдений, на которых порог 2% мог бы сработать в этих данных.
3. Body gate — единственный из двух проверенных фильтров, который объясняет разницу результатов E09. Не смешивать этот эффект с исполнением: market с body gate ON положителен суммарно, но fold 2 остаётся убыточным.
4. E09 согласуется с E08: значения limit OFF/ON повторяют E08 unrestricted/2% cap, но теперь body gate отделён от gap gate.

### Ограничения и решение

- Пять заранее выбранных инструментов и три fold — узкая выборка; это диагностический эксперимент, не доказательство переносимого edge и не основание для production deployment.
- Источник OHLCV — Binance proxy, не Bybit; ранее Bybit data endpoint вернул HTTP 403.
- Limit fill остаётся оптимистичной OHLC-моделью: нет очереди заявок, partial fills, реального bid/ask spread и adverse selection. Удвоенные комиссии/проскальзывание не устраняют эту модельную неопределённость.
- Funding не моделировался отдельно.
- Не использовать этот результат для подбора порога 2% как «оптимального»: порог был зафиксирован для изоляции эффекта, а не выбран по результатам.
- Первый запуск E09 упал из-за неверного пути к тестовому модулю (`tests/` не существует; файл лежит в корне). Второй запуск использовал `unittest` и фактически выполнил 0 тестов; его не считать тестовой валидацией. Финальный workflow `41355171678` исправлен: установлен pytest, выполнено **18/18 gap execution tests**, py_compile успешен, factorial успешно завершён, загружены все три CSV. Предыдущие промежуточные CI-запуски не включать в статистику эксперимента.

**Следующий эксперимент:** не перебирать gap threshold без причины. Проверить body gate на расширенной, заранее определённой выборке символов и на независимом последующем периоде; отдельно провести стресс limit-fill модели (haircut/очередь/спред) и сравнить fold 2 с fold 1/3. До этого body gate остаётся кандидатом для дальнейшей проверки, не утверждённым параметром стратегии.


## E09 — forensic fold analysis (2026-11-02)

Повторно разобран первичный artifact `e09-h1-gate-factorial` (run 41355171678, artifact 13103031404; SHA-256 `503aa4ef24f6f7ef5adef0a63297e0deeeb7298c55b4d3254df1be7dd274416f`). Это анализ сохранённых CSV, не новый backtest.

- Период 2 имеет более слабый broad-market breadth/momentum: медианная доля universe с положительной доходностью за 72h — 53.1% против 66.0% / 73.5% в периодах 1/3; медианная доходность broad universe за 72h — +0.222% против +1.044% / +2.008%.
- Локальные breakout признаки в периоде 2 не хуже по объёму и breakout/ATR: median volume ratio 3.219, breakout/ATR 0.889. ATR/close ниже: 0.925% против 0.994% / 1.313%.
- При body gate 2% market fold 2 gross +265.70 USDT не покрывает fees+slippage 623.55 USDT: net -357.85. Потери сконцентрированы в AAVE (-508), CAKE (-231), TAO (-711); PUMP дал +999, RAY +93.
- Limit fold 2 net +742.75, но OHLC fill с offset/penetration не моделирует очередь, spread и adverse selection; не считать это подтверждённым maker edge.
- Gap gate 2% не менял ни одной сделки; threshold sweep не нужен.

Подробные таблицы, ограничения и следующий эксперимент: [E09_FOLD_DIFFERENCES_RU.md](../reports/E09_FOLD_DIFFERENCES_RU.md).

**Следующий эксперимент:** один cross-sectional replication body gate ON/OFF при фиксированном пороге 2%, только market execution, все валидные H1 ряды загруженного universe (ориентир — 50 символов; точный список/исключения зафиксировать в manifest), те же три даты fold. Предыдущая 50-symbol signal-quality matrix варьировала volume/breakout пороги при фиксированном default body cap, но не сравнивала body gate ON/OFF. Не перебирать порог. До запуска закрепить состав universe, archive/blob SHA и полноту рядов. Цель — проверить переносимость эффекта за пределы пяти отобранных инструментов.


## E10 — cross-sectional H1 body-gate replication (2026-11-02)

- Workflow: [41360728294](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41360728294), success.
- Artifact: [e10-h1-body-gate-cross-sectional](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41360728294/artifacts/13104981517), SHA-256 `64832db93e5912c877debcfd4548cbf9a6fb2beb71ca647c39762e1321b963fa`.
- Commit: `483278f51d99d402215a1f26a690ea2661e28939`; script: `scripts/run_e10_h1_body_gate_replication.py`.
- Universe: 50 valid H1 symbols discovered; 47 included across all three fold (AERO, GRAM, HYPE excluded for insufficient coverage); 282 symbol-fold runs.
- Design: per-symbol independent 10,000 USDT runs; market execution only; body cap OFF vs fixed 2.0%; gap gate disabled; volume ratio >=1.6; breakout/ATR >=0.25; costs ×2. 2,422 trades OFF vs 1,797 ON.
- Sum of independent symbol net results: OFF -22,857.66 USDT; ON -15,912.54 USDT. This is not shared-capital portfolio PnL. Gate reduced trade count 25.8%, fees+slippage by 5,700.40 USDT and improved summed independent net by 6,945.12 USDT, but the overall result remained negative.
- Fold effect: fold 1 worsened by 492.79; fold 2 improved by 2,459.71; fold 3 improved by 4,978.20. Per-symbol response is mixed, so body gate is regime-dependent, not a universal fix.
- Positive symbol-fold counts 49/141 OFF vs 59/141 ON; median PF 0.81 OFF vs 0.78 ON; mean expectancy R -0.11 vs -0.08.
- Data: Binance OHLCV proxy, six CryptoFetch archives, uneven coverage; exact per-symbol coverage and archive SHA-256 values are in the artifact manifest. Funding not included. Not blind holdout.
- First attempt run 41360651282 failed before simulation because intersection of timestamps across all 50 symbols was only 758 bars. Corrected E10 runs each symbol independently on its own timestamps; failed attempt excluded from results.
- Decision: do not promote 2% body cap to production. No threshold sweep. Next inspect signal/trade funnel by fold to understand which trades the body cap removes and why fold 1 worsens; only then consider a frozen shared-capital portfolio replay and future untouched holdout.

Detailed report: [E10_H1_BODY_GATE_CROSS_SECTIONAL_RU.md](../reports/E10_H1_BODY_GATE_CROSS_SECTIONAL_RU.md).


### E10 — signal/trade funnel follow-up

- Among base-filtered breakout candidates, absolute body >2% share varied by fold: 31.8% (438/1,376), 20.4% (218/1,070), 44.1% (930/2,111).
- In body-gate-OFF realized trades, body >2% group net was +36.14 (240 trades) in fold 1, -2,856.12 (117) in fold 2, and -2,666.56 (481) in fold 3. Mean net R: +0.003 / -0.240 / -0.052.
- Candidate forward outcomes show body >2% had worse 24h/48h follow-through in fold 2 and fold 3, but not fold 1. In fold 3, median 48h return was -0.753% for body >2% vs +0.295% for body <=2%.
- Large-body candidates also had much larger 24h max-up and max-down excursions; the filter removes high-volatility opportunities and adverse excursions together. Do not treat this as a simple signal-quality monotonicity.
- This supports the working hypothesis that candle-body gate value is regime-dependent: it filters poor follow-through in folds 2/3, but fold 1 had no comparable forward-return disadvantage for large-body candidates.
- Caveat: candidate forward returns are not fills/PnL; realized bucket PnL is affected by position occupancy and changed trade sequence when the gate is toggled. This is diagnostic, not causal proof.



- Symbol-clustered forward-return check (minimum 3 signals per body bucket per symbol): median 24h return difference (body >2% minus <=2%) was -0.118 percentage points in fold 1 (20/39 symbols worse), -0.811 pp in fold 2 (20/30 worse), and -0.792 pp in fold 3 (28/44 worse). This avoids treating all overlapping signals as independent; fold 1 shows little cross-sectional separation, folds 2/3 show clearer weak follow-through for large candles.


- Paired trade identity comparison by `(symbol, signal_ts)` explains fold interaction:
  - Fold 1: 244 trades removed (240 body>2%, net -121.64), 76 new body<=2% trades (net -623.49), 449 shared trades (shared net +9.06); total ON-OFF -492.79.
  - Fold 2: 118 removed (117 body>2%, net -2,749.72), 30 new (net -351.92), 502 shared (delta +61.91); total ON-OFF +2,459.71.
  - Fold 3: 484 removed (481 body>2%, net -2,698.00), 115 new (net +2,311.53), 625 shared (delta -31.33); total ON-OFF +4,978.20.
- Interpretation: body gate changes the subsequent trade sequence. Fold 1 replacements were worse than removed trades; fold 2 replacements were less bad; fold 3 replacements were profitable. Gate value depends on the quality of signals that become available after skipping large-body entries, not only on the rejected candle itself.



- Replacement trades that appear only with body gate ON had lower median breakout/ATR and higher prior 24h momentum/efficiency than removed large-body trades. Their aggregate net was -623.49 (76 trades) in fold 1, -351.92 (30) in fold 2, and +2,311.53 (115) in fold 3. Fold 3 replacement set had median prior 24h return +8.06% and efficiency 0.410; this is a descriptive candidate interaction, not proof of a predictive filter.


## E11 — shared-capital H1 portfolio replay (2026-11-02)

- Workflow (optimized run): [41361376448](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41361376448), success.
- Artifact: [e11-h1-shared-capital-portfolio](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41361376448/artifacts/13105661683), SHA-256 `441e518a683435e47327cb85bb741c8fcb24e734ded1ab720722dc50dd588765`.
- Commit: `ae6f7b4c99b79cbe31fdfeded8780a058b118049`; script: `scripts/run_e11_h1_shared_capital_replay.py`.
- Universe: 47 symbols, common aligned coverage 4,321 H1 bars (2026-04-29 00:00 to 2026-10-26 00:00 UTC); AERO, GRAM, HYPE excluded for fold-1 coverage.
- One shared 10,000 USDT account per fold, 1% risk/trade, 2% portfolio risk cap, max 5 concurrent positions, market execution, costs ×2, gap gate OFF; body gate OFF vs fixed 2%.
- Results by fold: OFF net -617.62 / -2,970.05 / +409.06; ON -1,227.64 / -2,560.32 / +1,013.96.
- Sum of separate fold results: OFF -3,178.61; ON -2,774.00 (improvement +404.61 only). This is not one continuous account because each fold restarts at 10k.
- Body gate reduced trades 772 -> 680, but fees+slippage increased 5,167.70 -> 5,553.73; PF nearly unchanged 0.859 -> 0.862. No robust edge established.
- The shared-capital effect is much smaller than E10 per-symbol independent sum improvement (+404.61 vs +6,945.12), showing that independent symbol runs overstate the apparent value when portfolio slots/risk are shared.
- Fold 1 worsened, folds 2/3 improved; strategy still materially negative in folds 1 and 2. Funding absent; Binance OHLCV proxy; not blind holdout.
- Decision: do not promote 2% body gate. Next step is descriptive stratification of shared-capital signals/trades by causal broad-market breadth and 24–72h momentum/efficiency, without optimizing thresholds.

Detailed report: [E11_H1_SHARED_CAPITAL_PORTFOLIO_RU.md](../reports/E11_H1_SHARED_CAPITAL_PORTFOLIO_RU.md).


## E12 — causal broad-market context diagnostics (2026-11-02)

- Workflow: [41361856404](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41361856404), success.
- Artifact: [e12-h1-market-context-diagnostics](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41361856404/artifacts/13105721458), SHA-256 `5ac82041680ea6bcbb90561a6da11687c15c171885dd66034db321ce63bd8854`.
- Commit: `4100d800761983d9de148f368d2402280b3dc6be`; script: `scripts/run_e12_h1_market_context_diagnostics.py`.
- Calculated completed-bar broad breadth, median 24h/72h returns, efficiency, ATR, cross-sectional IQR/std and BTC/ETH context for 4,249 hourly timestamps over the fixed 47-symbol E11 universe. No backtest or threshold optimization.
- At unique base signal timestamps, fold 2 had the lowest 72h breadth (48.9%), median 72h return (-0.043%), median ATR (0.761%) and IQR72 (3.669%). Fold 3 was strongest; fold 1 was intermediate.
- At actual trade timestamps, fold 2 again had lowest breadth72 (44.7%), median return72 (-0.344%), ATR (0.768%) and IQR72 (3.611%).
- Winner/loser context changes sign by fold: fold 1 winners had weaker broad breadth/72h momentum than losers; fold 3 winners had stronger breadth/72h momentum; fold 2 winners and losers barely separated and all 72h momentum terciles were negative.
- Working regimes: fold 1 weak/mixed market with selective local opportunities; fold 2 compression/chop with poor breakout follow-through; fold 3 broad trend expansion. This is descriptive, not a validated classifier.
- Decision: no one-sided market-trend gate and no threshold sweep. Next define one causal compression classifier from rolling ATR + cross-sectional dispersion while preserving local opportunities in weak broad markets; only then one frozen shared-capital replay.

Detailed report: [E12_BROAD_MARKET_CONTEXT_DIAGNOSTICS_RU.md](../reports/E12_BROAD_MARKET_CONTEXT_DIAGNOSTICS_RU.md).


- E12 feasibility check: a single causal compression flag (current broad median ATR% AND cross-sectional IQR72 below expanding 25th percentiles of all prior hourly observations; minimum 336 prior hours) activated on 3.2% / 23.3% / 6.0% of hourly bars in folds 1/2/3. At candidate signal hours: 5.0% / 25.5% / 7.0%; at filled trade hours: 4.9% / 26.9% / 8.0%.
- Existing trade PnL inside compression is worse in fold 2 but not uniformly bad in fold 3. Because trade sequence changes when entries are blocked, this is only feasibility evidence; proceed with one frozen shared-capital replay, no threshold sweep.



## E13 — causal compression gate shared-capital replay (2026-11-02)

- Workflow: [41362217727](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362217727), success.
- Artifact: [e13-h1-compression-gate-shared-capital](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362217727/artifacts/13105403824), SHA-256 `9930d6f3651305ef9dcf254c85bc0b50b24cb098b6b367accbaaae4bbad6f601`.
- Commit: `f4da3cca0c0dc79cee86350ba6a680fc461e47fc`; script: `scripts/run_e13_h1_compression_gate_replay.py`.
- Rule: current broad median ATR% AND cross-sectional IQR72 below expanding q25 of all prior completed context hours; min 336 prior hours; no gate before warm-up. One frozen rule, no sweep.
- Shared 10k account per fold, 47 aligned symbols, max 5 concurrent positions, market execution, body/gap gate OFF, costs ×2.
- Baseline OFF exactly reproduced E11 body-gate-OFF metrics. Compression ON net by fold: -294.93 / -2,614.55 / +167.76 vs OFF -617.62 / -2,970.05 / +409.06.
- Sum of separate fold net: -2,741.72 ON vs -3,178.61 OFF (+436.89); trades 724 vs772; fees+slippage 4,844.57 vs5,167.70; PF 0.870 vs0.859. Still negative; fold 2 remains materially negative and fold 3 profit is reduced.
- Paired trade identity comparison shows gate removed losing trades in folds 1/2, but removed profitable trades in fold 3. It changes replacement sequence, not only the rejected set.
- Decision: promising diagnostic, not production-ready. No threshold sweep. Need untouched future holdout before considering deployment.

Detailed report: [E13_CAUSAL_COMPRESSION_GATE_RU.md](../reports/E13_CAUSAL_COMPRESSION_GATE_RU.md).


## Engineering gate — Bybit execution realism readiness audit (2026-11-02)

- Audit: [EXECUTION_REALISM_READINESS_RU.md](../audits/EXECUTION_REALISM_READINESS_RU.md).
- No market backtest was run.
- Research CI [41362633014](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362633014) passed deterministic tests for instrument spec parsing/history, exchange sizing, funding accounting/MTM/coverage, and portfolio/time/gap logic.
- Bybit instrument snapshot attempts failed: runs [41358634175](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41358634175) and [41362639497](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362639497). The latter tried six regional hosts; each returned HTTP 403. No dated snapshot is present in `data/instrument_specs/linear/`.
- Engine uses notional-based sizing and does not call `exchange_order_sizing.py` or `InstrumentSpecHistory`; exact contract quantity is not represented in position state.
- Funding helper uses `size_usdt / entry_price` quantity and timestamp-aligned mark-candle open proxy; E13 omitted funding.
- Fee/slippage constants are 0.055% taker, 0.020% maker, 0.0225% taker slippage per leg; E13 stress multiplier ×2 is not a measured spread/impact model.
- Decision: freeze strategy parameter research until Bybit data and dated specs can be captured and validated. No production change.



## ENG-KS-001 — kill-switch priority over same-bar TP2 (2026-11-02)

- Preregistered card: [ENG-KS-001](experiment_cards/ENG-KS-001_KILL_SWITCH_PRIORITY_RU.md).
- Confirmed defect in `UnifiedQuantEngine._manage_position()`: after intrabar mark-to-market had latched portfolio kill-switch, TP2 could still close the current symbol first because the kill-switch branch was only a fallback when no other exit had been selected.
- Fix: when kill-switch is already active at position-management time, close at the precomputed adverse intrabar risk mark (including stop/gap fill semantics) before TP1/TP2/time-stop processing. Do not count same-bar favourable wick in MFE because OHLC path is unknown.
- Regression: `test_kill_switch_overrides_tp2_when_same_bar_hits_adverse_mark_and_target` exercises full `step_candle()`; adverse low trips kill-switch while high touches TP2 and protective stop remains untouched. Expected journal reason is `kill_switch`, exit price is adverse mark, MFE excludes same-bar high.
- Commits: engine fix `3ef0626a776b99c083b0ef289f9ca8ab8fe82c97`; regression test `7f4fc3ee641e790451081a02628615b19618b230`.
- CI: [Research engine checks #41431556111](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41431556111), SUCCESS. `test_time_model.py` 38/38; `test_gap_execution.py` 22/22; compile and all other configured deterministic checks passed; secret scan found no obvious secret patterns.
- Decision: ACCEPT as a simulator correctness fix. No market backtest, parameter sweep, production change or live order was performed.
- Limitation: adverse intrabar mark remains an OHLC proxy, not a guaranteed executable fill. This fix does not validate real execution or strategy profitability.


## ENG-EXEC-002 — marketable limit gap-through entry costs (2026-11-02)

- Preregistered card: [ENG-EXEC-002](experiment_cards/ENG-EXEC-002_MARKETABLE_LIMIT_FEE_RU.md).
- Confirmed issue: `_try_fill_pending()` filled a limit order at the opening price when the market gapped through the limit, but retained `order_type="limit"`. Sizing, MTM and close-journal accounting therefore charged maker entry fee and zero entry slippage for a marketable opening fill.
- Fix: classify a long limit with `open < limit` and short limit with `open > limit` as effective market/taker entry. Pass that type to position sizing and persist it in the position so MTM and final journal use taker fee/slippage. A non-gap intrabar touch remains the existing maker proxy; maker exit behavior remains independently configured.
- Regression tests: buy and sell gap-through cases assert taker classification; non-gap limit touch asserts maker proxy; buy case also checks journal taker fee/slippage.
- Commits: engine fix `2a60a261ef5792b72d438ae39c5f99dda807c16e`; tests `f1667c273d30c20306e59a746318c8be4d532172`.
- CI: [Research engine checks #41431923590](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41431923590), SUCCESS. `test_gap_execution.py` 25/25; `test_time_model.py` 38/38; compile, all other configured deterministic checks and secret scan passed.
- Decision: ACCEPT as a correction to the simulator's marketable-limit entry cost classification. No market backtest, parameter sweep, production change or live order was performed.
- Limitation: ordinary intrabar limit touch is still an optimistic maker proxy without bid/ask, queue priority, partial fills or adverse-selection modelling. Taker slippage remains a static proxy.


## H1 entry-session boundary audit — timestamp semantics (2026-11-02)

- Workflow: [41428755424](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41428755424), success; artifact SHA-256 `3e4a1da0085dfb275395657ec4aa8d6d67e68c70ec9b509010696b30e875866f`.
- Script: `scripts/audit_h1_entry_session_boundary.py`; 25 symbols; two chronological periods (screen and forward); four variants: baseline, signal-candle US block, next-entry-bar US block, and next-entry-bar US block plus direction/24h alignment.
- Key semantic finding: native `blocked_sessions_utc` is evaluated against the signal candle timestamp in `QuantStrategyCore.evaluate_signal()`, while trade journal session is computed from the actual fill candle timestamp. A signal on the 15:00 H1 candle can be evaluated in EU session but enter at 16:00 UTC in US session. The native signal-session block therefore does not guarantee blocking actual US-session entries.
- Per-symbol independent sums (not shared-capital portfolio): screen net baseline -1,886.09; signal-US-block +9,959.67; entry-US-block +7,440.00; aligned-entry-US-block +8,543.31. Forward net baseline -14,789.82; signal-US-block -5,020.33; entry-US-block -5,341.50; aligned-entry-US-block -2,819.98. The signal-session variant still recorded 134 US-session entries in screen and 125 in forward; the entry-session variant recorded zero.
- Interpretation: signal-time and entry-time filters are different policies. The existing config field is signal-time semantics; do not describe it as an entry-session block. No automatic code change is made because changing the timestamp basis changes strategy behavior and the audit used independent per-symbol simulations. Any future adoption requires a separately preregistered experiment and shared-capital validation after the execution/data gate.
- Decision: diagnostic only; no filter promoted. Binance OHLCV proxy, static costs, per-symbol independent accounts; not evidence of portfolio profitability.


## ENG-STATE-003 — fail-closed state restore (2026-11-02)

- Preregistered card: [ENG-STATE-003](experiment_cards/ENG-STATE-003_FAIL_CLOSED_RESTORE_RU.md).
- Confirmed defect: `PlanBStatePersistence.load_state()` caught every exception and returned empty positions/pending/sequence. This conflated a missing file (valid cold start) with an existing but unreadable/incompatible backup (possible lost local record of open exchange positions).
- Fix: missing file still returns empty cold-start state; if an existing backup cannot be parsed or restored, loader logs CRITICAL and raises `RuntimeError` chained from the original exception. It no longer silently returns an empty state.
- Tests: `tests/test_state_persistence.py` covers missing file, full valid round-trip of risk flags/open position/pending/trade sequence, corrupt JSON, and malformed position object.
- Commits: engine `ce6f3a1b3ba7b3277c9e8180fee799bf7dc67a9f`; tests `1706cd3cf9f8e8022361b02c8e62516932f50dfc`; CI wiring `d6f6d2374f93979e1253f6bf22fe5192f18ae471`; test import fix `3bff014673d77ae7b6eddaa63aa010f6b89f08a0`.
- CI: [Research engine checks #41432693641](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41432693641), SUCCESS. New persistence tests 4/4; compile, all configured deterministic suites and secret scan passed.
- Decision: ACCEPT as a state-integrity correction. No market backtest, parameter sweep, production deployment or live order.
- Limitation: a valid backup may still be stale relative to Bybit. This fix does not implement exchange position/order reconciliation and must not be described as safe live-resume.


## ENG-STATE-004 — fail-closed state save (2026-11-02)

- Preregistered card: [ENG-STATE-004](experiment_cards/ENG-STATE-004_FAIL_CLOSED_SAVE_RU.md).
- Confirmed defect: with persistence enabled, `save_state()` caught write/replace exceptions, logged them and returned normally. The trading caller could continue despite a stale recovery point.
- Fix: when persistence is enabled, save failures now clean up the current attempt's temporary file on a best-effort basis, log CRITICAL and raise `RuntimeError`. Disabled persistence remains a no-op.
- Tests: `tests/test_state_persistence.py` now covers disabled no-op, successful round-trip, atomic replace failure + temp cleanup, missing backup, corrupt JSON, malformed position.
- Commits: engine `ac43d4aa23d2e797eae99d57e6c65c714642e120`; tests `0b142dcf5393683844e8e73b7d3f2096525a7722`.
- CI: [Research engine checks #41432914403](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41432914403), SUCCESS; state persistence tests 6/6, compile, all configured deterministic suites and secret scan passed.
- Decision: ACCEPT as a local persistence integrity correction. No market backtest, parameter sweep, production deployment or live order.
- Limitation: no fsync/remote durability guarantee; no Bybit position/order reconciliation.


## ENG-STATE-005 — transactional state restore (2026-11-02)

- Preregistered card: [ENG-STATE-005](experiment_cards/ENG-STATE-005_TRANSACTIONAL_RESTORE_RU.md).
- Confirmed defect: loader applied `risk_mgr.from_dict()` before parsing positions and pending orders. If later parsing failed, the method raised (after ENG-STATE-003) but the caller's risk manager had already been mutated.
- Fix: validate root/risk/positions/pending/trade_seq types; stage risk state in a temporary `AdaptiveRiskManager`; build all positions and sequence; only then apply staged risk values to the caller's manager. Position dictionary key must match `pos.symbol`.
- Tests: `tests/test_state_persistence.py` 9/9, including malformed position/pending/sequence proving original risk manager remains unchanged after failed restore.
- Commits: engine `ee191fb37711a2304b5a7a64752f629a7e0566d4`; tests `481a71484579f700feef53930326bde50a4513d1`.
- CI: [Research engine checks #41433598794](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41433598794), SUCCESS; compile, all configured deterministic suites and secret scan passed.
- Decision: ACCEPT as an in-memory restore atomicity correction. No market backtest, parameter sweep, production deployment or live order.
- Limitation: local restore still lacks exchange reconciliation and backup freshness/schema migration.


## ENG-STATE-006 — restored pending signal schema (2026-11-02)

- Preregistered card: [ENG-STATE-006](experiment_cards/ENG-STATE-006_PENDING_SCHEMA_RU.md).
- Confirmed defect: loader only checked that `pending_orders` was a dict; nested values could be arrays/scalars or malformed signal objects, and `pending_orders: []` was silently normalized to an empty dict by `or {}`.
- Fix: validate pending signal object shape, symbol/key identity, required fields, direction, order type, strategy, finite positive entry/stop distance and optional nonnegative finite vol_ratio. Do not normalize malformed empty list/null containers into an empty state.
- Tests: `tests/test_state_persistence.py` 14/14; includes malformed pending container/entry, missing fields, invalid direction/order type, NaN price, valid pending round-trip, and no risk-manager mutation on failed restore.
- Commits: engine `f7ecec11e571c26cce4be2d01903a4d104b7f223`, strict empty/null container handling `990bcf9e66551edb0369e4f2c606e643b3e2ac5f`; tests `b1eeede0558eec4125c7dd4be9bb8b80153bda0f`.
- CI: [Research engine checks #41433992368](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41433992368), SUCCESS; compile, all configured deterministic suites and secret scan passed.
- Decision: ACCEPT as a local backup validation correction. No market backtest, parameter sweep, production deployment or live order.
- Limitation: local pending signal state is not an exchange order; no reconciliation with Bybit active orders is implemented.


## ENG-STATE-007 — restored open-position schema (2026-11-02)

- Preregistered card: [ENG-STATE-007](experiment_cards/ENG-STATE-007_POSITION_SCHEMA_RU.md).
- Confirmed defect: dataclass annotations do not enforce runtime types/invariants; loader silently filtered unknown fields. Malformed position prices/sizes/direction could survive restore and fail later in PnL/position management.
- Fix: require core position fields; reject unknown fields; validate symbol/trade/strategy, direction/order type, positive integer timestamp, finite positive price/distance/size/risk, bounded remaining fraction, optional numeric/boolean/timestamp/bar fields; preserve defaults for omitted optional dataclass fields.
- Tests: `tests/test_state_persistence.py` 18/18, including unknown field, invalid direction, NaN entry price and negative notional; existing valid position round-trip passes and failed restore leaves risk manager unchanged.
- Commits: engine `3a5fc1bdb6df645f9dc010f2f8abefaac918b82d`; tests `c76ad2ed897bc05b7e59be5deff66ba74418aa9c`.
- CI: [Research engine checks #41434308834](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41434308834), SUCCESS; compile, all configured deterministic suites and secret scan passed.
- Decision: ACCEPT as local restore validation. No market backtest, parameter sweep, production deployment or live order.
- Limitation: no Bybit position/order reconciliation, backup freshness/schema migration or fsync durability.


## ENG-STATE-006 — pending signal schema validation (2026-11-02)

- Preregistered card: [ENG-STATE-006](experiment_cards/ENG-STATE-006_PENDING_SCHEMA_RU.md).
- Confirmed defect: restore checked only that `pending_orders` was a dictionary. Nested values could be lists or incomplete/malformed signal objects, later failing in the fill/risk path or admitting invalid direction/order type.
- Fix: validate symbol-keyed objects, required fields (`symbol`, `direction`, `strategy`, `entry_price`, `stop_dist`, `order_type`), symbol/key match, long/short direction, market/limit order type, non-empty strategy and finite positive price/stop distance; validate optional `vol_ratio` as finite and non-negative.
- Tests: `tests/test_state_persistence.py` 18/18; valid pending signal round-trip plus malformed entry, missing field, invalid direction/order type, NaN price and failed restore atomicity.
- Validator commit: `c76ad2ed897bc05b7e59be5deff66ba74418aa9c`.
- CI: [Research engine checks #41434308834](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41434308834), SUCCESS; compile, all configured deterministic suites and secret scan passed.
- Decision: ACCEPT as local pending-state schema validation. No market backtest, parameter sweep, production deployment or live order.
- Limitation: validated pending signal is not proof of an active Bybit order; exchange reconciliation remains mandatory.


## ENG-STATE-007 — open-position schema validation (2026-11-02)

- Preregistered card: [ENG-STATE-007](experiment_cards/ENG-STATE-007_POSITION_SCHEMA_RU.md).
- Confirmed defect: dataclass annotations are not runtime validation; loader silently dropped unknown fields and accepted malformed position values that could fail later in PnL/management.
- Fix: reject unknown position fields; validate required identifiers, direction/order type, positive finite price/distance/notional/risk, timestamp, optional numeric/fraction/boolean fields and bars-held before committing restored state. Optional fields omitted by legacy payloads continue using dataclass defaults.
- Tests: included in `tests/test_state_persistence.py` 18/18 at CI #41434308834, alongside ENG-STATE-006 pending-schema tests.
- Engine commit: `3a5fc1bdb6df645f9dc010f2f8abefaac918b82d`; test/CI commit: `c76ad2ed897bc05b7e59be5deff66ba74418aa9c`.
- CI: [Research engine checks #41434308834](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41434308834), SUCCESS.
- Decision: ACCEPT for local restore schema integrity. No market backtest, parameter sweep, production deployment or live order.
- Limitation: does not reconcile positions with Bybit or prove backup freshness.


## ENG-STATE-018 — risk-manager restore schema validation (2026-11-02)

- Preregistered card: [ENG-STATE-008](experiment_cards/ENG-STATE-018_RISK_SCHEMA_RU.md).
- Confirmed defect: `AdaptiveRiskManager.from_dict()` coerces values with `float()` and permissive `_as_bool()`; syntactically valid backups could inject NaN/infinity/negative equity, invalid drawdown, malformed date or non-boolean risk flags.
- Fix: validate known keys, finite numeric values, positive equity fields, drawdown range [0,100], ISO date string and strict boolean flags before staging/committing risk state. Omitted legacy keys retain defaults.
- Tests: `tests/test_state_persistence.py` 23/23, including invalid risk payloads and unchanged caller risk manager on failed restore.
- Commits: engine `84beee0dbe10cd0ab6f9e67255c21d6518a80957`; tests `4a9045fdc01f36c4b4a5e52278691056d4dce9ae`.
- CI: [Research engine checks #41434930478](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41434930478), SUCCESS; compile, all configured deterministic suites and secret scan passed.
- Decision: ACCEPT as local risk-state validation. No market backtest, parameter sweep, production deployment or live order.
- Limitation: validation does not prove risk state is current relative to Bybit or safe for live-resume.


## ENG-STATE-008 — TP1 cross-field restore invariants (2026-11-02)

- Preregistered card: [ENG-STATE-008](experiment_cards/ENG-STATE-008_TP1_INVARIANTS_RU.md).
- Confirmed gap: individually valid fields could contradict one another: e.g. `tp1_hit=true` with 100% remaining size, or `tp1_hit=false` with partial size/realized TP1 PnL. Such state corrupts subsequent MTM/exit accounting. Targets could also be reversed relative to entry.
- Fix: validate directional TP1/TP2 ordering and consistency between TP1 flag, remaining fraction and realized TP1 gross PnL. Current stop is intentionally not constrained relative to entry because trailing stop may cross breakeven.
- Tests: `tests/test_state_persistence.py` 29/29, including valid partial-TP1 round-trip and five invalid cross-field cases.
- Engine commit: `22664bd79f8fc93c0cbf7dbafc5c775a82e8cde3`; corrected test fixture commit: `529d1d725752a3010dedc3c06d1c48c572a1e15b`.
- CI: [Research engine checks #41435897233](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41435897233), SUCCESS; compile, configured deterministic suites and secret scan passed.
- Decision: ACCEPT for local restore invariants. No market backtest, parameter sweep, production deployment or live order.


## ENG-STATE-009 — restored identity consistency (2026-11-02)

- Preregistered card: [ENG-STATE-009](experiment_cards/ENG-STATE-009_RESTORE_IDENTITY_RU.md).
- Confirmed gap: same symbol could exist simultaneously in restored open positions and pending signals; multiple open positions could also reuse one trade_id.
- Fix: reject overlapping open/pending symbols and duplicate trade IDs before committing restored risk state.
- Tests: `tests/test_state_persistence.py` 31/31, including both cross-object conflicts and transactional no-mutation assertions.
- Engine commit: `984e6a085f74139299ae92c6dfc454686cc2a9a9`; test commit: `c8b0ae1c34768e89a9948fb9352c040bff315d0c`.
- CI: [Research engine checks #41436083033](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41436083033), SUCCESS; compile, deterministic suites and secret scan passed.
- Decision: ACCEPT for local restore identity integrity. No market backtest, parameter sweep, production deployment or live order.


## ENG-STATE-010 — complete backup envelope (2026-11-02)

- Preregistered card: [ENG-STATE-010](experiment_cards/ENG-STATE-010_COMPLETE_ENVELOPE_RU.md).
- Confirmed gap: existing syntactically valid JSON could omit `open_positions`, `pending_orders`, `trade_seq` or risk fields; permissive `.get(..., {})` defaults could silently restore an empty portfolio or reset protective flags.
- Fix: require all four envelope keys and all fields emitted by `AdaptiveRiskManager.to_dict()`; no silent empty defaults for an existing incomplete backup.
- Tests: `tests/test_state_persistence.py` 33/33. Existing malformed position/pending/risk tests were updated to use otherwise-complete snapshots so each test exercises its intended validator. Missing each envelope field and missing kill-switch flag are explicitly rejected.
- Engine commit: `e8171203ad3f87ad19bca064f9a32b4c8a4ec2f0`; test commit: `46c4f01a291634cc2b71f4227c41dfb0b0091e2f`.
- CI: [Research engine checks #41436427155](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41436427155), SUCCESS; compile, deterministic suites and secret scan passed.
- Decision: ACCEPT. Older backups missing fields now fail closed; explicit versioned migration is needed rather than silently inventing defaults. No market backtest or live order.


## ENG-STATE-011 — strict JSON backup serialization (2026-11-02)

- Preregistered card: [ENG-STATE-011](experiment_cards/ENG-STATE-011_STRICT_JSON_SAVE_RU.md).
- Confirmed defect: Python JSON encoder default `allow_nan=True` could persist non-standard NaN/Infinity tokens, replacing a valid backup with a file that restore correctly rejects.
- Fix: `json.dump(..., allow_nan=False)`; serialization failure follows ENG-STATE-004 fail-closed behavior, preserves previous backup and removes the failed temporary file best-effort.
- Tests: `tests/test_state_persistence.py` 35/35, including NaN risk and infinite position value; both fail save and preserve previous backup / clean temp file.
- Engine commit: `1a354260945ed34a0be466d790fa24254cd5d472`; test commit: `87a483a4fd9a2a2518bc1ca3fcdc9c4df5301c70`.
- CI: [Research engine checks #41436653943](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41436653943), SUCCESS; compile, configured deterministic suites and secret scan passed.
- Decision: ACCEPT. No market backtest, parameter sweep, production deployment or live order.


## ENG-STATE-012 — risk snapshot cross-field invariants (2026-11-02)

- Preregistered card: [ENG-STATE-009](experiment_cards/ENG-STATE-012_RISK_SNAPSHOT_INVARIANTS_RU.md).
- Confirmed gap: independently valid fields could contradict each other. Restore now requires current equity = rounded realized equity + unrealized PnL; peak equity >= current equity; and max drawdown >= the drawdown implied by peak/current equity.
- Historical max drawdown above current drawdown remains valid.
- Tests: `tests/test_state_persistence.py` 39/39; covers all three invalid identities, valid historical max DD and restore atomicity.
- Commits: engine `70b7b01fa6f549956e9be7ca19990e3724ee9416`; tests `23b3aa3f4af24b5d4b45f9a79eec0cf0be4f225a`.
- CI: [Research engine checks #41444495022](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41444495022), SUCCESS; compile, configured deterministic suites and secret scan passed.
- Decision: ACCEPT as local risk snapshot integrity. No market backtest, parameter sweep, production deployment or live order.
- Limitation: internally consistent backup can still be stale vs Bybit; exchange reconciliation remains a hard pre-live gate.


## ENG-STATE-013 — backup metadata validation (2026-11-02)

- Preregistered card: [ENG-STATE-013](experiment_cards/ENG-STATE-013_BACKUP_METADATA_RU.md).
- Confirmed gap: writer persisted `saved_at_utc` and `bot_version`, but restore ignored both.
- Fix: require both fields; parse timestamp as ISO-8601 with explicit zero UTC offset; require non-empty bot version. No age/freshness threshold was introduced.
- Tests: `tests/test_state_persistence.py` 40/40; malformed timestamp, timezone-naive timestamp, non-UTC offset and empty version rejected; valid writer output restores.
- Commits: engine `b25fde3ceb8032cac45a879622d192335979b6cb`; tests `f110f776a06bdde6aa7faa25b0e97a1601a6f989`.
- CI: [Research engine checks #41445058006](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41445058006), SUCCESS; compile, configured deterministic suites and secret scan passed.
- Decision: ACCEPT for envelope metadata integrity. No market backtest, parameter sweep, production deployment or live order.
- Limitation: timestamp syntax is not freshness validation; stale but correctly timestamped backup can still pass. Bybit reconciliation remains mandatory.


## ENG-STATE-014 — TP1 timestamp consistency (2026-11-02)

- Preregistered card: [ENG-STATE-014](experiment_cards/ENG-STATE-014_TP1_TIMESTAMP_RU.md).
- Confirmed gap: `tp1_hit` could be restored without an event timestamp, or with a timestamp before entry / while TP1 was marked untouched.
- Fix: TP1 hit requires positive integer `tp1_ts_ms >= entry_ts`; untouched TP1 requires timestamp absent/null.
- Tests: `tests/test_state_persistence.py` 43/43; valid partial TP1 round-trip plus missing, pre-entry and contradictory timestamp cases.
- Commits: engine `adc68a7c413abe5f642a10cd91348c81d15ea746`; tests `e128b6865e290a9b597e4c1749d1fbeb99efd188`.
- CI: [Research engine checks #41445386482](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41445386482), SUCCESS; compile, configured deterministic suites and secret scan passed.
- Decision: ACCEPT as local position event chronology validation. No market backtest, parameter sweep, production deployment or live order.
- Limitation: does not establish that TP1 was actually filled at Bybit or reconcile exchange event time.


## ENG-STATE-015 — pending signal next-bar chronology (2026-11-02)

- Preregistered card: [ENG-STATE-015](experiment_cards/ENG-STATE-015_PENDING_NEXT_BAR_RU.md).
- Confirmed lifecycle gap: pending entries were documented as next-candle-only, but restore did not require `signal_ts` and fill logic did not enforce the immediately following candle. After restart/data gap, a stale signal could be filled late.
- Fix: restore requires positive integer `signal_ts`; unknown pending fields rejected; fill requires `curr.ts == signal_ts + timeframe_ms`. Otherwise pending signal and its allocated entry-risk budget are discarded without opening.
- Tests: `tests/test_state_persistence.py` 48/48, including malformed/missing timestamps, unknown fields, stale signal discard and immediate-next-bar fill. Existing gap execution and time-model suites also passed after fixtures were made explicit about signal candle time.
- CI: [Research engine checks #41446661723](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41446661723), SUCCESS; compile, configured deterministic suites and secret scan passed.
- Decision: ACCEPT as preservation of existing one-next-bar policy; no strategy change intended. No market PnL sweep, production deployment or live order.
- Limitation: exact timestamp adjacency assumes complete candles for the configured timeframe. A missing candle causes safe cancellation rather than late fill; it does not query exchange-side order state.


## ENG-STATE-016 — backup event timestamps bounded by save time (2026-11-02)

- Preregistered card: [ENG-STATE-016](experiment_cards/ENG-STATE-016_BACKUP_EVENT_TIME_RU.md).
- Confirmed temporal gap: positive entry/TP1/pending timestamps could still lie after the backup's `saved_at_utc`.
- Fix: restore converts UTC save time to milliseconds and requires every position entry, TP1 event and pending signal timestamp to be no later than that save time.
- Tests: `tests/test_state_persistence.py` 51/51; future entry, TP1 and pending timestamps rejected. Existing valid round-trip, TP1 and pending lifecycle cases pass.
- Commits: engine `8b33bd56c73c7abaf43513b59d16f6c5295bc8fb`; tests `ab74e2918f3c897443f0b0d1acbbfd7059fa9528`.
- CI: [Research engine checks #41447112303](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41447112303), SUCCESS; compile, configured deterministic suites and secret scan passed.
- Decision: ACCEPT as internal backup chronology validation. No market PnL sweep, production deployment or live order.
- Limitation: this does not define maximum backup age or prove the snapshot matches exchange state; Bybit reconciliation remains mandatory.


## ENG-STATE-017 — durable atomic backup write (2026-11-02)

- Preregistered card: [ENG-STATE-017](experiment_cards/ENG-STATE-017_FSYNC_BACKUP_RU.md).
- Confirmed durability gap: atomic rename alone does not request that temporary-file contents and parent-directory rename metadata be committed to storage.
- Fix: flush + fsync the temporary file before replace; on POSIX fsync the parent directory after replace. Any fsync error raises through fail-closed persistence. Windows keeps file fsync and skips directory fsync.
- Tests: `tests/test_state_persistence.py` 53/53; verifies expected fsync calls and that file-fsync failure preserves prior backup and removes temp file.
- Commits: engine `3f2df9b78b9149e9f820dfc8d67140dbff7ba866`; tests `8d41fe9823d2465fe1ae64d674ed94a18027e4a2`.
- CI: [Research engine checks #41447569454](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41447569454), SUCCESS; compile, configured deterministic suites and secret scan passed.
- Decision: ACCEPT for improved local crash-durability. No market PnL sweep, production deployment or live order.
- Limitation: fsync is an OS/filesystem durability request, not an absolute hardware guarantee; Windows does not receive parent-directory fsync in this implementation.


### ENG-STATE-017 follow-up regression

- Added POSIX test for parent-directory fsync failing after atomic rename. It confirms save raises even though the new file is already visible, and the temp file is absent; caller must stop because directory-entry durability was not confirmed.
- Test commit: `dd808b3cb83e1308a26490f16582d26498fe0709`.
- CI: [Research engine checks #41447862710](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41447862710), SUCCESS; persistence tests 54/54.


## ENG-RECON-002 — strict read-only Bybit V5 snapshot parsers (2026-11-02)

- Added `bybit_reconciliation.py`; pure parser for fully paginated caller-supplied V5 positions, active orders and executions.
- Validates retCode, row shapes, decimals, positionIdx, partial order quantities, multiple executions per order, funding records, duplicate identities and pagination cursor continuity/completion.
- Tests: `tests/test_bybit_reconciliation.py` 13/13.
- Commits: parser `fa97a4810e14d5d7590c5c4794ba2f98856127da`; workflow `95e5afb46a2869957e90742560f95d21089ddad5`; test import fix `b6d2fe255e692fa001fef5cf86274863485ae26d`.
- CI: [Research engine checks #41448898597](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41448536690), SUCCESS; parser 13/13, persistence 54/54, compile, configured deterministic suites and secret scan passed.
- Decision: ACCEPT as parser-only milestone. No HTTP calls, credentials, account reads, order mutations or PnL backtests.
- Limitation: does not collect all pages, establish snapshot freshness or compare exchange state to local state. Overall reconciliation remains BLOCKED by missing exact local qty and exchange identifiers.


### ENG-RECON-002 strict retCode follow-up

- Parser now rejects boolean `retCode=False` even though Python considers `False == 0`; only an actual integer zero is accepted as API success.
- Tests: 13/13. Test commit `9fdaa02d764495a59747f0930e89fa677d03b890`.
- CI: [Research engine checks #41448898597](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41448898597), SUCCESS; parser 13/13 and persistence 54/54.


## ENG-RECON-003 — read-only Bybit V5 snapshot collector (2026-11-02)

- Card: [ENG-RECON-003](experiment_cards/ENG-RECON-003_READONLY_COLLECTOR_RU.md).
- Added `scripts/bybit_reconciliation_snapshot.py`: read-only API-key verification, enforced official-host allowlist, redirect refusal in the actual HTTP opener, server-time bounds, cursor pagination, seven-day execution windows, execId deduplication, raw SHA-256 and atomic fsync artifact write.
- Mocked tests: 12/12 passed; parser: 14/14 passed after ENG-RECON-005.
- CI: [Research engine checks #41457143134](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41457143134), SUCCESS. Compile, configured deterministic suites, collector/parser tests, secret scan and persistence suite completed.
- A prior run #41452045788 failed on the non-Bybit host test because the allowlist validation was not yet called from `collect_snapshot()`. Fixed by wiring `_validate_base_url()` into the entry point and using a no-redirect opener; regression run #41457143134 passed.
- Decision: ACCEPT for collector code + fixture/CI coverage only. No live Bybit call was made and no real snapshot exists.
- Limitations: no order history or exchange-side stop/TP verification; local model still lacks exact qty, positionIdx and order/execution identities. Reconciliation and live resume remain BLOCKED. No PnL sweep.


## ENG-RECON-004 — report-only comparator (2026-11-02)

- Card: [ENG-RECON-004](experiment_cards/ENG-RECON-004_REPORT_ONLY_COMPARATOR_RU.md).
- Added `scripts/bybit_reconciliation_report.py`: validates backup/snapshot schema, canonical raw SHA-256, parsed positions/orders/executions, counts, server-time chronology and contiguous <=7-day execution windows; reports symbol/direction diagnostics.
- Comparator intentionally **always blocks**: `BLOCKED_UNSUPPORTED_LOCAL_MODEL`, `reconciliation_pass=false`, `live_resume_allowed=false`. It does not infer exchange qty from notional, match pending signal intents to orders, or declare empty-state reconciliation without a local execution ledger.
- Tests: 16/16 passed. CI: [Research engine checks #41460727701](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41460727701), SUCCESS; parser 14/14, collector 15/15, comparator 16/16, configured deterministic suites and secret scan passed.
- No real Bybit snapshot was captured or compared. No order history or exchange-side stop/TP check. Overall reconciliation/live resume remain BLOCKED. No PnL sweep.


## ENG-RECON-005 — exchange-side position protection visibility (2026-11-02)

- Card: [ENG-RECON-005](experiment_cards/ENG-RECON-005_POSITION_PROTECTION_RU.md).
- Bybit position parser now preserves optional `takeProfit`, `stopLoss`, `trailingStop`, `tpslMode`; report identifies configured stop, absent stop or unknown fields.
- Official schema: [Bybit V5 Get Position Info](https://bybit-exchange.github.io/docs/v5/position).
- Parser: 14/14; comparator: 14/14; collector: 12/12. Full CI [#41459486381](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41459486381), SUCCESS.
- This only reports position-level configuration; it does not prove conditional-order health or stop trigger execution. No live Bybit request or real snapshot. Overall reconciliation/live resume remain BLOCKED.


## ENG-RECON-006 — paginated historical order capture (2026-11-02)

- Card: [ENG-RECON-006](experiment_cards/ENG-RECON-006_ORDER_HISTORY_RU.md).
- Collector now calls `GET /v5/order/history` in <=7-day intervals, collects every cursor page, parses rows and deduplicates by `orderId` using latest `updatedTime`; conflicting same-time records fail closed.
- Snapshot explicitly records `QUERYABLE_WINDOW_ONLY_NOT_COMPLETE`. Bybit documents that cancelled/rejected/deactivated statuses are queryable only in the last 24h; beyond 7d only orders with fills are queryable; endpoint data may be delayed. It is not a complete event journal.
- CI: [Research engine checks #41460727701](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41460727701), SUCCESS; parser 14/14, collector 15/15, comparator 16/16, persistence 54/54, configured suites and secret scan passed.
- No real Bybit request or snapshot. Comparator remains permanently BLOCKED until local exchange identities and execution ledger exist. No PnL sweep or live resume.


### ENG-RECON-003 follow-up — cross-interval execution identity integrity (2026-11-02)

- Confirmed risk: overlapping/adjacent seven-day execution windows can surface the same `execId`. Silent dict overwrite would hide conflicting payloads.
- Added shared `deduplicate_executions()` in `bybit_reconciliation.py`: exact duplicates deduplicate; same ID with differing fields raises `SnapshotValidationError`.
- Wired strict deduplication into both snapshot collector and report-only comparator.
- Added parser tests for exact and conflicting duplicates, plus comparator-level tampered cross-interval fixture.
- CI: [#41467807857](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41467807857), SUCCESS — parser 15/15, collector 15/15, comparator 17/17; full workflow passed.
- Status: ACCEPT for code/fixture coverage only. No live exchange capture. Reconciliation/live resume remains BLOCKED.


## ENG-DATA-001 — public instrument snapshot collector hardening (2026-11-02)

- Card: [ENG-DATA-001](experiment_cards/ENG-DATA-001_INSTRUMENT_SNAPSHOT_COLLECTOR_RU.md).
- Hardened public `instruments-info` collector with official host allowlist, redirect refusal, strict integer `retCode`, cursor type validation and 1,000-page cap.
- 13 deterministic tests passed in full Research checks [#41468327832](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468327832).
- Actual public fetch attempt [#41468304134](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468304134) ended in HTTP 403. No snapshot created; do not interpret as an empty universe or invent substitute specs.
- Snapshot workflow now runs weekly/manual only. The historical instrument-spec gate remains BLOCKED pending a real dated snapshot.


### ENG-RECON-002 follow-up — parser page-chain safety cap (2026-11-02)

- Added a 1,000-page maximum to the shared strict parser, matching the collector's pagination cap. The report-only comparator inherits this guard for all position/order/execution page chains.
- Added a regression test for a 1,001-page input. Full Research checks [#41468736376](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468736376) passed; parser suite 16/16.
- This limits pathological or corrupted inputs; it does not prove the exchange supplied all pages.


## ENG-SEC-001 — private Bybit API credential preflight hardening (2026-11-02)

- Card: [ENG-SEC-001](experiment_cards/ENG-SEC-001_PRIVATE_API_CHECK_RU.md).
- Confirmed and fixed arbitrary HTTPS host acceptance, redirect following with auth headers, boolean `False == 0` retCode acceptance and boolean `True == 1` readOnly acceptance in `scripts/bybit_private_api_check.py`.
- Added official-host allowlist, redirect refusal, strict integer response checks and no response-body logging.
- 10 mocked regression tests passed; full Research checks [#41469608200](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41469608200), SUCCESS including secret scan.
- No real API key or private request was used. Manual credential check remains unrun; no account permissions are claimed as verified.


### ENG-RECON-003 follow-up — explicit USDT execution scope (2026-11-02)

- Found a scope mismatch: positions and order-history calls used `settleCoin=USDT`, but `/v5/execution/list` did not. For `category=linear`, that could mix settlement universes.
- Added `settleCoin=USDT` to execution-history requests and asserted the query parameter on every history/execution call in the mocked collector test.
- CI: [#41470373006](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41470373006), SUCCESS; full Research workflow passed.


## E10 / E11 / E13 — уточнение сопоставимости временного покрытия (2026-11-02 audit)

Проверка ZIP-артефактов и исходных скриптов выявила важное ограничение при сравнении E10 с E11:

- E10 запускает каждый символ на его собственной временной последовательности свечей в фиксированных UTC fold bounds.
- E11 и E13 строят пересечение timestamps всех 47 включённых символов и используют общий синхронизированный replay из 4,321 бара.
- В manifest 25 символов имеют fold counts 1,314 / 1,314 / 1,753 (4,381 бар в сумме по fold windows), а 22 символа — 1,278 / 1,314 / 1,729 (4,321 бар). У 25 длинноисторических символов E10 включает дополнительно 36 часов в fold 1 и 24 часа в fold 3 на каждый символ, которых нет в common intersection E11/E13.
- Manifest E11/E13 сохраняет per-symbol source coverage до пересечения timestamps; фактическое синхронизированное покрытие отражено в summary как common_bars=4,321.

Следствие: E10 per-symbol aggregate PnL и E11 shared-capital PnL — разные estimands. Их разница не может быть приписана только переходу от независимых счетов к общему капиталу; влияет и разное фактическое временное покрытие. Для строгого сравнения E10 и E11 потребовался бы повтор E10 на том же 4,321-bar common timestamp set. Рыночные результаты старых fold windows уже просмотрены, поэтому такой повтор был бы диагностическим, а не новым holdout.

Сравнение E11 baseline с E13 compression-OFF baseline остаётся валидным: одинаковые шесть source archive hashes, одинаковое common timestamp set, точное совпадение per-fold baseline metrics. E13 compression-ON улучшает суммарный PnL на 436.89 USDT, но общий результат остаётся отрицательным.


## ENG-FUND-001 — funding при совпадении settlement и TP1 boundary (2026-11-02)

- Preregistered card: [ENG-FUND-001](experiment_cards/ENG-FUND-001_TP1_BOUNDARY_RU.md).
- Confirmed issue: TP1 timestamp is the candle-close boundary (`_manage_position()` passes `exit_ts` into `_apply_tp1()`). When funding settlement shares that timestamp, OHLC cannot establish event order. Existing helper always used full initial quantity at `ts <= tp1_ts_ms`, which correctly maximized a payment but also maximized a receipt and could overstate equity.
- Test-first CI [#41501387632](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41501387632) reproduced it: receipt test observed `-10.00` instead of conservative `-5.00`; remaining tests in the funding suite passed.
- Fix commit: `d88e7d900768d5b2bbdc67963fe2ff8c1d2f40f5`. At exact TP1 boundary, use full quantity for a positive funding cost (payment), remaining fraction for a negative funding cost (receipt). Before/after boundary behavior unchanged.
- Follow-up CI [#41501468001](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41501468001): full workflow completed SUCCESS, including compile, funding accounting, realized funding, MTM funding, coverage preflight, private API mock tests, reconciliation suites, regime suites, gap/time/portfolio/persistence tests and secret scan.
- Decision: FIXED; regression and all substantive test steps pass. Awaiting GitHub workflow finalization for a terminal run conclusion.
- No market backtest, parameter sweep, production deployment, private API request or live order.


## ENG-FUND-002 — funding при полном закрытии на settlement boundary (2026-11-02)

- Карточка: [ENG-FUND-002](experiment_cards/ENG-FUND-002_FINAL_CLOSE_FUNDING_BOUNDARY_RU.md).
- Test-first CI [#41502110789](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41502110789) воспроизвёл отсутствие final-close context: четыре новых случая упали с `TypeError: unexpected keyword argument 'closed_ts_ms'`.
- Исправление: `accrued_funding_cost()` принимает `closed_ts_ms`; если funding settlement совпадает с полным закрытием, payment считается на полном начальном объёме, receipt — на нулевом. `_close_position()` передаёт `exit_ts`.
- Добавлены engine-level тесты реальной записи trade ledger: receipt=0, payment=10 USDT для позиции 1,000 USDT при ставке 1%.
- Full Research CI [#41502251992](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41502251992), SUCCESS; funding, realized PnL, MTM, portfolio и остальные configured suites прошли.
- Решение: ACCEPT для realized PnL. Не является доказательством рыночной доходности.
- Оставшийся риск pre-exit MTM вынесен в ENG-FUND-003: до определения исхода свечи MTM может временно зачесть receipt на текущей границе.


## ENG-FUND-003 — funding receipt на pre-exit MTM boundary (2026-11-02)

- Карточка: [ENG-FUND-003](experiment_cards/ENG-FUND-003_MTM_BOUNDARY_RECEIPT_RU.md).
- Подтверждён порядок событий: adverse intrabar mark и portfolio MTM выполняются до разрешения stop/TP в `_manage_position()`. При совпадении funding settlement с текущей MTM-границей OHLC не задаёт порядок событий.
- Риск: receipt мог временно увеличить equity до определения исхода свечи и частично скрыть adverse mark при daily-stop / kill-switch проверке.
- Исправление: `accrued_funding_cost(..., defer_boundary_receipts=True)` откладывает receipt на точной текущей MTM-границе до следующего mark; payment продолжает учитываться немедленно. Если позиция остаётся открытой, receipt начисляется на фактический остаток объёма; полное закрытие на этой границе обработано ENG-FUND-002.
- Проверки: long/short receipt, TP1 reduced quantity и payment boundary. Полный Research CI [#41503287534](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41503287534), SUCCESS, commit `037aabd80769be88ea6ed99b05855665da92230d`.
- Отдельно проверен CI harness: все 21 тестовых файла, вызываемых workflow напрямую через `python tests/...`, имеют исполняемый `__main__`; plain-function suites имеют явные runners, unittest suites запускают `unittest.main()`. В логах подтверждены 27/27 gap, 38/38 time model, 5/5 timeframe, 16/16 portfolio accounting и 54 persistence tests.
- Решение: ACCEPT только для консервативного funding/MTM учёта. Не доказывает рыночную доходность; backtest и live execution не запускались.


## ENG-PERSIST-001 — немедленное сохранение MTM risk-stop latch (2026-11-02)

- Карточка: [ENG-PERSIST-001](experiment_cards/ENG-PERSIST-001_MTM_RISK_STOP_PERSISTENCE_RU.md).
- Подтверждён дефект: `_update_mark_to_market()` мог установить `daily_stop_triggered` / `kill_switch_triggered`, но не сохранял backup, если в этом событии не происходило закрытие позиции или изменение pending. При аварийном рестарте latch мог быть потерян.
- Test-first CI [#41504537789](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41504537789) упал на новом тесте daily-stop с AssertionError: persistence spy не был вызван.
- Исправление: `_update_mark_to_market()` вызывает `_persist()` при новом переходе daily-stop или kill-switch в true. Запись на каждом обычном candle MTM не добавлена.
- Первый post-fix прогон выявил неполную тестовую фикстуру `test_funding_mark_to_market.py` (объект `__new__` без persistence stub); фикстура исправлена отдельно, без изменения production-логики.
- Full Research CI [#41504995009](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41504995009), SUCCESS; portfolio accounting и state persistence прошли.
- Решение: ACCEPT для durability risk-stop latch. Никакого market backtest, parameter search, private API request или live order.


## ENG-PERSIST-002 — синхронизация MTM и сохранения после TP1 (2026-11-02)

- Карточка: [ENG-PERSIST-002](experiment_cards/ENG-PERSIST-002_TP1_MARK_TO_MARKET_SYNC_RU.md).
- Test-first [#41506138601](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41506138601) воспроизвёл рассинхронизацию: после `_manage_position()` TP1 уже был отмечен, но `risk_mgr.unrealized_pnl` оставался pre-TP1; новая проверка упала на сравнении с `_unrealized_pnl_at_marks()`.
- Исправление: после surviving TP1 transition выполняется MTM на той же bar-close границе; после каждого candle management открытая позиция сохраняет обновлённые `bars_held`, MFE/MAE и trailing stop. При закрытии сохранение по-прежнему выполняет `_close_position()`.
- Full Research CI [#41506990147](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41506990147), SUCCESS; portfolio suite 21/21. Новые тесты TP1 MTM, persistence открытой позиции и same-bar TP1/stop order-independence прошли.
- Решение: ACCEPT для согласованности accounting и durability open-position lifecycle. Рыночная доходность не тестировалась.

- Дополнительная проверка [CI #41507219610](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41507219610), SUCCESS: одновременные TP1 BTCUSDT + stop ETHUSDT и два stop-close в одной временной точке дали одинаковый итог при перестановке порядка символов. Обе записи закрытия создаются ровно по одному разу; realized equity = стартовый капитал + сумма net PnL, unrealized после двух закрытий = 0. Portfolio suite 22/22; persistence suite 54 tests.


## ENG-PERSIST-003 — сохранение last marks при восстановлении открытых позиций (2026-11-02)

- Карточка: [ENG-PERSIST-003](experiment_cards/ENG-PERSIST-003_RESTORE_LAST_MARKS_RU.md).
- Дефект: резервное состояние сохраняло risk equity и open positions, но не `_last_mark_prices`. После рестарта `_unrealized_pnl_at_marks()` подставлял entry price для ещё не обновлённых символов, из-за чего первое MTM могло потерять накопленный PnL и исказить equity/risk budget.
- Test-first CI [#41509292651](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41509292651) на pre-fix engine завершился ошибкой в persistence suite: шесть `TypeError` из-за отсутствия аргумента `last_mark_prices`.
- Исправление: `_persist()` передаёт цены последней отметки; `save_state()` валидирует и сохраняет конечные положительные цены для каждого open position; `load_state()` требует точное покрытие символов и восстанавливает карту в engine. Старые backups с открытыми позициями без last marks отклоняются fail-closed.
- Full Research CI [#41509504557](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41509504557), SUCCESS; 58 state-persistence tests. Проверены restore mark/equity, отсутствие mark и invalid values (zero/negative/NaN/Inf/bool).
- Ограничение: last mark — сохранённый recovery snapshot, а не свежая биржевая цена; он не заменяет exchange reconciliation и не гарантирует актуальность после длительного downtime. Live trading не запускался.

- Дополнительный engine-path тест подтвердил, что `_persist()` реально передаёт last marks в backup и новая persistence instance их восстанавливает. Full Research CI [#41509795468](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41509795468), SUCCESS; state-persistence suite 59 tests.

- Дополнительный regression: восстановленный Plan-B state блокирует запуск `run_simulation_pass()` как нового backtest (fail closed). CI [#41511547342](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41511547342), SUCCESS; state-persistence suite 60 tests.


## ENG-METRIC-001 — order-independent portfolio drawdown (2026-11-02)

- Карточка: [ENG-METRIC-001](experiment_cards/ENG-METRIC-001_SIMULTANEOUS_DRAWDOWN_ORDER_RU.md).
- Дефект подтверждён test-first: `MaintenanceGateAuditor.evaluate_portfolio()` считал drawdown по последовательности элементов списка, а не по времени. Одновременные сделки могли давать разный max_dd в зависимости от порядка; несортированный список мог нарушать хронологию.
- Test-only CI [#41512547727](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41512547727) failed на `test_drawdown_is_order_independent_for_simultaneous_trade_closes` (AssertionError).
- Fix: PnL закрытий агрегируется по UTC `exit_date`, группы применяются к equity в хронологическом порядке. Невалидные и timezone-naive timestamps fail closed.
- Full Research CI [#41512721144](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41512721144), SUCCESS; portfolio accounting 24/24, обе новые регрессии PASS; state persistence 60 tests.
- Это исправление отчётной метрики, не стратегии и не доказательство прибыльности.

- Follow-up проверка расширила same-bar stop permutation tests сравнением `risk_mgr.max_drawdown_pct`; порядок обхода BTC/ETH не меняет MTM drawdown в тестируемых сценариях. CI [#41513430881](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41513430881) SUCCESS; portfolio 24/24, persistence 60.


## ENG-METRIC-002 — fail-closed finalization requires marks for every open position (2026-11-02)

- Test-first reproduction: [Research CI #41515565933](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41515565933) failed in `test_finalize_rejects_missing_open_position_marks`. `finalize_open_positions()` accepted a marks map that omitted BTCUSDT and silently fell back to that position's entry price, creating a synthetic zero-price-move exit instead of rejecting incomplete input.
- Fix commit: `cc756497d6375c9ba08805699bacebafb82e752d`. Before MTM or closing any position, finalization now checks that every currently open symbol is present in `marks`; missing symbols raise a ValueError listing the symbols.
- Full Research CI [#41515639337](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41515639337), SUCCESS. Portfolio accounting suite 25/25; the new fail-closed regression passed. Gap 27/27, time model 38/38, timeframe validation 5/5 and persistence suite passed.
- Scope: protects incomplete caller input. The standard `run_simulation_pass()` caller already builds final marks from its selected symbol set; this does not by itself establish a historical PnL change. No market backtest, data modification, private API request or live order.

## Rejected hypothesis — same-bar newly tightened trailing stop (2026-11-02)

- Reviewed `_manage_position()` behavior after TP1 when the same OHLC candle also crosses the newly calculated trailing stop.
- Initially considered this a missed stop, but existing regression `test_new_trailing_stop_is_not_applied_retroactively_to_same_candle` explicitly encodes the policy: a stop calculated from the current candle's favorable high/low becomes active on the next candle only. OHLC cannot establish whether the favorable extreme preceded the adverse extreme.
- No code change warranted. The temporary test proposal was discarded; do not classify this behavior as a confirmed defect without changing the strategy's documented intrabar policy.


## E01–E03 — первичная provenance-сверка workflow и артефактов (2026-11-02)

Проверены GitHub run metadata, исходные workflow/scripts на commit `4e27b6adf8c3199ce78446d33703984394c94152`, загруженные CSV-артефакты и агрегаты.

### E01 — H1 Direction and Execution Ablation
- Run [40578394090](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578394090), branch `research/market-regime-v1-main`, commit `4e27b6adf8c3199ce78446d33703984394c94152`, workflow `.github/workflows/h1-direction-execution-ablation.yml`.
- Workflow blob SHA `c6036c8c63b1db78a9264ba4f4027bb2c4ce33c9`; strategy script blob SHA `7178fa588cf43ef67fd748037f04643be5cf21e6`; dataset loader blob SHA `a02af75b4ba8311b3ab46ae993c14996d4107a4c`; engine blob SHA `e4501bd3666d7fe25ae8c1a10a9813da89b535dd`.
- Artifact `h1-direction-execution-ablation`, 13,732 bytes, SHA-256 `a61dfb45f41792ae4dbfb2e0f09975b389e6b0aa1c6d89c64824087065823ebc`; CSV has 600 rows = 50 symbols × 3 folds × 4 variants.
- Independent recomputation from the downloaded CSV exactly matches ledger totals: both_market −16,911.93 USDT / 2,699 trades; long_market +1,056.65 / 1,458; both_limit20 −261.36 / 2,395; long_limit20 +9,823.41 / 1,308. Long-only market remains regime-sensitive: fold nets +2,815.06 / −732.75 / −1,025.66 USDT. Long-only limit20 fold nets +5,369.05 / +1,543.67 / +2,910.69.
- Cross-checked against E11/E13's archived SHA-256 manifest: the same six ZIP blobs (their Git blob SHAs match at the E01 and E11 commits) have SHA-256 values `c7ed7f08de10360468193d9a791a8aaf119603fa409c332765fb4761af117bfc` (2025-10-27...123436), `ca9d13dd891613ed7948071edfbead77c54541721d4389c697e1e6422353921d` (2025-10-27...123811), `774a408ec47485322771afd91601908f58703ddd29b5b75020cb4b2bc2f9716d` (2025-10-27...124334), `8d75012e8daf4987796ac8f0d2acf5b4396a8db1e06fbd99a1b92dcbadb448e8` (2026-10-26...170116), `f18cccf304ccfebe3674526a60ce9408efb21be7cb3c463d5dff11b7ce94eb09` (2026-10-26...230422), and `3fa8c24850d22546488f6c72e4e1014ba5d4b9ca7299ec0e5f1a0b4d951a3ed5` (2026-10-26...230719).
- All six source ZIPs are present in the exact run commit. Git blob SHAs: `2025-10-27...123436.zip` = `85b279d81ad9e81ec502b52adf4e1c6f5a459094`; `2025-10-27...123811.zip` = `86492adf07c6911e90ce128997d4ab5111f1f7d9`; `2025-10-27...124334.zip` = `f161c89f2002d13e11cf2cc85a94bd5828eeda5a`; `2026-10-26...170116.zip` = `6e3807e2d596726f5f1b5dd9d2b4397a9eb0dcee`; `2026-10-26...230422.zip` = `20faac7bb9e1caf29ae4e2fc55c1bb9012d9f538`; `2026-10-26...230719.zip` = `abdc80e73dbb37c81e070b3cd31a2a5cf88647ec`.

### E02 / E03 artifact checks
- E02 run [40578394009](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578394009), artifact SHA-256 `66483e95ece78e773dd47494bbbdfd8bd2a738f7f6be1e28958463d622122c83`, 174 rows. Recomputed 1h selected-policy aggregate −5,999.65 USDT across 150 symbol-fold rows / 2,509 trades; market comparator −16,911.93. 71/150 selected H1 rows positive. 15m selected aggregate −11,470.98 vs market −24,039.44.
- E03 run [40578393971](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/40578393971), artifact SHA-256 `880e4408f2d8ee2bd3e054ef76b43f06d089843da7086a2282999858645bfd66`, 754 rows. H1 market baseline −5,923.64; limit 10 bps / 3 bars +1,204.81; 10 bps / 5 bars +1,565.78; 20 bps / 3 bars +3,143.13. These are per-symbol parameter cells, not a shared-capital portfolio. 15m aggregate across all tested execution cells is not a valid single-strategy comparison; the market baseline remains −12,562.42.
- Interpretation unchanged: artifact and code provenance for E01–E03 is now substantially stronger, but the CSVs do not contain a SHA-256 manifest for each source archive. Git blob IDs at the run commit identify the exact committed ZIP objects. Binance OHLCV proxy, modelled fees/slippage and optimistic OHLC limit-touch fills remain decisive execution limitations; none of these runs establishes Bybit-executable profitability.


## ENG-EXEC-004 — short-side TP1 → trailing stop lifecycle coverage (2026-11-02)

- Added mirrored short-side regression in `tests/test_gap_execution.py`: TP1 partial close is recorded, remaining 50% is later closed by the updated trailing stop, and TP1 realized gross PnL/remaining fraction are preserved.
- Full Research CI [#41517776602](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41517776602), SUCCESS. Gap execution, portfolio accounting, funding, instrument-spec, reconciliation and persistence suites all completed successfully.
- This closes a test-coverage asymmetry only. No production-engine behavior changed and no new trading edge or execution realism is claimed.


## ENG-DATA-002 — dated Bybit risk-limit tier archive collector (2026-11-02)

- Official V5 `GET /v5/market/risk-limit` collector added at `scripts/snapshot_bybit_risk_limits.py`. It paginates the full linear universe, validates tier identifiers and finite numeric fields, rejects duplicate tiers/repeated cursors/empty responses, restricts requests to official HTTPS hosts, refuses redirects, suppresses HTTP bodies, and writes timestamped snapshots atomically with fsync.
- Added weekly/manual workflow `.github/workflows/bybit-risk-limit-snapshots.yml`; network capture is deliberately not part of CI. No API credentials are required or used.
- Offline tests: 9/9 passed. Full Research CI [#41518145630](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41518145630), SUCCESS. Includes existing instrument specs, sizing, funding, reconciliation, regime, gap, accounting and persistence suites.
- Important limitation: this is a prospective point-in-time archive, not a historical risk-tier source. Current risk tiers must not be backdated to earlier test periods. The workflow has not yet captured a real snapshot; previous public Bybit metadata access returned HTTP 403. No proxy or access-control bypass attempted.


## ENG-DATA-003 — официальный архив funding settlements и mark-price H1 (2026-11-02)

- Добавлен scripts/archive_bybit_market_history.py для GET /v5/market/funding/history и GET /v5/market/mark-price-kline (linear).
- Funding выгружается короткими непересекающимися окнами с обязательными startTime + endTime; насыщение лимита 200 строк приводит к ошибке, а не к тихо неполному архиву. Mark klines запрашиваются окнами до 899 H1-свечей, сортируются по времени и сверяются с полной ожидаемой часовой сеткой; любой пропуск останавливает сбор.
- Сборщик проверяет числовые значения, OHLC-инварианты, символ, временные границы, запрещает редиректы и неофициальные API-хосты, ограничивает имена символов безопасным ASCII-форматом, пишет CSV атомарно, выдерживает паузу между окнами и отбрасывает текущую незакрытую H1-свечу.
- Формат funding CSV совместим с scripts/validate_funding_coverage.py; после загрузки workflow требует точного совпадения каждого funding settlement timestamp с open timestamp mark-price H1 candle.
- Добавлен manual workflow .github/workflows/bybit-market-history-archive.yml. Каждый запуск сохраняет отдельную папку с start_ms, end_ms, GitHub run id, чтобы повторная выгрузка не затирала предыдущий архив. После preflight архив коммитится только в research branch.
- 11/11 новых offline tests прошли в CI #41518707514 (SUCCESS). Последующий кодовый commit 83af4e662e1f66a28a8dce5e064fbedb54347c0c прошёл тестовые шаги полного CI #41518737084 без ошибок; завершение runner cleanup проверялось отдельно.
- Источники и ограничения: endpoint definitions сверены с официальными Bybit V5 docs. Реальный API capture ещё не выполнен; предыдущий доступ к публичным Bybit API из GitHub Actions давал HTTP 403. Не утверждать, что история уже скачана. Нет обхода региональных ограничений.
- Funding cost helper по-прежнему использует H1 mark candle open как timestamp-aligned proxy, а не подтверждённую точную settlement mark price. Данные не подменяют реальную биржевую settlement price; до получения точного settlement mark модель остаётся приближённой.


## ENG-DATA-004 — Bybit-native H1 OHLCV added to market archive (2026-11-02)

- archive_bybit_market_history.py now archives native Bybit linear trade OHLCV from /v5/market/kline in addition to funding history and mark-price klines.
- Trade and mark H1 candles are independently fetched in bounded 899-candle windows; both require a complete timestamp grid, valid OHLC ordering, finite/non-negative volume and turnover, and a closed-candle end boundary.
- Added kline/ output per symbol. Coverage preflight now optionally requires exact equality of trade-kline and mark-kline timestamp sets, in addition to funding settlement timestamps matching mark candle opens.
- Added offline tests for sorted trade candles, incomplete OHLCV coverage, invalid volume/turnover, and trade-vs-mark timestamp mismatch. On code commit 9a94ee7d793e99cdbcc14da6a8eaffce0484dc6f, collector and coverage test steps both passed; full Research CI test steps showed no failures, but Actions runner cleanup had not yet returned a terminal conclusion at time of this note.
- This removes a future dependency on Binance OHLCV for the Bybit-native replay, but does not retroactively change E01–E13. Those experiments remain Binance-proxy results until rerun with captured Bybit data.
- Actual API download remains unverified because previous public Bybit requests from Actions returned HTTP 403. No archive data is claimed to exist yet.


## ENG-DATA-005 — Adaptive funding pagination and final CI (2026-11-02)

- Funding archive no longer stops at the first full 200-row Bybit response. It recursively subdivides saturated time windows and re-requests each half; if saturation persists at the minimum 1 ms width, it fails closed.
- Added regression tests for adaptive subdivision and minimum-width saturation. Research CI run #41520724088 completed SUCCESS on commit 77fee281686a2ca29bdf295e3b8dcc011ea856e4; all 23 test steps succeeded. Run #41520495668 remained in progress during runner cleanup when last checked; do not treat it as terminal success.
- Previous intermediate run #41520465851 failed only because it ran against the old test expecting immediate failure on a saturated page. The test was replaced with adaptive-pagination coverage and the subsequent full CI #41520724088 passed.
- The API archive workflow still requires a manual dispatch. This GitHub connection has no workflow-dispatch action; no Bybit API data has been fetched or claimed. No main-branch change and no live orders.



## ENG-DATA-006 — point-in-time linear universe collector (2026-11-03)

- Официальный Bybit V5 API Explorer указывает статусы `PreLaunch`, `Trading`, `Settling`, `Delivering`, `Closed`; документация инструмента содержит `launchTime` и `deliveryTime`. Основной instruments-info collector ранее не передавал `status` и получал default Trading/PendingOpen.
- Добавлен `scripts/snapshot_bybit_linear_universe.py`: запрашивает default Trading/PendingOpen плюс все документированные status filters, обходит pagination, валидирует status/symbol/launch/delivery и конфликтующие дубликаты, сохраняет датированный immutable snapshot в `data/universe_history/linear/`.
- Добавлен lifecycle predicate только для LinearPerpetual USDT-settled. Он использует launch/delivery bounds; Closed/Settling/Delivering без deliveryTime fail closed. Это границы жизненного цикла, а не доказательство отсутствия временных suspension или фактической доступности новых ордеров.
- Добавлены offline regression tests и manual-only workflow `.github/workflows/bybit-linear-universe-history.yml`. Существующий instrument-spec snapshot workflow переведён на schedule/manual-only, чтобы обычный push к collector code не инициировал сетевой запрос.
- Research CI [#41540392254](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41540392254), SUCCESS, commit `041b7eb2f26d65ff26242e56163529174de538df`, 33/33 job steps completed without failures. Новый collector test step прошёл.
- Параллельный автоматический запуск старого instrument-spec snapshot workflow [#41540268697](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41540268697) завершился HTTP 403 на `api.bybit.com`; snapshot step failed, commit step skipped. После этого push-trigger удалён; новый point-in-time workflow вручную не dispatch-ился. Никакого нового Bybit snapshot не создано и не заявляется.
- Ограничение: status=Closed retention и соответствие launch/delivery историческому факту торговой доступности ещё не подтверждены реальным capture. Перед использованием universe для бэктеста требуется успешный non-empty capture и cross-check с официальными listing/delisting announcements. E01–E13 не пересчитаны; market backtests не запускались.
- Code commits: `b424fdae1d2db583b00cce7c3fd47443c8bb44f8` (collector/workflow/CI wiring), `af47dca34628d8556dedbc1712c89508236912a0` (strict lifecycle bounds), `041b7eb2f26d65ff26242e56163529174de538df` (tests); latest docs commit at this note: `ad8bdae12a71472c979f98b576053756051e99d8`.


## ENG-DATA-007 — CryptoFetch archive overlap/provenance audit (2026-11-03)

- Confirmed loader behavior in `scripts/run_uploaded_dataset_backtests.py::read_zip_datasets`: for each symbol/timeframe it sorts candidate ZIP members by `(row_count, archive_path)` descending and selects the first. It does not compare overlapping OHLCV values, timestamp-set inclusion, or whether the longest file is a superset of shorter candidates.
- Added `scripts/audit_cryptofetch_archives.py`, a read-only scanner that inventories ZIP/member SHA-256, bar counts, time bounds and gaps; pairwise compares timestamp overlap and OHLCV equality; and reports whether the legacy longest-file winner actually contains every timestamp in each compared candidate.
- Added offline tests for identical overlap, a longest-but-not-superset case, conflicting OHLCV, and report writing.
- Research CI runs deterministic unit tests. The dedicated `.github/workflows/cryptofetch-archive-audit.yml` scans all checked-in CryptoFetch ZIPs when archive/code paths change and uploads CSV/JSON/Markdown diagnostics. A detected conflicting overlapping candle fails the audit step; non-superset selections are reported for review. Structurally valid one-row files are reported as below the legacy 200-bar eligibility floor, not as malformed datasets.
- No dataset is merged, rewritten, or substituted by this audit. E01–E13 inputs and historical PnL remain unchanged until the report is inspected and a deterministic conflict/coverage policy is approved by evidence.


### ENG-DATA-007 — результат полного CryptoFetch archive scan

- Dedicated audit run [#41542079766](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41542079766) завершился SUCCESS на code commit `627b005edc20424ba3b4e5e094612ed063dce521`; artifact [#13187466159](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41542079766/artifacts/13187466159).
- Research CI [#41542100415](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41542100415) завершился SUCCESS на commit `0546f53a45bb4508d1f16ba06bbb310cdd69b1de`; compile + deterministic archive-audit tests passed.
- Полный scan: 67 CSV members, 67 structurally valid, 64 содержат не менее 200 свечей (legacy loader minimum), 3 пустых CSV (DAIUSDT/MATICUSDT/XMRUSDT; loader их и так пропускает), 0 malformed members.
- В архивах 6 duplicate symbol/timeframe groups, 6 pairwise comparisons: 0 conflicting OHLCV overlap candles; 0 случаев, когда legacy longest-file winner не является timestamp superset пары. Для всех 67 members сумма missing/irregular interval gaps = 0.
- Duplicate detail: AAVEUSDT, DOTUSDT, TAOUSDT — 4,321-bar subset полностью совпадает с соответствующими 4,321 timestamps в 8,761-bar archive; ENAUSDT, ONDOUSDT, QNTUSDT — две 8,761-bar копии полностью совпадают.
- Все шесть SHA-256 из E11 и E13 artifact manifests совпадают с текущими SHA-256 тех же ZIP-файлов. Это подтверждает, что скан проверил именно те архивные байты, на которых были выполнены E11/E13.
- Вывод: текущая эвристика longest-file selection не привела к выявленному конфликту или потере покрытия в этих конкретных архивах. Это снимает текущий duplicate-archive blocker для E11/E13 inputs, но не заменяет Bybit-native market data и point-in-time universe. Будущие архивы по-прежнему должны проходить такой scan.


## ENG-EXEC-008 — dated Bybit risk-tier entry gate (2026-11-03)

- Добавлен `bybit_risk_tiers.py`: as-of загрузка датированных Bybit V5 risk-limit snapshots, выбор первого tier, покрывающего notional, fail-closed на отсутствующем/устаревшем snapshot, отсутствующем symbol, превышении максимального riskLimitValue и tier-specific maxLeverage.
- `UnifiedQuantEngine` получил необязательный `risk_tiers_dir`. Если он задан, вход отклоняется при отсутствии подходящего исторического tier; выбранные tier ID, risk limit, MMR и MM deduction сохраняются в состоянии позиции.
- Loader повторно валидирует tier_count, единственный lowest tier, монотонность riskLimit/MMR/IMR/maxLeverage и mmDeduction recurrence. Добавлены тесты на граничный notional, превышение плеча, stale/future snapshots, испорченные lowest-tier и deduction, engine fail-closed и round-trip сохранения tier metadata.
- Research CI [#41615868813](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41615868813) — **SUCCESS**, commit `b784559f8ca224a893ca6fb074f8376bbeeb6837`; полный deterministic suite завершён, включая cleanup.
- Важно: это только entry-time tier gate. Bybit пересчитывает tier по position value на Mark Price в реальном времени; движок пока не обновляет tier динамически и не моделирует MM/liquidation/IOC deleveraging. Источники: [официальный risk-limit API](https://bybit-exchange.github.io/docs/v5/market/risk-limit), [maintenance margin](https://www.bybit.com/en/help-center/article/Maintenance-Margin-USDT-Contract), [liquidation rules](https://www.bybit.com/en/help-center/article/UTA-Trading-Rules-Liquidation-Process).
- Снимки Bybit пока не получены: GitHub Actions получает HTTP 403 от `api.bybit.com`. H1 runner не передаёт `instrument_specs_dir` или `risk_tiers_dir`; результаты E01–E13 не менялись, рыночные backtests не запускались, реальные ордера не размещались.


## ENG-EXEC-009 — точное количество контрактов в lifecycle позиции (2026-11-03)

- Для strict entry sizing сохраняются Decimal-строки contract_qty, qty_step, min_order_qty, min_notional_value; TP1 и остаток хранятся отдельными количествами контрактов.
- TP1 округляется вниз по qtyStep. Если TP1 или остаточная нога не проходит сохранённые minQty/minNotional проверки, TP1 пропускается, позиция остаётся полной.
- Финальное закрытие проверяет фактическое остаточное количество, шаг и минимум на цене закрытия; при нарушении строгий replay выдаёт ошибку вместо фиктивной сделки.
- Gross PnL, fees/slippage и funding после TP1 используют фактическое количество, а не восстановление из USDT-notional и remaining_fraction.
- State persistence проверяет сохранность, шаг, TP1+остаток=исходное количество и согласованность доли.
- CI #41617395285 — SUCCESS, commit 916cbd036e3b397773682fcbce3e212f3b1e816c.
- Ограничения: фактические reduce-only исключения Bybit для minNotional не подтверждены реальными ответами биржи; строгий replay применяет сохранённый минимум консервативно. H1 runner всё ещё legacy proxy, исторические market PnL бэктесты не запускались.


## ENG-EXEC-010 — position-level IM/MM from dated Bybit risk tiers (2026-11-03)

- Added calculation: IM = position value / configured leverage; MM = position value × MMR − mmDeduction, using the selected point-in-time tier.
- Enforces riskLimitValue and maxLeverage through RiskTierHistory.get_tier.
- Test fixture: 250,000 USDT at 10x in tier 2 gives 25,000 USDT IM and 2,000 USDT MM.
- Research CI #41618208413 — SUCCESS, commit 7775b0358d975715273185cb80a3fa76bdccb1f9.
- Not a liquidation/account-solvency model: margin mode, other positions/orders, available balance, extra margin and fee reserve remain unknown. H1 runner remains legacy proxy; no market PnL backtest run.


## ENG-EXEC-011 — сохранить IM/MM оценку в позиции (2026-11-03)

- Strict entry теперь сохраняет risk tier maxLeverage отдельно от настроенного leverage.
- В OpenPositionState и Plan B backup сохраняются initial_margin_usdt и maintenance_margin_usdt как Decimal-строки; восстановление проверяет конечность и неотрицательность.
- Расчёт entry-time: IM = position value / configured leverage; MM = position value × MMR − mmDeduction.
- Research CI #41619268625 — SUCCESS, commit 889ae9ebdf3fbd06e81e14bed394612a5be050f6.
- Это не динамический mark-to-market margin/liquidation engine; нет account-wide margin solvency или close-fee reserve. Никакие market PnL тесты не запускались.


## ENG-EXEC-012 — H1 PnL runner требует dated Bybit snapshots (2026-11-03)

- H1 shared-capital runner больше не запускает PnL replay в legacy notional-proxy режиме.
- Перед загрузкой данных обязательны обе директории: linear instrument specs и risk-limit tiers; обе передаются в UnifiedQuantEngine strict mode.
- Preflight проверяет отсутствие/пустые директории; regression suite покрывает fail-closed и корректную конфигурацию.
- Research CI #41619800964 — SUCCESS, commit 1e25c1cc00e69dd515e29c4515437c026a654f0a.
- Снимков пока нет из-за US egress GitHub-hosted runner; H1 PnL workflow намеренно остановится до их сбора. Новые market PnL тесты не запускались.


## ENG-EXEC-013 — контроль временного покрытия exchange snapshots (2026-11-03)

- H1 runner проверяет датированные instrument specs и risk tiers отдельно для каждого scored fold.
- Нужен снимок не позднее начала fold; начальная давность, интервалы между снимками и давность последнего снимка не должны превышать 30 дней.
- Неподходящий сегодняшний снимок не может быть применён к старой исторической свече.
- Причина: официальные V5 endpoints instruments-info и risk-limit предоставляют текущие данные и не документируют historical/as-of query параметр; instruments-info указывает на bi-monthly изменение max order quantity fields.
- 6 gate tests PASS; Research CI #41622415461 SUCCESS, commit e7164073a2292ed51f01b45d131ff65b3c958612.
- До накопления датированной истории PnL replay остаётся заблокирован. Никакие рыночные PnL тесты не запускались.


## ENG-EXEC-014 — H1 net PnL использует Bybit-native candles + funding (2026-11-03)

- Удалён Binance/CryptoFetch ZIP как price source H1 runner. Теперь обязательна директория BYBIT_KLINE_DIR с official Bybit V5 H1 trade klines.
- Loader проверяет OHLCV, дубликаты и непрерывный интервал 1h; common synchronized overlap проверяется между выбранными инструментами.
- Runner требует Bybit funding и mark-price CSV для каждого выбранного инструмента; проверяет точное совпадение trade/mark timestamp grids и наличие mark candle для каждой scored H1 свечи и каждого funding settlement.
- UnifiedQuantEngine получает funding_dir и mark_price_dir; funding учитывается в MTM и final PnL. Поле costs включает fees + slippage + net funding, отдельно выводится funding_costs.
- H1 workflow требует путей kline_dir, funding_dir, mark_price_dir. Archive workflow для Bybit market history выбирает self-hosted runner по умолчанию и блокирует US/CN egress.
- Research CI #41623727845 SUCCESS; новые gate-тесты funding/data paths плюс Bybit H1 loader tests прошли на кодовом коммите e696af2f78e8ec7724d169899566c3825a9da56e.
- Market PnL replay не запускался: нет датированных instrument/risk snapshots и полных Bybit history CSV в репозитории. Не моделируются queue position, spread, partial-fill adverse selection; funding mark использует open свечи mark-price в timestamp settlement.

## E14 — H-A signal and post-break attribution (2026-11-03; diagnostic only)

- Financial replay summary: [H-A results report](../reports/H_A_RELATIVE_STRENGTH_BREAKOUT_RESULTS_2026-11-03_RU.md). Across the three reset-capital folds, baseline net PnL was −5,635.98 USDT (1,022 trades) and H-A was −6,135.26 USDT (1,033 trades); H-A underperformed by 499.28 USDT. Both variants were negative in every fold. Fold 3 accounts for the relative deterioration (H-A −2,307.78 vs baseline −985.85; max DD 30.01% vs 15.04%). These are CryptoFetch OHLCV proxy results with funding omitted, not Bybit net PnL.
- Frozen H-A replay with expanded trade ledger: [run 41670116033](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41670116033), artifact 13247672222. Baseline/H-A financial metrics reproduce the earlier H-A result at published precision; no signal, cost, fold or execution rule changed.
- Read-only signal-candle and post-entry path reconstruction: [run 41672420459](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41672420459), final schema-validated artifact 13249307987. 2,055 trade rows, 41 cohort rows; source archive SHA manifest matches. No PnL was recomputed.
- Pre-entry signal-candle features are weak stop-vs-profitable-outcome separators: AUC mostly 0.48–0.55. Do not add body, wick, volume or pre-break compression filters from this sample.
- H-A post-entry directional close return after 3 completed H1 bars: -0.104R for stop-loss trades (451 eligible) vs +0.222R for profitable exits (486 eligible); lower-return rank AUC ≈0.70. After 6 bars: -0.118R (353 eligible) vs +0.313R (475 eligible); lower-return AUC ≈0.734.
- Close back inside the prior Donchian boundary within 3 completed bars: 61.6% of eligible stop-loss trades vs 41.6% of profitable exits. The association is directionally consistent across all three folds and also appears in the frozen baseline.
- H-A realized net PnL conditional on 3-bar retest was negative in all folds (-1,206.64 / -2,540.07 / -2,917.66 USDT); no-retest cohorts were positive (+589.12 / +1,102.86 / +1,397.25). These are eventual outcomes conditioned on future path, not counterfactual early-exit PnL.
- Intrabar exit candles are excluded from post-entry path features; close-based time-stop/end-of-test bars may be included. Intrabar path order is not inferred.
- Research CI [41672385624](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41672385624) SUCCESS; causal signal diagnostic tests 6/6 PASS. H-A post-break diagnostic workflow [41672420459](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41672420459) SUCCESS; archive provenance/schema validation passed.
- Decision: no H-A optimization, no breakeven/stop-widening/session/direction filter and no new PnL on the reused folds. H-C close-based post-break invalidation is now implemented behind a default-OFF research flag, with synthetic semantics/state tests passing; it has NOT been PnL-tested or enabled live. See H_C_POST_BREAK_INVALIDATION_PREREGISTRATION_RU.md. Bybit-native point-in-time data and execution realism remain blockers.
- Follow-up engineering change: TradeRecord and the H-A runner now retain/export initial stop geometry, TP1 hit/time/realized gross, remaining fraction and final stop. This code change is regression-tested, but artifact 13249307987 predates it; do not claim those TP1 fields exist in E14 output until a later replay.
- Signal-time Donchian boundary is now emitted by baseline/H-A signal evaluators, persisted through pending/open/closed trade state, validated on restore, and exported by the runner. This is provenance-only and has no effect on execution/PnL; E14 artifact predates it.


## ENG-EXEC-015 — согласованность TP1 maker fee между MTM и close для legacy positions (2026-11-03)

- Карточка: [ENG-EXEC-015](experiment_cards/ENG-EXEC-015_LEGACY_TP1_MTM_FEE_FALLBACK_RU.md).
- Подтверждённый дефект: _close_position() при maker_exits=None использовал fallback order_type == "limit", а _unrealized_pnl_at_marks() трактовал None как taker. Legacy/restored limit position после TP1 поэтому имела разные TP1 fee/slippage в unrealized equity и final close accounting.
- Test-first CI [#41705641423](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41705641423) FAILED именно на новой регрессии test_legacy_limit_position_mtm_uses_same_tp1_fee_fallback_as_close; mismatch reproduced.
- Fix: MTM теперь разрешает maker_exits тем же fallback, что и _close_position(). Явные True/False не меняются. Торговые сигналы, risk sizing, stop/target и fee constants не затронуты.
- Full Research CI [#41705849389](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41705849389) SUCCESS; новая regression и portfolio accounting suite прошли.
- Влияние на текущий H1 preset: конкретно этот None fallback там не используется, поскольку maker_tp1_and_target=False. Это прежде всего legacy/restored-position accounting consistency defect; никаких market PnL runs не было.

- Follow-up test hardening: added numeric MTM regression for legacy `maker_exits=None` and explicit `maker_exits=False`; [CI #41707011122](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41707011122) SUCCESS (50/50 steps; funding MTM tests 8/8). No PnL replay.

 
## ENG-REPORT-001 — geometric monthly-equivalent net return for H1 folds (2026-11-03)

- Gap: H1 output reported cumulative fold `return_pct` only. This is insufficient to compare folds of different durations against the user's stated 20% net monthly hurdle.
- Added `duration_days`, `duration_months` and `geometric_monthly_return_pct` to each H1 result row and metric definitions to the validation manifest. Duration includes the final H1 candle through its close; net PnL already includes modeled fees, slippage and funding.
- This is a geometric monthly-equivalent normalization, not an observed calendar-month return series and not proof of consistent monthly performance. Actual month-by-month returns and losing-month frequency remain required before any candidate can be called consistent.
- Reporting-only change: no signal, ranking, execution, risk, or cost assumptions changed; no market PnL run.
- Tests cover +20% over one average month, +44% compounded over two months (=20% geometric monthly), reversed timestamps and total loss.
- Runner commit `4e481fcadba5a7692b619c3b219da73241e8c7d3`; tests commit `381aacadcd2965757b8d3907fd8bdebb8b8b3d59`.
- CI [#41708149842](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41708149842) and [#41708141158](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41708141158) SUCCESS, 50/50 steps each.


## ENG-REPORT-002 — H-A monthly return evidence against 20% hurdle (2026-11-04)

- Re-read the monthly equity path from the frozen H-A artifact (run 41670116033); no replay or parameter change.
- All three fully covered calendar months inside the separate folds were negative for both variants: May baseline -17.75% / H-A -12.38%; July -11.40% / -12.04%; September -7.90% / -14.16%.
- Partial boundary months are separately labelled and must not be stitched into one continuous equity curve because each fold resets capital to 10,000 USDT. Fold 3's partial August was +1.07% / +1.62%, not +20%.
- Conclusion: no evidence of the required 20% net monthly return; H-A remains rejected. Funding is omitted and CryptoFetch is not Bybit-native. Source artifact: h-a-preregistered-ohlcv-results, artifact ID 13247672222, workflow run 41670116033.


## ENG-EXEC-016 — per-leg maker/taker classification for TP1 and TP2 (2026-11-04)

- Confirmed execution-accounting defect: maker-exit configuration previously classified TP1/TP2 as maker even when the candle opened through the resting limit target, i.e. the order was marketable at the open. This understated taker fees and slippage for gap-through target fills in maker-enabled variants.
- Engine now records actual TP1 liquidity as optional OpenPositionState.tp1_maker, and TradeRecord records tp1_maker plus final_exit_maker. If a long target is gapped through above the sell limit at candle open, or a short target below the buy limit, the fill is classified taker. Non-gap intrabar target touches retain the existing maker proxy; queue position, spread and adverse selection remain unmodeled.
- TP2 final-leg maker classification is passed explicitly into close accounting. All non-target exits, including H-C breakout invalidation, remain taker. Mark-to-market uses the recorded TP1 classification; the remaining unrealized close stays taker as a conservative MTM assumption.
- Gap-through execution price remains the target price rather than crediting a better open fill; this is conservative for gross PnL while the liquidity classification correctly increases costs.
- H-A trade-ledger export now includes both liquidity fields. A synthetic H-C integration test verifies TP1 partial plus remaining-leg market close costs and exact net reconciliation. State persistence round-trip for explicit tp1_maker=False is added separately.
- Research CI [#41720355038](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41720355038) SUCCESS, 52/52 steps; H-C semantics 10/10; gap execution suite and MTM suite passed.
- Historical E08/E09 maker/limit results must be treated as provisional until replayed with this corrected accounting. The frozen H-A run used market exits (maker flags disabled), so this specific gap-liquidity fix does not explain or improve its negative result.
- Reporting/engineering only: no market PnL replay, no Bybit download, no API connection, no orders.

- Follow-up persistence regression: explicit tp1_maker=False survives Plan-B save/restore without collapsing to the maker_exits=True fallback. Research CI [#41720499938](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41720499938) SUCCESS, 52/52 steps. No market PnL replay.


## ENG-HC-RT-001 — H-C reverse-time CryptoFetch proxy (2026-11-04)

- Frozen run [#41722545731](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41722545731), artifact 13272957989, protocol H-C-RT-CRYPTOFETCH-2026-11-04-v1, research commit a5e7e1799f472db4cc00824dfcc774b40058165e.
- Window 2025-10-30 00:00 through 2026-04-26 23:00 UTC, fixed 25-symbol archive-available universe, 72 H1 warmup bars, same baseline versus baseline+H-C, 2x fees/taker slippage, market execution, funding/mark omitted.
- Baseline: 313 trades, gross -1,098.10, fees 1,151.42, slippage 470.95, proxy net before funding -2,720.47, PF 0.63, expectancy -0.213R, max DD 30.06%.
- H-C: 610 trades, gross +404.08, fees 2,330.71, slippage 953.49, proxy net before funding -2,880.12, PF 0.72, expectancy -0.120R, max DD 30.18%.
- H-C gross improved +1,502.18, but fees+slippage increased +1,661.83; trade count rose 94.9%; proxy net worsened -159.65. 296 invalidation exits averaged -0.399R and totalled -4,535.90 net. Stop-loss count fell 180→138; both variants hit the 30% kill switch.
- Decision: reject H-C for this proxy window; no tuning or rerun. CryptoFetch is not Bybit-native, not forward OOS, survivor-biased and excludes funding/mark. Full detail in docs/reports/H_C_REVERSE_TIME_RESULTS_2026-11-04_RU.md.
- Bootstrap failure [#41722181706] occurred before import/archive/PnL; path fix passed [#41722380421] 53/53 before the first complete run. The exact execution commit passed [#41722545755] 53/53.


## ENG-EMA-002 — exact timestamp EMA50/200 gate context (2026-11-04)

- Implemented `trend_label_index` / `lookup_trend_label`: exact timestamp lookup, 1,000-bar burn-in for EMA200, chronological uniqueness, optional contiguous H1 validation, and no nearest-label fallback.
- Added per-symbol precomputation and opt-in `ema_trend_labels_by_symbol` input to H1 `run_portfolio_variant`. The long-only H1 wrapper permits a signal only when the same completed candle is labelled `up`.
- Baseline and current H1 grid do not pass this optional input; default behavior is unchanged. No PnL replay was run.
- Research CI [#41727906187](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41727906187) SUCCESS, 54/54, commit `8ab840b7a127518411b01fd9828008dd479aef18`.
- Earlier intermediate CI attempts failed on test-import formatting and a test that accidentally queried a timestamp that was actually present; both test defects were corrected. The final full suite passed.


## ENG-EMA-003 — paired baseline versus EMA50/200 H1 comparison (2026-11-04)

- Added manual workflow input `ema50_200_comparison=off|paired`. Default `off` preserves baseline-only behavior; `paired` enables the EMA candidate and automatically runs both baseline and EMA-gated variants for each identical fold/config/cost setting.
- Added distinct candidate labels (`_ema50_200_up`) and manifest-level `build_paired_ema_comparison`, which matches by fold, volume threshold, breakout ATR threshold and cost multiplier. Missing or duplicate comparison legs fail closed; output records net-PnL, trade-count, cost, PF and expectancy deltas.
- Each baseline/candidate leg is an independent 10,000-USDT shared-capital portfolio replay with identical execution assumptions; they do not share capital with one another.
- Research CI [#41728994842](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41728994842) SUCCESS, 55/55 at commit `8ed9a1688d51538e2c31adf68edcfd41a9a7792c`.
- No market PnL replay. Bybit H1/funding/mark/spec/risk archives are still absent. Changes to replay-critical code invalidate selector provenance, so rerun train-only selection after the final code freeze and before any Bybit validation.


## ENG-DATA-017 — Funding schedule snapshots respect symbol lifecycle (2026-11-04)

- Dated instrument snapshots may legitimately omit a contract before its launch or after its delivery. Funding-schedule attachment now allows such out-of-window absence while requiring the symbol to be present in every dated snapshot inside the requested funding interval. Duplicate symbol rows and unknown/invalid intervals remain fail-closed.
- Added regression tests for absence before/after lifecycle and absence inside the funding interval.
- Research CI [#41730087544](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41730087544) SUCCESS, 54/54.
- This aligns funding schedule evidence with per-symbol lifecycle-aware market-history clipping; it does not reconstruct historical listing/delisting state that was never captured.

## ENG-EMA-004 — paired EMA comparison parity and explicit leverage (2026-11-04)

- Paired baseline/candidate manifest now rejects mismatched timeframe, symbol basket, common H1 bar count, fold start/end, starting capital or max concurrent positions. Pairing key remains fold + volume + breakout-ATR + cost multiplier.
- H1 runner now explicitly assigns `ISOLATED_5X` and `leverage_val=5.0` instead of relying on the BotConfig default; the same constants are written to the validation manifest.
- CI [#41730087544](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41730087544) SUCCESS, 54/54.
- No Bybit market PnL replay; all these changes are deterministic integrity hardening only.


## ENG-SEL-001 — per-symbol train/validation leakage in H1 Top-5 selector (2026-11-04)

- **Confirmed defect:** `scripts/select_h1_top5_train_only.py::select_train_only` applied the longest-history calendar cutoff to every symbol. Shorter histories could cross their own 50% validation boundary and influence ranking with validation-period data.
- Concrete reproduced case: 10,000-bar reference cutoff at index 4,998; 4,000-bar candidate's own validation begins at index 2,000. Old slicing included candidate bars through index 3,999.
- Fix: `candidate_training_slice()` calculates each candidate's own first-validation timestamp and excludes any candidate whose training slice reaches or crosses that timestamp. Manifest now records per-candidate validation boundaries.
- Regression: `tests/test_h1_top5_selector.py::test_candidate_training_slice_rejects_short_symbol_validation_leakage`; also verifies the reference series retains the one-bar embargo.
- Research CI [#41732028220](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41732028220) SUCCESS, 54/54 steps. Selector fix commit `d927703771ee66e818556dbae65d69c7e7763018`; test commit `d628eb42922898b672f975d15b7341f8dfe4ab5a`.
- Impact: future selector integrity only. No frozen Bybit selection manifest existed; no strategy PnL, Bybit API, download, paper trading or live orders.
- Remaining limitation: this does not reconstruct historical delisted/temporarily unavailable contracts and does not remove survivorship bias from incomplete historical universe evidence.
- Decision: selector must be rerun from scratch after final code/data freeze; no earlier manifest may be reused.


## HYPOTHESIS INTAKE — MASTERPROMPT_breakout_bot.md (2026-11-04)

- Пользовательская подборка разобрана и классифицирована в `docs/research/hypotheses/MASTERPROMPT_BREAKOUT_HYPOTHESIS_REVIEW_RU.md`.
- Новые кандидаты в backlog: HYP-BRK-02 (ATR breakout buffer) и HYP-RISK-09 (correlated directional exposure cap); execution retest, MAE/MFE exits, session timing и broad-market context оставлены отдельными отложенными направлениями.
- Не дублировать: H3 gap gate 2% (E09 не активировался); H4 post-break return-to-channel (пересекается с отклонённым H-C); H8 общий BTC/breadth gate (E12/E13 уже исследовали); H-A relative strength (отклонена).
- Источник — legacy v6.1 / 15m описание. Текущий рабочий приоритет остаётся H1; старые параметры не перенесены.
- Документальная регистрация בלבד: нет PnL run, parameter sweep, paper trading, API connection или live orders. Data/accounting gate остаётся закрытым.


## ENG-FUND-004 — reject duplicate Funding CSV timestamps (2026-11-04)

- Подтверждённый дефект: `validate_funding_manifest()` преобразовывал Funding timestamps в set без выявления дублей; дублированная выплата могла пройти сравнение с расписанием.
- Fix: повторный timestamp добавляет `duplicate_funding_timestamp_in_csv`; regression rehashes CSV/manifest with a duplicate row and verifies fail-closed rejection.
- CI [41735002481](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41735002481) and [41735022125](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41735022125): both SUCCESS, 55/55 steps.
- Классификация: accounting/archive validation guardrail; no market PnL experiment.
- Остаточный blocker: no authoritative historical effective-time series for fundingInterval; sparse point-in-time snapshots cannot exclude interval changes/reversions; settlement Mark remains candle-open proxy.

## ENG-H1-DONCHIAN-001 — параметризация preregistered Donchian48 arms (2026-11-04)

- Спецификация: `docs/research/LOW_FREQUENCY_DONCHIAN48_EMA_H1_PREREGISTRATION_RU.md`.
- Runner: `scripts/run_h1_shared_capital_portfolio_validation.py`; opt-in `H1_DONCHIAN48_EMA_ABLATION=1`.
- Три фиксированных paired arms: Donchian20 без EMA (control A), Donchian48 без EMA (control B), Donchian48 + causal EMA50/EMA200-up (candidate C).
- Все arms исполняются через тот же shared-capital replay и одинаковые fold/config/cost keys. Pairing fail-closed: отсутствие одной ноги или различия universe, временных границ, капитала и max positions приводят к ошибке.
- Default режим не изменён: Donchian20; legacy EMA50/200 ablation остаётся отдельным opt-in режимом. Одновременное включение двух разных схем запрещено.
- Workflow dispatch получил отдельный переключатель для трёхрукавной схемы. Manifest сохраняет period/EMA arms; CSV сохраняет фактический Donchian period.
- CI: [41734540443](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41734540443), SUCCESS; компиляция и deterministic tests passed.
- **Классификация:** инженерная реализация + unit/CI verification; не market experiment, не PnL evidence.
- Изменённый runner hash означает, что ранее созданный Top-5 selection manifest нельзя повторно использовать: его code provenance должен быть заново сформирован на официальных данных после открытия data gate.
- Никакого PnL replay, параметрического поиска, новых загрузок, API, paper trading или live orders не выполнялось.


## ENG-MARK-005 — Mark OHLC / isolated liquidation re-audit (2026-11-04)

- Re-audited Mark archive collector, engine integration, isolated USDT liquidation/MM calculator, risk-tier history and instrument-spec as-of history.
- Mark collector validates OHLC positivity/order, aligned timestamps, requested chunk membership and exact interval coverage; engine requires exact-timestamp full Mark OHLC for every open position when liquidation model is enabled.
- Formula cross-check against current Bybit UTA isolated USDT documentation found no confirmed arithmetic defect in the tested liquidation/MM components. Existing tests include published 36,380.25 USDT long LP example, directional close fee, dynamic MM tier changes, funding adjustment, TP1 remaining quantity and Mark/Last separation.
- Confirmed limitations: single-position isolated approximation only; no cross/portfolio/shared collateral, active-order aggregation, AMR, partial liquidation ladder or exact intrabar ordering. OHLC stress assumes conservative liquidation precedence within a bar.
- Dated snapshots are observations, not effective-from history. No complete Bybit Mark/risk-tier/instrument-spec archive exists in repository; max-age defaults of 30 days are stale guards, not proof of parameter stability.
- Official references: Bybit UTA isolated liquidation formula; V5 Mark Price Kline; USDT maintenance margin documentation (links in LEVERAGE_MARGIN_LIQUIDATION_AUDIT_2026-11-03.md).
- Classification: code/formula re-audit; no market PnL test, no strategy change.
- Decision: no ungrounded formula changes. Data/account-mode gate remains CLOSED; no PnL, private API, paper or live execution.


## ENG-DATA-006 — Bybit historical data source audit (2026-11-04)

- Official Bybit V5 public API supports H1 trade Kline, Mark Price Kline and Funding history. Official docs state US and Mainland China IPs are restricted (HTTP 403); exact egress location for the prior hosted-runner 403 was not recovered from old logs.
- Existing instrument/risk snapshot and market archive workflows already require a self-hosted runner outside US/Mainland China and accept BYBIT_API_BASE_URL. Official mainnet hosts include api.bybit.com and api.bytick.com; collectors allow both.
- Official Historical Market Data download page advertises public OHLCV/trade CSV, but current accessible page does not establish Mark/Funding/specification coverage. Treat as a possible trade-data source only until actual product coverage is verified.
- Audited independent CryptoHFTData Bybit funding/mark archive: starts 2025-06-28; vendor documents Bybit missing hours 2025-11-26 10 UTC–2025-12-26 19 UTC and 2026-04-13 15 UTC–2026-04-14 21 UTC; before Sep 2026 integrity release, mark/ticker/OI fields were change-only deltas with null unchanged values. Vendor explicitly describes archive as independent, not official Bybit.
- Decision: do not use third-party archive as sole PnL source; allow supplementary exploratory/cross-check only after forward-fill semantics, gaps and official sample reconciliation are handled.
- Next hard dependency: a legally/regionally permitted self-hosted execution host for public Bybit market-data endpoints. No private account API, no PnL, paper or live orders.
- Detailed evidence and source links: docs/audits/BYBIT_DATA_ACQUISITION_SOURCE_AUDIT_2026-11-04.md.


## ENG-FUND-005 — strict integer timestamp validation (2026-11-04)

- Подтверждённая проблема схемы: Funding accounting helpers и активный Bybit Funding parser применяли int() к timestamp без проверки исходного типа. Дробные числовые значения могли незаметно усекаться до миллисекунды.
- Исправление: accounting требует положительные non-bool int timestamps для entry/as-of/TP1/final-close/events; API parser принимает только integer или ASCII digit string. Float, bool и decimal string отклоняются.
- Регрессии: дробные/boolean timestamps в accounting; float/bool/decimal string в API parser.
- Final Research CI #41848927029, commit 39af6fa583ef2074b33905e89c8b78c9b58d83a1: SUCCESS, 57/57 steps. Funding accounting 23/23; Bybit market-history parser 26/26; новые проверки прошли.
- Межуточные CI запуски завершались fail только из-за неверного regex в новом тесте (ошибка была обёрнута contextual ValueError); ожидание теста исправлено, финальный CI зелёный.
- Классификация: data/accounting contract guardrail; не рыночный эксперимент и не PnL evidence. No market replay, archive download, private API, paper/live orders.
- Остаточные блокеры не меняются: историческая полнота funding schedule и exact settlement mark не доказаны; maker fill realism и account-specific costs не подтверждены.


## ENG-EXEC-015 — TP1 remainder minNotional at short TP2 (2026-11-04)

- Дефект: TP1 exchange-sized остаток проверялся по min(stop, entry), не включая TP2. Для short TP2 может быть ниже обеих цен; остаток мог пройти TP1, но нарушить minNotionalValue на плановом TP2 close.
- Исправление: lowest planned exit = min(stop_price, entry_price, tp2_price); остаток проверяется по этой цене, TP1-часть — по TP1 цене.
- Регрессия: 0.5 контракта * TP1 90 = 45 (ровно minNotional), остаток 0.5 * TP2 80 = 40 (ниже minNotional 45). Старый код принимал TP1; новый отклоняет без изменения состояния.
- Final Research CI #41850162961, commit e01a53868885f5ac79f2ad3d3cfa3179e7207b1a: SUCCESS, 57/57 steps; MarkPriceEngineIntegrationTests 9/9; новая регрессия подтверждена в логе.
- Классификация: exchange validity guardrail, не PnL evidence. No market replay, data downloads, private API, runner, paper/live orders.


## ENG-EXEC-016 — fail-closed exchange-sized state restore (2026-11-04)

- Restore validation now enforces minOrderQty for initial/remaining quantity, minNotionalValue for remaining quantity at min(stop, entry, TP2), and minOrderQty/minNotionalValue for TP1 quantity at TP1 price.
- Added two regressions for below-minimum restored remaining quantity and below-minimum remaining exit notional.
- CI #41851236490, d50c923b2e158e951d9ca979708d093e54ae3983: SUCCESS 57/57. First test run had assertion-text mismatch only; corrected to assert wrapped fail-closed RuntimeError.

## ENG-FUND-006 — enforce TP1 flag/timestamp invariant in funding helpers (2026-11-04)

- Both funding accounting helpers now reject non-bool tp1_hit, require tp1_ts_ms when TP1 is hit, and reject a TP1 timestamp when tp1_hit=false.
- Added two regression tests for timestamp-without-hit and integer-as-bool.
- Final CI #41851768270, 3170738a78eac92b0a93eda66510c038660f0864: SUCCESS 57/57; actual log confirms both tests passed; funding accounting suite ran 76 tests. Source-only CI #41851738950 also SUCCESS 57/57.
- These are correctness gates, not PnL evidence; no live/paper activity.


### ENG-EXEC-015/016 amendment — planned exits only (2026-11-04)

- Уточнение: entry price не является самостоятельной плановой ценой выхода. Использование min(stop, entry, TP2) могло ложно отклонять валидное восстановление long после подъёма trailing stop выше entry.
- Исправлено на min(stop, TP2) и в TP1 guard, и в restore validation; TP1-ордер по-прежнему отдельно проверяется по TP1 price.
- Регрессия: long entry 100, trailing stop 110, TP2 112, qty 1, minNotional 105 — restore разрешён, так как обе реальные цены выхода проходят ограничение.
- CI #41852293859, c88e587d01739eb7c0ee6fe94e0369b28aff664c: SUCCESS 57/57; state persistence 77/77, новая регрессия подтверждена логом.


## ENG-FUND-007 — TP1 flag must agree with funding quantity state (2026-11-04)

- Both funding helpers now reject `tp1_hit=false` with partial remaining quantity and `tp1_hit=true` with unchanged initial quantity. Remaining-margin helper validates remaining_fraction [0,1].
- Exact contract quantity remains authoritative over stale/rounded display fraction.
- Test fixture default corrected: full remaining quantity when TP1 false. Three regressions added for contradictory TP1/quantity states.
- Final CI #41853410298, 0cf45d16809a04e2653325934b37723b009097d0: SUCCESS 57/57; actual log confirms all three regressions and 28 funding tests. Intermediate source-only run failed because it still had the prior contradictory fixture; corrected in test commit and final run green.
- Technical correctness only; no PnL/backtest or exchange operations.


## ENG-EXEC-017 — Validate persisted realized TP1 gross (2026-11-04)

- Restore now recomputes realized TP1 gross from actual closed leg and TP1 price; rejects arbitrary/stale values. Exchange-sized: exact TP1 contract quantity × price move. Legacy: initial notional × closed fraction × relative price move. 4-decimal rounding tolerance.
- Regression corrupts legacy realized TP1 gross 30→31 and expects fail-closed restore. Exchange-sized fixtures now use exact gross 3; legacy liquidity fixture uses gross 30.
- Final CI #41854119883, f42979860d97090120ee3a8aed79d59695d441ee: SUCCESS 57/57; state persistence 78 tests. Earlier runs exposed stale fixture values, corrected before final green run.
- Persisted PnL integrity guardrail only; no PnL/backtest or exchange operations.


## ENG-EXEC-018 — Validate persisted MFE/MAE extrema (2026-11-04)

- Restore rejects zero/non-positive saved favorable/adverse extrema and directionally impossible values (long favorable below entry/adverse above entry; short favorable above entry/adverse below entry). Missing legacy fields retain entry-price defaults.
- Three regression tests cover zero favorable, long favorable below entry, and short adverse below entry.
- Source CI #41854906684 SUCCESS 57/57; final CI #41854947672, 4c7744c22180a97fa868547eac034cdf91b69491 SUCCESS 57/57; state persistence 81 tests.
- Persisted excursion-metric integrity only; no PnL/backtest or exchange operations.


## ENG-RISK-004 — Restore must preserve drawdown stop latches (2026-11-04)

- Restore rejects `kill_switch_triggered=false` when current implied DD or historical max_drawdown_pct reaches emergency threshold; this preserves the latch after equity recovery.
- Restore rejects `daily_stop_triggered=false` when current-day DD reaches daily stop threshold and current_day_str is active.
- Three regressions cover current emergency breach, recovered historical emergency breach, and current daily breach.
- Source CI #41861236015 SUCCESS 57/57; final CI #41861273155, 669a7d66c50df5426e63c5490580b2d8bbc92f22 SUCCESS 57/57; state persistence suite 84 tests.
- Limitation: recovered intraday daily breach cannot be inferred from existing schema if latch is corrupted; no daily equity-low watermark exists.
- Risk-control state integrity only; no PnL/backtest or exchange operations.

## ENG-EXEC-019 — Inspector и replay используют строгий trade timestamp parser (2026-11-04)

- В `scripts/inspect_bybit_trade_sample.py` обнаружено округление CSV timestamp через `float()` + `round()`. Sub-millisecond timestamps могли быть приняты после потери точности, в отличие от строгого queue replay parser.
- Инспектор переведён на общий `parse_trade_timestamp_ms()` из `bybit_l2_queue_replay.py`; отдельный parser удалён. Сохраняются точные seconds/milliseconds, запрещены non-finite/non-positive и sub-millisecond timestamps.
- Regression coverage: exact seconds and milliseconds; rejection of sub-millisecond, NaN/Infinity, zero/negative and malformed values.
- Финальный CI #41873039139 на `ec28763da6ade2635c31cd0111ae8c612625f23d`: SUCCESS, 57/57 workflow steps, zero failures; inspector/runner suite 7/7; aggregate-L2 primitive suite 81/81.
- Промежуточный #41872989853 failed только потому, что тест ссылался на удалённый helper `parse_archive_timestamp_ms` после refactor к shared parser; тест синхронизирован в `ec28763`, полный финальный CI прошёл.
- Это timestamp-integrity guardrail диагностического инструмента, не доказательство исполнения или доходности. Никакие архивы не скачивались; inspector с сетевым вызовом не запускался. No PnL/backtest, API, runner, paper/live orders or main changes.


## ENG-EXEC-020 — Report missing and malformed public trade IDs in archive inspector (2026-11-04)

- The historical trade archive inspector previously counted only truthy `trdMatchID` values. Missing/blank IDs and IDs with surrounding whitespace were silently omitted from the identity counts, unlike the strict replay parser.
- Added `classify_trade_id()` and report fields for missing IDs, malformed whitespace IDs, duplicate IDs, presence of the ID column, and an overall `trade_id_validation_status`.
- Regression covers None, empty, whitespace-only, surrounding whitespace, unique ID and duplicate ID.
- Source commit `bd2c0f9bc9fe2ad64044a4b9fe672ceb148950b3`; test commit `6dcb9d8bc000778c09975dbd462c36545e23682c`.
- Source-only CI #41873380445 SUCCESS; final CI #41873425668 on `6dcb9d8` SUCCESS, 57/57 steps, zero failures. Actual logs: inspector/runner suite 9/9; aggregate-L2 primitives 81/81; portfolio accounting 54/54; state persistence 84/84.
- Data-quality diagnostic only; no execution/PnL evidence. No new archives downloaded and network inspector not run. Historical AAVE CSV still lacks BT/isBlockTrade; maker execution realism remains blocked. No PnL/backtest, API, runner, paper/live orders or main changes.
