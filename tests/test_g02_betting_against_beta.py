import numpy as np
import pandas as pd

from strategies import g02_betting_against_beta as g02
from strategies.g02_betting_against_beta_audit import check_cross_symbol_causality, loaded
from strategies.t17_keltner_breakout_audit import frame

N = g02.MIN_ROWS + 5


def _from_log_returns(symbol, r):
    return frame(symbol, 100.0 * np.exp(np.r_[0.0, np.cumsum(r)]))


def test_exact_multiples_give_known_betas():
    """B's log returns are 3 x A's: market = 2 x A's, beta_A = 0.5, beta_B = 1.5;
    shrunk 0.7 and 1.3, scores +0.3 and -0.3."""
    r = np.random.default_rng(7).normal(0, 0.01, N - 1)
    sc = g02.score(pd.concat([_from_log_returns("A", r), _from_log_returns("B", 3 * r)]))
    assert abs(sc["A"] - 0.3) < 1e-9 and abs(sc["B"] + 0.3) < 1e-9


def test_hand_computed_beta_matches_an_independent_calculation():
    rng = np.random.default_rng(11)
    rets = {s: rng.normal(0, 0.01, N - 1) for s in ("A", "B", "C")}
    hist = pd.concat([_from_log_returns(s, r) for s, r in rets.items()])
    m = np.mean(np.vstack(list(rets.values())), axis=0)[-g02.BETA_WINDOW:]
    a = rets["A"][-g02.BETA_WINDOW:]
    beta = np.mean((a - a.mean()) * (m - m.mean())) / np.var(m)
    assert abs(g02.score(hist)["A"] - (1 - (0.6 * beta + 0.4))) < 1e-10


def test_low_beta_bullish_high_beta_bearish():
    hist = pd.concat([loaded("LOW", N, 0.3, 1), loaded("HIGH", N, 2.0, 2), loaded("MID", N, 1.0, 3)])
    sc = g02.score(hist)
    assert sc["HIGH"] < 0 < sc["LOW"]


def test_short_history_abstains():
    hist = pd.concat([loaded("A", g02.MIN_ROWS - 1, 0.5, 1), loaded("B", g02.MIN_ROWS - 1, 2.0, 2)])
    assert g02.score(hist).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([loaded("F", N, 0.5, 1), loaded("G", N, 2.0, 2), loaded("CASH", N, 1.0, 3)])
    hist["has_future"] = hist["symbol"] != "CASH"
    assert "CASH" not in g02.score(hist).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    hist = pd.concat([loaded("LOW", N, 0.3, 1), loaded("HIGH", N, 2.0, 2)])
    assert g02.rules_fired(hist, "HIGH").endswith("bearish")
