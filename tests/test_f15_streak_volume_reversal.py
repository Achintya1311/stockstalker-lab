import numpy as np
import pandas as pd

from strategies import f15_streak_volume_reversal as f15
from strategies.f13_accel_range_top_audit import walk, with_turnover
from strategies.f15_streak_volume_reversal_audit import check_cross_symbol_causality
from strategies.t17_keltner_breakout_audit import frame

N = f15.MIN_ROWS


def stock(symbol: str, last3, last5_turnover: float) -> pd.DataFrame:
    """Flat closes then three daily log steps; turnover 1e9 except the last five sessions."""
    steps = np.r_[np.zeros(N - 3), last3]
    turnover = np.r_[np.full(N - 5, 1e9), np.full(5, last5_turnover)]
    return with_turnover(frame(symbol, 100.0 * np.exp(np.cumsum(steps))), turnover)


def hist() -> pd.DataFrame:
    # D: three down closes on heavy recent turnover; U: three up closes on light; M: flat.
    return pd.concat([stock("D", [-0.01] * 3, 3e9), stock("U", [0.01] * 3, 0.5e9),
                      stock("M", [0.0] * 3, 1e9)], ignore_index=True)


def test_parts_match_hand_values():
    d = stock("D", [-0.01] * 3, 3e9).assign(adj_close=lambda x: x["close"])
    streak, ratio = f15.parts(d)
    assert streak == -3 and abs(ratio - 15 / 30) < 1e-12


def test_hand_computed_scores():
    """Streak ranks D 1/3, M 2/3, U 1. Ratios D 15/30, M 5/20, U 2.5/17.5.
    p: D 2/3 x 1/2 = 1/3, M 1/3 x 1/4 = 1/12, U 0. Median 1/12: D +1/4 bullish, U -1/12 bearish, M abstains."""
    sc = f15.score(hist())
    assert abs(sc["D"] - 0.25) < 1e-12
    assert abs(sc["U"] + 1 / 12) < 1e-12
    assert "M" not in sc.index


def test_short_history_abstains():
    assert f15.score(hist().groupby("symbol").tail(N - 1)).empty


def test_needs_turnover():
    assert f15.score(hist().drop(columns="turnover")).empty


def test_symbols_without_a_future_on_the_last_date_leave():
    h = hist()
    h.loc[(h["symbol"] == "M") & (h["date"] == h["date"].max()), "has_future"] = False
    assert "M" not in f15.score(h).index and set(f15.score(h).index) <= {"D", "U"}


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    h = hist()
    assert f15.rules_fired(h, "D").endswith("bullish") and "-3" in f15.rules_fired(h, "D")
    assert f15.rules_fired(h, "U").endswith("bearish")
    assert "abstain" in f15.rules_fired(h, "M")
