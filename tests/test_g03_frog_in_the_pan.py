import numpy as np
import pandas as pd

from strategies import g03_frog_in_the_pan as g03
from strategies.g03_frog_in_the_pan_audit import check_cross_symbol_causality, steady
from strategies.t17_keltner_breakout_audit import frame

N = g03.MIN_ROWS + 5


def _from_log_returns(symbol, r):
    return frame(symbol, 100.0 * np.exp(np.r_[0.0, np.cumsum(r)]))


def test_hand_computed_score():
    """150 up days of +1% and 102 down days of -0.5% in the window: PRET = 0.99,
    ID = (102 - 150) / 252, score = 0.99 x 48 / 252."""
    window = np.r_[np.full(150, 0.01), np.full(102, -0.005)]
    r = np.r_[np.zeros(N - 1 - g03.SKIP - g03.LOOKBACK), window, np.full(g03.SKIP, 0.03)]
    sc = g03.score(_from_log_returns("A", r))
    assert abs(sc["A"] - 0.99 * 48 / 252) < 1e-9


def test_jump_driven_winner_abstains():
    """One +50% day and 251 small down days: a winner, but discrete (ID > 0)."""
    window = np.r_[0.5, np.full(251, -0.001)]
    r = np.r_[np.zeros(N - 1 - g03.SKIP - g03.LOOKBACK), window, np.zeros(g03.SKIP)]
    assert g03.score(_from_log_returns("J", r)).empty


def test_continuous_winner_bullish_and_loser_bearish():
    sc = g03.score(pd.concat([steady("UP", N, 0.002, 1), steady("DOWN", N, -0.002, 2)]))
    assert sc["DOWN"] < 0 < sc["UP"]


def test_skipped_month_does_not_move_the_score():
    a = steady("A", N, 0.002, 4)
    b = a.copy()
    b.loc[b.index[-g03.SKIP:], ["open", "high", "low", "close"]] *= 1.2
    assert abs(g03.score(a)["A"] - g03.score(b)["A"]) < 1e-12


def test_short_history_abstains():
    assert g03.score(steady("A", g03.MIN_ROWS - 1, 0.002, 1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([steady("F", N, 0.002, 1), steady("CASH", N, 0.002, 3)])
    hist["has_future"] = hist["symbol"] != "CASH"
    assert "CASH" not in g03.score(hist).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert g03.rules_fired(steady("UP", N, 0.002, 1), "UP").endswith("bullish (continuous winner)")
