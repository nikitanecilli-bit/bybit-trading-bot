"""Regression tests for joined as-of instrument and risk-tier metadata."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bybit_market_state import get_linear_market_state
from instrument_spec_history import InstrumentSpecHistory
from bybit_risk_tiers import RiskTierHistory

def write_inputs(spec_dir, risk_dir, spec_stamp, risk_stamp):
    row = {"symbol":"BTCUSDT","status":"Trading","contractType":"LinearPerpetual",
           "baseCoin":"BTC","quoteCoin":"USDT","settleCoin":"USDT",
           "priceFilter":{"tickSize":"0.1","minPrice":"0.1"},
           "lotSizeFilter":{"qtyStep":"0.001","minOrderQty":"0.001","minNotionalValue":"5"},
           "leverageFilter":{"maxLeverage":"100","leverageStep":"0.01"}}
    Path(spec_dir,"spec.json").write_text(json.dumps({
        "schema_version":1,"source":"Bybit V5 GET /v5/market/instruments-info",
        "category":"linear","fetched_at":spec_stamp,"count":1,"instruments":[row]}))
    tiers=[{"symbol":"BTCUSDT","id":1,"riskLimitValue":"100000",
            "maintenanceMargin":"0.005","initialMargin":"0.01","maxLeverage":"100",
            "mmDeduction":"0","isLowestRisk":1}]
    Path(risk_dir,"risk.json").write_text(json.dumps({
        "schema_version":1,"source":"Bybit V5 GET /v5/market/risk-limit",
        "category":"linear","fetched_at":risk_stamp,"tier_count":1,"tiers":tiers}))

class JoinedMarketStateTests(unittest.TestCase):
    def load(self, spec_stamp, risk_stamp):
        sd, rd = tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory()
        self.addCleanup(sd.cleanup); self.addCleanup(rd.cleanup)
        write_inputs(sd.name,rd.name,spec_stamp,risk_stamp)
        return InstrumentSpecHistory.from_directory(sd.name), RiskTierHistory.from_directory(rd.name)

    def test_joins_completed_asof_snapshots_and_reports_skew(self):
        s,r=self.load("2026-11-01T00:00:00Z","2026-11-01T00:00:01Z")
        state=get_linear_market_state(s,r,"btcusdt",1793491202000,max_snapshot_skew_ms=1000)
        self.assertEqual(state.symbol,"BTCUSDT")
        self.assertEqual(state.snapshot_skew_ms,1000)
        self.assertEqual(state.risk_tiers[0].tier_id,1)

    def test_rejects_skew_above_explicit_budget(self):
        s,r=self.load("2026-11-01T00:00:00Z","2026-11-01T00:00:02Z")
        with self.assertRaisesRegex(ValueError,"skew exceeds budget"):
            get_linear_market_state(s,r,"BTCUSDT",1793491203000,max_snapshot_skew_ms=1000)

    def test_never_uses_future_risk_snapshot(self):
        s,r=self.load("2026-11-01T00:00:00Z","2026-11-01T00:00:01Z")
        with self.assertRaisesRegex(ValueError,"no completed risk-tier snapshot"):
            get_linear_market_state(s,r,"BTCUSDT",1793491200500,max_snapshot_skew_ms=1000)

    def test_rejects_stale_component(self):
        s,r=self.load("2026-11-01T00:00:00Z","2026-11-01T00:00:01Z")
        with self.assertRaisesRegex(ValueError,"risk-tier snapshot stale"):
            get_linear_market_state(s,r,"BTCUSDT",1793491202000,max_snapshot_skew_ms=1000,
                                    max_risk_tier_age_ms=500)

    def test_skew_budget_must_be_explicit_nonnegative_integer(self):
        s,r=self.load("2026-11-01T00:00:00Z","2026-11-01T00:00:00Z")
        for value in (-1,True,1.5):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,"max_snapshot_skew_ms"):
                get_linear_market_state(s,r,"BTCUSDT",1793491200000,max_snapshot_skew_ms=value)

if __name__ == "__main__":
    unittest.main(verbosity=2)
