import pandas as pd

from strategies import a07_high_volume_premium as a07
from strategies import o04_order_block_composite as o04
from tests.test_o01_order_block import _bull_setup, _flat, _history

# Bullish-zone retest tails (same zone/impulse `_bull_setup` already builds and O01's own tests
# already prove retest at ~100.0-101.0 scores near-full proximity): one ends on an UP bar (last
# session's own price move agrees with the bullish zone's side, so D01 reads "long build-up" when
# OI is also up), the other ends on a DOWN bar (`_DISAGREE_TAIL` is the exact fixture
# `tests/test_o01_order_block.py::test_retest_scores_bullish_and_far_price_abstains` already uses
# as its "near" case, so it is already proven to make O01 fire with score > 0.5).
_AGREE_TAIL = [(105.0, 99.5), (99.5, 100.0)]
_DISAGREE_TAIL = [(105.0, 104.0), (104.0, 101.0)]


def _with_oi(h: pd.DataFrame, oi_chg: float, oi_level: float = 10_000.0) -> pd.DataFrame:
    """D01 (`strategies/d01_oi_buildup.py`) only ever reads a symbol's own LAST visible row, so only
    that row's `oi_futstk`/`oi_chg_futstk` matter; earlier rows are set the same way for a tidy frame."""
    h = h.copy()
    h["oi_futstk"] = oi_level
    h["oi_chg_futstk"] = 0.0
    h.iloc[-1, h.columns.get_loc("oi_chg_futstk")] = oi_chg
    return h


def _with_volume(h: pd.DataFrame, baseline_step: float, recent_shift: float, base_volume: float = 1_000_000.0) -> pd.DataFrame:
    """Overwrites the trailing `BASELINE_WINDOW + RECENT_WINDOW` rows' volume so A07's own z-score
    comes out to exactly `recent_shift / baseline_step` on this slice - the same construction
    `tests/test_a07_high_volume_premium.py` uses for its own fixtures."""
    h = h.copy()
    n = a07.BASELINE_WINDOW + a07.RECENT_WINDOW
    assert len(h) >= n
    baseline = [base_volume + (baseline_step if i % 2 == 0 else -baseline_step) for i in range(a07.BASELINE_WINDOW)]
    recent = [base_volume + recent_shift] * a07.RECENT_WINDOW
    h.iloc[-n:, h.columns.get_loc("volume")] = baseline + recent
    return h


def test_abstains_when_o01_itself_abstains():
    h = _history(_flat(70), "AAA")  # no impulse anywhere, so O01 never finds a zone
    assert o04.score(h).empty


def test_sign_always_matches_o01_side_even_when_other_ingredients_disagree():
    # AAA: bullish zone, OI and volume both agree with it. BBB: bullish zone, OI and volume both
    # disagree with it (oi up but the last bar's own price move is down, and recent volume is
    # unusually LOW rather than high). BBB's score must still come out positive (O01's own side),
    # just lower than AAA's.
    agree = _with_volume(_with_oi(_history(_bull_setup(_AGREE_TAIL), "AAA"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=20_000.0)
    disagree = _with_volume(_with_oi(_history(_bull_setup(_DISAGREE_TAIL), "BBB"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=-20_000.0)
    s = o04.score(pd.concat([agree, disagree], ignore_index=True))
    assert s["AAA"] > 0 and s["BBB"] > 0
    assert s["AAA"] > s["BBB"]


def test_full_agreement_ranks_above_partial_agreement():
    # Same OI build-up magnitude and same volume reading for both; only the last bar's own price
    # direction differs, which is what flips D01's sign relative to O01's (bullish) side. Isolates
    # the D01 ingredient's contribution to the composite rank.
    agree = _with_volume(_with_oi(_history(_bull_setup(_AGREE_TAIL), "AAA"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=20_000.0)
    disagree = _with_volume(_with_oi(_history(_bull_setup(_DISAGREE_TAIL), "BBB"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=20_000.0)
    s = o04.score(pd.concat([agree, disagree], ignore_index=True))
    assert s["AAA"] > s["BBB"] > 0


def test_falls_back_to_o01_rank_alone_when_d01_and_volume_both_abstain():
    # Plain `_history()` fixtures carry no OI columns (D01 abstains for every row) and a constant
    # volume (A07's baseline std is 0, so it abstains too) - the composite must still rank purely
    # on O01's own proximity, not crash or silently return NaN.
    deep = _history(_bull_setup([(105.0, 99.5), (99.5, 100.0)]), "AAA")   # retest inside the zone
    edge = _history(_bull_setup([(105.0, 101.1)] * 3), "BBB")             # just inside, near the far edge
    s = o04.score(pd.concat([deep, edge], ignore_index=True))
    assert not s.isna().any()
    assert s["AAA"] > 0 and s["BBB"] > 0
    assert s["AAA"] >= s["BBB"]


def test_symbols_not_in_an_order_block_never_appear():
    ob = _history(_bull_setup(_AGREE_TAIL), "AAA")
    none = _history(_flat(70), "BBB")
    s = o04.score(pd.concat([ob, none], ignore_index=True))
    assert "AAA" in s.index and "BBB" not in s.index


def test_rank_is_universe_dependent_by_design():
    # Not a bug: a rank-average composite's whole point is comparing a symbol against its peers, so
    # the SAME symbol's score can differ depending on who else is in the universe that day. Contrast
    # with O01/O02/O03's own tests, which assert the opposite for their (non-ranking) formulas.
    agree = _with_volume(_with_oi(_history(_bull_setup(_AGREE_TAIL), "AAA"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=20_000.0)
    weaker_peer = _with_volume(_with_oi(_history(_bull_setup(_DISAGREE_TAIL), "BBB"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=20_000.0)
    stronger_peer = _with_volume(_with_oi(_history(_bull_setup(_AGREE_TAIL), "CCC"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=20_000.0)

    with_weaker_peer = o04.score(pd.concat([agree, weaker_peer], ignore_index=True))["AAA"]
    with_stronger_peer = o04.score(pd.concat([agree, stronger_peer], ignore_index=True))["AAA"]
    assert with_weaker_peer != with_stronger_peer


def test_rules_fired_wording():
    agree = _with_volume(_with_oi(_history(_bull_setup(_AGREE_TAIL), "AAA"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=20_000.0)
    disagree = _with_volume(_with_oi(_history(_bull_setup(_DISAGREE_TAIL), "BBB"), oi_chg=500.0), baseline_step=20_000.0, recent_shift=20_000.0)
    both = pd.concat([agree, disagree], ignore_index=True)

    reasoning = o04.rules_fired(both, "AAA")
    assert "O04:" in reasoning and "bullish" in reasoning and "conviction rank" in reasoning and "3/3" in reasoning

    no_zone = _history(_flat(70), "ZZZ")
    assert "no valid zone" in o04.rules_fired(no_zone, "ZZZ")


def test_rules_fired_reports_partial_ingredients():
    plain = _history(_bull_setup(_AGREE_TAIL), "AAA")  # no OI columns, constant volume -> D01 and A07 both abstain
    reasoning = o04.rules_fired(plain, "AAA")
    assert "1/3" in reasoning


def test_causality_audit_passes():
    from strategies.o04_order_block_composite_audit import check_cross_symbol_causality

    assert check_cross_symbol_causality()["passed"]
