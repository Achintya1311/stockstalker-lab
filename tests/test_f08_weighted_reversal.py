import numpy as np
import pandas as pd

from strategies import f08_weighted_reversal as f08
from strategies.f08_weighted_reversal_audit import check_cross_symbol_causality, walk
from strategies.t17_keltner_breakout_audit import frame

N = f08.MIN_ROWS + 2


def path(symbol: str, daily: float, last7: float) -> pd.DataFrame:
    """Constant daily growth `daily`, then the last 7 sessions at `last7` per session."""
    steps = np.r_[np.full(N - 7, daily), np.full(7, last7)]
    return frame(symbol, 100.0 * np.cumprod(1.0 + steps))


def test_hand_computed_scores():
    """Three stocks; yearly sums rank W (winner) > M > L (loser). W rose over 7 sessions
    (bearish, weight 1 + 3/3 = 2), M fell (bullish, 1 + 2/3), L rose (bearish, 1 + 1/3)."""
    hist = pd.concat([path("W", 0.004, 0.002), path("M", 0.001, -0.001), path("L", -0.002, 0.001)],
                     ignore_index=True)
    sc = f08.score(hist)
    assert abs(sc["W"] + 2.0) < 1e-12
    assert abs(sc["M"] - (1 + 2 / 3)) < 1e-12
    assert abs(sc["L"] + (1 + 1 / 3)) < 1e-12


def test_unchanged_over_seven_sessions_abstains():
    closes = np.r_[100.0 * np.cumprod(np.full(N - 7, 1.001)), np.full(7, 0.0)]
    closes[-7:] = closes[-8]
    assert f08.score(frame("A", closes)).empty


def test_short_history_abstains():
    assert f08.score(path("A", 0.001, 0.001).tail(f08.MIN_ROWS - 1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([path("A", 0.001, -0.001), walk("CASH", N, 1)], ignore_index=True)
    hist["has_future"] = hist["symbol"] == "A"
    assert list(f08.score(hist).index) == ["A"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    hist = pd.concat([path("W", 0.004, 0.002), path("M", 0.001, -0.001)], ignore_index=True)
    assert f08.rules_fired(hist, "W").endswith("bearish")
    assert f08.rules_fired(hist, "M").endswith("bullish")
