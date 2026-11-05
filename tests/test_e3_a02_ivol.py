import pandas as pd

from strategies import a02_extreme_day_reversal as a02
from strategies import e3a_a02_high_ivol as e3a
from strategies import e3b_a02_low_ivol as e3b
from strategies import h02_idiosyncratic_volatility as h02
from strategies.e3_a02_ivol_audit import check_cross_symbol_causality, fixture


def hist() -> pd.DataFrame:
    return fixture(45, 0)


def test_extreme_up_day_on_volatile_stock_is_kept_bearish_with_a02s_score():
    """AAA: quiet, then +8% (A02 fires bearish); the jump makes its stock-specific volatility
    above the median, so E3A keeps it with A02's own score and E3B drops it."""
    h = hist()
    assert h02.score(h)["AAA"] < 0
    assert e3a.score(h)["AAA"] == a02.score(h)["AAA"] < 0
    assert "AAA" not in e3b.score(h).index


def test_arms_partition_a02_by_the_ivol_median():
    h = hist()
    base, ivol = a02.score(h), h02.score(h)
    high, low = e3a.score(h), e3b.score(h)
    assert set(high.index).isdisjoint(low.index)
    assert set(high.index) == {s for s in base.index if s in ivol and ivol[s] < 0}
    assert set(low.index) == {s for s in base.index if s in ivol and ivol[s] > 0}
    assert len(low) >= 1  # the fixture has a calm stock with an A02 move (S4)
    for s in low.index:
        assert low[s] == base[s]


def test_no_a02_pick_abstains():
    h = hist()
    quiet = h[~h["symbol"].isin(["AAA", "CCC", "S0", "S4"])]
    assert e3a.score(quiet).empty and e3b.score(quiet).empty


def test_empty_history():
    assert e3a.score(pd.DataFrame()).empty


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired():
    h = hist()
    assert e3a.rules_fired(h, "AAA").startswith("E3A: A02 pick")
    assert e3b.rules_fired(h, "AAA").startswith("E3B: no A02 pick")
