from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.audit_instrument_snapshot_coverage import (
    audit_directory, audit_joint_market_state, audit_risk_tier_directory, build_report, main,
)


def write_snapshot(root: Path, name: str, fetched_at: str, instruments: list[dict],
                   started_at: str | None = None,
                   page_observations: list[dict] | None = None,
                   category: str = "linear") -> None:
    payload = {
        "schema_version": 1,
        "source": "Bybit V5 GET /v5/market/instruments-info",
        "category": category,
        "fetched_at": fetched_at,
        "count": len(instruments),
        "instruments": instruments,
    }
    if started_at is not None:
        payload["collection_started_at"] = started_at
    if page_observations is not None:
        payload["page_observations"] = page_observations
    if started_at is not None:
        payload["collection_started_at"] = started_at
    if page_observations is not None:
        payload["page_observations"] = page_observations
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(payload), encoding="utf-8")


def instrument(symbol: str, status: str = "Trading") -> dict:
    base = symbol.removesuffix("USDT")
    return {
        "symbol": symbol, "status": status, "category": "linear",
        "contractType": "LinearPerpetual", "baseCoin": base,
        "quoteCoin": "USDT", "settleCoin": "USDT",
        "priceFilter": {"minPrice": "0.01", "maxPrice": "1000000", "tickSize": "0.1"},
        "lotSizeFilter": {
            "qtyStep": "0.001", "minOrderQty": "0.001",
            "maxOrderQty": "100", "maxMktOrderQty": "50",
            "minNotionalValue": "5",
        },
        "leverageFilter": {
            "minLeverage": "1", "maxLeverage": "50", "leverageStep": "0.01",
        },
    }


def write_risk_snapshot(root: Path, name: str, fetched_at: str,
                        symbols: tuple[str, ...], *,
                        started_at: str | None = None,
                        page_observations: list[dict] | None = None) -> None:
    tiers = []
    for symbol in symbols:
        tiers.append({
            "symbol": symbol, "id": 1, "riskLimitValue": "100000",
            "maintenanceMargin": "0.005", "initialMargin": "0.01",
            "maxLeverage": "100", "isLowestRisk": 1, "mmDeduction": "0",
        })
    payload = {
        "schema_version": 1,
        "source": "Bybit V5 GET /v5/market/risk-limit",
        "category": "linear", "fetched_at": fetched_at,
        "symbol_count": len(symbols), "tier_count": len(tiers), "tiers": tiers,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(payload), encoding="utf-8")


