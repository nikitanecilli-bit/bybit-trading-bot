"""Fail-closed execution snapshot gate for the H1 market PnL runner."""
from pathlib import Path
from datetime import datetime, timezone
import sys
import tempfile

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "scripts"))

import Bybit_Trading_Engine_v14_research as em
from run_h1_shared_capital_portfolio_validation import (
    resolve_execution_snapshot_dirs, validate_snapshot_history_coverage,
    resolve_funding_dirs, validate_funding_mark_coverage,
    resolve_bybit_kline_dir, load_bybit_h1_datasets,
    round_limit_quote_to_bybit_tick, engine_cost_stress,
    BASE_TAKER_FEE, BASE_MAKER_FEE, BASE_TAKER_SLIP,
)



def test_cost_stress_restores_engine_globals_after_success_and_exception():
    original = (em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP)
    with engine_cost_stress(2.0):
        assert em.TAKER_FEE == BASE_TAKER_FEE * 2.0
        assert em.MAKER_FEE == BASE_MAKER_FEE * 2.0
        assert em.TAKER_SLIP == BASE_TAKER_SLIP * 2.0
    assert (em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP) == original

    try:
        with engine_cost_stress(1.5):
            raise RuntimeError("synthetic replay failure")
    except RuntimeError as exc:
        assert str(exc) == "synthetic replay failure"
    else:
        raise AssertionError("synthetic exception should propagate")
    assert (em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP) == original

    for invalid in (0, -1, float("inf"), float("nan")):
        try:
            with engine_cost_stress(invalid):
                pass
        except ValueError:
            continue
        raise AssertionError(f"invalid multiplier accepted: {invalid!r}")


def test_missing_snapshot_directories_reject_legacy_replay():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            resolve_execution_snapshot_dirs({
                "BYBIT_INSTRUMENT_SPECS_DIR": str(Path(tmp) / "specs"),
                "BYBIT_RISK_TIERS_DIR": str(Path(tmp) / "tiers"),
            })
        except SystemExit as exc:
            assert "Refusing legacy notional-proxy" in str(exc)
        else:
            raise AssertionError("missing snapshots must fail closed")


def test_empty_snapshot_directory_rejects_legacy_replay():
    with tempfile.TemporaryDirectory() as tmp:
        specs, tiers = Path(tmp) / "specs", Path(tmp) / "tiers"
        specs.mkdir()
        tiers.mkdir()
        (specs / "spec.json").write_text("{}", encoding="utf-8")
        try:
            resolve_execution_snapshot_dirs({
                "BYBIT_INSTRUMENT_SPECS_DIR": str(specs),
                "BYBIT_RISK_TIERS_DIR": str(tiers),
            })
        except SystemExit as exc:
            assert "No dated Bybit risk tiers" in str(exc)
        else:
            raise AssertionError("empty risk-tier archive must fail closed")


def test_existing_archives_are_returned():
    with tempfile.TemporaryDirectory() as tmp:
        specs, tiers = Path(tmp) / "specs", Path(tmp) / "tiers"
        specs.mkdir()
        tiers.mkdir()
        (specs / "spec.json").write_text("{}", encoding="utf-8")
        (tiers / "tiers.json").write_text("{}", encoding="utf-8")
        result = resolve_execution_snapshot_dirs({
            "BYBIT_INSTRUMENT_SPECS_DIR": str(specs),
            "BYBIT_RISK_TIERS_DIR": str(tiers),
        })
        assert result == (str(specs), str(tiers))




def _write_dated_snapshot(path, timestamp_ms):
    fetched_at = datetime.fromtimestamp(
        timestamp_ms / 1000, tz=timezone.utc
    ).isoformat().replace("+00:00", "Z")
    path.write_text('{"schema_version":1,"fetched_at":"' + fetched_at + '"}', encoding="utf-8")


def test_current_only_snapshots_reject_historical_fold():
    with tempfile.TemporaryDirectory() as tmp:
        specs, tiers = Path(tmp) / "specs", Path(tmp) / "tiers"
        specs.mkdir()
        tiers.mkdir()
        current = int(datetime(2026, 11, 3, tzinfo=timezone.utc).timestamp() * 1000)
        _write_dated_snapshot(specs / "spec.json", current)
        _write_dated_snapshot(tiers / "tiers.json", current)
        historical_start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        historical_end = historical_start + 10 * 24 * 60 * 60 * 1000
        try:
            validate_snapshot_history_coverage(specs, tiers, historical_start, historical_end)
        except SystemExit as exc:
            assert "at or before test start" in str(exc)
        else:
            raise AssertionError("current-only snapshots must not validate historical folds")


