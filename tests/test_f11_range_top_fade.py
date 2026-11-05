import numpy as np
import pandas as pd

from strategies import f11_range_top_fade as f11
from strategies.f11_range_top_fade_audit import check_cross_symbol_causality, walk
from strategies.t17_keltner_breakout_audit import frame

N = f11.MIN_ROWS + 2


def growth(symbol: str, steps) -> pd.DataFrame:
    """`frame` opens each bar at the previous close, so close / open = 1 + the step."""
    return frame(symbol, 100.0 * np.cumprod(np.r_[1.0, 1.0 + np.asarray(steps, float)]))


A = np.full(N - 1, 0.01)                       # ten-session high on a +1% bar
B = np.full(N - 1, -0.01)                      # ten-session low on a -1% bar
C = np.r_[np.full(N - 2, 0.01), -0.005]        # second-highest close on a -0.5% bar


def hist() -> pd.DataFrame:
    return pd.concat([growth("A", A), growth("B", B), growth("C", C)], ignore_index=True)


def test_parts_match_hand_values():
    ts_rank, bar = f11.parts(growth("C", C).rename(columns={"close": "adj_close"}).assign(close=lambda d: d["adj_close"]))
    assert abs(ts_rank - 0.9) < 1e-12 and abs(bar - 0.995) < 1e-12


def test_hand_computed_scores():
    """Ts-rank 1.0 / 0.1 / 0.9 and bars 1.01 / 0.99 / 0.995 rank A 1, C 2/3, B 1/3 in both.
    Products 1, 4/9, 1/9; median 4/9: A -5/9 (bearish), B +1/3 (bullish), C abstains."""
    sc = f11.score(hist())
    assert abs(sc["A"] + 5 / 9) < 1e-12
    assert abs(sc["B"] - 1 / 3) < 1e-12
    assert "C" not in sc.index


def test_short_history_abstains():
    assert f11.score(growth("A", A).tail(f11.MIN_ROWS - 1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    h = pd.concat([hist(), walk("CASH", N, 1)], ignore_index=True)
    h["has_future"] = h["symbol"] != "CASH"
    assert "CASH" not in f11.score(h).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert f11.rules_fired(hist(), "A").endswith("bearish")
    assert f11.rules_fired(hist(), "B").endswith("bullish")
