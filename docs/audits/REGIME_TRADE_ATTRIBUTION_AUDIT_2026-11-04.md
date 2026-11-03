# Аудит атрибуции сделок к рыночному режиму

Дата: 2026-11-04  
Ветка: `research/market-regime-v1-main`  
Scope: `scripts/run_regime_analysis.py`, `scripts/run_regime_gate_holdout.py`, `TradeRecord.signal_ts_ms`.

## Подтверждённое ограничение

`trade_signal_regime()` ранее определяла сигнальную свечу как `entry_ts - timeframe_ms`. Это корректно только для немедленного next-bar fill. Движок поддерживает delayed fills и сохраняет исходный `signal_ts_ms` в TradeRecord; при задержанном исполнении вычитание одного таймфрейма могло приписать сделку к другому режиму, чем тот, на котором возник исходный сигнал.

Текущие `run_regime_analysis.py` и `run_regime_gate_holdout.py` используют market-entry baseline, поэтому данный дефект не менял уже сформированные ими отчёты. Это был latent reporting defect при повторном использовании helper с delayed-fill records, а не PnL/accounting defect.

## Исправление

- При наличии `signal_ts_ms` helper использует точную исходную метку сигнала для lookup режима.
- Для старых journal rows без этого поля сохранён fallback `entry_ts - timeframe_ms`, действительный только для legacy next-bar market-entry convention.
- Некорректный непустой `signal_ts_ms` возвращает `unknown` (fail closed), а не подменяется вычисленной датой.
- Добавлены регрессии: delayed fill с разными режимами на исходной и предполагаемой свече; invalid signal timestamp.

Изменённые файлы:
- `scripts/run_regime_analysis.py`
- `tests/test_regime_analysis.py`

Commit: `8e73e05f8bc97163d44527001c302d35a8b84a62`.

## Проверка

Research CI [#41738201800](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41738201800) завершился **SUCCESS**. Compile, regime-analysis report helper tests, frozen regime gate tests, portfolio accounting и остальные workflow steps прошли.

## Границы

- Изменена только диагностическая атрибуция режима; торговые сигналы, fills, риск и PnL не менялись.
- Не запускались рыночные backtests, parameter sweeps или новые holdout PnL расчёты.
- Это не закрывает Funding completeness, Bybit-native data provenance, directional-scope или maker-fill realism gates.
