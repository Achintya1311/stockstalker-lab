import numpy as np
import pandas as pd

from strategies import q04_range_extreme_timing as q04
from strategies.q04_range_extreme_timing_audit import check_cross_symbol_causality, trend
from strategies.t17_keltner_breakout_audit import frame

N = q04.MIN_ROWS


def test_hand_computed_timing():
    """A straight rise: the low is the first bar (position 0) and the high today (59),
    so imxd = 59/60 and the score adds TIE x tanh(r60 / 0.3)."""
    closes = 100.0 * np.exp(0.005 * np.arange(N))
    f = q04.compute_adjustment_factors(frame("A", closes))
    imxd, r60 = q04.parts(f)
    assert abs(imxd - 59 / 60) < 1e-12
    assert abs(r60 - 0.005 * (N - 1)) < 1e-9
    expected = 59 / 60 + q04.TIE * np.tanh(r60 / 0.3)
    assert abs(q04.score(frame("A", closes))["A"] - expected) < 1e-12


def test_fall_is_bearish_and_tie_break_stays_inside_half_a_step():
    fall = frame("F", 100.0 * np.exp(-0.005 * np.arange(N)))
    sc = q04.score(fall)
    assert sc["F"] < 0
    assert abs(sc["F"] + 59 / 60) < 1 / 120


def test_old_high_then_recent_low_is_bearish():
    """High at position 10, low at position 50: imxd = (10 - 50) / 60."""
    closes = np.full(N, 100.0)
    closes[10] = 120.0
    closes[50] = 80.0
    f = q04.compute_adjustment_factors(frame("A", closes, spread=0.0))
    assert abs(q04.parts(f)[0] + 40 / 60) < 1e-12


def test_short_history_abstains():
    assert q04.score(frame("A", 100.0 * np.exp(0.005 * np.arange(N - 1)))).empty


def test_only_last_window_rows_are_read():
    """Rows before the window (here an old spike to 500) do not change the score."""
    rng = np.random.default_rng(4)
    closes = np.r_[np.full(5, 500.0), 100.0 * np.exp(np.cumsum(rng.normal(0.002, 0.01, N + 5)))]
    f = frame("A", closes)
    assert abs(q04.score(f)["A"] - q04.score(f.tail(N))["A"]) < 1e-12


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = trend("F", N + 5, 0.01, 1)
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(q04.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    f = trend("UP", N + 5, 0.01, 1)
    assert "bullish" in q04.rules_fired(f, "UP")