def test_snapshot_history_rejects_stale_start_and_gaps():
    with tempfile.TemporaryDirectory() as tmp:
        specs, tiers = Path(tmp) / "specs", Path(tmp) / "tiers"
        specs.mkdir()
        tiers.mkdir()
        start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        _write_dated_snapshot(specs / "spec.json", start - 40 * 86400000)
        _write_dated_snapshot(tiers / "tiers.json", start)
        try:
            validate_snapshot_history_coverage(specs, tiers, start, start + 86400000)
        except SystemExit as exc:
            assert "starts stale" in str(exc)
        else:
            raise AssertionError("stale instrument snapshot must fail")
        _write_dated_snapshot(specs / "spec.json", start)
        _write_dated_snapshot(specs / "spec2.json", start + 31 * 86400000)
        try:
            validate_snapshot_history_coverage(specs, tiers, start, start + 32 * 86400000)
        except SystemExit as exc:
            assert "Gap" in str(exc) or "ends stale" in str(exc)
        else:
            raise AssertionError("snapshot gaps over max age must fail")


def test_continuous_snapshot_history_covers_fold():
    with tempfile.TemporaryDirectory() as tmp:
        specs, tiers = Path(tmp) / "specs", Path(tmp) / "tiers"
        specs.mkdir()
        tiers.mkdir()
        start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        end = start + 50 * 86400000
        for directory in (specs, tiers):
            for idx, day in enumerate((0, 25, 50)):
                _write_dated_snapshot(directory / f"{idx}.json", start + day * 86400000)
        validate_snapshot_history_coverage(specs, tiers, start, end)



def test_funding_dirs_are_mandatory_and_non_empty():
    with tempfile.TemporaryDirectory() as tmp:
        funding, marks = Path(tmp) / "funding", Path(tmp) / "marks"
        funding.mkdir()
        marks.mkdir()
        try:
            resolve_funding_dirs({})
        except SystemExit as exc:
            assert "funding as zero" in str(exc)
        else:
            raise AssertionError("missing funding env must fail")
        (funding / "BTCUSDT.csv").write_text("symbol,funding_timestamp_ms,funding_rate\nBTCUSDT,1000,0.001\n", encoding="utf-8")
        (marks / "BTCUSDT.csv").write_text("symbol,timestamp_ms,open\nBTCUSDT,1000,100\n", encoding="utf-8")
        result = resolve_funding_dirs({
            "BYBIT_FUNDING_DIR": str(funding),
            "BYBIT_MARK_PRICE_DIR": str(marks),
        })
        assert result == (str(funding), str(marks))


def test_funding_mark_coverage_requires_every_symbol_and_h1_mark_bar():
    with tempfile.TemporaryDirectory() as tmp:
        funding, marks = Path(tmp) / "funding", Path(tmp) / "marks"
        funding.mkdir()
        marks.mkdir()
        (funding / "BTCUSDT.csv").write_text(
            "symbol,funding_timestamp_ms,funding_rate\nBTCUSDT,1000,0.001\n",
            encoding="utf-8",
        )
        (marks / "BTCUSDT.csv").write_text(
            "symbol,timestamp_ms,open\nBTCUSDT,1000,100\n",
            encoding="utf-8",
        )
        try:
            validate_funding_mark_coverage(
                funding, marks, ["BTCUSDT"], [1000, 3601000], 1000, 3601000
            )
        except SystemExit as exc:
            assert "missing 1 candles" in str(exc)
        else:
            raise AssertionError("missing H1 mark candle must fail")


def test_funding_mark_coverage_rejects_no_settlement_in_fold():
    with tempfile.TemporaryDirectory() as tmp:
        funding, marks = Path(tmp) / "funding", Path(tmp) / "marks"
        funding.mkdir()
        marks.mkdir()
        (funding / "BTCUSDT.csv").write_text(
            "symbol,funding_timestamp_ms,funding_rate\nBTCUSDT,1000,0.001\n",
            encoding="utf-8",
        )
        (marks / "BTCUSDT.csv").write_text(
            "symbol,timestamp_ms,open\nBTCUSDT,1000,100\n",
            encoding="utf-8",
        )
        try:
            validate_funding_mark_coverage(
                funding, marks, ["BTCUSDT"], [2000], 2000, 2000
            )
        except SystemExit as exc:
            assert "No Bybit funding settlements" in str(exc)
        else:
            raise AssertionError("no settlement in fold must fail")




