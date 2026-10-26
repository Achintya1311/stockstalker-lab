import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import t17_keltner_breakout as t17
from strategies.t17_keltner_breakout_audit import check_cross_symbol_causality, frame, quiet_then_jump

N = t17.MIN_ROWS


def test_flat_series_has_known_channel():
    """Constant close 100 with high/low 100 +/- 0.5%: every true range is 1.0,
    so ATR = 1, EMA = 100, channel = 98 to 102."""
    hist = frame("AAA", np.full(N, 100.0))
    close, upper, lower, atr = t17.channel(compute_adjustment_factors(hist))
    assert abs(atr - 1.0) < 1e-9 and abs(upper - 102.0) < 1e-9 and abs(lower - 98.0) < 1e-9
    assert t17.score(hist).empty  # close 100 is inside


def test_jump_up_fires_bullish_with_atr_scaled_score():
    closes = np.full(N, 100.0)
    closes[-1] = 110.0
    hist = frame("AAA", closes)
    close, upper, lower, atr = t17.channel(compute_adjustment_factors(hist))
    sc = t17.score(hist)
    assert sc["AAA"] > 0
    assert abs(sc["AAA"] - (close - upper) / atr) < 1e-12


def test_jump_down_fires_bearish():
    assert t17.score(quiet_then_jump("AAA", N, -0.08, seed=4))["AAA"] < 0


def test_quiet_walk_abstains():
    rng = np.random.default_rng(5)
    hist = frame("AAA", 100.0 * np.exp(np.cumsum(rng.normal(0, 0.001, N))))
    assert t17.score(hist).empty


def test_short_history_abstains():
    assert t17.score(quiet_then_jump("AAA", N - 1, 0.08, seed=1)).empty


def test_old_rows_do_not_matter():
    base = quiet_then_jump("AAA", N + 30, 0.08, seed=1)
    changed = base.copy()
    changed.loc[:9, "high"] *= 1.5
    assert t17.score(base)["AAA"] == t17.score(changed)["AAA"]


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([quiet_then_jump("F", N, 0.08, 1), quiet_then_jump("CASH", N, 0.08, 2)])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(t17.score(hist).index) == ["F"]


def test_rules_fired_wording():
    hist = quiet_then_jump("UP", N, 0.08, 1)
    assert "bullish" in t17.rules_fired(hist, "UP")
    assert "abstain" in t17.rules_fired(frame("FLAT", np.full(N, 100.0)), "FLAT")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
