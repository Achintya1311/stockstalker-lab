import numpy as np
import pandas as pd

from strategies import h02_idiosyncratic_volatility as h02
from strategies.h02_idiosyncratic_volatility_audit import check_cross_symbol_causality, walk
from strategies.t17_keltner_breakout_audit import frame

N = h02.MIN_ROWS + 5


def _from_log_returns(symbol, r):
    return frame(symbol, 100.0 * np.exp(np.r_[0.0, np.cumsum(r)]))


def test_calm_stock_bullish_noisy_stock_bearish():
    hist = pd.concat([walk("CALM", N, 1, 0.004), walk("MID", N, 2, 0.01), walk("WILD", N, 3, 0.04)])
    sc = h02.score(hist)
    assert sc["WILD"] < 0 < sc["CALM"]


def test_pure_market_moves_carry_no_idiosyncratic_volatility():
    """B's daily log returns are exactly twice A's, so both are linear in the market mean and both abstain."""
    rng = np.random.default_rng(4)
    r = rng.normal(0, 0.01, N - 1)
    hist = pd.concat([_from_log_returns("A", r), _from_log_returns("B", 2 * r)])
    assert h02.idiosyncratic_vol(hist).empty
    assert h02.score(hist).empty


def test_hand_computed_ivol_matches_an_independent_calculation():
    rng = np.random.default_rng(9)
    rets = {s: rng.normal(0, 0.01 * (i + 1), N - 1) for i, s in enumerate(("A", "B", "C"))}
    hist = pd.concat([_from_log_returns(s, r) for s, r in rets.items()])
    m = np.mean(np.vstack(list(rets.values())), axis=0)[-h02.WINDOW:]
    a = rets["A"][-h02.WINDOW:]
    beta = np.mean((a - a.mean()) * (m - m.mean())) / np.var(m)
    e = (a - a.mean()) - beta * (m - m.mean())
    assert abs(h02.idiosyncratic_vol(hist)["A"] - e.std()) < 1e-10


def test_score_is_log_ratio_to_median():
    hist = pd.concat([walk(f"S{i}", N, i, 0.005 * (i + 1)) for i in range(5)])
    ivol = h02.idiosyncratic_vol(hist)
    sc = h02.score(hist)
    for s in sc.index:
        assert abs(sc[s] - (np.log(ivol.median()) - np.log(ivol[s]))) < 1e-12


def test_short_history_abstains():
    hist = pd.concat([walk("A", h02.MIN_ROWS - 1, 1), walk("B", h02.MIN_ROWS - 1, 2, 0.03)])
    assert h02.score(hist).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([walk("A", N, 1, 0.004), walk("B", N, 2, 0.01), walk("CASH", N, 3, 0.05)])
    hist["has_future"] = hist["symbol"] != "CASH"
    assert "CASH" not in h02.score(hist).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    hist = pd.concat([walk("CALM", N, 1, 0.004), walk("MID", N, 2, 0.01), walk("WILD", N, 3, 0.04)])
    assert h02.rules_fired(hist, "WILD").endswith("bearish")
    assert h02.rules_fired(hist, "CALM").endswith("bullish")
