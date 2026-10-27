import pandas as pd

from strategies import f05_close_location_change as f05
from strategies.f05_close_location_change_audit import check_cross_symbol_causality, location_bar

N = f05.MIN_ROWS + 2


def test_hand_computed_location_change():
    """Nine sessions ago: L 99, H 101, C 100, loc (1 - 1) / 1 = 0. Today C 99.5:
    loc (0.5 - 1.5) / 0.5 = -2, so the score is -(-2 - 0) = +2 (bullish)."""
    assert abs(f05.score(location_bar("A", N, 99.5))["A"] - 2.0) < 1e-9


def test_close_near_the_high_is_bearish():
    """Today C 100.5: loc (1.5 - 0.5) / 1.5 = 2/3, score -2/3."""
    assert abs(f05.score(location_bar("A", N, 100.5))["A"] + 2.0 / 3.0) < 1e-9


def test_close_at_the_low_or_no_change_abstains():
    at_low = location_bar("L", N, 99.0)
    same = location_bar("S", N, 100.0)
    assert f05.score(pd.concat([at_low, same])).empty


def test_short_history_abstains():
    assert f05.score(location_bar("A", f05.MIN_ROWS - 1, 99.5)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = location_bar("F", N, 99.5)
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(f05.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert f05.rules_fired(location_bar("A", N, 99.5), "A").endswith("bullish")
