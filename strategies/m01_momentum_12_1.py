"""M01: 12-1 momentum, ranked across the universe, for the month horizon (`cards/M01.yml`).

Jegadeesh and Titman (1993): stocks with the strongest return over the past 12
months, skipping the most recent month, keep outperforming over the next few
months. A03 tested the same return as a raw signed score at one week; M01 ranks
it across the universe on each date and is meant for the one-month horizon,
where the published effect lives.

Return: adjusted close `SKIP_DAYS` rows back over adjusted close
`SKIP_DAYS + LOOKBACK_DAYS` rows back, minus 1 (A03's `_formation_return`,
imported, on `scripts.adjustments.compute_adjustment_factors` closes). The
universe for the rank is the symbols whose last visible row is on the last
date, with `has_future` true there (when the column exists), and at least
`MIN_ROWS` rows. Mid-rank percentile `pct = (rank - 0.5) / n` (average ties);
score = 2 * pct - 1, so the strongest names score near +1 (bullish picks) and
the weakest near -1 (bearish picks); the engine's `top` selection then takes
the 5 strongest as bullish picks and the 5 weakest as bearish picks.

Adjustment factors depend only on later rows, so adjusting just the last
`TAIL_DATES` market dates gives the same adjusted closes on that tail as
adjusting the whole history (the `strategies/g_gates.py` convention).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies.a03_momentum_12_1 import LOOKBACK_DAYS, MIN_ROWS, SKIP_DAYS, _formation_return

TAIL_DATES = MIN_ROWS + 5


def _flag(col: pd.Series) -> pd.Series:
    return col.fillna(False).astype(bool)


def formation_returns(history: pd.DataFrame) -> pd.Series:
    """12-1 adjusted return per eligible symbol on the last visible date."""
    if history.empty:
        return pd.Series(dtype=float)
    last_date = history["date"].max()
    if "has_future" in history.columns:
        live = history[(history["date"] == last_date) & _flag(history["has_future"])]["symbol"].unique()
    else:
        live = history.loc[history["date"] == last_date, "symbol"].unique()
    if len(live) == 0:
        return pd.Series(dtype=float)
    dates = np.sort(history["date"].unique())
    tail = history[history["symbol"].isin(live) & (history["date"] >= dates[max(len(dates) - TAIL_DATES, 0)])]
    adj = compute_adjustment_factors(tail)
    out = {}
    for s, g in adj.groupby("symbol", sort=False):
        if len(g) < MIN_ROWS:
            continue
        g = g.sort_values("date")
        if g["adj_close"].iloc[-MIN_ROWS] == 0:
            continue
        out[s] = _formation_return(g["adj_close"])
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """Centred cross-sectional percentile of the 12-1 return; symbols without a reading abstain."""
    r = formation_returns(history)
    if r.empty:
        return r
    pct = (r.round(10).rank(method="average") - 0.5) / len(r)
    return 2.0 * pct - 1.0


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    r = formation_returns(history)
    if symbol not in r.index:
        return "M01 12-1 momentum: no reading, abstain"
    s = float(score(history)[symbol])
    side = "bullish" if s > 0 else "bearish" if s < 0 else "neutral"
    return (f"M01 12-1 momentum: {LOOKBACK_DAYS}-day return skipping the last {SKIP_DAYS} days "
            f"{r[symbol]:+.1%}, rank score {s:+.2f} of {len(r)} names ({side})")
