# H-C reverse-time CryptoFetch proxy — результаты 2026-11-04

## Краткий вердикт

**H-C отклонена как прибыльная стратегия на этом proxy-окне.** Она улучшила gross PnL и expectancy на сделку относительно базовой H1 Donchian-volume версии, но почти удвоила количество сделок и более чем удвоила совокупные издержки. Итоговый proxy net до funding оказался хуже baseline на 159.65 USDT. Ни одна версия не приблизилась к цели +20% в месяц.

Это reverse-time robustness check на CryptoFetch OHLCV, а не forward OOS, не Bybit-native backtest и не funding-inclusive net PnL. Правило H-C было сформулировано после изучения более позднего окна; этот результат не является независимым prospective proof.

## Воспроизводимость

- Protocol ID: H-C-RT-CRYPTOFETCH-2026-11-04-v1
- GitHub Actions run: [#41722545731](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41722545731), SUCCESS.
- Artifact: h-c-reverse-time-cryptofetch-proxy, ID 13272957989.
- Research commit: a5e7e1799f472db4cc00824dfcc774b40058165e.
- Research CI / deterministic gates before execution: [#41722380421](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41722380421), SUCCESS, 53/53. The exact execution commit also passed Research CI [#41722545755](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41722545755), SUCCESS, 53/53.
- The earlier workflow attempt [#41722181706](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41722181706) failed on a script import before archive loading or PnL execution. The path fix passed CI before the completed replay. The failed bootstrap did not consume the preregistered PnL run.
- Input archive integrity summary: 50 valid H1 symbols in archive, 6 duplicate symbol/timeframe groups, zero conflicting overlap bars, zero longest-archive-not-superset pairs. The frozen early-window universe below is a 25-symbol subset.
- Code SHA-256 inventory is embedded in the artifact manifest.

## Зафиксированный протокол

- Window: 2025-10-30 00:00 UTC — 2026-04-26 23:00 UTC inclusive; 72 H1 warmup bars before first scored candle.
- Frozen symbols (25): AAVEUSDT, ASTERUSDT, BCHUSDT, CAKEUSDT, DASHUSDT, DOTUSDT, ENAUSDT, ETCUSDT, GMXUSDT, HBARUSDT, ICPUSDT, JSTUSDT, MORPHOUSDT, ONDOUSDT, PAXGUSDT, PUMPUSDT, QNTUSDT, RAYUSDT, RENDERUSDT, SHIBUSDT, SKYUSDT, TAOUSDT, WLDUSDT, WLFIUSDT, XLMUSDT.
- Baseline: H1 Donchian(20), volume ratio 1.6.
- H-C: same signal/portfolio model with fixed post-break invalidation enabled for the first 3 completed H1 bars after fill, including the fill bar.
- Capital 10,000 USDT per variant; risk/trade 0.5%; portfolio risk cap 2%; max 5 concurrent; leverage 5x; daily stop 5%; kill switch 30%; max chase 1.5%; ATR14; stop 2.5 ATR; TP1 2R; TP2 5R; trail 3 ATR; max hold 32 bars.
- Market entries/exits; fee and taker-slippage constants multiplied by 2.0. No maker credit.
- Funding and mark-price data omitted. No Bybit API, private account API, new market-data download or orders.

## Итоговые метрики

| Метрика | Baseline | H-C | Изменение H-C |
|---|---:|---:|---:|
| Сделки | 313 | 610 | +94.9% |
| Gross PnL | −1,098.10 | +404.08 | +1,502.18 |
| Комиссии | 1,151.42 | 2,330.71 | +1,179.29 |
| Проскальзывание | 470.95 | 953.49 | +482.54 |
| Совокупные издержки | 1,622.37 | 3,284.20 | +1,661.83 |
| Proxy net до funding | −2,720.47 | −2,880.12 | −159.65 |
| Profit Factor | 0.63 | 0.72 | улучшение, но <1 |
| Expectancy | −0.213R | −0.120R | улучшение, но отрицательная |
| Max drawdown | 30.06% | 30.18% | на 0.12 п.п. хуже |
| Geometric monthly proxy | −5.26% | −5.61% | хуже |

Оба варианта убыточны ещё до funding. Средние моделируемые издержки на сделку: baseline 5.18 USDT, H-C 5.38 USDT. Основной рост совокупных издержек вызван частотой сделок, а не резким ростом стоимости одной сделки.

## Что изменил H-C

| Причина выхода | Baseline сделок | H-C сделок | Baseline net | H-C net |
|---|---:|---:|---:|---:|
| Stop loss | 180 | 138 | −6,947.31 | −5,251.93 |
| Breakout retest invalidation | 0 | 296 | — | −4,535.90 |
| Take profit | 12 | 25 | +1,130.05 | +2,253.80 |
| Time stop | 74 | 87 | +1,180.24 | +1,838.94 |
| Trailing stop | 42 | 62 | +1,982.69 | +2,846.01 |
| Kill switch | 5 | 2 | −66.14 | −31.04 |

- 296 H-C invalidation exits — 48.5% всех сделок H-C.
- Среднее удержание такой сделки: 1.53 часа; средний результат −0.399R / −15.32 USDT.
- Invalidation exits дали gross −3,112.09, fees 1,010.47, slippage 413.34, net −4,535.90.
- H-C сократила stop-loss exits на 42 и уменьшила net-убыток stop-loss примерно на 1,695 USDT. Также выросли прибыльные TP/time/trailing exits.
- Но новые ранние закрытия добавили −4,535.90 USDT net; улучшений по остальным причинам не хватило, чтобы их компенсировать.
- Kill switch сработал у baseline 2025-12-28 20:00 UTC, у H-C 2026-01-27 18:00 UTC — H-C продержалась примерно на 29 дней 22 часа дольше, но обе версии всё равно достигли аварийного лимита.

### Помесячная equity

| Месяц UTC | Baseline | H-C | Примечание |
|---|---:|---:|---|
| 2025-10 | −0.86% | −1.34% | частичный месяц |
| 2025-11 | −13.35% | −9.14% | полный месяц |
| 2025-12 | −15.26% | −10.70% | полный месяц |
| 2026-01 | 0.00% | −11.06% | baseline уже остановлен kill switch 28 Dec |
| 2026-02 | 0.00% | 0.00% | обе версии остановлены |
| 2026-03 | 0.00% | 0.00% | обе версии остановлены |
| 2026-04 | 0.00% | 0.00% | частичный месяц; обе версии остановлены |

Нулевые месяцы после kill switch — это отсутствие торговли после аварийной остановки, а не стабильность/безубыточность. Ни одного полного месяца с +20% нет.

## Дополнительная пост-хок диагностика

После H-C invalidation exit последующая сделка того же символа и направления нашлась в 270 из 296 случаев. Медианное время до неё — 111 часов; только 11 из 270 следующих входов (4.1%) имели breakout boundary в пределах 0.2% от предыдущей. Следовательно, рост числа сделок не объясняется в основном немедленным повторным входом на тот же уровень: раннее закрытие освобождало риск-бюджет, после чего стратегия позже принимала новые сигналы. Это post-hoc описание, не основание для настройки cooldown на этом же окне.

PAXGUSDT был крупнейшим cost sink: 52 сделки, gross +179.52, fees 562.32 и slippage 230.02, итог −612.82 USDT. Это наблюдение не используется для отбора монет: выбор символов по результату этого же окна был бы selection bias.

## Решение

1. H-C отклонена как кандидат на прибыльную стратегию в рамках preregistered reverse-time proxy: proxy net отрицателен и хуже baseline.
2. Не менять горизонт 3 бара, границу пробоя или правила re-entry на этом окне; оно использовано и закрыто.
3. Не использовать эти результаты как Bybit net PnL: funding, mark-price liquidation и point-in-time listing/delisting отсутствуют.
4. Весь годовой CryptoFetch архив теперь development-only; новых PnL sweep на нём не запускать как будто это независимый holdout.
5. Следующая гипотеза должна уменьшать частоту слабых входов и повышать gross edge на сделку (длиннее Donchian / causal trend regime filter), а не добавлять ещё один ранний выход. Её параметры нужно заранее заморозить; для честной проверки понадобится новая, неиспользованная история.
6. H-C остаётся disabled-by-default. Никакого Bybit API, подключения аккаунта или реальных ордеров.
