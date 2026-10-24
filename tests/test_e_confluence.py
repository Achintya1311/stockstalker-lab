import pandas as pd
import pytest

from strategies import d01_oi_buildup, d01c_oi_fade, e1_a02_ob_confluence as e1, e1a_a02_with_ob, e1b_a02_without_ob
from strategies import e2a_a02_crowded, e2b_a02_uncrowded
from strategies.a02_extreme_day_reversal_audit import _window_then_move


def _bearish_a02(oi_last=None, symbol="AAA"):
    h = _window_then_move(symbol, 10, 0.01, 0.05)       # extreme UP day, so A02 is bearish (score about -5)
    if oi_last is not None:
        h["oi_chg_futstk"] = 0.0
        h.loc[h.index[-1], "oi_chg_futstk"] = oi_last
    return h


def test_e2_splits_a02_by_whether_oi_rose_on_the_extreme_day():
    crowded, closing = _bearish_a02(500.0), _bearish_a02(-500.0)
    assert e2a_a02_crowded.score(crowded)["AAA"] == pytest.approx(-5.0) and e2b_a02_uncrowded.score(crowded).empty
    assert e2b_a02_uncrowded.score(closing)["AAA"] == pytest.approx(-5.0) and e2a_a02_crowded.score(closing).empty


def test_e2_abstains_when_oi_is_missing_rather_than_guessing():
    h = _bearish_a02()
    assert e2a_a02_crowded.score(h).empty and e2b_a02_uncrowded.score(h).empty


def test_e1_keeps_a02_only_where_the_zone_agrees_and_the_two_arms_never_overlap(monkeypatch):
    h = _bearish_a02()
    for ob_score, with_n, without_n in ((-1.0, 1, 0), (+1.0, 0, 1), (None, 0, 1)):
        ob = pd.Series({} if ob_score is None else {"AAA": ob_score}, dtype=float)
        monkeypatch.setattr(e1.o01_order_block_retest, "score", lambda hist, ob=ob: ob)
        assert len(e1a_a02_with_ob.score(h)) == with_n and len(e1b_a02_without_ob.score(h)) == without_n


def test_d01c_is_exactly_minus_d01_with_the_same_abstentions():
    rows = [{"date": "2015-01-05", "symbol": s, "open": 100.0, "high": 101.0, "low": 99.0, "close": c, "prevclose": 100.0,
             "volume": 1e6, "has_future": True, "oi_futstk": 10_000.0, "oi_chg_futstk": chg}
            for s, c, chg in (("UP", 101.0, 500.0), ("DN", 98.0, 500.0), ("FLAT", 100.0, 500.0))]
    h = pd.DataFrame(rows)
    base, fade = d01_oi_buildup.score(h), d01c_oi_fade.score(h)
    assert list(fade.index) == list(base.index) and "FLAT" not in fade.index
    assert (fade == -base).all() and fade["UP"] < 0 < fade["DN"]


def test_confluence_never_reads_a_symbol_it_was_not_given():
    a, b = _bearish_a02(500.0, "AAA"), _bearish_a02(-500.0, "BBB")
    both = pd.concat([a, b], ignore_index=True)
    assert e2a_a02_crowded.score(both).index.tolist() == ["AAA"] and e2b_a02_uncrowded.score(both).index.tolist() == ["BBB"]
