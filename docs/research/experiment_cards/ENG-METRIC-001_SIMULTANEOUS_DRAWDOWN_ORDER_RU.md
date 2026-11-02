# ENG-METRIC-001 — независимость max drawdown от порядка закрытия сделок

Статус: ACCEPT

## Гипотеза дефекта
`MaintenanceGateAuditor.evaluate_portfolio()` проходил `trades` в порядке списка. При нескольких закрытиях с одним `exit_date` промежуточные изменения equity внутри одного timestamp создавали искусственный внутримоментный peak/drawdown. Перестановка символов могла менять `max_dd_pct`, хотя совокупный PnL на timestamp оставался тем же. Несортированный входной список также мог искажать временную последовательность equity.

## Test-first доказательство
- Тестовый коммит: `68edd2ea5f6649c1327bcbcb22e72a6a35e629f1`.
- CI до исправления: [#41512547727](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41512547727) — portfolio accounting step FAILED именно на `test_drawdown_is_order_independent_for_simultaneous_trade_closes` (AssertionError).
- Контрольные примеры:
  - Одновременные +100 и -200 USDT при капитале 10 000 USDT должны дать net -100 и drawdown 1.00%, независимо от порядка списка.
  - Более ранний -200 и более поздний +100 должны дать drawdown 2.00%, независимо от порядка входного списка.

## Исправление
- Коммит: `2d44d14a4981b1b3b6c259c8c04e2123acc0b489`.
- В `MaintenanceGateAuditor.evaluate_portfolio()` сделки группируются по UTC-моменту `exit_date`; PnL каждой группы применяется к equity одним событием. Группы обрабатываются хронологически.
- Некорректный или timezone-naive `exit_date` отклоняется с ValueError, а не используется для потенциально неверной кривой equity.
- MTM max drawdown по-прежнему объединяется через максимум с закрытой equity-кривой; отчёт не занижает уже зафиксированную внутрисвечную просадку движка.

## Верификация
- Full Research CI: [#41512721144](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41512721144) — SUCCESS.
- Portfolio accounting: 24/24 tests; обе новые регрессии PASS.
- State persistence: 60 tests; остальные шаги Research CI завершились успешно.

## Границы
Это исправление корректности метрики отчёта, а не торгового сигнала и не доказательство прибыльности. Синхронные сделки считаются одним net equity event на timestamp; отдельная внутрисвечная траектория equity не восстанавливается из OHLC и должна оцениваться по MTM-маркам, если они доступны.