def test_bybit_kline_dir_is_mandatory():
    try:
        resolve_bybit_kline_dir({})
    except SystemExit as exc:
        assert "refusing Binance/CryptoFetch proxy" in str(exc)
    else:
        raise AssertionError("missing Bybit kline dir must fail")


def test_load_bybit_h1_datasets_rejects_gaps_and_loads_exchange_candles():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "BTCUSDT.csv"
        rows = ["symbol,timestamp_ms,open,high,low,close,volume,turnover"]
        for index in range(501):
            ts = 1_699_999_200_000 + index * 3_600_000
            rows.append(f"BTCUSDT,{ts},100,102,99,101,10,1010")
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        loaded = load_bybit_h1_datasets(root)
        assert len(loaded["BTCUSDT"][1]) == 501
        assert loaded["BTCUSDT"][1][0].ts == 1_699_999_200_000
        rows.pop(201)  # remove one H1 candle to create a real one-hour gap
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        try:
            load_bybit_h1_datasets(root)
        except SystemExit as exc:
            assert "duplicate" in str(exc) or "missing or irregular" in str(exc)
        else:
            raise AssertionError("gapped/duplicate Bybit H1 series must fail")


def test_load_bybit_h1_datasets_rejects_off_hour_timestamp_grid():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "BTCUSDT.csv"
        rows = ["symbol,timestamp_ms,open,high,low,close,volume,turnover"]
        for index in range(501):
            ts = 1_700_000_000_000 + index * 3_600_000
            rows.append(f"BTCUSDT,{ts},100,102,99,101,10,1010")
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        try:
            load_bybit_h1_datasets(root)
        except SystemExit as exc:
            assert "not aligned to a UTC hour" in str(exc)
        else:
            raise AssertionError("off-hour timestamps must fail H1 archive validation")



def test_delayed_limit_quotes_are_tick_aligned_without_crossing():
    from bybit_instrument_specs import InstrumentSpec

    snapshot = {
        "instrument": {
            "symbol": "TESTUSDT", "category": "linear", "status": "Trading",
            "priceFilter": {
                "minPrice": "0.05", "maxPrice": "1000000", "tickSize": "0.05"
            },
            "lotSizeFilter": {
                "qtyStep": "0.001", "minOrderQty": "0.01",
                "maxOrderQty": "1000", "maxMktOrderQty": "800",
                "minNotionalValue": "5",
            },
            "leverageFilter": {
                "minLeverage": "1", "maxLeverage": "50", "leverageStep": "0.01"
            },
        }
    }
    spec = InstrumentSpec.from_snapshot(snapshot)
    long_quote = round_limit_quote_to_bybit_tick(spec, 100.079, "long")
    short_quote = round_limit_quote_to_bybit_tick(spec, 100.051, "short")
    assert long_quote == 100.05
    assert short_quote == 100.10
    assert long_quote <= 100.079
    assert short_quote >= 100.051


if __name__ == "__main__":
    for test in (
        test_cost_stress_restores_engine_globals_after_success_and_exception,
        test_missing_snapshot_directories_reject_legacy_replay,
        test_empty_snapshot_directory_rejects_legacy_replay,
        test_existing_archives_are_returned,
        test_current_only_snapshots_reject_historical_fold,
        test_snapshot_history_rejects_stale_start_and_gaps,
        test_continuous_snapshot_history_covers_fold,
        test_funding_dirs_are_mandatory_and_non_empty,
        test_funding_mark_coverage_requires_every_symbol_and_h1_mark_bar,
        test_funding_mark_coverage_rejects_no_settlement_in_fold,
        test_bybit_kline_dir_is_mandatory,
        test_load_bybit_h1_datasets_rejects_gaps_and_loads_exchange_candles,
        test_load_bybit_h1_datasets_rejects_off_hour_timestamp_grid,
        test_delayed_limit_quotes_are_tick_aligned_without_crossing,
    ):
        test()
        print(f"PASS {test.__name__}")
