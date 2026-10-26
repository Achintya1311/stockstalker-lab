import numpy as np
import pandas as pd

from strategies import t18_ichimoku_cloud as t18
from strategies.t17_keltner_breakout_audit import frame
from strategies.t18_ichimoku_cloud_audit import check_cross_symbol_causality

N = t18.MIN_ROWS


def test_hand_computed_lines_on_a_straight_line():
    """Closes 1..N with zero spread, so each bar's high is its close and its low the
    previous close. Tenkan = (N + N-9) / 2 = N-4.5; Kijun = (N + N-26) / 2 = N-13;
    26 bars ago Tenkan = N-30.5 and Kijun = N-39, so Senkou A = N-34.75; Senkou B
    then = (N-26 + N-78) / 2 = N-52."""
    closes = np.arange(1, N + 1, dtype=float)
    f = frame("A", closes, spread=0.0)
    close, tenkan, kijun, top, bottom = t18.lines(t18.compute_adjustment_factors(f))
    assert close == N and tenkan == N - 4.5 and kijun == N - 13
    assert top == N - 34.75 and bottom == N - 52
    assert abs(t18.score(f)["A"] - 34.75 / N) < 1e-12


def test_uptrend_is_bullish_downtrend_bearish():
    t = np.arange(N)
    hist = pd.concat([frame("UP", 100.0 * np.exp(0.004 * t)), frame("DOWN", 100.0 * np.exp(-0.004 * t))])
    sc = t18.score(hist)
    assert sc["UP"] > 0 > sc["DOWN"]


def test_inside_cloud_abstains():
    """A flat series ends inside (on) its cloud, so it does not fire."""
    assert t18.score(frame("FLAT", np.full(N, 100.0))).empty


def test_close_above_cloud_but_tenkan_below_kijun_abstains():
    """Long rise, then a 12-day dip that stays above the cloud: Tenkan falls
    below Kijun, so the bullish rule needs both and abstains."""
    closes = np.concatenate([np.linspace(50, 200, N - 12), np.linspace(185, 180, 12)])
    f = t18.compute_adjustment_factors(frame("DIP", closes))
    close, tenkan, kijun, top, _ = t18.lines(f)
    assert close > top and tenkan < kijun
    assert t18.score(frame("DIP", closes)).empty


def test_short_history_abstains():
    assert t18.score(frame("A", 100.0 * np.exp(0.004 * np.arange(N - 1)))).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    t = np.arange(N)
    hist = pd.concat([frame("F", 100.0 * np.exp(0.004 * t)), frame("CASH", 100.0 * np.exp(0.004 * t))])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(t18.score(hist).index) == ["F"]


def test_rules_fired_wording():
    hist = frame("UP", 100.0 * np.exp(0.004 * np.arange(N)))
    assert "bullish" in t18.rules_fired(hist, "UP")
    assert "abstain" in t18.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
