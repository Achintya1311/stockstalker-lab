import numpy as np
import pandas as pd

from strategies import q01_price_volume_corr as q01
from strategies import q01c_thin_volume_fall as q01c
from strategies.q01c_thin_volume_fall_audit import check_cross_symbol_causality
from strategies.q01_price_volume_corr_audit import thinning
from tests.test_q01_price_volume_corr import _with_volume

N = q01.MIN_ROWS
T = np.arange(N, dtype=float)
FALL_THIN = (120.0 - T, np.exp(10.0 - 0.1 * T) - 1.0)   # Q01 scores +1 (bullish) exactly
RISE_THIN = (100.0 + T, np.exp(10.0 - 0.1 * T) - 1.0)   # Q01 scores -1 (bearish) exactly


def test_fall_on_thinning_volume_scores_bearish_with_q01_magnitude():
    f = _with_volume("A", *FALL_THIN)
    assert abs(q01.score(f)["A"] - 1.0) < 1e-9
    assert abs(q01c.score(f)["A"] + 1.0) < 1e-9


def test_rise_on_thinning_volume_abstains():
    f = _with_volume("A", *RISE_THIN)
    assert q01.score(f)["A"] < 0
    assert q01c.score(f).empty


def test_never_bullish_and_matches_q01_falls_only():
    hist = pd.concat([
        _with_volume("AAA", *FALL_THIN),
        _with_volume("BBB", *RISE_THIN),
        _with_volume("CCC", 120.0 - T, np.exp(10.0 + 0.1 * T)),  # volume confirms the fall: Q01 abstains
        _with_volume("DDD", *(x[: N - 1] for x in FALL_THIN)),   # too short
        thinning("EEE", N + 5, -0.01, 2),
    ], ignore_index=True)
    base, flipped = q01.score(hist), q01c.score(hist)
    assert sorted(flipped.index) == ["AAA", "EEE"]
    assert (flipped < 0).all()
    pd.testing.assert_series_equal(flipped, -base[base > 0])


def test_empty_history():
    assert q01c.score(pd.DataFrame()).empty


def test_rules_fired_wording():
    fall = q01c.rules_fired(_with_volume("A", *FALL_THIN), "A")
    rise = q01c.rules_fired(_with_volume("A", *RISE_THIN), "A")
    short = q01c.rules_fired(_with_volume("A", *FALL_THIN), "NONE")
    assert fall.startswith("Q01C thin-volume fall") and "bearish" in fall
    assert rise.startswith("Q01C thin-volume fall") and rise.endswith("abstain")
    assert short.endswith("abstain")
    for text in (fall, rise, short):
        for word in ("buy", "sell", "target", "stop"):
            assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
