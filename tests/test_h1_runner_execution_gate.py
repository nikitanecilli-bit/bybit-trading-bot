"""Fail-closed execution snapshot gate for the H1 market PnL runner."""
from pathlib import Path
from datetime import datetime, timezone
import sys
import os
import tempfile
import json
import csv

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "scripts"))

import Bybit_Trading_Engine_v14_research as em
from funding_archive_manifest import record_funding_collection, sha256_file


def _write_funding_manifest(
    funding_path, start_ms, end_ms, *,
    schedule_start_ms=None, expected_events=None, funding_interval_minutes=60,
    include_schedule=True,
):
    manifest_path = funding_path.with_suffix(funding_path.suffix + ".audit.json")
    with funding_path.open("r", encoding="utf-8-sig", newline="") as handle:
        funding_rows = list(csv.DictReader(handle))
    funding_timestamps = [
        int(row.get("funding_timestamp_ms", row.get("timestamp")))
        for row in funding_rows
    ]
    payload = record_funding_collection(
        funding_path, manifest_path, symbol=funding_path.stem,
        category="linear", api_base="https://api.bybit.com",
        requested_start_ms=start_ms, requested_end_ms=end_ms,
        pages=[{
            "request_start_ms": start_ms, "request_end_ms": end_ms,
            "response_rows": len(funding_timestamps),
            "first_ts": min(funding_timestamps) if funding_timestamps else None,
            "last_ts": max(funding_timestamps) if funding_timestamps else None,
            "complete": True, "saturated": False,
        }],
        collected_at_ms=max(end_ms, start_ms) + 1,
    )
    if include_schedule:
        source_snapshots = []
        schedule_start = schedule_start_ms if schedule_start_ms is not None else start_ms
        for ts in sorted(set((schedule_start, end_ms))):
            snapshot_path = funding_path.parent / f"instrument_snapshot_{ts}.json"
            fetched_at = (
                "1970-01-01T00:00:01Z" if ts == 1000
                else "1970-01-01T00:00:02Z" if ts == 2000
                else datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            )
            snapshot_path.write_text(json.dumps({
                "schema_version": 1, "source": "Bybit V5 GET /v5/market/instruments-info", "category": "linear", "fetched_at": fetched_at,
                "count": 1, "instruments": [{"symbol": funding_path.stem, "fundingInterval": str(funding_interval_minutes)}],
            }), encoding="utf-8")
            source_snapshots.append({
                "path": snapshot_path.name, "sha256": sha256_file(snapshot_path),
                "fetched_at_ms": ts, "funding_interval_minutes": funding_interval_minutes,
            })
        schedule_path = funding_path.parent / f"{funding_path.stem}.schedule.json"
        schedule = {
            "schema_version": 1,
            "source": "bybit_dated_instrument_snapshots",
            "symbol": funding_path.stem,
            "category": "linear",
            "coverage_start_ms": schedule_start,
            "coverage_end_ms": end_ms,
            "source_snapshots": source_snapshots,
            "expected_settlement_timestamps_ms": (
                expected_events if expected_events is not None else [start_ms]
            ),
        }
        schedule_path.write_text(json.dumps(schedule), encoding="utf-8")
        payload["settlement_schedule_evidence"] = {
            "path": schedule_path.name,
            "sha256": sha256_file(schedule_path),
        }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    return manifest_path


from run_h1_shared_capital_portfolio_validation import (
    resolve_execution_snapshot_dirs, validate_snapshot_history_coverage,
    resolve_funding_dirs, validate_funding_mark_coverage,
    resolve_bybit_kline_dir, load_bybit_h1_datasets,
    round_limit_quote_to_bybit_tick, engine_cost_stress,
    BASE_TAKER_FEE, BASE_MAKER_FEE, BASE_TAKER_SLIP,
    resolve_validation_design, load_frozen_selection_manifest,
    validate_selection_cutoff, validate_selection_provenance, runtime_provenance,
    selection_validation_boundary, geometric_monthly_return_pct,
)




def _selection_env(tmpdir):
    manifest = Path(tmpdir) / "selection.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "selection_protocol": "h1-top5-train-only-v2",
        "selection_status": "ok",
        "generated_at_utc": "2026-11-03T00:00:00Z",
        "training_window": {"cutoff_timestamp_ms": 1000},
        "input_files": {key: [] for key in ("kline", "funding", "mark_price", "instrument_specs", "risk_tiers", "universe_snapshot")},
        "code_files": [],
        "primary": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"],
    }), encoding="utf-8")
    return {
        "H1_SELECTION_MANIFEST": str(manifest),
        "H1_SYMBOL_ALLOWLIST": "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT",
    }


