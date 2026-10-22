"""T02: golden/death cross 50/200 (`cards/T02.yml`, `state/queue.md` port lane).

The slower, media-reported cousin of `cards/T01.yml`'s 20/50 crossover: the
50-day simple moving average above the 200-day one is bullish ("golden
cross"), below is bearish ("death cross"). Score is continuous, not a bare
sign, the exact same shape `strategies/t01_sma_crossover.py` uses with only
the window lengths swapped: `score = (fast_sma - slow_sma) / abs(slow_sma)`
(SPEC.md section 5: "one score per symbol; NaN means abstain"; sign gives
direction, magnitude gives conviction).

`cards/catalog.csv` lists this card's horizon as week only (T01's is
"both") - a 200-day SMA moves too slowly to plausibly carry a one-day
signal, so only a week-split experiment is queued for this card, unlike
T01's day-and-week pair.

Per SPEC.md section 2, both SMAs run on the adjusted close series
(`scripts.adjustments.compute_adjustment_factors`), so a split or bonus
inside either window doesn't masquerade as a real trend move.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

FAST, SLOW = 50, 200

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
        # `strategies/t01_sma_crossover.py`'s identical prefilter): a symbol
        # with no F&O future anywhere in its visible history can never
        # survive the downstream universe restriction regardless of what it
        # scores here, and skipping it here avoids recomputing adjustment
        # factors over the full EQ series on every pick date.
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
        return "T02 golden/death cross: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    close = adjusted["adj_close"]
    fast_latest = _sma(close, FAST)
    slow_latest = _sma(close, SLOW)
    spread = _spread(close)
    direction = "bullish" if spread > 0 else "bearish" if spread < 0 else "neutral"
    return (
        f"T02 golden/death cross ({FAST}/{SLOW}): "
        f"SMA{FAST}={fast_latest:.2f} vs SMA{SLOW}={slow_latest:.2f} -> "
        f"spread {spread:+.4f} ({direction})"
    )
