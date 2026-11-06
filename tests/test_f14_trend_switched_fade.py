import numpy as np
import pandas as pd

from strategies import f14_trend_switched_fade as f14
from strategies.f13_accel_range_top_audit import walk, with_turnover
from strategies.f14_trend_switched_fade_audit import check_cross_symbol_causality
from strategies.t17_keltner_breakout_audit import frame

N = f14.MIN_ROWS


def series(symbol: str, closes) -> pd.DataFrame:
    return with_turnover(frame(symbol, np.asarray(closes, float)), np.full(len(closes), 1e9))


FLAT = np.r_[np.full(N - 10, 100.0), np.full(9, 90.0), 99.0]     # trend ~ -1%: flat branch; low 90, close 99
RISING = np.r_[np.linspace(50, 100, N - 3), 104.0, 102.0, 98.0]  # trend far above 5%: 3-session change


def test_flat_branch_hand_value():
    g, branch, s = f14.parts(FLAT)
    assert branch == "flat" and g <= 0.05
    assert abs(s - (-(99.0 - 90.0) / 99.0)) < 1e-12


def test_rising_branch_hand_value():
    g, branch, s = f14.parts(RISING)
    assert branch == "rising" and g > 0.05
    c = RISING
    assert abs(s - (-(98.0 - c[-4]) / 98.0)) < 1e-12 and s > 0   # a 3-session fall in an uptrend is bullish


def test_threshold_is_inclusive():
    c = np.r_[np.full(f14.MEAN, 100.0), np.full(f14.MEAN, 105.0)]   # g = 5/100 exactly
    assert f14.parts(c)[1] == "flat"


def test_scores_end_to_end():
    sc = f14.score(pd.concat([series("F", FLAT), series("R", RISING)], ignore_index=True))
    assert sc["F"] < 0 and sc["R"] > 0


def test_short_history_abstains():
    assert f14.score(series("F", FLAT[-(N - 1):])).empty


def test_at_the_low_abstains():
    c = np.r_[np.full(N - 1, 100.0), 90.0]   # flat trend, close is its own 100-session low: score 0
    assert f14.score(series("L", c)).empty


def test_symbols_without_a_future_on_the_last_date_leave():
    h = pd.concat([series("F", FLAT), series("R", RISING)], ignore_index=True)
    h.loc[(h["symbol"] == "R") & (h["date"] == h["date"].max()), "has_future"] = False
    assert list(f14.score(h).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_branch_and_side():
    h = pd.concat([series("F", FLAT), series("R", RISING)], ignore_index=True)
    f, r = f14.rules_fired(h, "F"), f14.rules_fired(h, "R")
    assert "at most +5%" in f and f.endswith("bearish")
    assert "above +5%" in r and r.endswith("bullish")
