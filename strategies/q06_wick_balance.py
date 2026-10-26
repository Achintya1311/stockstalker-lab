"""Q06: candle wick balance (`cards/Q06.yml`, `state/queue.md` port lane).

Alpha158's KLOW2 and KUP2 features (microsoft/qlib, MIT; feature list in
`third_party/qlib/loader.py`): the lower and upper shadows of the last bar as
shares of its range. The lab's reading, on the adjusted last bar (SPEC.md
section 2):

    lower = (min(open, close) - low) / (high - low)
    upper = (high - max(open, close)) / (high - low)
    score = lower - upper

A long lower wick (the day's dip was bought back) scores towards +1, bullish; a
long upper wick (the day's rise was given back) towards -1, bearish. A bar with
no range, or equal wicks, abstains.

Only the last `MIN_ROWS` rows per symbol are read; the score uses the last bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

MIN_ROWS = 2
EQUAL = 1e-9  # wick shares closer than this count as equal (floating-point noise)


def wicks(frame: pd.DataFrame) -> tuple[float, float]:
    """(lower share, upper share) of the last bar's range; NaN when it has no range."""
    last = frame.iloc[-1]
    o, h, l, c = (float(last[k]) for k in ("adj_open", "adj_high", "adj_low", "adj_close"))
    width = h - l
    if not width > 0:
        return float("nan"), float("nan")
    return (min(o, c) - l) / width, (h - max(o, c)) / width


def _score(frame: pd.DataFrame) -> float:
    lower, upper = wicks(frame)
    if np.isnan(lower) or abs(lower - upper) < EQUAL:
        return float("nan")
    return lower - upper


def score(history: pd.DataFrame) -> pd.Series:
    """Lower-minus-upper wick share of the last bar for every symbol with unequal wicks."""
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
        return "Q06 wick balance: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    lower, upper = wicks(frame)
    value = _score(frame)
    if np.isnan(value):
        return "Q06 wick balance: no range or equal wicks on the last bar, abstain"
    detail = f"last bar lower wick {lower:.0%} and upper wick {upper:.0%} of its range"
    side = "bullish (dip bought back)" if value > 0 else "bearish (rise given back)"
    return f"Q06 wick balance: {detail}, {side}"
