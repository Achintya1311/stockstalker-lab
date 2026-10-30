import numpy as np
import pandas as pd

from strategies import h06_downside_beta as h06
from strategies.h06_downside_beta_audit import check_cross_symbol_causality, market_and_stocks
from strategies.t17_keltner_breakout_audit import frame

N = h06.MIN_ROWS + 5


def test_high_downside_loading_bullish_low_bearish():
    hist = market_and_stocks(N, {"LOW": 0.3, "MID": 1.0, "HIGH": 2.0})
    sc = h06.score(hist)
    assert sc["LOW"] < 0 < sc["HIGH"]


def test_only_down_market_days_count():
    """A stock that tracks the market only on up days has a downside beta near zero."""
    rng = np.random.default_rng(3)
    f = rng.normal(0, 0.01, N)
    a = f + rng.normal(0, 0.002, N)
    b = f + rng.normal(0, 0.002, N)
    up_only = np.where(f > 0, 2 * f, 0.0) + rng.normal(0, 0.002, N)
    hist = pd.concat([frame(s, 100.0 * np.exp(np.cumsum(r))) for s, r in (("A", a), ("B", b), ("UP", up_only))])
    beta = h06.downside_betas(hist)
    assert abs(beta["UP"]) < 0.4 < beta["A"]


def test_hand_computed_downside_beta():
    rng = np.random.default_rng(8)
    rets = {s: rng.normal(0, 0.01 * (i + 1), N - 1) for i, s in enumerate(("A", "B", "C"))}
    hist = pd.concat([frame(s, 100.0 * np.exp(np.r_[0.0, np.cumsum(r)])) for s, r in rets.items()])
    m = np.mean(np.vstack(list(rets.values())), axis=0)[-h06.WINDOW:]
    a = rets["A"][-h06.WINDOW:]
    down = m < m.mean()
    ad, md = a[down], m[down]
    expected = np.mean((ad - ad.mean()) * (md - md.mean())) / np.var(md)
    assert abs(h06.downside_betas(hist)["A"] - expected) < 1e-10


def test_score_is_distance_from_median():
    hist = market_and_stocks(N, {"S0": 0.3, "S1": 0.8, "S2": 1.1, "S3": 1.9})
    beta = h06.downside_betas(hist)
    sc = h06.score(hist)
    for s in sc.index:
        assert abs(sc[s] - (beta[s] - beta.median())) < 1e-12


def test_short_history_abstains():
    hist = market_and_stocks(h06.MIN_ROWS - 1, {"A": 0.5, "B": 1.5})
    assert h06.score(hist).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = market_and_stocks(N, {"A": 0.3, "B": 1.0, "CASH": 2.0})
    hist["has_future"] = hist["symbol"] != "CASH"
    assert "CASH" not in h06.score(hist).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    hist = market_and_stocks(N, {"LOW": 0.3, "MID": 1.0, "HIGH": 2.0})
    assert h06.rules_fired(hist, "HIGH").endswith("bullish")
    assert h06.rules_fired(hist, "LOW").endswith("bearish")
