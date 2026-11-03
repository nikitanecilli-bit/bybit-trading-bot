# H-A Relative Strength Breakout — результаты preregistered replay

Дата: 2026-11-03  
Workflow: [H-A preregistered OHLCV replay, run 41670116033](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41670116033)  
Артефакт: `h-a-preregistered-ohlcv-results`  
Стратегия: frozen H-A relative-strength rank + Donchian(20), сравнение с frozen H1 Donchian + volume baseline.  
Статус: **H-A отклонена как кандидат на текущем тестовом дизайне; baseline также не проходит net-PnL gate.**

## 1. Итог

Обе версии проиграли после моделируемых комиссий и slippage во всех трёх fold. H-A улучшила baseline в fold 1 и 2, но ухудшила fold 3 настолько, что суммарно потеряла на 499.28 USDT больше baseline.

| Метрика (сумма трёх независимых fold) | Baseline | H-A |
|---|---:|---:|
| Сделки | 1,022 | 1,033 |
| Gross PnL, USDT | +587.02 | +29.53 |
| Fees, USDT | 4,416.37 | 4,375.03 |
| Slippage, USDT | 1,806.63 | 1,789.76 |
| Funding, USDT | 0.00 | 0.00 |
| Net PnL, USDT | **−5,635.98** | **−6,135.26** |
| Net на 30,000 USDT суммарного fold-start capital | −18.79% | −20.45% |

Сумма PnL — арифметическая сумма результатов трёх отдельных запусков с reset капитала на 10,000 USDT в каждом fold, а не одна непрерывная equity curve. Доли от 30,000 USDT приведены только как нормализация общей суммы потерь.

## 2. Fold-разбивка

| Fold (UTC) | Вариант | Символы | Сделки | Net PnL | PF | Expectancy R | Max DD |
|---|---|---:|---:|---:|---:|---:|---:|
| 1: 27 Apr–21 Jun | Baseline | 47 | 320 | −2,278.63 | 0.66 | −0.1930 | 24.01% |
| 1: 27 Apr–21 Jun | H-A | 47 | 306 | −1,601.57 | 0.74 | −0.1404 | 17.79% |
| 2: 21 Jun–14 Aug | Baseline | 49 | 306 | −2,371.50 | 0.62 | −0.1990 | 24.59% |
| 2: 21 Jun–14 Aug | H-A | 49 | 322 | −2,225.91 | 0.66 | −0.1937 | 23.26% |
| 3: 15 Aug–26 Oct* | Baseline | 50 | 396 | −985.85 | 0.88 | −0.0335 | 15.04% |
| 3: 15 Aug–26 Oct* | H-A | 50 | 405 | −2,307.78 | 0.74 | −0.1360 | 30.01% |

* В исходном плане конец fold 3 был 27 Oct 00:00 UTC, но общий фактический terminal bar архива — 26 Oct 00:00 UTC. Нельзя выдавать fold за полное покрытие до 27 Oct.

Изменение H-A относительно baseline:
- Fold 1: +677.06 USDT, DD ниже на 6.22 п.п.
- Fold 2: +145.59 USDT, DD ниже на 1.33 п.п.
- Fold 3: −1,321.93 USDT, DD выше на 14.97 п.п.
- Итого: −499.28 USDT относительно baseline.

## 3. Экономика результата

- Baseline: gross +587.02 USDT при fees + slippage 6,223.00 USDT.
- H-A: gross +29.53 USDT при fees + slippage 6,164.79 USDT.
- Следовательно, текущая проблема не сводится к отсутствию cross-sectional rank: даже gross edge почти исчезает у H-A, а costs на порядок больше gross PnL.
- H-A не уменьшила число сделок относительно baseline: 1,033 против 1,022. Значит, этот rank gate в данном исполнении не обеспечил достаточного сокращения оборота.
- Fold 3 особенно важен: baseline там почти достиг нулевой expectancy до costs, тогда как H-A вернулась к заметно отрицательной expectancy и почти удвоила max drawdown.

## 4. Что доказано и что не доказано

**Доказано этим replay:**
1. Frozen H-A не проходит net-PnL gate ни в одном fold.
2. H-A не улучшает суммарный net PnL baseline; суммарный результат хуже на 499.28 USDT.
3. Fold 3 — главный источник относительного ухудшения H-A.
4. В этой конфигурации cross-sectional relative-strength rank не создаёт достаточного gross edge и не компенсирует costs.

**Не доказано:**
1. Что relative strength в принципе бесполезна: проверена только одна preregistered формула/порог/тайминг.
2. Что причина провала исключительно в сигнале: replay использует CryptoFetch OHLCV proxy, удвоенные базовые fee/slippage constants и не включает funding.
3. Что результаты соответствуют реальной торговле на Bybit: отсутствуют Bybit-native point-in-time universe, dated instrument/risk-tier snapshots, funding и Mark OHLC.

## 5. Решение и следующие действия

- Не запускать sweep порогов rank, lookback или Donchian на этих же fold: это будет повторная подгонка к уже исследованным периодам.
- Не включать H-A в рабочий пул и не выбирать символы по её in-sample PnL.
- Сохранить replay как отрицательный результат и использовать его для обновления experiment ledger.
- Следующий исследовательский шаг — диагностировать механику ухудшения fold 3: post-entry 1/3/6-bar returns, retest frequency, breakout extension, adverse excursion, направление и символы. Это диагностика причины, не основание для немедленной оптимизации.
- До нового market PnL replay получить Bybit-native архивы и dated snapshots; все три fold уже исследовались и не являются blind holdout.

## 6. Provenance и ограничения

- Source data: existing audited CryptoFetch H1 OHLCV ZIP archives; dynamic sparse universe.
- Universe: 47 / 49 / 50 symbols by fold; no fixed future-PnL top-5 selection.
- Shared capital: 10,000 USDT per fold; max 5 concurrent positions; 0.5% risk/trade; 2% portfolio risk cap.
- Market entry/exit; no maker fill credit; costs ×2 baseline engine constants.
- Funding omitted; reported funding is zero, not a verified zero-cost outcome.
- No Bybit point-in-time listing/delisting history; symbol availability reflects the archived dataset.
- Fold 3 ends at 2026-10-26 00:00 UTC, one day before requested terminal boundary.
- These are previously inspected E11/E13 windows, not blind holdout.

The run's deterministic tests and archive preparation are separate from the strategy result: a green CI or successful workflow means the code completed, not that H-A is profitable.
