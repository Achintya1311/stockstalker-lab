import numpy as np
import pandas as pd

from strategies import t21_minervini_template as t21
from strategies.t21_minervini_template_audit import _frame, check_cross_symbol_causality, trend

N = t21.MIN_ROWS


def test_steady_uptrend_passes_bullish_at_the_high():
    sc = t21.score(trend("UP", 0.003, N))
    assert "UP" in sc
    assert 0.9 < sc["UP"] <= 1.0  # at (or a wiggle below) its 52-week high


def test_steady_downtrend_passes_bearish():
    sc = t21.score(trend("DOWN", -0.003, N))
    assert "DOWN" in sc and -1.0 <= sc["DOWN"] < -0.9


def test_flat_series_abstains():
    assert t21.score(trend("FLAT", 0.0, N)).empty


def test_uptrend_too_close_to_its_low_abstains():
    """A gentle uptrend: every SMA condition holds but the close is less than
    30% above the 52-week low, so rule 6 fails."""
    sc = t21.score(trend("GENTLE", 0.0005, N))  # about +13% over a year
    assert "GENTLE" not in sc


def test_pullback_more_than_25pct_from_high_abstains():
    t = np.arange(N)
    up = 100.0 * np.exp(0.004 * t)
    closes = up.copy()
    closes[-5:] = up[-6] * 0.70  # a 30% drop in the last week
    assert t21.score(_frame("DROP", closes)).empty


def test_proximity_score_formula():
    t = np.arange(N)
    closes = 100.0 * np.exp(0.003 * t)
    closes[-1] = closes[-2] * 0.97  # 3% off the high, trend intact
    sc = t21.score(_frame("AAA", closes))
    high = closes[-t21.YEAR:].max()
    assert abs(sc["AAA"] - (closes[-1] / high - 0.75) / 0.25) < 1e-12


def test_short_history_abstains():
    assert t21.score(trend("UP", 0.003, N - 1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([trend("F", 0.003, N), trend("CASH", 0.003, N)])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(t21.score(hist).index) == ["F"]


def test_rules_fired_wording():
    hist = pd.concat([trend("UP", 0.003, N), trend("FLAT", 0.0, N)])
    assert "bullish" in t21.rules_fired(hist, "UP")
    assert "abstain" in t21.rules_fired(hist, "FLAT")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
