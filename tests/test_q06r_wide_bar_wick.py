import numpy as np
import pandas as pd

from strategies import q06_wick_balance as q06
from strategies import q06r_wide_bar_wick as q06r
from strategies.q06_wick_balance_audit import wick_bar
from strategies.q06r_wide_bar_wick_audit import check_cross_symbol_causality

N = q06r.MIN_ROWS + 3


def test_wide_bar_keeps_q06_score():
    """`wick_bar`'s last bar spans 5.7 against flat bars of about 1.0, so Q06R equals Q06."""
    bull, bear = wick_bar("A", N, +1), wick_bar("B", N, -1)
    hist = pd.concat([bull, bear])
    assert q06r.score(hist).to_dict() == q06.score(hist).to_dict()
    assert q06r.score(hist)["A"] > 0 > q06r.score(hist)["B"]


def test_hand_computed_range_ratio():
    """Flat bars at 100 with spread 0.5% span 100.5 - 99.5 = 1.0; the last bar spans 5.7."""
    f = q06r.compute_adjustment_factors(wick_bar("A", N, +1))
    assert abs(q06r.range_ratio(f) - 5.7) < 1e-9


def test_narrow_bar_abstains():
    """Same wick shape, shrunk to a range below the 20-session median: abstain."""
    f = wick_bar("A", N, +1)
    i = N - 1
    f.loc[i, ["open", "close", "low", "high"]] = [100.0, 100.02, 99.5, 100.07]
    assert q06.score(f)["A"] > 0
    assert q06r.score(f).empty


def test_short_history_abstains():
    assert q06r.score(wick_bar("A", q06r.MIN_ROWS - 1, +1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = wick_bar("F", N, +1)
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(q06r.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_side_and_width():
    text = q06r.rules_fired(wick_bar("A", N, +1), "A")
    assert "bullish" in text and "5.70x" in text
