import numpy as np
import pandas as pd

from strategies import g05_residual_reversal as g05
from strategies.g05_residual_reversal_audit import check_cross_symbol_causality, walk
from strategies.t17_keltner_breakout_audit import frame

N = g05.MIN_ROWS + 5


def _from_log_returns(symbol, r):
    return frame(symbol, 100.0 * np.exp(np.r_[0.0, np.cumsum(r)]))


def test_pure_beta_moves_leave_no_residual():
    """B's daily log returns are exactly twice A's, so the market is 1.5 x A's, beta_A = 2/3,
    beta_B = 4/3, and both residuals are zero."""
    rng = np.random.default_rng(7)
    r = rng.normal(0, 0.01, N - 1)
    res = g05.residuals(pd.concat([_from_log_returns("A", r), _from_log_returns("B", 2 * r)]))
    assert np.allclose(res.values, 0.0, atol=1e-12)


def test_hand_computed_residual_matches_an_independent_calculation():
    rng = np.random.default_rng(11)
    rets = {s: rng.normal(0, 0.01, N - 1) for s in ("A", "B", "C")}
    rets["A"][-5:] += 0.02
    hist = pd.concat([_from_log_returns(s, r) for s, r in rets.items()])
    m = np.mean(np.vstack(list(rets.values())), axis=0)[-(g05.MIN_ROWS - 1):]
    a = rets["A"][-(g05.MIN_ROWS - 1):]
    est_a, est_m = a[: g05.BETA_WINDOW], m[: g05.BETA_WINDOW]
    beta = np.mean((est_a - est_a.mean()) * (est_m - est_m.mean())) / np.var(est_m)
    expected = np.sum(a[g05.BETA_WINDOW:] - beta * m[g05.BETA_WINDOW:])
    assert abs(g05.score(hist)["A"] + expected) < 1e-10


def test_residual_winner_is_bearish_and_loser_bullish():
    hist = pd.concat([walk("UP", N, 1, 0.10), walk("DOWN", N, 2, -0.10), walk("FLAT", N, 3)])
    sc = g05.score(hist)
    assert sc["UP"] < 0 < sc["DOWN"]


def test_short_history_abstains():
    hist = pd.concat([walk("A", g05.MIN_ROWS - 1, 1), walk("B", g05.MIN_ROWS - 1, 2)])
    assert g05.score(hist).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([walk("F", N, 1, 0.1), walk("G", N, 2), walk("CASH", N, 3)])
    hist["has_future"] = hist["symbol"] != "CASH"
    assert "CASH" not in g05.score(hist).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    hist = pd.concat([walk("UP", N, 1, 0.10), walk("DOWN", N, 2, -0.10)])
    assert g05.rules_fired(hist, "UP").endswith("bearish")
