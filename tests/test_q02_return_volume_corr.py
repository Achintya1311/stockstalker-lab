import numpy as np
import pandas as pd

from strategies import q02_return_volume_corr as q02
from strategies.q02_return_volume_corr_audit import check_cross_symbol_causality, confirmed
from tests.test_q01_price_volume_corr import _with_volume

N = q02.MIN_ROWS


def _alternating(up_first: bool, drift: float, volume_follows: bool):
    """Closes alternate +2% / -1% (or the mirror) around a drift; volume steps up on
    up days and down on down days when `volume_follows`, the reverse otherwise."""
    steps = np.array([0.02, -0.01] * N)[:N - 1] * (1 if up_first else -1) + drift
    closes = 100.0 * np.exp(np.r_[0.0, np.cumsum(steps)])
    vol_steps = np.where(steps > drift, 0.3, -0.3) * (1 if volume_follows else -1)
    volumes = 1e6 * np.exp(np.r_[0.0, np.cumsum(vol_steps)])
    return closes, volumes


def test_hand_computed_correlation():
    """x = close ratio and y = log(volume ratio + 1) are both two-valued and move together,
    so rho = +1 exactly; the move is up, so the score is +1."""
    closes, volumes = _alternating(True, 0.0, True)
    f = q02.compute_adjustment_factors(_with_volume("A", closes, volumes))
    rho, r20 = q02.parts(f)
    assert abs(rho - 1.0) < 1e-9
    assert abs(r20 - np.log(closes[-1] / closes[0])) < 1e-12 and r20 > 0
    assert abs(q02.score(_with_volume("A", closes, volumes))["A"] - 1.0) < 1e-9


def test_confirmed_fall_is_bearish_and_unconfirmed_rise_is_bearish():
    fall = _with_volume("F", *_alternating(False, 0.0, True))
    rise = _with_volume("R", *_alternating(True, 0.0, False))
    sc = q02.score(pd.concat([fall, rise]))
    assert abs(sc["F"] + 1.0) < 1e-9 and abs(sc["R"] + 1.0) < 1e-9


def test_flat_volume_or_no_move_abstains():
    t = np.arange(N, dtype=float)
    flat_volume = _with_volume("V", 100.0 + t, np.full(N, 1e6))
    flat_price = _with_volume("P", np.full(N, 100.0), 1e6 * np.exp(0.1 * t))
    assert q02.score(pd.concat([flat_volume, flat_price])).empty


def test_audit_fixtures_fire_on_both_sides():
    sc = q02.score(pd.concat([confirmed("UP", N + 5, 0.01, 1), confirmed("DOWN", N + 5, -0.01, 2)]))
    assert sc["DOWN"] < 0 < sc["UP"]


def test_short_history_abstains():
    closes, volumes = _alternating(True, 0.0, True)
    assert q02.score(_with_volume("A", closes[:-1], volumes[:-1])).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = _with_volume("F", *_alternating(True, 0.0, True))
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(q02.score(hist).index) == ["F"]


def test_rules_fired_wording():
    hist = _with_volume("A", *_alternating(True, 0.0, True))
    text = q02.rules_fired(hist, "A")
    assert "confirmed move, bullish" in text
    assert "abstain" in q02.rules_fired(hist, "NONE")
    for word in ("buy", "sell", "target", "stop"):
        assert word not in text.lower()


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
