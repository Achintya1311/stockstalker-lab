import numpy as np
import pandas as pd

from strategies import t22_vcp as t22
from strategies.t17_keltner_breakout_audit import frame
from strategies.t22_vcp_audit import check_cross_symbol_causality, vcp_frame

N = t22.MIN_ROWS + 10


def test_peaks_are_confirmed_and_strict_on_the_right():
    h = np.array([1, 2, 3, 3, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], dtype=float)
    old = t22.PEAK_ORDER
    try:
        t22.PEAK_ORDER = 2
        assert t22.peaks(h, start=0) == [3]     # flat top counts once, at its last bar
        assert t22.peaks(h[:5], start=0) == []  # bar 3 lacks two later bars: not confirmed
    finally:
        t22.PEAK_ORDER = old


def test_constructed_vcp_fires_with_hand_computed_pullbacks():
    f = t22.compute_adjustment_factors(vcp_frame("A", N))
    value, reason = t22.check(f)
    # Pullbacks run between consecutive peaks (200 -> 176, 201 -> 189); the dip after
    # the last peak is the base the stock lifts off from. High = close x 1.005, low x 0.995.
    first = (200 * 1.005 - 176 * 0.995) / (200 * 1.005)
    last = (201 * 1.005 - 189 * 0.995) / (201 * 1.005)
    assert abs(value - first / last) < 1e-9, reason
    assert t22.score(vcp_frame("A", N))["A"] > 0


def test_each_checklist_item_can_veto():
    assert t22.score(vcp_frame("A", N, lift=1.0)).empty          # no lift-off volume
    assert t22.score(vcp_frame("A", N, dry=1.0)).empty           # no dry-up in the pullback
    falling = frame("D", 200.0 * np.exp(-0.003 * np.arange(N)))
    assert t22.score(falling).empty                              # no uptrend


def test_widening_pullbacks_abstain():
    """A second pullback to 180 (about 10%, 0.85x the first 12%) is not tightening."""
    from strategies import t22_vcp_audit as audit
    legs = audit.LEGS
    try:
        audit.LEGS = [(10, 176.0), (12, 201.0), (8, 180.0), (10, 202.0), (6, 196.0), (13, 201.0)]
        value, reason = t22.check(t22.compute_adjustment_factors(audit.vcp_frame("A", N)))
        assert np.isnan(value) and "not tightening" in reason
    finally:
        audit.LEGS = legs


def test_short_history_abstains():
    assert t22.score(vcp_frame("A", N).iloc[N - t22.MIN_ROWS + 1:]).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([vcp_frame("F", N), vcp_frame("CASH", N)], ignore_index=True)
    hist["has_future"] = hist["symbol"] == "F"
    assert list(t22.score(hist).index) == ["F"]


def test_rules_fired_wording():
    hist = vcp_frame("A", N)
    assert "bullish" in t22.rules_fired(hist, "A")
    assert "abstain" in t22.rules_fired(hist, "NONE")
    assert "abstain" in t22.rules_fired(vcp_frame("A", N, lift=1.0), "A")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
