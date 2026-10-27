import numpy as np
import pandas as pd

from strategies import f04_open_volume_corr as f04
from strategies.f04_open_volume_corr_audit import check_cross_symbol_causality, trend_with_volume
from strategies.t17_keltner_breakout_audit import frame

N = f04.MIN_ROWS


def test_hand_computed_correlation():
    """Opens step +1 a session while volume steps -1e5: correlation -1 exactly, so the score is +1."""
    f = frame("A", 100.0 + np.arange(N + 1, dtype=float))  # open of row t = close of row t-1
    f["volume"] = 2e6 - 1e5 * np.arange(N + 1)
    assert abs(f04.correlation(f04.compute_adjustment_factors(f)) + 1.0) < 1e-9
    assert abs(f04.score(f)["A"] - 1.0) < 1e-9


def test_volume_rising_with_opens_is_bearish():
    sc = f04.score(pd.concat([trend_with_volume("UP", N + 2, 0.1), trend_with_volume("DN", N + 2, -0.1)]))
    assert sc["UP"] < 0 < sc["DN"]


def test_flat_volume_abstains():
    f = frame("A", 100.0 + np.arange(N, dtype=float))  # volume is 1e6 throughout
    assert f04.score(f).empty


def test_short_history_abstains():
    assert f04.score(trend_with_volume("A", N - 1, 0.1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = trend_with_volume("F", N + 2, 0.1)
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(f04.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert f04.rules_fired(trend_with_volume("A", N + 2, -0.1), "A").endswith("bullish")
