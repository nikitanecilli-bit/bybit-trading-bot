"""Tests for the frozen regime-gate holdout experiment."""
from scripts.run_regime_gate_holdout import gate_allows


def test_long_only_allowed_in_uptrend():
    assert gate_allows("long", "trend_up")
    assert not gate_allows("long", "trend_down")
    assert not gate_allows("long", "transition")


def test_short_only_allowed_in_downtrend():
    assert gate_allows("short", "trend_down")
    assert not gate_allows("short", "trend_up")
    assert not gate_allows("short", "range")


def test_unknown_direction_is_rejected():
    assert not gate_allows("sideways", "trend_up")


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("All regime-gate holdout tests passed.")
