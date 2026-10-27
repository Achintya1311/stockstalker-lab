import pandas as pd

from strategies import f06_trend_acceleration as f06
from strategies.f06_trend_acceleration_audit import check_cross_symbol_causality, two_slopes

N = f06.MIN_ROWS


def test_hand_computed_acceleration_is_faded():
    """Older slope 0, recent 0.02 a session: x = 0.02 > 0.00625, score -0.02."""
    f = f06.compute_adjustment_factors(two_slopes("A", N, 0.0, 0.02))
    x, r1 = f06.parts(f)
    assert abs(x - 0.02) < 1e-12 and abs(r1 - 0.02) < 1e-12
    assert abs(f06.score(two_slopes("A", N, 0.0, 0.02))["A"] + 0.02) < 1e-12


def test_slowdown_is_bullish():
    """Older 0.02, recent 0.0: x = -0.02, score +0.02."""
    assert abs(f06.score(two_slopes("A", N, 0.02, 0.0))["A"] - 0.02) < 1e-12


def test_middle_band_reverses_todays_move():
    """Older 0.0, recent 0.004: x = 0.004 sits in [0, 0.00625], so score = -r1 = -0.004."""
    assert abs(f06.score(two_slopes("A", N, 0.0, 0.004))["A"] + 0.004) < 1e-12


def test_flat_series_abstains():
    assert f06.score(two_slopes("A", N, 0.0, 0.0)).empty


def test_short_history_abstains():
    assert f06.score(two_slopes("A", N, 0.0, 0.02).iloc[1:]).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = two_slopes("F", N + 2, 0.0, 0.02)
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(f06.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_kind_and_side():
    assert f06.rules_fired(two_slopes("A", N, 0.0, 0.02), "A").endswith("faded, bearish")
