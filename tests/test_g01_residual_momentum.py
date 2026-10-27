import numpy as np
import pandas as pd

from strategies import g01_residual_momentum as g01
from strategies.g01_residual_momentum_audit import check_cross_symbol_causality, walk
from strategies.t17_keltner_breakout_audit import frame

N = g01.MIN_ROWS + 5


def _from_log_returns(symbol, r):
    return frame(symbol, 100.0 * np.exp(np.r_[0.0, np.cumsum(r)]))


def test_pure_beta_moves_leave_no_score():
    """B's daily log returns are exactly twice A's, so both residuals are zero and both abstain."""
    rng = np.random.default_rng(7)
    r = rng.normal(0, 0.01, N - 1)
    sc = g01.score(pd.concat([_from_log_returns("A", r), _from_log_returns("B", 2 * r)]))
    assert sc.empty


def test_hand_computed_score_matches_an_independent_calculation():
    rng = np.random.default_rng(11)
    rets = {s: rng.normal(0, 0.01, N - 1) for s in ("A", "B", "C")}
    rets["A"][-200:-30] += 0.002
    hist = pd.concat([_from_log_returns(s, r) for s, r in rets.items()])
    m = np.mean(np.vstack(list(rets.values())), axis=0)[-(g01.MIN_ROWS - 1):][: g01.LOOKBACK]
    a = rets["A"][-(g01.MIN_ROWS - 1):][: g01.LOOKBACK]
    beta = np.mean((a - a.mean()) * (m - m.mean())) / np.var(m)
    e = a - beta * m
    expected = e.sum() / (e.std() * np.sqrt(g01.LOOKBACK))
    assert abs(g01.score(hist)["A"] - expected) < 1e-10


def test_skipped_month_does_not_move_the_score():
    """Changing only the last SKIP returns (and their share of the market) leaves the score as is."""
    rng = np.random.default_rng(5)
    rets = {s: rng.normal(0, 0.01, N - 1) for s in ("A", "B", "C")}
    before = g01.score(pd.concat([_from_log_returns(s, r) for s, r in rets.items()]))
    rets["A"] = rets["A"].copy()
    rets["A"][-g01.SKIP:] += 0.05
    after = g01.score(pd.concat([_from_log_returns(s, r) for s, r in rets.items()]))
    assert np.allclose(before.sort_index().values, after.sort_index().values, atol=1e-12)


def test_residual_winner_is_bullish_and_loser_bearish():
    hist = pd.concat([walk("UP", N, 1, 0.40), walk("DOWN", N, 2, -0.40), walk("FLAT", N, 3)])
    sc = g01.score(hist)
    assert sc["DOWN"] < 0 < sc["UP"]


def test_short_history_abstains():
    hist = pd.concat([walk("A", g01.MIN_ROWS - 1, 1), walk("B", g01.MIN_ROWS - 1, 2)])
    assert g01.score(hist).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([walk("F", N, 1, 0.4), walk("G", N, 2), walk("CASH", N, 3)])
    hist["has_future"] = hist["symbol"] != "CASH"
    assert "CASH" not in g01.score(hist).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    hist = pd.concat([walk("UP", N, 1, 0.40), walk("DOWN", N, 2, -0.40)])
    assert g01.rules_fired(hist, "UP").endswith("bullish")
