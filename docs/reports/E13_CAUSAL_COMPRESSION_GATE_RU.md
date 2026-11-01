# E13 — causal compression gate on shared-capital H1 portfolio

Дата: 2026-11-02  
Статус: **завершён, workflow success**  
Workflow: [41362217727](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362217727)  
Artifact: [e13-h1-compression-gate-shared-capital](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362217727/artifacts/13105403824)  
Artifact SHA-256: `9930d6f3651305ef9dcf254c85bc0b50b24cb098b6b367accbaaae4bbad6f601`  
Commit: `f4da3cca0c0dc79cee86350ba6a680fc461e47fc`  
Script: `scripts/run_e13_h1_compression_gate_replay.py`

## Вопрос

Может ли один causal compression veto уменьшить убытки в слабом/сжатом режиме fold 2, не отключая локальные breakout-сигналы в fold 1 и broad trend-сигналы в fold 3?

## Зафиксированное правило

Compression = одновременно:
1. текущий broad median ATR% ниже expanding 25th percentile всех предыдущих завершённых hourly context observations;
2. текущий cross-sectional IQR 72h returns ниже expanding 25th percentile всех предыдущих завершённых hourly context observations.

Минимум 336 предыдущих context hours для активации. До завершения warm-up gate не блокирует сигналы. Порог не подбирался по PnL; один rule, без sweep.

## Методика

- 47 символов на общей сетке 4,321 H1 баров (2026-04-29 00:00 — 2026-10-26 00:00 UTC).
- Один общий капитал 10,000 USDT на каждый fold; 1% risk/trade, 2% portfolio risk cap, max 5 concurrent positions.
- Market execution, body gate OFF, next-open gap gate OFF.
- Donchian 20, ATR 14, volume ratio >=1.6, breakout/ATR >=0.25.
- Taker fees/slippage ×2.
- Сравнение compression gate OFF/ON — единственное изменяемое условие.
- Baseline compression OFF точно воспроизвёл E11 body-gate-OFF результаты по всем трём fold. Это подтверждает отсутствие дрейфа в baseline.

## Результаты

| Fold | Compression | Trades | Заблокировано candidate signals | Gross PnL | Fees + slippage | Net PnL | PF | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | OFF | 207 | 0 | +774.98 | 1,392.60 | **-617.62** | 0.888 | 39.61% |
| 1 | ON | 211 | 65 | +1,109.44 | 1,404.37 | **-294.93** | 0.945 | 41.71% |
| 2 | OFF | 227 | 0 | -1,395.34 | 1,574.71 | **-2,970.05** | 0.545 | 31.72% |
| 2 | ON | 197 | 137 | -1,255.84 | 1,358.71 | **-2,614.55** | 0.540 | 32.99% |
| 3 | OFF | 338 | 0 | +2,609.45 | 2,200.39 | **+409.06** | 1.039 | 37.57% |
| 3 | ON | 316 | 89 | +2,249.25 | 2,081.49 | **+167.76** | 1.017 | 37.34% |

### Сумма трёх отдельных fold

| Метрика | OFF | ON |
|---|---:|---:|
| Сделки | 772 | 724 |
| Gross PnL | +1,989.09 | +2,102.85 |
| Fees + slippage | 5,167.70 | 4,844.57 |
| Net PnL | **-3,178.61** | **-2,741.72** |
| Profit factor | 0.859 | 0.870 |
| Win rate | 36.4% | 37.4% |
| Mean net R | -0.080 | -0.059 |

Сумма fold — не непрерывная equity curve: каждый fold стартует с 10,000 USDT заново.

Gate:
- уменьшил количество сделок на 48 (6.2%);
- уменьшил fees+slippage на 323.13 USDT (6.3%);
- увеличил gross на 113.76 USDT;
- улучшил сумму независимых fold результатов на 436.89 USDT (снижение абсолютного убытка на 13.7%).

Но итог всё ещё отрицательный. Fold 2 остаётся сильно убыточным (-2,614.55), а прибыль fold 3 уменьшилась с +409.06 до +167.76.

## Почему эффект различается по fold

Сопоставление сделок OFF/ON по ключу `(symbol, signal_ts)`:

| Fold | Общие сделки | Удалены | Net удалённых | Новые | Net новых | Delta общих | Итог ON − OFF |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 194 | 13 | -171.10 | 17 | +173.77 | -22.18 | **+322.69** |
| 2 | 150 | 77 | -970.05 | 47 | -474.56 | -139.99 | **+355.50** |
| 3 | 298 | 40 | +295.06 | 18 | +24.79 | +28.97 | **-241.30** |

- Fold 1: gate удалил 13 убыточных сделок и открыл место для 17 новых, которые в сумме дали небольшой плюс. Результат улучшился.
- Fold 2: удалены 77 сделок с net -970.05, но новые 47 сделок тоже убыточны (-474.56). Убыток сократился, но режим остаётся плохим.
- Fold 3: среди удалённых были прибыльные сделки (+295.06), а новые сделки принесли только +24.79. Поэтому фильтр уменьшил прибыль.

Это подтверждает, что compression gate меняет не только список отсеянных сигналов, но и последующую последовательность доступных входов.

## Вывод

1. Causal compression gate умеренно улучшил суммарный shared-capital результат и уменьшил издержки.
2. Он помог fold 1 и fold 2, но сократил прибыль fold 3.
3. Улучшение не устранило отрицательное матожидание в fold 1/2 и не доказало устойчивость на будущем holdout.
4. Не следует добавлять его в production или оптимизировать percentile threshold по этим же периодам.
5. По сравнению с E10 per-symbol независимыми счетами, E11/E13 shared-capital replay остаётся более строгим критерием.

## Ограничения

- Binance OHLCV proxy, не Bybit trades/order book.
- Fees/slippage model ×2; funding не включён.
- Нет реального spread, market impact, partial fills и intrabar liquidation model.
- Три исторических fold уже исследовались; это не blind holdout.
- Каждый fold начинается с 10,000 USDT заново.
- Реальные ордера не размещались.

## Решение

Оставить compression gate в исследовательской ветке как promising but unproven. Не менять production config и не перебирать пороги. Следующий этап — проверить, устойчив ли compression regime за пределами этих трёх fold, и отдельно проверить его на будущих данных. Если будет возможность, сохранить правило без изменений до накопления нового holdout.

