import numpy as np
import pandas as pd

from strategies import t16_parabolic_sar as t16
from strategies.t16_parabolic_sar_audit import check_cross_symbol_causality
from strategies.t21_minervini_template_audit import _frame

N = t16.MIN_ROWS


def test_hand_computed_first_steps():
    """Rising bars: bar 0 seeds SAR at its low (10) with EP 11; bar 1 SAR =
    10 + 0.02 x (11 - 10) = 10.02, capped at the previous low (10) -> 10."""
    h = np.array([11.0, 12.0, 13.0]); l = np.array([10.0, 11.0, 12.0]); c = np.array([10.5, 11.5, 12.5])
    sar, up = t16.parabolic_sar(h, l, c)
    assert up.all()
    assert sar[0] == 10.0 and sar[1] == 10.0
    # bar 1 made a new high (12 > 11): EP 12, AF 0.04; bar 2 SAR = 10 + 0.04 x 2 = 10.08, capped at min(lows 11, 10)
    assert abs(sar[2] - 10.0) < 1e-12


def test_reversal_flips_to_downtrend_at_ep():
    h = np.array([11.0, 12.0, 13.0, 9.0]); l = np.array([10.0, 11.0, 12.0, 8.0]); c = np.array([10.5, 11.5, 12.5, 8.5])
    sar, up = t16.parabolic_sar(h, l, c)
    assert not up[-1]
    assert sar[-1] == 13.0  # the trend's extreme high


def test_af_is_capped():
    n = 50
    h = 100.0 + np.arange(n, dtype=float); l = h - 0.5; c = h - 0.2
    sar, up = t16.parabolic_sar(h, l, c)
    assert up.all()
    assert (np.diff(sar) >= 0).all() and sar[-1] < l[-1]


def test_uptrend_is_bullish_downtrend_bearish():
    t = np.arange(N)
    hist = pd.concat([_frame("UP", 100.0 * np.exp(0.004 * t)), _frame("DOWN", 100.0 * np.exp(-0.004 * t))])
    sc = t16.score(hist)
    assert sc["UP"] > 0 > sc["DOWN"]


def test_short_history_abstains():
    assert t16.score(_frame("A", 100.0 * np.exp(0.004 * np.arange(N - 1)))).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    t = np.arange(N)
    hist = pd.concat([_frame("F", 100.0 * np.exp(0.004 * t)), _frame("CASH", 100.0 * np.exp(0.004 * t))])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(t16.score(hist).index) == ["F"]


def test_rules_fired_wording():
    hist = _frame("UP", 100.0 * np.exp(0.004 * np.arange(N)))
    assert "bullish" in t16.rules_fired(hist, "UP")
    assert "abstain" in t16.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
