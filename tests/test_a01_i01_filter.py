import numpy as np
import pandas as pd

from strategies import a01_i01_filter as f
from strategies import a01_weekly_reversal, i01_momentum_score
from strategies.a01_i01_filter_audit import check_cross_symbol_causality, downtrend_then_bounce
from strategies.t21_minervini_template_audit import _frame

N = i01_momentum_score.MIN_ROWS


def uptrend_then_bounce(symbol: str, n_rows: int = N) -> pd.DataFrame:
    closes = 100.0 * np.exp(0.002 * np.arange(n_rows))
    closes[-5:] = closes[-6] * np.array([1.03, 1.06, 1.09, 1.12, 1.15])
    return _frame(symbol, closes)


def uptrend_then_drop(symbol: str, n_rows: int = N) -> pd.DataFrame:
    closes = 100.0 * np.exp(0.002 * np.arange(n_rows))
    closes[-5:] = closes[-6] * np.array([0.97, 0.94, 0.91, 0.88, 0.85])
    return _frame(symbol, closes)


def _hist():
    return pd.concat([downtrend_then_bounce("WEAK", N), uptrend_then_bounce("STRONG"), uptrend_then_drop("DROP")])


def test_bounce_in_a_downtrend_is_kept_with_a01_magnitude():
    hist = _hist()
    sc = f.score(hist)
    assert list(sc.index) == ["WEAK"]
    assert sc["WEAK"] == a01_weekly_reversal.score(hist)["WEAK"] < 0


def test_bounce_in_an_uptrend_is_dropped():
    hist = _hist()
    assert i01_momentum_score.score(hist)["STRONG"] > 0
    assert a01_weekly_reversal.score(hist)["STRONG"] < 0
    assert "STRONG" not in f.score(hist)


def test_a01_bullish_scores_are_dropped():
    hist = _hist()
    assert a01_weekly_reversal.score(hist)["DROP"] > 0
    assert "DROP" not in f.score(hist)


def test_no_i01_reading_abstains():
    """Short history: A01 can read it, I01 cannot."""
    hist = pd.concat([_hist(), downtrend_then_bounce("NEW", 30)])
    assert "NEW" in a01_weekly_reversal.score(hist)
    assert "NEW" not in f.score(hist)


def test_rules_fired_wording():
    hist = _hist()
    assert "bearish" in f.rules_fired(hist, "WEAK")
    assert "not below zero" in f.rules_fired(hist, "STRONG")
    assert "abstain" in f.rules_fired(hist, "DROP")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
