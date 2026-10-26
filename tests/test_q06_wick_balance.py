import numpy as np
import pandas as pd

from strategies import q06_wick_balance as q06
from strategies.q06_wick_balance_audit import check_cross_symbol_causality, wick_bar
from strategies.t17_keltner_breakout_audit import frame

N = 12


def test_hand_computed_wicks():
    """Last bar O 100, C 100.2, L 95, H 100.7: range 5.7, lower 5/5.7, upper 0.5/5.7."""
    f = q06.compute_adjustment_factors(wick_bar("A", N, +1))
    lower, upper = q06.wicks(f)
    assert abs(lower - 5.0 / 5.7) < 1e-12 and abs(upper - 0.5 / 5.7) < 1e-12
    assert abs(q06.score(wick_bar("A", N, +1))["A"] - 4.5 / 5.7) < 1e-12


def test_upper_wick_is_bearish():
    assert q06.score(wick_bar("A", N, -1))["A"] < 0


def test_no_range_or_equal_wicks_abstain():
    flat = frame("F", np.full(N, 100.0), spread=0.0)
    even = frame("E", np.full(N, 100.0))       # spread 0.5% both ways: equal wicks
    assert q06.score(pd.concat([flat, even])).empty


def test_split_on_the_last_bar_is_adjusted_consistently():
    """Halving every price of the last bar (and its PREVCLOSE) leaves the shares unchanged."""
    f = wick_bar("A", N, +1)
    g = f.copy()
    g.loc[N - 1, ["open", "high", "low", "close", "prevclose"]] = g.loc[N - 1, ["open", "high", "low", "close", "prevclose"]] / 2
    assert abs(q06.score(f)["A"] - q06.score(g)["A"]) < 1e-12


def test_short_history_abstains():
    assert q06.score(wick_bar("A", N, +1).iloc[-1:]).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = wick_bar("F", N, +1)
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(q06.score(hist).index) == ["F"]


def test_rules_fired_wording():
    hist = wick_bar("A", N, +1)
    assert "bullish" in q06.rules_fired(hist, "A")
    assert "abstain" in q06.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
