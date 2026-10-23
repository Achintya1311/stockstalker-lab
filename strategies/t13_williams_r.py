"""T13: Williams %R, 14-day, -80/-20 thresholds (`cards/T13.yml`,
`state/queue.md` port lane).

Larry Williams' %R oscillator: %R below -80 is "oversold" (bullish), above
-20 is "overbought" (bearish). The catalog's own wording here is
"below"/"above", not "crossing" - the same persisted-state reading
`strategies/t03_rsi_thresholds.py`'s RSI 30/70 thresholds use, unlike
`strategies/t12_stochastic.py`'s Stochastic card (whose catalog row
literally says "crossing"). This card fires on every bar %R sits past
either threshold, not only on the bar it first gets there.

%R = -100 * (highest_high_14 - close) / (highest_high_14 - lowest_low_14),
over a trailing 14-day window of adjusted high/low - the mirror image of
T12's raw (unsmoothed) %K (%R = raw_%K - 100), read directly off %R's own
[-100, 0] scale.

Score reuses T03's threshold-distance convention: the boundary-to-edge
distance is 20 on both sides (-80 is 20 above the -100 floor, -20 is 20
below the 0 ceiling, the same symmetric shape T03's 30/70-against-[0,100]
distances have). Unlike T12, this reads the LATEST bar's %R (there is no
crossing condition to key off the prior bar for) - the same "read your own
latest value" convention T03's RSI already uses.

Catalog lists this card's horizon as day only, so one module serves that
one horizon (unlike T01/T03's "both").
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

PERIOD = 14
OVERSOLD, OVERBOUGHT = -80.0, -20.0
EDGE_DISTANCE = 20.0  # -80 to the -100 floor, and -20 to the 0 ceiling.

# The 14-day rolling high/low window needs 14 rows before %R is a real
# value (not a partial-window artefact). Unlike T12, no extra row is
# needed: this card reads only the latest bar, with no prior-bar cross
# condition to compare against.
MIN_ROWS = PERIOD


def _williams_r(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    rolling_high = high.rolling(PERIOD).max()
    rolling_low = low.rolling(PERIOD).min()
    denom = (rolling_high - rolling_low).where(lambda d: d != 0)
    return -100.0 * (rolling_high - close) / denom


def _threshold_score(r_latest: float) -> float:
    """NaN means abstain (SPEC.md section 5): %R sits inside -80 to -20."""
    if pd.isna(r_latest):
        return float("nan")
    if r_latest < OVERSOLD:
        return (OVERSOLD - r_latest) / EDGE_DISTANCE
    if r_latest > OVERBOUGHT:
        return -(r_latest - OVERBOUGHT) / EDGE_DISTANCE
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """One Williams-%R-threshold score per symbol with at least `MIN_ROWS`
    rows of history and %R past one of the two thresholds; every other
    symbol abstains (left out of the returned Series, same convention
    every other card here uses)."""
    if history.empty:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
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
        r_latest = _williams_r(group["adj_high"], group["adj_low"], group["adj_close"]).iloc[-1]
        value = _threshold_score(float(r_latest))
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T13 Williams %R(14): insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    r_latest = float(_williams_r(adjusted["adj_high"], adjusted["adj_low"], adjusted["adj_close"]).iloc[-1])
    value = _threshold_score(r_latest)
    if pd.isna(value):
        return f"T13 Williams %R(14): %R={r_latest:.2f} inside -80 to -20, abstain"
    direction = "bullish (oversold)" if value > 0 else "bearish (overbought)"
    return f"T13 Williams %R(14): %R={r_latest:.2f} -> score {value:+.4f} ({direction})"
