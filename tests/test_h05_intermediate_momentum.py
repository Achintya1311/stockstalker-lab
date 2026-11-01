import numpy as np
import pandas as pd

from strategies import h05_intermediate_momentum as h05
from strategies.h05_intermediate_momentum_audit import check_cross_symbol_causality
from strategies.t17_keltner_breakout_audit import frame


def _series(symbol, n, far_to_near, recent=0.0):
    """Flat at 100 until the far anchor, `far_to_near` move by the near anchor, then `recent` move after it."""
    closes = np.full(n, 100.0)
    near_idx = n - h05.NEAR_DAYS - 1
    closes[near_idx:] = 100.0 * (1 + far_to_near)
    if recent:
        closes[near_idx + 1:] = 100.0 * (1 + far_to_near) * (1 + recent)
    return frame(symbol, closes)


N = h05.MIN_ROWS + 5


def test_gain_bullish_loss_bearish_exact():
    hist = pd.concat([_series("UP", N, 0.25), _series("DN", N, -0.2)])
    sc = h05.score(hist)
    assert abs(sc["UP"] - 0.25) < 1e-9 and abs(sc["DN"] + 0.2) < 1e-9


def test_latest_six_months_ignored():
    a = h05.score(_series("X", N, 0.1, recent=0.0))["X"]
    b = h05.score(_series("X", N, 0.1, recent=-0.5))["X"]
    assert abs(a - b) < 1e-9


def test_short_history_abstains():
    assert h05.score(_series("X", h05.MIN_ROWS - 1, 0.1)).empty


def test_flat_abstains():
    assert h05.score(_series("X", N, 0.0)).empty


def test_non_fno_dropped_when_flag_present():
    hist = pd.concat([_series("A", N, 0.1), _series("B", N, 0.2)])
    hist["has_future"] = hist["symbol"] != "B"
    assert list(h05.score(hist).index) == ["A"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert h05.rules_fired(_series("X", N, 0.1), "X").endswith("bullish")
    assert h05.rules_fired(_series("X", N, -0.1), "X").endswith("bearish")
