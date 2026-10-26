import numpy as np
import pandas as pd

from strategies import q05_trend_smoothness as q05
from strategies.q05_trend_smoothness_audit import check_cross_symbol_causality
from strategies.t17_keltner_breakout_audit import frame

N = q05.MIN_ROWS


def test_straight_line_scores_one_with_its_slope():
    f = frame("A", 100.0 * np.exp(0.01 * np.arange(N)))
    slope, r2 = q05.fit(q05.compute_adjustment_factors(f))
    assert abs(slope - 0.01) < 1e-12 and abs(r2 - 1.0) < 1e-12
    assert abs(q05.score(f)["A"] - 1.0) < 1e-12


def test_hand_computed_r_squared():
    """Log closes 0,1,0,1,... (x 0.01) plus 0.001 x t: R^2 from the closed form."""
    t = np.arange(N, dtype=float)
    y = 0.01 * (t % 2) + 0.001 * t
    f = frame("A", 100.0 * np.exp(y))
    xm, ym = t - t.mean(), y - y.mean()
    expected = (xm @ ym) ** 2 / ((xm @ xm) * (ym @ ym))
    assert abs(q05.score(f)["A"] - expected) < 1e-9
    assert 0 < expected < 1


def test_smooth_beats_choppy_with_the_same_net_move():
    t = np.arange(N)
    smooth = frame("S", 100.0 * np.exp(0.005 * t))
    choppy = frame("C", 100.0 * np.exp(0.005 * t + 0.03 * (t % 2)))
    sc = q05.score(pd.concat([smooth, choppy]))
    assert sc["S"] > sc["C"] > 0


def test_falling_is_bearish_and_flat_abstains():
    t = np.arange(N)
    sc = q05.score(pd.concat([frame("D", 100.0 * np.exp(-0.01 * t)), frame("F", np.full(N, 100.0))]))
    assert sc["D"] < 0 and "F" not in sc


def test_short_history_abstains():
    assert q05.score(frame("A", 100.0 * np.exp(0.01 * np.arange(N - 1)))).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    t = np.arange(N)
    hist = pd.concat([frame("F", 100.0 * np.exp(0.01 * t)), frame("CASH", 100.0 * np.exp(0.01 * t))])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(q05.score(hist).index) == ["F"]


def test_rules_fired_wording():
    hist = frame("UP", 100.0 * np.exp(0.01 * np.arange(N)))
    assert "bullish" in q05.rules_fired(hist, "UP")
    assert "abstain" in q05.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
