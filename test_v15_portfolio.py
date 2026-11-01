"""Tests for research-only portfolio risk capacity guardrails."""
import unittest

from research_v15.portfolio import portfolio_risk_capacity


class PortfolioRiskCapacityTests(unittest.TestCase):
    def test_approves_position_that_fits_remaining_portfolio_budget(self):
        result = portfolio_risk_capacity(10_000, 0.03, [100, 80], 100)
        self.assertTrue(result["approved"])
        self.assertAlmostEqual(result["portfolio_risk_limit"], 300)
        self.assertAlmostEqual(result["open_position_risk"], 180)
        self.assertAlmostEqual(result["available_risk"], 120)
        self.assertAlmostEqual(result["remaining_after_proposal"], 20)

    def test_rejects_position_that_exceeds_remaining_budget(self):
        result = portfolio_risk_capacity(10_000, 0.03, [100, 180], 50)
        self.assertFalse(result["approved"])
        self.assertEqual(result["available_risk"], 20)
        self.assertEqual(result["remaining_after_proposal"], 0)

    def test_existing_over_budget_positions_block_new_risk(self):
        result = portfolio_risk_capacity(10_000, 0.02, [150, 100], 0.01)
        self.assertFalse(result["approved"])
        self.assertEqual(result["available_risk"], 0)

    def test_zero_proposed_risk_is_allowed_at_capacity(self):
        result = portfolio_risk_capacity(1_000, 0.02, [20], 0)
        self.assertTrue(result["approved"])
        self.assertEqual(result["remaining_after_proposal"], 0)

    def test_rejects_invalid_equity_limit_and_risks(self):
        cases = [
            (0, 0.02, [], 0),
            (1000, 0, [], 0),
            (1000, 1.1, [], 0),
            (1000, 0.02, [-1], 0),
            (1000, 0.02, [float("inf")], 0),
            (1000, 0.02, [], -1),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                portfolio_risk_capacity(*args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
