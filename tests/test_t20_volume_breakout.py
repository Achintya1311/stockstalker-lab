import pandas as pd

from strategies import t20_volume_breakout as t20
from strategies.t20_volume_breakout_audit import bars, check_cross_symbol_causality

N = t20.MIN_ROWS


def test_bullish_breakout_scores_the_volume_ratio():
    sc = t20.score(bars("AAA", N, 0.9, 3e6))
    assert abs(sc["AAA"] - 3.0) < 1e-12


def test_bearish_breakout_is_negative():
    sc = t20.score(bars("AAA", N, 0.1, 2.5e6))
    assert abs(sc["AAA"] + 2.5) < 1e-12


def test_boundaries():
    assert "A" in t20.score(bars("A", N, 0.75, 3e6))  # top quarter, inclusive
    assert "B" in t20.score(bars("B", N, 0.25, 3e6))  # bottom quarter, inclusive
    assert t20.score(bars("C", N, 0.9, 2e6)).empty  # exactly 2x is not over 2x
    assert t20.score(bars("D", N, 0.5, 5e6)).empty  # mid-range close


def test_quiet_day_abstains():
    assert t20.score(bars("AAA", N)).empty


def test_session_is_not_in_its_own_baseline():
    """Baseline is the 20 sessions before the last: a 3x day is 3x, not
    3 / mean(19 ones and a 3)."""
    assert t20.score(bars("AAA", N + 5, 0.9, 3e6))["AAA"] == 3.0


def test_zero_range_abstains():
    hist = bars("AAA", N, 0.9, 3e6)
    hist.loc[hist.index[-1], ["high", "low", "close"]] = 100.0
    assert t20.score(hist).empty


def test_short_history_abstains():
    assert t20.score(bars("AAA", N - 1, 0.9, 3e6)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([bars("F", N, 0.9, 3e6), bars("CASH", N, 0.9, 3e6)])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(t20.score(hist).index) == ["F"]


def test_rules_fired_wording():
    assert "bullish" in t20.rules_fired(bars("A", N, 0.9, 3e6), "A")
    assert "abstain" in t20.rules_fired(bars("B", N), "B")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
