"""Deterministic tests for dated Bybit risk-tier lookup and selection."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from decimal import Decimal
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bybit_risk_tiers import RiskTierHistory


def payload(fetched_at="2026-11-01T00:00:00Z", tiers=None):
    rows = tiers or [
        {"symbol":"BTCUSDT","id":1,"riskLimitValue":"100000","maintenanceMargin":"0.005","initialMargin":"0.01","maxLeverage":"100","mmDeduction":"0","isLowestRisk":1},
        {"symbol":"BTCUSDT","id":2,"riskLimitValue":"500000","maintenanceMargin":"0.01","initialMargin":"0.02","maxLeverage":"50","mmDeduction":"500","isLowestRisk":0},
    ]
    return {
        "schema_version": 1, "category": "linear", "fetched_at": fetched_at,
        "tier_count": len(rows), "tiers": rows,
    }


class RiskTierHistoryTests(unittest.TestCase):
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

    def test_rejects_invalid_tier_structure(self):
        bad = payload(tiers=[
            {"symbol":"BTCUSDT","id":1,"riskLimitValue":"100000","maintenanceMargin":"0.01","initialMargin":"0.01","maxLeverage":"100","mmDeduction":"0","isLowestRisk":1},
            {"symbol":"BTCUSDT","id":2,"riskLimitValue":"500000","maintenanceMargin":"0.005","initialMargin":"0.02","maxLeverage":"50","mmDeduction":"500","isLowestRisk":0},
        ])
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "risk.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "MMR decreases"):
                RiskTierHistory.from_directory(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
