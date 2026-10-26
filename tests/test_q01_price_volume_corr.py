import numpy as np
import pandas as pd

from strategies import q01_price_volume_corr as q01
from strategies.q01_price_volume_corr_audit import check_cross_symbol_causality, thinning
from strategies.t17_keltner_breakout_audit import frame

N = q01.MIN_ROWS


def _with_volume(symbol, closes, volumes):
    f = frame(symbol, closes)
    f["volume"] = np.asarray(volumes, dtype=float)
    return f


def test_hand_computed_correlation_and_sign():
    """Closes rise linearly while log volume falls linearly: rho = -1 exactly, so a
    rise on thinning volume scores -1 (bearish)."""
    t = np.arange(N, dtype=float)
    f = _with_volume("A", 100.0 + t, np.exp(10.0 - 0.1 * t) - 1.0)
    rho, r20 = q01.parts(q01.compute_adjustment_factors(f))
    assert abs(rho + 1.0) < 1e-9 and abs(r20 - np.log(120.0 / 100.0)) < 1e-12
    assert abs(q01.score(f)["A"] + 1.0) < 1e-9


def test_fall_on_thinning_volume_is_bullish():
    """Close and log volume both fall linearly: rho = +1 against a negative move, so
    it scores +1 (bullish)."""
    t = np.arange(N, dtype=float)
    assert abs(q01.score(_with_volume("A", 120.0 - t, np.exp(10.0 - 0.1 * t) - 1.0))["A"] - 1.0) < 1e-9


def test_volume_confirming_the_move_abstains():
    t = np.arange(N, dtype=float)
    up_heavy = _with_volume("U", 100.0 + t, np.exp(10.0 + 0.1 * t))
    down_heavy = _with_volume("D", 120.0 - t, np.exp(10.0 + 0.1 * t))
    assert q01.score(pd.concat([up_heavy, down_heavy])).empty


def test_audit_fixtures_fire_on_both_sides():
    sc = q01.score(pd.concat([thinning("UP", N + 5, 0.01, 1), thinning("DOWN", N + 5, -0.01, 2)]))
    assert sc["UP"] < 0 < sc["DOWN"]


def test_short_history_abstains():
    t = np.arange(N - 1, dtype=float)
    assert q01.score(_with_volume("A", 100.0 + t, np.exp(10.0 - 0.1 * t))).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    t = np.arange(N, dtype=float)
    f = _with_volume("F", 100.0 + t, np.exp(10.0 - 0.1 * t))
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(q01.score(hist).index) == ["F"]


def test_rules_fired_wording():
    t = np.arange(N, dtype=float)
    hist = _with_volume("A", 100.0 + t, np.exp(10.0 - 0.1 * t))
    assert "bearish" in q01.rules_fired(hist, "A")
    assert "abstain" in q01.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
