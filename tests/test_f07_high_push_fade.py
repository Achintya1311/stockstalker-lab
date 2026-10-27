import numpy as np
import pandas as pd

from strategies import f07_high_push_fade as f07
from strategies.f07_high_push_fade_audit import check_cross_symbol_causality, push
from strategies.t17_keltner_breakout_audit import frame

N = f07.MIN_ROWS + 3


def test_hand_computed_push_is_bearish():
    """Highs: 100.5 flat, then 102 x 1.005 and 104 x 1.005. Two sessions back the high is
    100.5, so the change is log(104.52 / 100.5) and the score its negative."""
    f = push("A", N, (102.0, 104.0))
    expected = -np.log(104.0 * 1.005 / 100.5)
    assert abs(f07.score(f)["A"] - expected) < 1e-12


def test_high_below_its_mean_abstains():
    closes = np.r_[np.full(N - 2, 110.0), 100.0, 101.0]
    assert f07.score(frame("A", closes)).empty


def test_lower_high_still_above_the_mean_is_bullish():
    """A spike to 110 two sessions ago, then 105: still above the 20-session mean high, but lower."""
    closes = np.r_[np.full(N - 3, 100.0), 110.0, 106.0, 105.0]
    sc = f07.score(frame("A", closes))
    assert sc["A"] > 0


def test_short_history_abstains():
    assert f07.score(push("A", f07.MIN_ROWS - 1, (102.0, 104.0))).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = push("F", N, (102.0, 104.0))
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(f07.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert f07.rules_fired(push("A", N, (102.0, 104.0)), "A").endswith("bearish")
