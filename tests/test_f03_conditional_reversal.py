import pandas as pd

from strategies import f03_conditional_reversal as f03
from strategies.f03_conditional_reversal_audit import check_cross_symbol_causality, from_returns


def test_hand_computed_runs_continue_and_mixed_days_reverse():
    hist = pd.concat([
        from_returns("UPRUN", 3, [0.01, 0.01, 0.01, 0.01, 0.02]),     # continuation: +0.02
        from_returns("DOWNRUN", 3, [-0.01, -0.01, -0.01, -0.01, -0.02]),  # continuation: -0.02
        from_returns("MIXED_UP", 3, [0.01, -0.01, 0.01, -0.01, 0.03]),    # reversal: -0.03
        from_returns("MIXED_DOWN", 3, [0.01, 0.01, 0.01, 0.01, -0.03]),   # reversal: +0.03
    ])
    sc = f03.score(hist)
    for sym, want in [("UPRUN", 0.02), ("DOWNRUN", -0.02), ("MIXED_UP", -0.03), ("MIXED_DOWN", 0.03)]:
        assert abs(sc[sym] - want) < 1e-12


def test_a_zero_return_inside_the_run_breaks_it():
    sc = f03.score(from_returns("A", 3, [0.01, 0.0, 0.01, 0.01, 0.02]))
    assert abs(sc["A"] + 0.02) < 1e-12


def test_unchanged_last_close_abstains():
    assert f03.score(from_returns("A", 3, [0.01, -0.01, 0.01, 0.01, 0.0])).empty


def test_short_history_abstains():
    assert f03.score(from_returns("A", 0, [0.01, 0.01, 0.01, 0.02])).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = from_returns("F", 3, [0.01, -0.01, 0.01, -0.01, 0.03])
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(f03.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_kind_and_side():
    text = f03.rules_fired(from_returns("A", 3, [0.01, -0.01, 0.01, -0.01, 0.03]), "A")
    assert "reversal" in text and text.endswith("bearish")
