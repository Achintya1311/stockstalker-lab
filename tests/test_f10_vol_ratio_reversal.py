import numpy as np
import pandas as pd

from strategies import f10_vol_ratio_reversal as f10
from strategies.f10_vol_ratio_reversal_audit import check_cross_symbol_causality, walk
from strategies.t17_keltner_breakout_audit import frame


def from_returns(symbol: str, rets) -> pd.DataFrame:
    return frame(symbol, np.r_[np.full(4, 100.0), 100.0 * np.exp(np.cumsum(rets))])


A = [0.05, -0.05, 0.05, -0.001, -0.002]   # turbulent then calm, fell yesterday
B = [0.001, -0.001, 0.001, -0.05, 0.05]   # calm then turbulent, rose yesterday
C = [0.01, -0.01, 0.01, -0.01, 0.0]       # in between, unchanged yesterday


def hist() -> pd.DataFrame:
    return pd.concat([from_returns("A", A), from_returns("B", B), from_returns("C", C)], ignore_index=True)


def test_parts_match_hand_values():
    ratio, last = f10.parts(from_returns("B", B).rename(columns={"close": "adj_close"}))
    assert abs(ratio - np.std([-0.05, 0.05], ddof=1) / np.std(B, ddof=1)) < 1e-9
    assert abs(last - 0.05) < 1e-12


def test_hand_computed_scores():
    """Ratio ranks A 1/3, C 2/3, B 1; last-return ranks the same. Sums 4/3, 2/3, 0;
    median 2/3, so A +2/3 (bullish), B -2/3 (bearish), C at the median abstains."""
    sc = f10.score(hist())
    assert abs(sc["A"] - 2 / 3) < 1e-12
    assert abs(sc["B"] + 2 / 3) < 1e-12
    assert "C" not in sc.index


def test_flat_stock_abstains():
    sc = f10.score(pd.concat([hist(), frame("F", np.full(9, 100.0))], ignore_index=True))
    assert "F" not in sc.index


def test_short_history_abstains():
    assert f10.score(from_returns("A", A).tail(f10.MIN_ROWS - 1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    h = pd.concat([hist(), walk("CASH", 12, 1)], ignore_index=True)
    h["has_future"] = h["symbol"] != "CASH"
    assert "CASH" not in f10.score(h).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert f10.rules_fired(hist(), "A").endswith("bullish")
    assert f10.rules_fired(hist(), "B").endswith("bearish")
