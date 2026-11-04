"""Fail-closed as-of join for Bybit linear instrument and risk-tier snapshots."""
from dataclasses import dataclass

@dataclass(frozen=True)
class BybitLinearMarketState:
    symbol: str
    instrument_spec: object
    risk_tiers: tuple
    instrument_fetched_at_ms: int
    risk_tiers_fetched_at_ms: int
    as_of_ts: int

    @property
    def snapshot_skew_ms(self):
        return abs(self.instrument_fetched_at_ms - self.risk_tiers_fetched_at_ms)


def get_linear_market_state(instrument_history, risk_tier_history, symbol, as_of_ts, *,
                            max_snapshot_skew_ms, max_instrument_age_ms=None,
                            max_risk_tier_age_ms=None):
    """Join latest completed snapshots; explicit skew/staleness budgets are mandatory/optional.

    Completion timestamps are client observations, not an exchange-atomic snapshot guarantee.
    """
    if isinstance(as_of_ts, bool) or not isinstance(as_of_ts, int):
        raise ValueError("as_of_ts must be an integer millisecond timestamp")
    if (isinstance(max_snapshot_skew_ms, bool)
            or not isinstance(max_snapshot_skew_ms, int) or max_snapshot_skew_ms < 0):
        raise ValueError("max_snapshot_skew_ms must be a non-negative integer")
    for label, value in (("max_instrument_age_ms", max_instrument_age_ms),
                         ("max_risk_tier_age_ms", max_risk_tier_age_ms)):
        if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError(f"{label} must be a non-negative integer or None")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")
    if instrument_history.category != "linear" or risk_tier_history.category != "linear":
        raise ValueError("combined market state only supports linear category")
    specs = [s for s in instrument_history.snapshots if s.fetched_at_ms <= as_of_ts]
    risks = [s for s in risk_tier_history.snapshots if s.fetched_at_ms <= as_of_ts]
    if not specs:
        raise ValueError("no completed instrument snapshot at or before as_of_ts")
    if not risks:
        raise ValueError("no completed risk-tier snapshot at or before as_of_ts")
    spec_snapshot, risk_snapshot = specs[-1], risks[-1]
    spec_age, risk_age = as_of_ts-spec_snapshot.fetched_at_ms, as_of_ts-risk_snapshot.fetched_at_ms
    if max_instrument_age_ms is not None and (
            max_instrument_age_ms < 0 or spec_age > max_instrument_age_ms):
        raise ValueError(f"instrument snapshot stale: age_ms={spec_age}")
    if max_risk_tier_age_ms is not None and (
            max_risk_tier_age_ms < 0 or risk_age > max_risk_tier_age_ms):
        raise ValueError(f"risk-tier snapshot stale: age_ms={risk_age}")
    skew = abs(spec_snapshot.fetched_at_ms-risk_snapshot.fetched_at_ms)
    if skew > max_snapshot_skew_ms:
        raise ValueError(f"instrument/risk-tier snapshot skew exceeds budget: skew_ms={skew}")
    key = symbol.strip().upper()
    spec = instrument_history.get_spec(
        key, as_of_ts, max_age_ms=max_instrument_age_ms, require_trading=True
    )
    tiers = risk_tier_history.get_tiers(key, as_of_ts, max_age_ms=max_risk_tier_age_ms)
    return BybitLinearMarketState(key, spec, tiers, spec_snapshot.fetched_at_ms,
                                  risk_snapshot.fetched_at_ms, as_of_ts)
