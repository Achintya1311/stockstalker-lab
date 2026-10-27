"""Q06R: Q06's wick balance on wide bars only (`cards/Q06R.yml`, the refinement named
in `research/diagnostics/q06.md`).

Q06 scores lower-minus-upper wick share of the last bar, so a tiny-range bar scores
the same as a wide one. Q06R keeps Q06's score (`strategies/q06_wick_balance.py`,
unchanged) only when the last bar's adjusted range (high - low) is at least the
median adjusted range of the 20 sessions before it; every narrower bar abstains.
Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import q06_wick_balance as q06

LOOKBACK = 20
MIN_ROWS = LOOKBACK + 1


def range_ratio(frame: pd.DataFrame) -> float:
    """Last bar's range over the median range of the `LOOKBACK` bars before it; NaN if that median is 0."""
    width = (frame["adj_high"] - frame["adj_low"]).to_numpy(float)[-MIN_ROWS:]
    median = float(np.median(width[:-1]))
    return float("nan") if not median > 0 else float(width[-1] / median)


def _score(frame: pd.DataFrame) -> float:
    ratio = range_ratio(frame)
    if np.isnan(ratio) or ratio < 1.0:
        return float("nan")
    return q06._score(frame)


def score(history: pd.DataFrame) -> pd.Series:
    """Q06's score for symbols whose last bar is at least as wide as their 20-session median bar."""
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        value = _score(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS)
    if len(sub) < MIN_ROWS:
        return "Q06R wide-bar wick balance: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    ratio = range_ratio(frame)
    if np.isnan(ratio) or ratio < 1.0:
        return f"Q06R wide-bar wick balance: last bar {ratio:.2f}x its 20-session median range, narrow, abstain"
    lower, upper = q06.wicks(frame)
    value = _score(frame)
    if np.isnan(value):
        return "Q06R wide-bar wick balance: equal wicks on the last bar, abstain"
    detail = f"last bar {ratio:.2f}x its median range, lower wick {lower:.0%} and upper wick {upper:.0%}"
    side = "bullish (dip bought back)" if value > 0 else "bearish (rise given back)"
    return f"Q06R wide-bar wick balance: {detail}, {side}"
