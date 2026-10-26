"""T24: classic (floor-trader) pivot points (`cards/T24.yml`, `state/queue.md` port lane).

The floor-trader convention: from a session's high, low and close, pivot P =
(H + L + C) / 3, R1 = 2P - L, S1 = 2P - H. `cards/catalog.csv`: open above the
pivot bullish, below bearish, with a bounce or break at S1/R1.

The pick is made before the open (SPEC.md section 10), so the next open is not
visible. The lab's reading, on the adjusted series (SPEC.md section 2): the
pivot, R1 and S1 come from the second-to-last bar, and the last bar's close is
placed against them:

    score = (close - P) / (R1 - S1)

Positive (close above the pivot) is bullish, negative bearish; a close beyond
R1 or S1 scores above +0.5 or below -0.5 (R1 - P and P - S1 add up to R1 - S1),
so the size ranks breaks above bounces. A bar with no range abstains.

Only the last two rows are read; `MIN_ROWS` keeps the adjustment window equal
to the other day strategies'.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

MIN_ROWS = 20


def levels(frame: pd.DataFrame) -> tuple[float, float, float, float]:
    """(close, pivot, R1, S1): levels from the second-to-last row, close from the last."""
    prev = frame.iloc[-2]
    h, l, c = float(prev["adj_high"]), float(prev["adj_low"]), float(prev["adj_close"])
    pivot = (h + l + c) / 3.0
    return float(frame["adj_close"].iloc[-1]), pivot, 2.0 * pivot - l, 2.0 * pivot - h


def _pivot_score(frame: pd.DataFrame) -> float:
    close, pivot, r1, s1 = levels(frame)
    width = r1 - s1
    if not width > 0:
        return float("nan")
    return (close - pivot) / width


def score(history: pd.DataFrame) -> pd.Series:
    """Score for every symbol whose previous bar had a range; the sign is the side."""
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
        value = _pivot_score(group.sort_values("date"))
        if not np.isnan(value) and value != 0.0:
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS)
    if len(sub) < MIN_ROWS:
        return "T24 pivot points: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    close, pivot, r1, s1 = levels(frame)
    value = _pivot_score(frame)
    if np.isnan(value) or value == 0.0:
        return f"T24 pivot points: close {close:.2f} at pivot {pivot:.2f} or no range, abstain"
    where = "beyond R1" if close > r1 else "beyond S1" if close < s1 else "between S1 and R1"
    side = "bullish (above pivot)" if value > 0 else "bearish (below pivot)"
    return f"T24 pivot points: close {close:.2f} vs pivot {pivot:.2f} (S1 {s1:.2f}, R1 {r1:.2f}), {where}, {side}"
