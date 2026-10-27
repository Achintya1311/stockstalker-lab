import numpy as np
import pandas as pd

from strategies import q07_trend_residual as q07
from strategies.q07_trend_residual_audit import check_cross_symbol_causality, line_then_last
from strategies.t17_keltner_breakout_audit import frame

N = q07.MIN_ROWS


def test_hand_computed_residual():
    """Log closes on a line, last one moved down by d. Refitting with the last point
    moved changes the fit; for x = 0..19 the last point's leverage is
    h = 1/20 + (9.5^2)/665 = 0.1857..., so the residual is -d x (1 - h)."""
    d = 0.05
    f = q07.compute_adjustment_factors(line_then_last("A", N, 0.01, -d))
    h = 1 / N + 9.5**2 / 665.0
    assert abs(q07.residual(f) + d * (1 - h)) < 1e-9
    assert abs(q07.score(line_then_last("A", N, 0.01, -d))["A"] - d * (1 - h)) < 1e-9


def test_stretched_close_is_bearish_and_pullback_bullish_whatever_the_trend():
    hist = pd.concat([
        line_then_last("UP_DIP", N, 0.01, -0.03),
        line_then_last("DOWN_DIP", N, -0.01, -0.03),
        line_then_last("UP_JUMP", N, 0.01, 0.03),
    ])
    sc = q07.score(hist)
    assert sc["UP_DIP"] > 0 and sc["DOWN_DIP"] > 0 and sc["UP_JUMP"] < 0


def test_close_on_the_line_abstains():
    assert q07.score(frame("A", np.full(N, 100.0))).empty


def test_short_history_abstains():
    assert q07.score(line_then_last("A", N - 1, 0.01, -0.05)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = line_then_last("F", N + 3, 0.01, -0.05)
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(q07.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert "bullish" in q07.rules_fired(line_then_last("A", N, 0.01, -0.05), "A")
