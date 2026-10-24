"""O04: order-block composite / "conviction" guess (`cards/O04.yml`, `docs/orderblock_hypotheses.md`).

Rank-average across the universe of O01 proximity, D01 OI build-up, and A07's volume z-score,
signed by O01's own side - the lab's best guess at the vendor's unpublished "conviction score
(0-100, five dots)" sitting beside every order-block tile (docs/orderblock_hypotheses.md), with
the side coming from the order block (O01) and the magnitude from how this symbol's OI and
volume reading rank against every OTHER symbol O01 also read a side for, that same session.

Formula (`cards/catalog.csv`'s own `default_params`: "equal weights; abstain when O01 abstains"):
  side         = sign(O01 score)            +1 bullish zone, -1 bearish zone (0 already excluded
                                              by O01's own abstain rule, so side is never 0)
  aligned_o01  = |O01 score|                 (= side * O01 score, by construction)
  aligned_d01  = side * D01 score            positive when OI agrees with this symbol's own side
  aligned_vol  = side * A07 volume-z score   positive when A07's own direction agrees with this side
  rank_x       = cross-sectional percentile rank of aligned_x (pandas `.rank(pct=True)`), taken only
                 among the symbols O01 did not abstain on this session - ranking a symbol against
                 names with no order block at all would compare unlike things
  composite    = row-wise mean of whichever of {rank_o01, rank_d01, rank_vol} are defined (D01 and
                 A07 can each abstain independently of O01 - SPEC.md section 5's own abstain
                 convention - so a missing ingredient is left out of the average, not forced to a
                 neutral default; rank_o01 is always defined for every row in this group, so
                 `composite` itself is never undefined)
  score        = side * composite           always signed by O01's own side ("signed by the O01
                 side" per the catalog): a symbol whose other ingredients disagree gets a smaller
                 magnitude, never a flipped sign - the vendor's screenshots show side and conviction
                 as two separate fields (a zone side plus a 0-100 dial), not one blended number

Imports `o01_order_block_retest`, `d01_oi_buildup` and `a07_high_volume_premium` as libraries (not
copied), the same convention O02/O03 already use for D01/T01: this card's whole point is testing
the vendor's composite guess against the bare retest it is built from, so it must stay bit-for-bit
consistent with those three already-scored strategies.

Unlike every other O-series card, this one's final score for a symbol is NOT invariant to which
other symbols are in the universe that day - ranking is the entire point of a rank-average, so
adding or removing a peer symbol can and should shift a rank; that is by design, not a bug (see
`o04_order_block_composite_audit.py`'s docstring for the narrower causality property that does
still have to hold).
"""

from __future__ import annotations

import pandas as pd

from strategies import a07_high_volume_premium, d01_oi_buildup, o01_order_block_retest

INGREDIENTS = ["o01", "d01", "vol"]


def _ingredients(history: pd.DataFrame) -> pd.DataFrame:
    """One row per symbol O01 did not abstain on: `side` (+1.0/-1.0) and the side-aligned `o01`,
    `d01`, `vol` readings (NaN where that ingredient itself abstains)."""
    o01_scores = o01_order_block_retest.score(history)
    if o01_scores.empty:
        return pd.DataFrame(columns=["side", *INGREDIENTS])

    side = o01_scores.apply(lambda v: 1.0 if v > 0 else -1.0)
    d01_scores = d01_oi_buildup.score(history).reindex(side.index)
    vol_scores = a07_high_volume_premium.score(history).reindex(side.index)

    return pd.DataFrame(
        {
            "side": side,
            "o01": o01_scores.abs(),
            "d01": side * d01_scores,
            "vol": side * vol_scores,
        }
    )


def _composite(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Returns (`ingredients`, `avg_rank`) so both `score` and `rules_fired` share one computation."""
    ing = _ingredients(history)
    if ing.empty:
        return ing, pd.Series(dtype=float)
    ranks = ing[INGREDIENTS].rank(pct=True)
    avg_rank = ranks.mean(axis=1, skipna=True)
    return ing, avg_rank


def score(history: pd.DataFrame) -> pd.Series:
    ing, avg_rank = _composite(history)
    if ing.empty:
        return pd.Series(dtype=float)
    return ing["side"] * avg_rank


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    ing, avg_rank = _composite(history)
    if ing.empty or symbol not in ing.index:
        return "O04: O01 has no valid zone at price, abstain"

    row = ing.loc[symbol]
    side = "bullish" if row["side"] > 0 else "bearish"
    have = [name for name in INGREDIENTS if pd.notna(row[name])]
    final = row["side"] * avg_rank.loc[symbol]
    return (
        f"O04: {side} order block, composite conviction rank {avg_rank.loc[symbol]:.2f} "
        f"from {len(have)}/3 ingredients ({'+'.join(have)}) against {len(ing)} order-block picks "
        f"today -> score {final:+.3f}"
    )
