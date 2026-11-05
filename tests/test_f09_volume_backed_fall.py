import numpy as np
import pandas as pd

from strategies import f09_volume_backed_fall as f09
from strategies.f09_volume_backed_fall_audit import check_cross_symbol_causality, stock, walk

N = f09.MIN_ROWS + 3


def heavy_fall(symbol: str) -> pd.DataFrame:
    """Flat, then an accelerating fall over the last 9 sessions; the last session's turnover triples."""
    steps = -0.005 * np.arange(1, 10) ** 1.5
    closes = np.r_[np.full(N - 9, 100.0), 100.0 * np.exp(np.cumsum(steps))]
    return stock(symbol, closes, np.r_[np.full(N - 1, 1e9), 3e9])


def flat(symbol: str) -> pd.DataFrame:
    return stock(symbol, np.full(N, 100.0), np.full(N, 1e9))


def test_hand_computed_ranks():
    """Heavy fall: both factors are the top of their windows, raw = 1. Flat: every ratio is 1
    and every 7-session change 0, so ranks are the tie midpoints 10.5/20 and 4.5/8."""
    raw = f09.raw_scores(pd.concat([heavy_fall("A"), flat("B")], ignore_index=True))
    assert abs(raw["A"] - 1.0) < 1e-12
    assert abs(raw["B"] - (10.5 / 20) * (4.5 / 8)) < 1e-12


def test_centred_by_median_heavy_fall_is_bullish():
    sc = f09.score(pd.concat([heavy_fall("A"), flat("B")], ignore_index=True))
    expected = (1.0 - (10.5 / 20) * (4.5 / 8)) / 2
    assert abs(sc["A"] - expected) < 1e-12 and abs(sc["B"] + expected) < 1e-12


def test_zero_turnover_abstains():
    f = heavy_fall("A")
    f.loc[f.index[-3], "turnover"] = 0.0
    assert "A" not in f09.score(pd.concat([f, flat("B"), walk("C", N, 1)], ignore_index=True)).index


def test_short_history_abstains():
    assert f09.score(heavy_fall("A").tail(f09.MIN_ROWS - 1)).empty


def test_needs_turnover_column():
    assert f09.score(heavy_fall("A").drop(columns="turnover")).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([heavy_fall("A"), flat("B"), walk("CASH", N, 2)], ignore_index=True)
    hist["has_future"] = hist["symbol"] != "CASH"
    assert set(f09.score(hist).index) == {"A", "B"}


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    hist = pd.concat([heavy_fall("A"), flat("B")], ignore_index=True)
    assert f09.rules_fired(hist, "A").endswith("bullish")
    assert f09.rules_fired(hist, "B").endswith("bearish")
