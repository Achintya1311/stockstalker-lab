"""A03: price momentum 12-1 (`cards/A03.yml`, `state/queue.md` port lane).

Ported from Jegadeesh and Titman (1993, JF): rank stocks by their trailing
return over the last `LOOKBACK_DAYS` trading days (approximating 12
months), ending `SKIP_DAYS` trading days before the pick date
(approximating the most recent month, skipped per the paper so a very
short-term reversal effect, A01's own territory, doesn't contaminate the
momentum read). The biggest past winners are bullish for the coming week,
the biggest past losers are bearish - the opposite sign convention from
A01's short-term reversal. Neither the paper's own effect size nor its
3-12 month horizon is assumed to transfer to a one-week NSE pick (SPEC.md
section 5) - this module only computes the signal; `cards/A03.yml`'s
`status` moves to `confirmed`/`refuted` once a real train replay's edge is
in.

Score is continuous, not a decile rank: `score = +(12-1 trailing return)`,
so a bigger past gain gives a larger bullish score and a bigger past loss
a larger bearish score, the same "sign gives direction, magnitude gives
conviction" convention `strategies/a01_weekly_reversal.py` and
`strategies/champion_v1.py` already use (SPEC.md section 5: "one score per
symbol; NaN means abstain").

Per SPEC.md section 2, the trailing return is computed on the adjusted
close series (`scripts.adjustments.compute_adjustment_factors`), so a
split or bonus inside the window doesn't masquerade as a real 12-1 move.
`history` is whatever truncated slice `engine.replay` hands this module
(never the full dataset): for a week pick made at Monday's open, the last
row visible is the prior Friday's close, so "skip the most recent month"
and "the 12 months before that" are both already in the past without this
module doing any date arithmetic itself.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

LOOKBACK_DAYS = 252
SKIP_DAYS = 21

# Closes needed: the formation-period return needs the close `SKIP_DAYS +
# LOOKBACK_DAYS` rows back and the close `SKIP_DAYS` rows back, i.e.
# SKIP_DAYS + LOOKBACK_DAYS + 1 observations (the "+1" is the earlier of the
# two anchor closes itself).
MIN_ROWS = SKIP_DAYS + LOOKBACK_DAYS + 1


def _formation_return(close: pd.Series) -> float:
    recent_anchor = close.iloc[-(SKIP_DAYS + 1)]
    distant_anchor = close.iloc[-MIN_ROWS]
    if distant_anchor == 0:
        return 0.0
    return float((recent_anchor - distant_anchor) / distant_anchor)


def score(history: pd.DataFrame) -> pd.Series:
    """One momentum score per symbol with at least `MIN_ROWS` rows of history.

    A symbol with too little history, or a zero-priced anchor row, abstains
    (left out of the returned Series) rather than falling back to a
    default score that would masquerade as a real reading.
    """
    if history.empty:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/champion_v1.py`'s identical prefilter for why: a
        # symbol with no F&O future anywhere in its visible history can
        # never survive the downstream universe restriction regardless of
        # what it scores here, and skipping it here avoids recomputing
        # adjustment factors over the full EQ series on every pick date).
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
        formation_return = _formation_return(group["adj_close"])
        out[symbol] = formation_return
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "A03 momentum 12-1: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    formation_return = _formation_return(adjusted["adj_close"])
    direction = "bullish" if formation_return > 0 else "bearish" if formation_return < 0 else "neutral"
    return (
        "A03 momentum 12-1 (Jegadeesh and Titman 1993): "
        f"trailing {LOOKBACK_DAYS}-day return skipping the last {SKIP_DAYS} days "
        f"{formation_return:+.3%} -> momentum score {formation_return:+.4f} ({direction})"
    )
