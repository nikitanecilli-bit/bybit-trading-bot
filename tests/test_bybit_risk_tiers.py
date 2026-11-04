"""Deterministic tests for dated Bybit risk-tier lookup and selection."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from decimal import Decimal
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bybit_risk_tiers import RiskTierHistory, calculate_margin_requirements_from_tiers


def payload(fetched_at="2026-11-01T00:00:00Z", tiers=None):
    rows = tiers or [
        {"symbol":"BTCUSDT","id":1,"riskLimitValue":"100000","maintenanceMargin":"0.005","initialMargin":"0.01","maxLeverage":"100","mmDeduction":"0","isLowestRisk":1},
        {"symbol":"BTCUSDT","id":2,"riskLimitValue":"500000","maintenanceMargin":"0.01","initialMargin":"0.02","maxLeverage":"50","mmDeduction":"500","isLowestRisk":0},
    ]
    return {
        "schema_version": 1, "source": "Bybit V5 GET /v5/market/risk-limit",
        "category": "linear", "fetched_at": fetched_at,
        "tier_count": len(rows), "tiers": rows,
    }


class RiskTierHistoryTests(unittest.TestCase):

    def test_runtime_loader_validates_optional_collection_and_page_metadata(self):
        observations = [{
            "page_index": 1,
            "request_started_at": "2026-11-01T00:00:00.100Z",
            "request_completed_at": "2026-11-01T00:00:00.200Z",
            "tier_count": 2, "symbol_count": 1,
            "symbols": ["BTCUSDT"], "has_next_page": False,
        }]
        valid = payload(fetched_at="2026-11-01T00:00:00.500Z")
        valid["symbol_count"] = 1
        valid["collection_started_at"] = "2026-11-01T00:00:00.000Z"
        valid["page_observations"] = observations
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(valid), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)
            self.assertEqual(len(history.get_tiers("BTCUSDT", 1793491200500)), 2)

        bad_total = json.loads(json.dumps(valid))
        bad_total["page_observations"][0]["tier_count"] = 1
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad_total), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tier counts do not match"):
                RiskTierHistory.from_directory(tmp)

        bad_window = json.loads(json.dumps(valid))
        bad_window["collection_started_at"] = "2026-11-01T00:00:01.000Z"
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad_window), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "after fetched_at"):
                RiskTierHistory.from_directory(tmp)

    def test_selects_first_tier_covering_position_value_and_enforces_max_leverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(payload()), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)
            tier = history.get_tier("BTCUSDT", 1793606400000, "250000", leverage="40")
            self.assertEqual(tier.tier_id, 2)
            self.assertEqual(tier.mm_deduction, 500)
            with self.assertRaisesRegex(ValueError, "exceeds tier 2 maxLeverage"):
                history.get_tier("BTCUSDT", 1793606400000, "250000", leverage="60")

    def test_get_tiers_returns_full_point_in_time_ladder_without_entry_leverage_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(payload()), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)
            tiers = history.get_tiers("BTCUSDT", 1793606400000)
            self.assertEqual([item.tier_id for item in tiers], [1, 2])
            self.assertEqual(tiers[1].max_leverage, Decimal("50"))

    def test_risk_tier_parameters_are_selected_from_the_as_of_snapshot(self):
        first = payload(fetched_at="2026-11-01T00:00:00Z")
        second = payload(fetched_at="2026-11-02T00:00:00Z", tiers=[
            {"symbol":"BTCUSDT","id":1,"riskLimitValue":"200000","maintenanceMargin":"0.004","initialMargin":"0.008","maxLeverage":"80","mmDeduction":"0","isLowestRisk":1},
            {"symbol":"BTCUSDT","id":2,"riskLimitValue":"600000","maintenanceMargin":"0.009","initialMargin":"0.018","maxLeverage":"40","mmDeduction":"1000","isLowestRisk":0},
        ])
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.json").write_text(json.dumps(first), encoding="utf-8")
            Path(tmp, "b.json").write_text(json.dumps(second), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)

            before = history.get_tier(
                "BTCUSDT", 1793577599999, "50000", leverage="80"
            )
            after = history.get_tier(
                "BTCUSDT", 1793577600000, "50000", leverage="80"
            )
            self.assertEqual(before.risk_limit_value, Decimal("100000"))
            self.assertEqual(before.maintenance_margin_rate, Decimal("0.005"))
            self.assertEqual(before.initial_margin_rate, Decimal("0.01"))
            self.assertEqual(before.max_leverage, Decimal("100"))
            self.assertEqual(before.mm_deduction, Decimal("0"))

            self.assertEqual(after.risk_limit_value, Decimal("200000"))
            self.assertEqual(after.maintenance_margin_rate, Decimal("0.004"))
            self.assertEqual(after.initial_margin_rate, Decimal("0.008"))
            self.assertEqual(after.max_leverage, Decimal("80"))
            self.assertEqual(after.mm_deduction, Decimal("0"))
    def test_calculates_position_level_initial_and_maintenance_margin(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(payload()), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)
            result = history.calculate_margin_requirements(
                "BTCUSDT", 1793606400000, "250000", leverage="10"
            )
            self.assertEqual(result.tier_id, 2)
            self.assertEqual(result.initial_margin, 25000)
            self.assertEqual(result.maintenance_margin, 2000)
            self.assertEqual(result.maintenance_margin_rate, Decimal("0.01"))
            self.assertEqual(result.mm_deduction, 500)

    def test_margin_calculation_accepts_already_joined_tier_ladder(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(payload()), encoding="utf-8")
            tiers = RiskTierHistory.from_directory(tmp).get_tiers(
                "BTCUSDT", 1793606400000
            )
            result = calculate_margin_requirements_from_tiers(
                "BTCUSDT", "250000", leverage="10", tiers=tiers
            )
            self.assertEqual(result.tier_id, 2)
            self.assertEqual(result.initial_margin, Decimal("25000"))
            self.assertEqual(result.maintenance_margin, Decimal("2000"))
            with self.assertRaisesRegex(ValueError, "exceeds tier 2 maxLeverage"):
                calculate_margin_requirements_from_tiers(
                    "BTCUSDT", "250000", leverage="60", tiers=tiers
                )
            with self.assertRaisesRegex(ValueError, "exceeds highest"):
                calculate_margin_requirements_from_tiers(
                    "BTCUSDT", "500001", leverage="10", tiers=tiers
                )
            with self.assertRaisesRegex(ValueError, "no joined risk tiers"):
                calculate_margin_requirements_from_tiers(
                    "BTCUSDT", "1000", leverage="10", tiers=()
                )

    def test_margin_requirement_rejects_uncovered_position_and_invalid_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(payload()), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)
            with self.assertRaisesRegex(ValueError, "exceeds highest"):
                history.calculate_margin_requirements(
                    "BTCUSDT", 1793606400000, "500001", leverage="10"
                )

    def test_boundary_uses_lower_tier_until_risk_limit_exceeded(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(payload()), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)
            self.assertEqual(history.get_tier("BTCUSDT", 1793606400000, "100000", leverage="100").tier_id, 1)
            self.assertEqual(history.get_tier("BTCUSDT", 1793606400000, "100000.01", leverage="50").tier_id, 2)

    def test_rejects_future_or_stale_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(payload()), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)
            with self.assertRaisesRegex(ValueError, "no linear risk-tier snapshot"):
                history.get_tier("BTCUSDT", 1793400000000, "1000", leverage="10")
            with self.assertRaisesRegex(ValueError, "stale"):
                history.get_tier("BTCUSDT", 1793606400000, "1000", leverage="10", max_age_ms=1)

    def test_rejects_missing_symbol_and_position_above_highest_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(payload()), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)
            with self.assertRaisesRegex(ValueError, "absent"):
                history.get_tier("ETHUSDT", 1793606400000, "1000", leverage="10")
            with self.assertRaisesRegex(ValueError, "exceeds highest"):
                history.get_tier("BTCUSDT", 1793606400000, "500001", leverage="10")

    def test_rejects_invalid_lowest_flag_and_mm_deduction_recurrence(self):
        bad_lowest = payload(tiers=[
            {"symbol":"BTCUSDT","id":1,"riskLimitValue":"100000","maintenanceMargin":"0.005","initialMargin":"0.01","maxLeverage":"100","mmDeduction":"0","isLowestRisk":0},
            {"symbol":"BTCUSDT","id":2,"riskLimitValue":"500000","maintenanceMargin":"0.01","initialMargin":"0.02","maxLeverage":"50","mmDeduction":"500","isLowestRisk":1},
        ])
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad_lowest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "lowest tier"):
                RiskTierHistory.from_directory(tmp)
        bad_deduction = payload()
        bad_deduction["tiers"][1]["mmDeduction"] = "499"
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad_deduction), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mmDeduction recurrence"):
                RiskTierHistory.from_directory(tmp)

    def test_rejects_missing_mm_deduction_on_higher_tier(self):
        bad = payload()
        bad["tiers"][1].pop("mmDeduction")
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing mmDeduction for non-lowest tier"):
                RiskTierHistory.from_directory(tmp)

    def test_rejects_boolean_values_in_numeric_risk_tier_fields(self):
        bad = payload()
        bad["tiers"][0]["maintenanceMargin"] = True
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid maintenanceMargin"):
                RiskTierHistory.from_directory(tmp)

    def test_rejects_float_is_lowest_risk_metadata(self):
        bad = payload()
        bad["tiers"][0]["isLowestRisk"] = 1.0
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "isLowestRisk must be integer 0 or 1"):
                RiskTierHistory.from_directory(tmp)

    def test_rejects_inverse_category_for_linear_margin_history(self):
        from bybit_risk_tiers import RiskTierSnapshot
        with self.assertRaisesRegex(ValueError, "only supports linear contracts"):
            RiskTierHistory([RiskTierSnapshot(
                fetched_at="2026-11-01T00:00:00Z",
                fetched_at_ms=1793491200000,
                category="inverse",
                tiers_by_symbol={},
            )])

    def test_rejects_invalid_tier_structure(self):
        bad = payload(tiers=[
            {"symbol":"BTCUSDT","id":1,"riskLimitValue":"100000","maintenanceMargin":"0.01","initialMargin":"0.01","maxLeverage":"100","mmDeduction":"0","isLowestRisk":1},
            {"symbol":"BTCUSDT","id":2,"riskLimitValue":"500000","maintenanceMargin":"0.005","initialMargin":"0.02","maxLeverage":"50","mmDeduction":"500","isLowestRisk":0},
        ])
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "MMR decreases"):
                RiskTierHistory.from_directory(tmp)


    def test_as_of_timestamp_must_be_strict_integer_milliseconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(payload()), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)
            for value in (1793606400000.5, True, "1793606400000"):
                with self.subTest(value=value):
                    with self.assertRaisesRegex(ValueError, "as_of_ts must be an integer"):
                        history.get_tiers("BTCUSDT", value)
                    with self.assertRaisesRegex(ValueError, "as_of_ts must be an integer"):
                        history.get_tier("BTCUSDT", value, "1000", leverage="10")

    def test_snapshot_timestamp_rejects_submillisecond_precision(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = payload(fetched_at="2026-11-01T00:00:00.000500Z")
            Path(tmp, "risk.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "millisecond precision"):
                RiskTierHistory.from_directory(tmp)

    def test_snapshot_timestamp_conversion_is_exact_across_timezone_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = payload(fetched_at="2026-11-01T03:00:00.123+03:00")
            Path(tmp, "risk.json").write_text(json.dumps(value), encoding="utf-8")
            history = RiskTierHistory.from_directory(tmp)
            self.assertEqual(history.snapshots[0].fetched_at_ms, 1793491200123)

    def test_snapshot_schema_version_and_tier_count_require_integer_types(self):
        bad = payload(tiers=[
            {"symbol":"BTCUSDT","id":1,"riskLimitValue":"100000","maintenanceMargin":"0.005","initialMargin":"0.01","maxLeverage":"100","mmDeduction":"0","isLowestRisk":1},
        ])
        bad["schema_version"] = True
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported risk-tier schema"):
                RiskTierHistory.from_directory(tmp)

        bad["schema_version"] = 1
        bad["tier_count"] = True
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tier_count does not match"):
                RiskTierHistory.from_directory(tmp)

    def test_missing_or_mismatched_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = payload()
            bad.pop("source")
            Path(tmp, "risk.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid or missing Bybit risk-limit source"):
                RiskTierHistory.from_directory(tmp)

if __name__ == "__main__":
    unittest.main(verbosity=2)