def test_explore_mode_uses_only_frozen_train_selected_top_five():
    with tempfile.TemporaryDirectory() as tmp:
        env = _selection_env(tmp)
        env["H1_VALIDATION_MODE"] = "explore"
        design = resolve_validation_design(env)
    assert [fold[0] for fold in design["folds"]] == [1, 2]
    assert design["volume_thresholds"] == [1.2, 1.6, 2.0, 2.5]
    assert design["breakout_atr_thresholds"] == [0.0, 0.10, 0.25]
    assert design["cost_multipliers"] == [1.0, 1.5, 2.0]
    assert design["selection"]["symbols"] == ["BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]


def test_confirm_mode_requires_one_frozen_predeclared_config_and_selection_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        env = _selection_env(tmp)
        env.update({
            "H1_VALIDATION_MODE": "confirm",
            "H1_FROZEN_MIN_VOLUME_RATIO": "1.6",
            "H1_FROZEN_MIN_BREAKOUT_ATR": "0.10",
        })
        design = resolve_validation_design(env)
    assert [fold[0] for fold in design["folds"]] == [3]
    assert design["volume_thresholds"] == [1.6]
    assert design["breakout_atr_thresholds"] == [0.10]
    assert design["cost_multipliers"] == [1.0, 1.5, 2.0]
    assert design["frozen_config"]["symbols"] == ["BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    assert design["frozen_config"]["selection_manifest_sha256"] == design["selection"]["sha256"]


def test_selection_manifest_and_allowlist_must_match_exactly():
    with tempfile.TemporaryDirectory() as tmp:
        env = _selection_env(tmp)
        env["H1_SYMBOL_ALLOWLIST"] = "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT"
        try:
            resolve_validation_design(env)
        except SystemExit as exc:
            assert "exactly match" in str(exc)
        else:
            raise AssertionError("mismatched frozen allowlist must fail")


def test_selection_manifest_must_be_valid_and_successful():
    with tempfile.TemporaryDirectory() as tmp:
        env = _selection_env(tmp)
        Path(env["H1_SELECTION_MANIFEST"]).write_text(
            '{"schema_version":1,"selection_protocol":"h1-top5-train-only-v2","selection_status":"insufficient_candidates"}',
            encoding="utf-8",
        )
        try:
            resolve_validation_design(env)
        except SystemExit as exc:
            assert "no valid top-five" in str(exc)
        else:
            raise AssertionError("failed selector manifest must fail closed")



def test_selection_provenance_rejects_changed_data_and_code():
    selection = {
        "input_files": {
            "kline": [{"path": "data/BTC.csv", "sha256": "abc", "size_bytes": 10}],
            "funding": [], "mark_price": [], "instrument_specs": [], "risk_tiers": [],
            "universe_snapshot": [{"path": "data/universe.json", "sha256": "universe1", "size_bytes": 30}],
        },
        "code_files": [{"path": "engine.py", "sha256": "code1", "size_bytes": 20}],
    }
    current = {
        "kline": [{"path": "data/BTC.csv", "sha256": "abc", "size_bytes": 10}],
        "funding": [], "mark_price": [], "instrument_specs": [], "risk_tiers": [],
        "universe_snapshot": [{"path": "data/universe.json", "sha256": "universe1", "size_bytes": 30}],
    }
    validate_selection_provenance(
        selection, current,
        [{"path": "engine.py", "sha256": "code1", "size_bytes": 20}],
    )
    changed_data = dict(current)
    changed_data["kline"] = [{"path": "data/BTC.csv", "sha256": "changed", "size_bytes": 10}]
    try:
        validate_selection_provenance(
            selection, changed_data,
            [{"path": "engine.py", "sha256": "code1", "size_bytes": 20}],
        )
    except SystemExit as exc:
        assert "provenance mismatch" in str(exc)
    else:
        raise AssertionError("changed training/validation data must force reselection")
    try:
        validate_selection_provenance(
            selection, current,
            [{"path": "engine.py", "sha256": "changed", "size_bytes": 20}],
        )
    except SystemExit as exc:
        assert "code changed" in str(exc)
    else:
        raise AssertionError("changed replay code must force reselection")



def test_selection_provenance_rejects_changed_universe_snapshot():
    selection = {
        "input_files": {
            "kline": [], "funding": [], "mark_price": [],
            "instrument_specs": [], "risk_tiers": [],
            "universe_snapshot": [{"path": "universe.json", "sha256": "old", "size_bytes": 10}],
        },
        "code_files": [],
    }
    current = {
        "kline": [], "funding": [], "mark_price": [],
        "instrument_specs": [], "risk_tiers": [],
        "universe_snapshot": [{"path": "universe.json", "sha256": "new", "size_bytes": 10}],
    }
    try:
        validate_selection_provenance(selection, current, [])
    except SystemExit as exc:
        assert "universe_snapshot" in str(exc)
    else:
        raise AssertionError("changed lifecycle snapshot must force a new selection")



def test_runtime_provenance_separates_research_checkout_from_workflow_ref():
    names = ("H1_RESEARCH_CHECKOUT_SHA", "GITHUB_SHA", "GITHUB_WORKFLOW_REF", "GITHUB_REF")
    original = {name: os.environ.get(name) for name in names}
    try:
        os.environ["H1_RESEARCH_CHECKOUT_SHA"] = "research-sha"
        os.environ["GITHUB_SHA"] = "workflow-sha"
        os.environ["GITHUB_WORKFLOW_REF"] = "owner/repo/.github/workflows/validation.yml@refs/heads/main"
        os.environ["GITHUB_REF"] = "refs/heads/main"
        result = runtime_provenance()
        assert result["git_commit"] == "research-sha"
        assert result["workflow_definition_commit"] == "workflow-sha"
        assert result["workflow_definition_ref"].endswith("@refs/heads/main")
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value




def test_geometric_monthly_return_normalizes_compounded_returns_by_exact_duration():
    month_ms = int(round(365.2425 / 12.0 * 86_400_000))
    one_month = geometric_monthly_return_pct(2_000.0, 10_000.0, 0, month_ms - 3_600_000)
    two_months = geometric_monthly_return_pct(4_400.0, 10_000.0, 0, 2 * month_ms - 3_600_000)
    assert abs(one_month["geometric_monthly_return_pct"] - 20.0) < 1e-8
    assert abs(two_months["geometric_monthly_return_pct"] - 20.0) < 1e-8
    assert abs(one_month["duration_months"] - 1.0) < 1e-8


def test_geometric_monthly_return_rejects_invalid_duration_and_handles_total_loss():
    try:
        geometric_monthly_return_pct(100.0, 10_000.0, 2_000, 1_000)
    except ValueError:
        pass
    else:
        raise AssertionError("reversed fold timestamps must fail")
    wiped = geometric_monthly_return_pct(-10_000.0, 10_000.0, 0, 30 * 86_400_000)
    assert wiped["geometric_monthly_return_pct"] == -100.0


def test_selection_boundary_remains_first_explore_fold_in_confirm_mode():
    timestamps = [1_700_000_000_000 + i * 3_600_000 for i in range(10)]
    boundary = selection_validation_boundary(timestamps)
    assert boundary == timestamps[5]
    validate_selection_cutoff({"training_cutoff_timestamp_ms": timestamps[4]}, boundary)
    try:
        # A cutoff at 60% would pass a confirm-only 80% check, but must fail the 50% gate.
        validate_selection_cutoff({"training_cutoff_timestamp_ms": timestamps[6]}, boundary)
    except SystemExit as exc:
        assert "selection leakage" in str(exc)
    else:
        raise AssertionError("selection must not consume data from explore folds")


def test_selection_cutoff_must_precede_validation():
    selection = {"training_cutoff_timestamp_ms": 1000}
    validate_selection_cutoff(selection, 1001)
    try:
        validate_selection_cutoff(selection, 1000)
    except SystemExit as exc:
        assert "selection leakage" in str(exc)
    else:
        raise AssertionError("validation window overlapping selector train period must fail")


def test_confirm_mode_rejects_missing_or_unregistered_config():
    for volume, breakout in ((None, None), ("1.7", "0.10"), ("1.6", "0.20")):
        with tempfile.TemporaryDirectory() as tmp:
            env = _selection_env(tmp)
            env["H1_VALIDATION_MODE"] = "confirm"
            if volume is not None:
                env["H1_FROZEN_MIN_VOLUME_RATIO"] = volume
            if breakout is not None:
                env["H1_FROZEN_MIN_BREAKOUT_ATR"] = breakout
            try:
                resolve_validation_design(env)
            except SystemExit:
                continue
            raise AssertionError("invalid frozen configuration accepted")


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
            "symbol,funding_timestamp_ms,funding_rate\n"
            "BTCUSDT,28800000,0.001\n"
            "BTCUSDT,57600000,0.001\n",
            encoding="utf-8",
        )
        (marks / "BTCUSDT.csv").write_text(
            "symbol,timestamp_ms,open\n"
            "BTCUSDT,28800000,100\n"
            "BTCUSDT,32400000,100\n"
            "BTCUSDT,57600000,100\n",
            encoding="utf-8",
        )
        _write_funding_manifest(
            funding / "BTCUSDT.csv", 28800000, 57600000,
            expected_events=[28800000, 57600000], funding_interval_minutes=480,
        )
        try:
            validate_funding_mark_coverage(
                funding, marks, ["BTCUSDT"],
                [28800000, 32400000, 36000000], 28800000, 36000000,
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
            "symbol,funding_timestamp_ms,funding_rate\n"
            "BTCUSDT,28800000,0.001\n"
            "BTCUSDT,57600000,0.001\n",
            encoding="utf-8",
        )
        (marks / "BTCUSDT.csv").write_text(
            "symbol,timestamp_ms,open\n"
            "BTCUSDT,28800000,100\n"
            "BTCUSDT,57600000,100\n",
            encoding="utf-8",
        )
        _write_funding_manifest(
            funding / "BTCUSDT.csv", 28800000, 57600000,
            expected_events=[28800000, 57600000], funding_interval_minutes=480,
        )
        try:
            validate_funding_mark_coverage(
                funding, marks, ["BTCUSDT"], [32400000, 36000000],
                32400000, 36000000,
            )
        except SystemExit as exc:
            assert "No Bybit funding settlements" in str(exc)
        else:
            raise AssertionError("no settlement in fold must fail")


def test_funding_mark_coverage_rejects_missing_or_unverified_archive_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        funding, marks = Path(tmp) / "funding", Path(tmp) / "marks"
        funding.mkdir()
        marks.mkdir()
        funding_path = funding / "BTCUSDT.csv"
        funding_path.write_text(
            "symbol,funding_timestamp_ms,funding_rate\nBTCUSDT,3600000,0.001\n",
            encoding="utf-8",
        )
        (marks / "BTCUSDT.csv").write_text(
            "symbol,timestamp_ms,open\nBTCUSDT,3600000,100\n",
            encoding="utf-8",
        )
        _write_funding_manifest(funding_path, 3600000, 3600000, include_schedule=False)
        try:
            validate_funding_mark_coverage(
                funding, marks, ["BTCUSDT"], [3600000], 3600000, 3600000
            )
        except SystemExit as exc:
            assert "dated_settlement_schedule_evidence_missing" in str(exc)
        else:
            raise AssertionError("unverified funding schedule must block H1 replay")


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


def test_load_bybit_h1_datasets_rejects_symbol_filename_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "BTCUSDT.csv"
        rows = ["symbol,timestamp_ms,open,high,low,close,volume,turnover"]
        for index in range(501):
            ts = 1_699_999_200_000 + index * 3_600_000
            row_symbol = "ETHUSDT" if index == 0 else "BTCUSDT"
            rows.append(f"{row_symbol},{ts},100,102,99,101,10,1010")
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        try:
            load_bybit_h1_datasets(root)
        except SystemExit as exc:
            assert "does not match filename symbol BTCUSDT" in str(exc)
        else:
            raise AssertionError("mismatched CSV symbol must fail archive validation")



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
        test_explore_mode_uses_only_frozen_train_selected_top_five,
        test_confirm_mode_requires_one_frozen_predeclared_config_and_selection_manifest,
        test_selection_manifest_and_allowlist_must_match_exactly,
        test_selection_manifest_must_be_valid_and_successful,
        test_selection_provenance_rejects_changed_data_and_code,
        test_selection_provenance_rejects_changed_universe_snapshot,
        test_runtime_provenance_separates_research_checkout_from_workflow_ref,
        test_geometric_monthly_return_normalizes_compounded_returns_by_exact_duration,
        test_geometric_monthly_return_rejects_invalid_duration_and_handles_total_loss,
        test_selection_boundary_remains_first_explore_fold_in_confirm_mode,
        test_selection_cutoff_must_precede_validation,
        test_confirm_mode_rejects_missing_or_unregistered_config,
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
        test_funding_mark_coverage_rejects_missing_or_unverified_archive_manifest,
        test_bybit_kline_dir_is_mandatory,
        test_load_bybit_h1_datasets_rejects_gaps_and_loads_exchange_candles,
        test_load_bybit_h1_datasets_rejects_off_hour_timestamp_grid,
        test_load_bybit_h1_datasets_rejects_symbol_filename_mismatch,
        test_delayed_limit_quotes_are_tick_aligned_without_crossing,
    ):
        test()
        print(f"PASS {test.__name__}")
