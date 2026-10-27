"""F05: change in close location (`cards/F05.yml`, `state/queue.md` port lane).

Alpha#53 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix 27 Oct 2026, SPEC.md section 5):

    -1 * delta((((close - low) - (high - close)) / (close - low)), 9)

On the adjusted bars (SPEC.md section 2): loc = ((close - low) - (high - close)) /
(close - low), and score = -(loc today - loc 9 sessions ago). The paper's
denominator is close - low, not the bar's range, so loc is at most 1 (a close at
the high) and unbounded below as the close nears the low; a bar that closed exactly
at its low has no loc, and the stock abstains. That asymmetry is the paper's own
and is kept.

Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

LAG = 9
MIN_ROWS = LAG + 1


def location(bar: pd.Series) -> float:
    """((close - low) - (high - close)) / (close - low) of one adjusted bar; NaN when close == low."""
    h, l, c = float(bar["adj_high"]), float(bar["adj_low"]), float(bar["adj_close"])
    if not c - l > 0:
        return float("nan")
    return ((c - l) - (h - c)) / (c - l)


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(loc today, loc LAG sessions ago)."""
    tail = frame.iloc[-MIN_ROWS:]
    return location(tail.iloc[-1]), location(tail.iloc[0])


def _score(frame: pd.DataFrame) -> float:
    now, then = parts(frame)
    if np.isnan(now) or np.isnan(then) or now == then:
        return float("nan")
    return -(now - then)


def score(history: pd.DataFrame) -> pd.Series:
    """Minus the 9-session change in close location, per symbol."""
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
        return "F05 close location change: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    now, then = parts(frame)
    value = _score(frame)
    if np.isnan(value):
        return "F05 close location change: a close at its low, or no change, abstain"
    side = "bullish" if value > 0 else "bearish"
    return f"F05 close location change (Alpha#53): location {then:+.2f} nine sessions ago, {now:+.2f} today, {side}"
