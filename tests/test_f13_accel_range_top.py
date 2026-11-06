import numpy as np
import pandas as pd

from strategies import f13_accel_range_top as f13
from strategies.f13_accel_range_top_audit import check_cross_symbol_causality, surge, walk, with_turnover
from strategies.t17_keltner_breakout_audit import frame

N = f13.MIN_ROWS + 2


def shaped(symbol: str, tail_steps, last_turnover: float) -> pd.DataFrame:
    """Flat closes then the given log steps; flat turnover then `last_turnover` on the last row."""
    steps = np.r_[np.zeros(N - len(tail_steps)), tail_steps]
    turnover = np.r_[np.full(N - 1, 1e9), last_turnover]
    return with_turnover(frame(symbol, 100.0 * np.exp(np.cumsum(steps))), turnover)


def hist() -> pd.DataFrame:
    # A: 10-session high, accelerating (+1% then +3%), turnover surge -> highest in all three ranks.
    # B: 10-session low, decelerating (-1% then -3%), light turnover -> lowest in all three.
    # C: middle (flat, unchanged turnover).
    return pd.concat([shaped("A", [0.01, 0.03], 3e9), shaped("B", [-0.01, -0.03], 0.5e9),
                      shaped("C", [0.0, 0.0], 1e9)], ignore_index=True)


def test_parts_match_hand_values():
    a = shaped("A", [0.01, 0.03], 3e9).assign(adj_close=lambda d: d["close"])
    tsr, acc, vr = f13.parts(a)
    assert tsr == 1.0 and abs(acc - 0.02) < 1e-9 and vr == 1.0


def test_hand_computed_scores():
    """Ranks A 1, C 2/3, B 1/3 in all three: p = 1, 8/27, 1/27; median 8/27.
    A = 8/27 - 1 (bearish), B = 8/27 - 1/27 (bullish), C abstains."""
    sc = f13.score(hist())
    assert abs(sc["A"] - (8 / 27 - 1)) < 1e-9
    assert abs(sc["B"] - 7 / 27) < 1e-9
    assert "C" not in sc.index


def test_short_history_abstains():
    assert f13.score(shaped("A", [0.01, 0.03], 3e9).tail(f13.MIN_ROWS - 1)).empty


def test_needs_turnover():
    assert f13.score(hist().drop(columns="turnover")).empty


def test_symbols_without_a_future_on_the_last_date_leave_the_cross_section():
    h = pd.concat([hist(), walk("CASH", N, 1)], ignore_index=True)
    last = h["date"].max()
    h.loc[(h["symbol"] == "CASH") & (h["date"] == last), "has_future"] = False
    sc = f13.score(h)
    assert "CASH" not in sc.index
    pd.testing.assert_series_equal(sc, f13.score(hist().assign(has_future=True)))


def test_stale_symbol_with_no_last_row_is_dropped():
    stale = walk("OLD", N, 2).iloc[:-1]
    h = pd.concat([hist().assign(has_future=True), stale], ignore_index=True)
    assert "OLD" not in f13.score(h).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_audit_fixture_is_extreme():
    assert f13.score(pd.concat([walk("S0", N, 3), walk("S1", N, 4), surge(N, 0.4)], ignore_index=True))["BBB"] < 0


def test_rules_fired_names_the_side():
    assert f13.rules_fired(hist(), "A").endswith("bearish")
    assert f13.rules_fired(hist(), "B").endswith("bullish")
    assert "abstain" in f13.rules_fired(hist(), "C")
