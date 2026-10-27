"""Research-only portfolio risk guardrails; not wired to live execution."""
from __future__ import annotations

import math
from collections.abc import Iterable


def portfolio_risk_capacity(
    equity: float,
    max_portfolio_risk_pct: float,
    open_position_risks: Iterable[float],
    proposed_position_risk: float = 0.0,
) -> dict[str, float | bool]:
    """Estimate stop-risk capacity before admitting another position.

    Risks are supplied in quote currency (e.g. USDT) and should represent
    each position's estimated loss to its current stop, including modeled
    trading costs. This is a guardrail helper, not a portfolio backtester.
    It does not account for gaps, funding, correlation, margin/liquidation,
    or simultaneous stop execution.
    """
    if not math.isfinite(equity) or equity <= 0:
        raise ValueError("equity must be finite and positive")
    if not math.isfinite(max_portfolio_risk_pct) or not 0 < max_portfolio_risk_pct <= 1:
        raise ValueError("max_portfolio_risk_pct must be in (0, 1]")
    if not math.isfinite(proposed_position_risk) or proposed_position_risk < 0:
        raise ValueError("proposed_position_risk must be finite and non-negative")

    risks = list(open_position_risks)
    if any(not math.isfinite(risk) or risk < 0 for risk in risks):
        raise ValueError("open position risks must be finite and non-negative")

    limit = equity * max_portfolio_risk_pct
    used = sum(risks)
    available = max(0.0, limit - used)
    approved = proposed_position_risk <= available + max(1e-12, limit * 1e-12)
    return {
        "portfolio_risk_limit": limit,
        "open_position_risk": used,
        "available_risk": available,
        "proposed_position_risk": proposed_position_risk,
        "approved": approved,
        "risk_after_proposal": used + proposed_position_risk,
        "remaining_after_proposal": max(0.0, limit - used - proposed_position_risk),
    }
