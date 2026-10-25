import pandas as pd

from strategies import o04_order_block_composite as o04
from strategies import o04b_no_d01 as o04b
from strategies.o04b_no_d01_audit import check_cross_symbol_causality
from tests.test_o01_order_block import _bull_setup, _flat, _history
from tests.test_o04_order_block_composite import _AGREE_TAIL, _DISAGREE_TAIL, _with_oi, _with_volume


def _pair(oi_aaa: float, oi_bbb: float, vol_aaa: float = 20_000.0, vol_bbb: float = -20_000.0) -> pd.DataFrame:
    a = _with_volume(_with_oi(_history(_bull_setup(_AGREE_TAIL), "AAA"), oi_chg=oi_aaa), baseline_step=20_000.0, recent_shift=vol_aaa)
    b = _with_volume(_with_oi(_history(_bull_setup(_DISAGREE_TAIL), "BBB"), oi_chg=oi_bbb), baseline_step=20_000.0, recent_shift=vol_bbb)
    return pd.concat([a, b], ignore_index=True)


def test_oi_no_longer_moves_the_score():
    # Same zones and volume; with the OI columns removed D01 abstains everywhere. O04 moves, O04B must not.
    with_oi = _pair(500.0, 500.0)
    without_oi = with_oi.drop(columns=["oi_futstk", "oi_chg_futstk"])
    assert not o04.score(with_oi).equals(o04.score(without_oi))
    pd.testing.assert_series_equal(o04b.score(with_oi), o04b.score(without_oi))


def test_is_o04s_rank_average_over_o01_and_volume_only():
    h = _pair(500.0, 500.0)
    ing = o04._ingredients(h)
    expected = ing["side"] * ing[["o01", "vol"]].rank(pct=True).mean(axis=1, skipna=True)
    pd.testing.assert_series_equal(o04b.score(h), expected)


def test_sign_matches_o01_side_and_abstains_with_o01():
    h = pd.concat([_pair(500.0, 500.0, vol_aaa=-20_000.0, vol_bbb=20_000.0), _history(_flat(70), "CCC")], ignore_index=True)
    s = o04b.score(h)
    assert "CCC" not in s.index
    assert (s > 0).all()
    assert o04b.score(_history(_flat(70), "ZZZ")).empty


def test_rules_fired_wording():
    h = _pair(500.0, 500.0)
    text = o04b.rules_fired(h, "AAA")
    assert text.startswith("O04B (O04 without OI)") and "bullish" in text and "2/2" in text
    assert "no valid zone" in o04b.rules_fired(_history(_flat(70), "ZZZ"), "ZZZ")
    for word in ("buy", "sell", "target", "stop"):
        assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
