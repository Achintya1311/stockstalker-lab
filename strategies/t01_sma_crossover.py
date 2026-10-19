"""T01: SMA crossover 20/50 (`cards/T01.yml`, `state/queue.md` port lane).

Classic trend rule, isolated from `strategies/champion_v1.py`'s own trend
component (`cards/catalog.csv`'s own description: "StockStalker's current
trend signal"): the fast (20-day) simple moving average above the slow
(50-day) one is bullish, below is bearish. Score is continuous, not a bare
sign: `score = (fast_sma - slow_sma) / abs(slow_sma)`, the same spread
champion v1's trend component computes before that module clips and scales
it for blending - here left unscaled, since this card is tested standalone,
not blended (SPEC.md section 5: "one score per symbol; NaN means abstain";
sign gives direction, magnitude gives conviction, same convention
`strategies/a01_weekly_reversal.py` and `strategies/champion_v1.py` already
use).

Unlike the calendar-effect cards (C01-C04), this rule needs no pick-date
knowledge at all - both SMAs are computed purely from past adjusted closes
already inside whatever truncated `history` slice `engine.replay` hands this
module, so one module serves both horizons (SPEC.md section 4's walk-forward
truncation already enforces that a week pick's `history` ends at the prior
Friday's close and a day pick's ends at yesterday's close; this module reads
whichever last row it is given either way), the same way
`strategies/champion_v1.py` serves both without a day/week split.

Per SPEC.md section 2, both SMAs run on the adjusted close series
(`scripts.adjustments.compute_adjustment_factors`), so a split or bonus
inside either window doesn't masquerade as a real trend move.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

FAST, SLOW = 20, 50

# The slow SMA needs SLOW rows to produce its first non-NaN value; the fast
# SMA's shorter window is already satisfied once the slow one is.
MIN_ROWS = SLOW


def _sma(close: pd.Series, window: int) -> float:
    return float(close.tail(window).mean())


def _spread(close: pd.Series) -> float:
    fast_latest = _sma(close, FAST)
    slow_latest = _sma(close, SLOW)
    if slow_latest == 0:
        return 0.0
    return (fast_latest - slow_latest) / abs(slow_latest)


def score(history: pd.DataFrame) -> pd.Series:
    """One trend-spread score per symbol with at least `MIN_ROWS` rows of history.

    A symbol with too little history abstains (left out of the returned
    Series) rather than falling back to a default score that would
    masquerade as a real reading.
    """
    if history.empty:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/champion_v1.py`'s identical prefilter): a symbol with
        # no F&O future anywhere in its visible history can never survive
        # the downstream universe restriction regardless of what it scores
        # here, and skipping it here avoids recomputing adjustment factors
        # over the full EQ series on every pick date.
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
        out[symbol] = _spread(group["adj_close"])
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T01 SMA crossover: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    close = adjusted["adj_close"]
    fast_latest = _sma(close, FAST)
    slow_latest = _sma(close, SLOW)
    spread = _spread(close)
    direction = "bullish" if spread > 0 else "bearish" if spread < 0 else "neutral"
    return (
        f"T01 SMA crossover ({FAST}/{SLOW}): "
        f"SMA{FAST}={fast_latest:.2f} vs SMA{SLOW}={slow_latest:.2f} -> "
        f"spread {spread:+.4f} ({direction})"
    )
