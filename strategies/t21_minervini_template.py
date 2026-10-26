"""T21: Minervini trend template (`cards/T21.yml`, `state/queue.md` port lane).

Minervini (2013), Trade Like a Stock Market Wizard: a "stage 2" uptrend
filter. `cards/catalog.csv`: price above the 50, 150 and 200-day SMAs, 150 >
200, 200 rising, near the 52-week high: bullish; mirror conditions bearish.

The lab's reading of the published bullish checklist (on the adjusted close,
SPEC.md section 2), all required:

1. close > SMA150 and close > SMA200;
2. SMA150 > SMA200;
3. SMA200 rising: today's SMA200 above its value 21 sessions earlier;
4. SMA50 > SMA150 and SMA50 > SMA200;
5. close > SMA50;
6. close at least 30% above the 52-week (252-session) low close;
7. close within 25% of the 52-week high close (close >= 0.75 x high).

The book's eighth point (RS rating at least 70) is left out here so the
template is tested on its own; `cards/T23.yml` tests the RS rating.

Bearish is the mirror: every inequality reversed, SMA200 falling, close at
least 30% below the 52-week high (close <= high / 1.30) and within 25% of the
52-week low (close <= low / 0.75).

The template is a pass/fail state. For ranking, a passing stock's score is
its proximity to the extreme it is trending towards, scaled to (0, 1]:
bullish `(close / high - 0.75) / 0.25`, bearish `-(low / close - 0.75) / 0.25`.
A stock at a new 52-week high scores +1, one at a new low -1. Every other
stock abstains.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

FAST, MID, SLOW = 50, 150, 200
RISING_LAG = 21
YEAR = 252
NEAR, AWAY = 0.75, 1.30
MIN_ROWS = max(YEAR, SLOW + RISING_LAG)


def _template_score(close: pd.Series) -> float:
    c = close.iloc[-MIN_ROWS:].to_numpy(dtype=float)
    last = c[-1]
    sma50, sma150, sma200 = c[-FAST:].mean(), c[-MID:].mean(), c[-SLOW:].mean()
    sma200_then = c[-SLOW - RISING_LAG:-RISING_LAG].mean()
    year = c[-YEAR:]
    high, low = year.max(), year.min()
    if low <= 0:
        return float("nan")

    bullish = (
        last > sma150 and last > sma200 and sma150 > sma200 and sma200 > sma200_then
        and sma50 > sma150 and sma50 > sma200 and last > sma50
        and last >= AWAY * low and last >= NEAR * high
    )
    if bullish:
        return float((last / high - NEAR) / (1 - NEAR))

    bearish = (
        last < sma150 and last < sma200 and sma150 < sma200 and sma200 < sma200_then
        and sma50 < sma150 and sma50 < sma200 and last < sma50
        and last <= high / AWAY and last <= low / NEAR
    )
    if bearish:
        return float(-(low / last - NEAR) / (1 - NEAR))
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """Score for symbols passing the bullish or bearish template; every other
    symbol abstains (left out of the returned Series)."""
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
        value = _template_score(group.sort_values("date")["adj_close"])
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T21 Minervini trend template: insufficient history, abstain"
    close = compute_adjustment_factors(sub)["adj_close"]
    value = _template_score(close)
    if np.isnan(value):
        return "T21 Minervini trend template: neither template passes, abstain"
    side = "bullish (stage-2 uptrend)" if value > 0 else "bearish (mirror downtrend)"
    return f"T21 Minervini trend template: {side}, proximity to 52-week extreme -> score {value:+.3f}"
