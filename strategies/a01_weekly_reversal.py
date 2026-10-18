"""A01: short-term (weekly) reversal (`cards/A01.yml`, `state/queue.md` port lane).

Ported from Lehmann (1990, QJE) and Jegadeesh (1990, JF): rank stocks by
their trailing return over the last `LOOKBACK_DAYS` trading days
(approximating "last week"); the biggest losers are bullish for the coming
week, the biggest winners are bearish. Neither paper's own effect size is
assumed true here (SPEC.md section 5) - this module only computes the
signal; `cards/A01.yml`'s `status` moves to `confirmed`/`refuted` once a
real train replay's edge is in.

Score is continuous, not a decile rank: `score = -(trailing return)`, so a
deeper loss gives a larger bullish score and a bigger gain a larger
bearish score, the same "sign gives direction, magnitude gives conviction"
convention `strategies/champion_v1.py` already uses (SPEC.md section 5:
"one score per symbol; NaN means abstain" - the engine reads a pick's side
from the score's sign, `engine.scoring`).

Per SPEC.md section 2, the trailing return is computed on the adjusted
close series (`scripts.adjustments.compute_adjustment_factors`), so a
split or bonus inside the lookback window doesn't masquerade as a real
weekly move. `history` is whatever truncated slice `engine.replay` hands
this module (never the full dataset): for a week pick made at Monday's
open, the last row visible is the prior Friday's close, so `LOOKBACK_DAYS`
trading days back from there already is "last week" without this module
doing any date-of-week arithmetic itself.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

LOOKBACK_DAYS = 5

# One extra row beyond the lookback: a `LOOKBACK_DAYS`-day return needs the
# close `LOOKBACK_DAYS` rows back AND today's close, i.e. LOOKBACK_DAYS + 1
# observations.
MIN_ROWS = LOOKBACK_DAYS + 1


def _trailing_return(close: pd.Series) -> float:
    latest = close.iloc[-1]
    prior = close.iloc[-MIN_ROWS]
    if prior == 0:
        return 0.0
    return float((latest - prior) / prior)


def score(history: pd.DataFrame) -> pd.Series:
    """One reversal score per symbol with at least `MIN_ROWS` rows of history.

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
        trailing_return = _trailing_return(group["adj_close"])
        out[symbol] = -trailing_return
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "A01 weekly reversal: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    trailing_return = _trailing_return(adjusted["adj_close"])
    reversal_score = -trailing_return
    direction = "bullish" if reversal_score > 0 else "bearish" if reversal_score < 0 else "neutral"
    return (
        "A01 weekly reversal (Lehmann 1990 / Jegadeesh 1990): "
        f"trailing {LOOKBACK_DAYS}-day return {trailing_return:+.3%} -> "
        f"reversal score {reversal_score:+.4f} ({direction})"
    )
