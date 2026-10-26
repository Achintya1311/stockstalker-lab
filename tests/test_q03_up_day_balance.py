import numpy as np
import pandas as pd

from strategies import q03_up_day_balance as q03
from strategies.q03_up_day_balance_audit import check_cross_symbol_causality
from strategies.t17_keltner_breakout_audit import frame

N = q03.MIN_ROWS


def _closes(steps):
    """21 closes from 100 following `steps` (+1 up 1%, -1 down 1%, 0 flat)."""
    return 100.0 * np.cumprod(np.concatenate([[1.0], 1 + 0.01 * np.asarray(steps, dtype=float)]))


def test_hand_computed_balance_and_tie_break():
    steps = [1] * 14 + [-1] * 4 + [0] * 2          # 14 up, 4 down, 2 flat
    f = q03.compute_adjustment_factors(frame("A", _closes(steps)))
    balance, r20 = q03.parts(f)
    assert balance == 0.5
    assert abs(r20 - (14 * np.log(1.01) + 4 * np.log(0.99))) < 1e-12
    assert abs(q03.score(frame("A", _closes(steps)))["A"] - (0.5 + 0.02 * np.tanh(r20 / 0.2))) < 1e-12


def test_tie_break_never_reorders_different_balances():
    """Balance 0.10 with the largest possible return still ranks below 0.15 with
    the most negative one."""
    assert 0.10 + q03.TIE * 1.0 < 0.15 - q03.TIE * 1.0


def test_signs_and_zero_balance_abstains():
    hist = pd.concat([
        frame("UP", _closes([1] * 20)),
        frame("DOWN", _closes([-1] * 20)),
        frame("EVEN", _closes([1, -1] * 10)),
    ])
    sc = q03.score(hist)
    assert sc["UP"] > 0 > sc["DOWN"]
    assert "EVEN" not in sc


def test_only_the_last_window_counts():
    """Forty earlier down days do not change the reading of the last 20 up days."""
    long = 100.0 * np.cumprod(np.concatenate([[1.0], np.full(40, 0.99), np.full(20, 1.01)]))
    short = long[-N:]
    assert q03.score(frame("A", long))["A"] == q03.score(frame("A", short))["A"]


def test_short_history_abstains():
    assert q03.score(frame("A", _closes([1] * 19))).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([frame("F", _closes([1] * 20)), frame("CASH", _closes([1] * 20))])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(q03.score(hist).index) == ["F"]


def test_rules_fired_wording():
    hist = frame("UP", _closes([1] * 20))
    assert "bullish" in q03.rules_fired(hist, "UP")
    assert "abstain" in q03.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
