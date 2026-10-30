import numpy as np
import pandas as pd

from strategies import g01_residual_momentum as g01
from strategies import g01b_residual_momentum_volatile as g01b
from strategies.g01b_residual_momentum_volatile_audit import check_cross_symbol_causality, walk

N = g01b.MIN_ROWS + 5


def _universe():
    # Two volatile losers, two calm losers, two winners (one volatile).
    return pd.concat([
        walk("VOL_LOSER", N, 1, -1.20, 0.02),
        walk("VOL_LOSER2", N, 2, -1.00, 0.02),
        walk("CALM_LOSER", N, 3, -0.60, 0.006),
        walk("CALM_LOSER2", N, 4, -0.40, 0.006),
        walk("VOL_WINNER", N, 5, 0.60, 0.02),
        walk("CALM_WINNER", N, 6, 0.60, 0.006),
    ])


def test_only_volatile_losers_are_scored_bearish():
    sc = g01b.score(_universe())
    assert set(sc.index) == {"VOL_LOSER", "VOL_LOSER2"}
    assert (sc < 0).all()


def test_no_bullish_scores():
    sc = g01b.score(_universe())
    assert not (sc > 0).any()


def test_scores_equal_g01_where_emitted():
    hist = _universe()
    sc, base = g01b.score(hist), g01.score(hist)
    for s in sc.index:
        assert abs(sc[s] - base[s]) < 1e-12


def test_median_threshold_is_inclusive_and_cross_sectional():
    stats = g01b.residual_stats(_universe())
    med = stats["resid_vol"].median()
    sc = g01b.score(_universe())
    expected = stats.index[(stats["score"] < 0) & (stats["resid_vol"] >= med)]
    assert set(sc.index) == set(expected)


def test_short_history_abstains():
    hist = pd.concat([walk("A", g01b.MIN_ROWS - 1, 1, -0.5, 0.02), walk("B", g01b.MIN_ROWS - 1, 2)])
    assert g01b.score(hist).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = _universe()
    hist["has_future"] = hist["symbol"] != "VOL_LOSER"
    assert "VOL_LOSER" not in g01b.score(hist).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    hist = _universe()
    assert g01b.rules_fired(hist, "VOL_LOSER").endswith("bearish")
    assert "abstain" in g01b.rules_fired(hist, "CALM_WINNER")
