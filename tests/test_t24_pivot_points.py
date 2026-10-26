import numpy as np
import pandas as pd

from strategies import t24_pivot_points as t24
from strategies.t17_keltner_breakout_audit import frame
from strategies.t24_pivot_points_audit import check_cross_symbol_causality

N = t24.MIN_ROWS


def _with_last_two(prev_hlc, last_close, n=N):
    """`n` flat rows at 100, then the second-to-last bar set to `prev_hlc` and the
    last close to `last_close` (prevclose kept consistent, so no adjustment)."""
    f = frame("A", np.full(n, 100.0))
    h, l, c = prev_hlc
    f.loc[n - 2, ["high", "low", "close"]] = [h, l, c]
    f.loc[n - 1, ["prevclose", "close", "high", "low"]] = [c, last_close, max(c, last_close), min(c, last_close)]
    return f


def test_hand_computed_levels():
    """Previous bar H 110, L 90, C 106: P = 102, R1 = 114, S1 = 94; last close 108
    scores (108 - 102) / (114 - 94) = 0.3."""
    f = _with_last_two((110.0, 90.0, 106.0), 108.0)
    close, pivot, r1, s1 = t24.levels(t24.compute_adjustment_factors(f))
    assert (close, pivot, r1, s1) == (108.0, 102.0, 114.0, 94.0)
    assert abs(t24.score(f)["A"] - 0.3) < 1e-12


def test_below_pivot_is_bearish_and_breaks_rank_beyond_bounces():
    bounce = t24.score(_with_last_two((110.0, 90.0, 106.0), 96.0))["A"]   # between S1 94 and P 102
    breaks = t24.score(_with_last_two((110.0, 90.0, 106.0), 90.0))["A"]   # below S1
    assert breaks < -0.5 < bounce < 0


def test_no_range_abstains():
    assert t24.score(frame("FLAT", np.full(N, 100.0), spread=0.0)).empty


def test_split_between_the_two_bars_is_adjusted():
    """A 1:1 bonus on the last bar halves its prices and its PREVCLOSE; the
    adjusted previous bar is halved too, so the score equals the unsplit one."""
    plain = t24.score(_with_last_two((110.0, 90.0, 106.0), 108.0))["A"]
    f = _with_last_two((110.0, 90.0, 106.0), 108.0)
    f.loc[N - 1, ["prevclose", "close", "high", "low"]] = [53.0, 54.0, 54.0, 53.0]
    assert abs(t24.score(f)["A"] - plain) < 1e-9


def test_short_history_abstains():
    assert t24.score(_with_last_two((110.0, 90.0, 106.0), 108.0).iloc[1:]).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = _with_last_two((110.0, 90.0, 106.0), 108.0)
    g = f.assign(symbol="CASH")
    hist = pd.concat([f, g], ignore_index=True)
    hist["has_future"] = hist["symbol"] == "A"
    assert list(t24.score(hist).index) == ["A"]


def test_rules_fired_wording():
    hist = _with_last_two((110.0, 90.0, 106.0), 116.0)
    text = t24.rules_fired(hist, "A")
    assert "bullish" in text and "beyond R1" in text
    assert "abstain" in t24.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