class InstrumentSnapshotCoverageAuditTests(unittest.TestCase):


    def test_risk_tier_audit_reports_page_timing_and_tier_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            observations = [
                {
                    "page_index": 1,
                    "request_started_at": "2026-11-01T00:00:00.000Z",
                    "request_completed_at": "2026-11-01T00:00:00.100Z",
                    "tier_count": 2, "symbol_count": 1,
                    "symbols": ["BTCUSDT"], "has_next_page": True,
                },
                {
                    "page_index": 2,
                    "request_started_at": "2026-11-01T00:00:00.200Z",
                    "request_completed_at": "2026-11-01T00:00:00.350Z",
                    "tier_count": 1, "symbol_count": 1,
                    "symbols": ["ETHUSDT"], "has_next_page": False,
                },
            ]
            write_risk_snapshot(
                target, "a.json", "2026-11-01T00:00:01.000Z",
                ("BTCUSDT", "ETHUSDT"), started_at="2026-11-01T00:00:00.000Z",
                page_observations=observations,
            )
            report = audit_risk_tier_directory(target)
        self.assertEqual(report["snapshot_count"], 1)
        self.assertEqual(report["snapshots_with_page_observations"], 1)
        page = report["snapshots"][0]["page_observations"]
        self.assertEqual(page["page_count"], 2)
        self.assertEqual(page["tier_count"], 3)
        self.assertEqual(page["request_duration_ms"]["max"], 150)

    def test_risk_tier_audit_rejects_missing_page_continuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            observations = [
                {
                    "page_index": 1,
                    "request_started_at": "2026-11-01T00:00:00.000Z",
                    "request_completed_at": "2026-11-01T00:00:00.100Z",
                    "tier_count": 1, "symbol_count": 1,
                    "symbols": ["BTCUSDT"], "has_next_page": False,
                },
                {
                    "page_index": 2,
                    "request_started_at": "2026-11-01T00:00:00.200Z",
                    "request_completed_at": "2026-11-01T00:00:00.300Z",
                    "tier_count": 1, "symbol_count": 1,
                    "symbols": ["ETHUSDT"], "has_next_page": False,
                },
            ]
            write_risk_snapshot(
                target, "a.json", "2026-11-01T00:00:01.000Z",
                ("BTCUSDT", "ETHUSDT"), started_at="2026-11-01T00:00:00.000Z",
                page_observations=observations,
            )
            with self.assertRaisesRegex(ValueError, "missing risk page continuation"):
                audit_risk_tier_directory(target)

    def test_joint_audit_reports_skew_and_missing_trading_symbol_tiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = root / "data" / "instrument_specs" / "linear"
            risks = root / "data" / "instrument_specs" / "risk_limits" / "linear"
            write_snapshot(
                specs, "i1.json", "2026-11-01T00:00:00.000Z",
                [instrument("BTCUSDT"), instrument("ETHUSDT")],
            )
            write_snapshot(
                specs, "i2.json", "2026-11-01T00:10:00.000Z",
                [instrument("BTCUSDT"), instrument("ETHUSDT")],
            )
            write_risk_snapshot(
                risks, "r1.json", "2026-11-01T00:01:00.000Z",
                ("BTCUSDT", "ETHUSDT"),
            )
            write_risk_snapshot(
                risks, "r2.json", "2026-11-01T00:12:00.000Z",
                ("BTCUSDT",),
            )
            report = audit_joint_market_state(specs, risks)

        self.assertEqual(report["status"], "DATA_FOUND")
        self.assertEqual(report["distinct_as_of_pairs"], 3)
        self.assertEqual(report["snapshot_skew_ms"]["max"], 540_000)
        self.assertEqual(report["pairs_with_missing_trading_symbol_risk_tiers"], 1)
        missing = [
            item for item in report["observations"]
            if item["trading_symbols_missing_risk_tiers"]
        ]
        self.assertEqual(missing[0]["trading_symbols_missing_risk_tiers"], ["ETHUSDT"])
        self.assertIsNone(report["skew_budget_recommendation_ms"])

    def test_joint_audit_reports_incomplete_without_both_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = audit_joint_market_state(root / "specs", root / "risk")
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIsNone(result["skew_budget_recommendation_ms"])

    def test_empty_repository_reports_no_data_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_report(Path(tmp))
        self.assertEqual(report["status"], "NO_DATA")
        self.assertEqual(report["sections"]["linear_universe"]["snapshot_count"], 0)

    def test_reports_collection_duration_cadence_and_symbol_status_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root, "a.json", "2026-11-01T00:00:02.000Z",
                           [instrument("BTCUSDT"), instrument("ETHUSDT")],
                           "2026-11-01T00:00:00.000Z")
            write_snapshot(root, "b.json", "2026-11-01T01:00:04.000Z",
                           [instrument("BTCUSDT", "Closed"), instrument("SOLUSDT")],
                           "2026-11-01T01:00:00.000Z")
            report = audit_directory(root)
        self.assertEqual(report["snapshot_count"], 2)
        self.assertEqual(report["collection_duration_ms"]["max"], 4000)
        self.assertEqual(report["inter_snapshot_gap_ms"]["max"], 3_598_000)
        self.assertEqual(report["intervals"][0]["symbols_added"], 1)
        self.assertEqual(report["intervals"][0]["symbols_removed"], 1)
        self.assertEqual(report["intervals"][0]["status_changes"], 1)
        self.assertEqual(report["intervals"][0]["gap_basis"], "completion_to_start")

    def test_legacy_snapshot_without_start_time_uses_completion_to_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root, "a.json", "2026-11-01T00:00:00.000Z",
                           [instrument("BTCUSDT")])
            write_snapshot(root, "b.json", "2026-11-01T00:10:00.000Z",
                           [instrument("BTCUSDT")])
            report = audit_directory(root)
        self.assertEqual(report["snapshots_missing_collection_started_at"], 2)
        self.assertEqual(report["intervals"][0]["gap_basis"], "completion_to_completion")
        self.assertEqual(report["intervals"][0]["gap_from_previous_completion_ms"], 600_000)

    def test_overlapping_collection_windows_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root, "a.json", "2026-11-01T00:00:02.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:00.000Z")
            write_snapshot(root, "b.json", "2026-11-01T00:00:03.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:01.000Z")
            report = audit_directory(root)
        self.assertEqual(report["overlapping_collection_windows"], 1)
        self.assertEqual(report["intervals"][0]["gap_from_previous_completion_ms"], -1000)

    def test_overlapping_collection_windows_fail_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "data" / "universe_history" / "linear"
            write_snapshot(target, "a.json", "2026-11-01T00:00:02.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:00.000Z")
            write_snapshot(target, "b.json", "2026-11-01T00:00:03.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:01.000Z")
            with patch("sys.argv", ["audit", "--root", str(root)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = main()
        self.assertEqual(result, 1)


    def test_audit_reports_per_page_status_timing_and_validates_symbol_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "data" / "universe_history" / "linear"
            observations = []
            pages = {
                "default": ["BTCUSDT"], "PreLaunch": [],
                "Settling": [], "Delivering": [], "Closed": ["OLDUSDT"],
            }
            for index, (status, page_symbols) in enumerate(pages.items()):
                start_ms = index * 400
                end_ms = start_ms + 100
                observations.append({
                    "status_filter": status, "page_index": 1,
                    "request_started_at": f"2026-11-01T00:00:{start_ms // 1000:02d}.{start_ms % 1000:03d}Z",
                    "request_completed_at": f"2026-11-01T00:00:{end_ms // 1000:02d}.{end_ms % 1000:03d}Z",
                    "row_count": len(page_symbols), "symbols": page_symbols,
                    "has_next_page": False,
                })
            write_snapshot(
                target, "a.json", "2026-11-01T00:00:02.000Z",
                [instrument("BTCUSDT"), instrument("OLDUSDT", "Closed")],
                "2026-11-01T00:00:00.000Z", observations,
            )
            report = audit_directory(target)
        self.assertEqual(report["snapshots_with_page_observations"], 1)
        page_summary = report["snapshots"][0]["page_observations"]
        self.assertEqual(page_summary["page_count"], 5)
        self.assertEqual(page_summary["status_filters"]["Closed"]["row_count"], 1)
        self.assertEqual(page_summary["request_duration_ms"]["max"], 100)

    def test_audit_rejects_page_observation_symbol_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data" / "instrument_specs" / "linear"
            observations = []
            for index, status in enumerate(("PreLaunch", "Trading", "Settling", "Delivering", "Closed")):
                start_ms = index * 100
                page_symbols = ["ETHUSDT"] if status == "Trading" else []
                observations.append({
                    "status_filter": status, "page_index": 1,
                    "request_started_at": f"2026-11-01T00:00:00.{start_ms:03d}Z",
                    "request_completed_at": f"2026-11-01T00:00:00.{start_ms + 10:03d}Z",
                    "row_count": len(page_symbols), "symbols": page_symbols,
                    "has_next_page": False,
                })
            write_snapshot(target, "a.json", "2026-11-01T00:00:01.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:00.000Z",
                           observations)
            with self.assertRaisesRegex(ValueError, "symbols do not match"):
                audit_directory(target)


    def test_audit_rejects_missing_continuation_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data" / "instrument_specs" / "spot"
            observations = [
                {
                    "status_filter": "Trading", "page_index": 1,
                    "request_started_at": "2026-11-01T00:00:00.000Z",
                    "request_completed_at": "2026-11-01T00:00:00.100Z",
                    "row_count": 1, "symbols": ["BTCUSDT"], "has_next_page": False,
                },
                {
                    "status_filter": "Trading", "page_index": 2,
                    "request_started_at": "2026-11-01T00:00:00.200Z",
                    "request_completed_at": "2026-11-01T00:00:00.300Z",
                    "row_count": 1, "symbols": ["ETHUSDT"], "has_next_page": False,
                },
            ]
            write_snapshot(target, "a.json", "2026-11-01T00:00:01.000Z",
                           [instrument("BTCUSDT"), instrument("ETHUSDT")],
                           "2026-11-01T00:00:00.000Z", observations)
            with self.assertRaisesRegex(ValueError, "continuation flags"):
                audit_directory(target)

    def test_audit_reports_repeated_symbols_across_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data" / "instrument_specs" / "spot"
            observations = [
                {
                    "status_filter": "Trading", "page_index": 1,
                    "request_started_at": "2026-11-01T00:00:00.000Z",
                    "request_completed_at": "2026-11-01T00:00:00.100Z",
                    "row_count": 1, "symbols": ["BTCUSDT"], "has_next_page": True,
                },
                {
                    "status_filter": "Trading", "page_index": 2,
                    "request_started_at": "2026-11-01T00:00:00.200Z",
                    "request_completed_at": "2026-11-01T00:00:00.300Z",
                    "row_count": 2, "symbols": ["BTCUSDT", "ETHUSDT"], "has_next_page": False,
                },
            ]
            write_snapshot(target, "a.json", "2026-11-01T00:00:01.000Z",
                           [instrument("BTCUSDT"), instrument("ETHUSDT")],
                           "2026-11-01T00:00:00.000Z", observations, category="spot")
            report = audit_directory(target)
        self.assertEqual(
            report["snapshots"][0]["page_observations"]["duplicate_symbol_observations"],
            [{"symbol": "BTCUSDT", "occurrences": 2}],
        )


    def test_audit_rejects_interleaved_status_filter_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data" / "instrument_specs" / "linear"
            observations = [
                {
                    "status_filter": "PreLaunch", "page_index": 1,
                    "request_started_at": "2026-11-01T00:00:00.000Z",
                    "request_completed_at": "2026-11-01T00:00:00.100Z",
                    "row_count": 1, "symbols": ["NEWUSDT"], "has_next_page": True,
                },
                {
                    "status_filter": "Trading", "page_index": 1,
                    "request_started_at": "2026-11-01T00:00:00.200Z",
                    "request_completed_at": "2026-11-01T00:00:00.300Z",
                    "row_count": 1, "symbols": ["BTCUSDT"], "has_next_page": False,
                },
                {
                    "status_filter": "PreLaunch", "page_index": 2,
                    "request_started_at": "2026-11-01T00:00:00.400Z",
                    "request_completed_at": "2026-11-01T00:00:00.500Z",
                    "row_count": 1, "symbols": ["ALTUSDT"], "has_next_page": False,
                },
            ]
            write_snapshot(target, "a.json", "2026-11-01T00:00:01.000Z",
                           [instrument("NEWUSDT"), instrument("BTCUSDT"), instrument("ALTUSDT")],
                           "2026-11-01T00:00:00.000Z", observations)
            with self.assertRaisesRegex(ValueError, "interleave"):
                audit_directory(target)

    def test_duplicate_snapshot_timestamps_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root, "a.json", "2026-11-01T00:00:00.000Z", [instrument("BTCUSDT")])
            write_snapshot(root, "b.json", "2026-11-01T00:00:00.000Z", [instrument("ETHUSDT")])
            with self.assertRaisesRegex(ValueError, "duplicate fetched_at"):
                audit_directory(root)

    def test_optional_gap_threshold_is_user_supplied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root / "data" / "universe_history" / "linear", "a.json",
                           "2026-11-01T00:00:00.000Z", [instrument("BTCUSDT")])
            write_snapshot(root / "data" / "universe_history" / "linear", "b.json",
                           "2026-11-01T01:00:00.000Z", [instrument("BTCUSDT")])
            output = io.StringIO()
            with patch("sys.argv", ["audit", "--root", str(root), "--max-gap-hours", "0.5"]):
                with contextlib.redirect_stdout(output):
                    result = main()
        self.assertEqual(result, 1)
        self.assertIn('"status": "DATA_FOUND"', output.getvalue())


    def test_optional_collection_duration_threshold_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "data" / "instrument_specs" / "linear"
            write_snapshot(target, "a.json", "2026-11-01T00:00:10.000Z",
                           [instrument("BTCUSDT")], "2026-11-01T00:00:00.000Z")
            output = io.StringIO()
            with patch("sys.argv", ["audit", "--root", str(root),
                                    "--max-collection-minutes", "0.1"]):
                with contextlib.redirect_stdout(output):
                    result = main()
        self.assertEqual(result, 1)

    def test_require_data_is_explicit_and_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch("sys.argv", ["audit", "--root", tmp, "--require-data"]):
                with contextlib.redirect_stdout(output):
                    result = main()
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
