"""Fail-closed execution snapshot gate for the H1 market PnL runner."""
from pathlib import Path
from datetime import datetime, timezone
import sys
import tempfile

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "scripts"))
from run_h1_shared_capital_portfolio_validation import (
    resolve_execution_snapshot_dirs, validate_snapshot_history_coverage,
)


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

if __name__ == "__main__":
    for test in (
        test_missing_snapshot_directories_reject_legacy_replay,
        test_empty_snapshot_directory_rejects_legacy_replay,
        test_existing_archives_are_returned,
        test_current_only_snapshots_reject_historical_fold,
        test_snapshot_history_rejects_stale_start_and_gaps,
        test_continuous_snapshot_history_covers_fold,
    ):
        test()
        print(f"PASS {test.__name__}")
