"""A05B: MAX effect, cross-sectionally ranked (`cards/A05B.yml`, `state/queue.md` port lane).

A new version of `strategies/a05_max_effect.py`, not an edit of it (versions
are immutable). A05 v1 scored `-z` with `z = MAX / sigma`, which rescales MAX
but never centres it: MAX is the largest of 21 daily returns, so `z` is almost
always positive and the v1 score was positive on only 12 of 61,270 scored
symbol-dates in its train replay. Its bullish tables never picked a stock
(`research/diagnostics/a05.md`).

This card keeps v1's per-symbol reading unchanged (imported, not copied:
`a05_max_effect._max_over_sigma` on the same adjusted closes, same
`MAX_WINDOW`/`SIGMA_WINDOW`) and centres it the way Bali, Cakici and
Whitelaw (2011) do: cross-sectionally. On each call (one pick date), every
symbol with a v1 reading is ranked by `z` (average ranks for ties) and turned
into a mid-rank percentile `pct = (rank - 0.5) / n`, and `score = 1 - 2 * pct`.
The mid-rank form keeps the two sides symmetric: with `n` stocks the scores run
from `+(1 - 1/n)` (least lottery-like, bullish) to `-(1 - 1/n)` (most
lottery-like, bearish), and the median stock of an odd-sized field scores
exactly 0. A plain `rank(pct=True)` would put the median at `-1/n` and tilt
every field bearish. A score of exactly 0 abstains, the same rule every other
card uses for "no direction", so a lone stock with no peers abstains too.

Unlike v1, this score depends on which other symbols are present that date.
That is the point of a cross-sectional sort, not a leak. The causality audit
(`strategies/a05b_max_effect_ranked_audit.py`) checks the narrower property
that still must hold: each symbol's own pre-rank `z` depends only on its own
history, the same shape as `strategies/o04_order_block_composite_audit.py`.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import a05_max_effect

MAX_WINDOW = a05_max_effect.MAX_WINDOW
SIGMA_WINDOW = a05_max_effect.SIGMA_WINDOW
MIN_ROWS = a05_max_effect.MIN_ROWS


def _z_by_symbol(history: pd.DataFrame) -> pd.Series:
    """v1's own per-symbol `z = MAX / sigma`, before any ranking.

    Symbols with too little history or a zero baseline sigma are left out,
    exactly as in v1, so they neither get a score nor count as peers in the rank.
    """
    if history.empty:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        # Same performance prefilter as v1 (see `strategies/a05_max_effect.py`).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        group = group.sort_values("date")
        z = a05_max_effect._max_over_sigma(group["adj_close"])
        if z is None or pd.isna(z):
            continue
        out[symbol] = z
    return pd.Series(out, dtype=float)


def _mid_rank_pct(z: pd.Series) -> pd.Series:
    """`(rank - 0.5) / n` with average ranks for ties: symmetric around 0.5.

    `z` is rounded to 10 decimals before ranking so two readings that differ
    only by floating-point noise count as a tie rather than as two ranks.
    """
    return (z.round(10).rank(method="average") - 0.5) / len(z)


def _rank_scores(z: pd.Series) -> pd.Series:
    """`1 - 2 * pct` across the symbols scored this date; exact zeros abstain."""
    if z.empty:
        return pd.Series(dtype=float)
    scores = 1.0 - 2.0 * _mid_rank_pct(z)
    return scores[scores != 0].astype(float)


def score(history: pd.DataFrame) -> pd.Series:
    """One cross-sectionally ranked MAX score per symbol with a v1 reading."""
    return _rank_scores(_z_by_symbol(history))


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    z = _z_by_symbol(history)
    if symbol not in z.index:
        return "A05B MAX effect (ranked): no MAX/sigma reading (insufficient history or zero baseline volatility), abstain"

    scores = _rank_scores(z)
    pct = float(_mid_rank_pct(z)[symbol])
    if symbol not in scores.index:
        return (
            f"A05B MAX effect (ranked): best day in the trailing {MAX_WINDOW} days is {z[symbol]:+.2f} sigma, "
            f"exactly the median of {len(z)} stocks this session, abstain"
        )
    value = float(scores[symbol])
    direction = "bullish" if value > 0 else "bearish"
    return (
        "A05B MAX effect, cross-sectionally ranked (Bali, Cakici and Whitelaw 2011): "
        f"best day in the trailing {MAX_WINDOW} days is {z[symbol]:+.2f} sigma above the prior "
        f"{SIGMA_WINDOW}-day baseline, percentile {pct:.0%} of {len(z)} stocks this session "
        f"-> score {value:+.4f} ({direction})"
    )
