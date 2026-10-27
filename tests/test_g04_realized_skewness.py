import numpy as np
import pandas as pd

from strategies import g04_realized_skewness as g04
from strategies.g04_realized_skewness_audit import check_cross_symbol_causality, one_jump
from strategies.t17_keltner_breakout_audit import frame

N = g04.MIN_ROWS


def _from_log_returns(symbol, r):
    return frame(symbol, 100.0 * np.exp(np.r_[0.0, np.cumsum(r)]))


def test_hand_computed_skewness():
    """19 returns of 0 and one of +0.2: mean 0.01, deviations -0.01 (x19) and 0.19;
    m2 = (19 x 1e-4 + 0.0361) / 20 = 0.0019, m3 = (19 x -1e-6 + 0.006859) / 20 = 0.000342,
    skew = 0.000342 / 0.0019^1.5."""
    r = np.r_[np.zeros(19), 0.2]
    expected = 0.000342 / 0.0019**1.5
    f = g04.compute_adjustment_factors(_from_log_returns("A", r))
    assert abs(g04.skewness(f) - expected) < 1e-9
    assert abs(g04.score(_from_log_returns("A", r))["A"] + expected) < 1e-9


def test_crash_is_bullish_and_spike_bearish():
    sc = g04.score(pd.concat([one_jump("DOWN", N + 3, -0.08, 1), one_jump("UP", N + 3, 0.08, 2)]))
    assert sc["UP"] < 0 < sc["DOWN"]


def test_flat_series_abstains():
    assert g04.score(frame("A", np.full(N, 100.0))).empty


def test_short_history_abstains():
    assert g04.score(one_jump("A", N - 1, 0.08, 1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = one_jump("F", N + 3, 0.08, 1)
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(g04.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert "lottery-like" in g04.rules_fired(one_jump("A", N + 3, 0.08, 1), "A")
