import pandas as pd

from strategies import a10_gap_and_go as a10
from strategies.a10_gap_and_go_audit import check_cross_symbol_causality, gap_and_go


def test_hand_computed_gap_and_go_is_bullish_with_score_z():
    """Gaps alternate +-1% (sigma exactly 1%), then +5%: z = 5, volume 3x, close above
    every prior high, so the score is 5."""
    f = a10.compute_adjustment_factors(gap_and_go("A"))
    z, ratio, above = a10.parts(f)
    assert abs(z - 5.0) < 1e-9 and abs(ratio - 3.0) < 1e-12 and above
    assert abs(a10.score(gap_and_go("A"))["A"] - 5.0) < 1e-9


def test_each_condition_is_needed():
    weak_volume = gap_and_go("V", volume_jump=1.4)
    small_gap = gap_and_go("G", m=0.015)  # z = 1.5
    gap_down = gap_and_go("D", m=-0.05)
    assert a10.score(pd.concat([weak_volume, small_gap, gap_down])).empty


def test_close_below_resistance_abstains():
    f = gap_and_go("R")
    i = f.index[-1]
    f.loc[f.index[-10], "high"] = float(f.loc[i, "close"]) * 1.2
    assert a10.score(f).empty


def test_short_history_abstains():
    assert a10.score(gap_and_go("A").iloc[-(a10.MIN_ROWS - 1):]).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = gap_and_go("F")
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(a10.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_all_three_conditions():
    text = a10.rules_fired(gap_and_go("A"), "A")
    assert "+5.00 sigma" in text and "3.00x" in text and "above" in text and text.endswith("bullish")
