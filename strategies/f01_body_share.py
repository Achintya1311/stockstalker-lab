"""F01: bar body share (`cards/F01.yml`, `state/queue.md` port lane).

Alpha#101 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from
the paper's formula, SPEC.md section 5): (close - open) / ((high - low) + 0.001).
The lab's reading, on the adjusted last bar (SPEC.md section 2):

    score = (close - open) / (high - low)

The paper's +0.001 keeps the ratio finite on a zero-range bar in its own price
units; adjusted NSE prices are not on one scale, so a zero-range bar abstains
instead. A close near the high after an open near the low scores towards +1,
bullish; the reverse towards -1, bearish; a doji (close equal to open) abstains.

Only the last `MIN_ROWS` rows per symbol are read; the score uses the last bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

MIN_ROWS = 2


def body_share(frame: pd.DataFrame) -> float:
    """(close - open) / (high - low) of the last bar; NaN when it has no range."""
    last = frame.iloc[-1]
    o, h, l, c = (float(last[k]) for k in ("adj_open", "adj_high", "adj_low", "adj_close"))
    width = h - l
    if not width > 0:
        return float("nan")
    return (c - o) / width


def _score(frame: pd.DataFrame) -> float:
    value = body_share(frame)
    return float("nan") if value == 0.0 else value


def score(history: pd.DataFrame) -> pd.Series:
    """Body share of the last bar for every symbol with a range and a non-zero body."""
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
        return "F01 bar body share: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    value = _score(frame)
    if np.isnan(value):
        return "F01 bar body share: no range or no body on the last bar, abstain"
    side = "bullish (closed near the high)" if value > 0 else "bearish (closed near the low)"
    return f"F01 bar body share (Alpha#101): last bar body {value:+.0%} of its range, {side}"
