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
