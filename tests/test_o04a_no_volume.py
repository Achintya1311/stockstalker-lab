import pandas as pd

from strategies import o04_order_block_composite as o04
from strategies import o04a_no_volume as o04a
from strategies.o04a_no_volume_audit import check_cross_symbol_causality
from tests.test_o01_order_block import _bull_setup, _flat, _history
from tests.test_o04_order_block_composite import _AGREE_TAIL, _DISAGREE_TAIL, _with_oi, _with_volume


def _pair(vol_aaa: float, vol_bbb: float) -> pd.DataFrame:
    a = _with_volume(_with_oi(_history(_bull_setup(_AGREE_TAIL), "AAA"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=vol_aaa)
    b = _with_volume(_with_oi(_history(_bull_setup(_DISAGREE_TAIL), "BBB"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=vol_bbb)
    return pd.concat([a, b], ignore_index=True)


def test_volume_no_longer_moves_the_score():
    # Same zones and OI; only the volume reading differs. O04 moves, O04A must not.
    low_high, high_low = _pair(-20_000.0, 20_000.0), _pair(20_000.0, -20_000.0)
    assert not o04.score(low_high).equals(o04.score(high_low))
    pd.testing.assert_series_equal(o04a.score(low_high), o04a.score(high_low))


def test_is_o04s_rank_average_over_o01_and_d01_only():
    h = _pair(20_000.0, -20_000.0)
    ing = o04._ingredients(h)
    expected = ing["side"] * ing[["o01", "d01"]].rank(pct=True).mean(axis=1, skipna=True)
    pd.testing.assert_series_equal(o04a.score(h), expected)


def test_sign_matches_o01_side_and_abstains_with_o01():
    h = pd.concat([_pair(20_000.0, -20_000.0), _history(_flat(70), "CCC")], ignore_index=True)
    s = o04a.score(h)
    assert "CCC" not in s.index
    assert (s > 0).all() and s["AAA"] > s["BBB"]  # D01 agrees with AAA's side, not BBB's
    assert o04a.score(_history(_flat(70), "ZZZ")).empty


def test_rules_fired_wording():
    h = _pair(20_000.0, -20_000.0)
    text = o04a.rules_fired(h, "AAA")
    assert text.startswith("O04A (O04 without volume)") and "bullish" in text and "2/2" in text
    assert "no valid zone" in o04a.rules_fired(_history(_flat(70), "ZZZ"), "ZZZ")
    for word in ("buy", "sell", "target", "stop"):
        assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
