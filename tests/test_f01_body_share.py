import numpy as np
import pandas as pd

from strategies import f01_body_share as f01
from strategies.f01_body_share_audit import body_bar, check_cross_symbol_causality
from strategies.t17_keltner_breakout_audit import frame

N = 12


def test_hand_computed_body_share():
    """Last bar O 100, H 104, L 99, C 103: (103 - 100) / (104 - 99) = 0.6."""
    assert abs(f01.score(body_bar("A", N, +1))["A"] - 0.6) < 1e-12
    assert abs(f01.score(body_bar("B", N, -1))["B"] + 0.6) < 1e-12


def test_no_range_or_doji_abstains():
    flat = frame("F", np.full(N, 100.0), spread=0.0)
    doji = frame("D", np.full(N, 100.0))  # open = close = 100 with a 0.5% range
    assert f01.score(pd.concat([flat, doji])).empty


def test_split_on_the_last_bar_is_adjusted_consistently():
    """Halving every price of the last bar and its PREVCLOSE leaves the share unchanged."""
    f = body_bar("A", N, +1)
    i = N - 1
    f.loc[i, ["open", "high", "low", "close", "prevclose"]] = f.loc[i, ["open", "high", "low", "close", "prevclose"]] / 2
    assert abs(f01.score(f)["A"] - 0.6) < 1e-12


def test_short_history_abstains():
    assert f01.score(body_bar("A", N, +1).tail(1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = body_bar("F", N, +1)
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(f01.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert "bullish" in f01.rules_fired(body_bar("A", N, +1), "A")
    assert "bearish" in f01.rules_fired(body_bar("B", N, -1), "B")
