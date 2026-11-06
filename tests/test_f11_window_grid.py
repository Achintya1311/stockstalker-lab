import importlib

import numpy as np
import pandas as pd
import pytest

from strategies import f11_range_top_fade as f11
from strategies import f11_window_grid as grid
from strategies.f11_range_top_fade_audit import walk


def hist(n=40) -> pd.DataFrame:
    h = pd.concat([walk(f"S{i}", n, i) for i in range(8)], ignore_index=True)
    h["has_future"] = h["symbol"] != "S7"
    return h


def test_window_10_reproduces_f11_exactly():
    h = hist()
    pd.testing.assert_series_equal(grid.scorer(10)(h).sort_index(), f11.score(h).sort_index())


@pytest.mark.parametrize("w", [6, 8, 12, 15])
def test_grid_modules_expose_the_interface(w):
    m = importlib.import_module(f"strategies.f11_w{w:02d}")
    assert m.WINDOW == w
    sc = m.score(hist())
    assert len(sc) > 0 and "S7" not in sc.index
    s = sc.index[0]
    assert m.rules_fired(hist(), s).endswith("bullish" if sc[s] > 0 else "bearish")


def test_window_changes_the_reading():
    h = hist()
    assert not grid.scorer(6)(h).sort_index().equals(grid.scorer(15)(h).sort_index())


def test_short_history_abstains_per_window():
    h = hist(n=11)
    assert grid.scorer(12)(h).empty and not grid.scorer(10)(h).empty


def test_causality_window_6():
    """BBB at a range top on the biggest up bar in two versions of its last session (same place in both
    ranks): every other stock's score is unchanged (as `strategies/f11_range_top_fade_audit.py`)."""
    from strategies.t17_keltner_breakout_audit import frame
    others = [walk(f"S{i}", 30, 40 + i) for i in range(5)]
    base = np.full(28, 100.0)
    s1 = grid.scorer(6)(pd.concat(others + [frame("BBB", np.r_[base, 120.0, 144.0])], ignore_index=True))
    s2 = grid.scorer(6)(pd.concat(others + [frame("BBB", np.r_[base, 120.0, 180.0])], ignore_index=True))
    fired = [s for s in s1.index if s != "BBB"]
    assert fired
    for s in fired:
        assert abs(s1[s] - s2[s]) < 1e-12
