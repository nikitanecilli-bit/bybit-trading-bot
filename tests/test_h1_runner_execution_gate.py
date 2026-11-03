"""Fail-closed execution snapshot gate for the H1 market PnL runner."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.run_h1_shared_capital_portfolio_validation import resolve_execution_snapshot_dirs


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


if __name__ == "__main__":
    for test in (
        test_missing_snapshot_directories_reject_legacy_replay,
        test_empty_snapshot_directory_rejects_legacy_replay,
        test_existing_archives_are_returned,
    ):
        test()
        print(f"PASS {test.__name__}")
