"""F03: conditional one-day continuation (`cards/F03.yml`, `state/queue.md` port lane).

Alpha#9 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix 27 Oct 2026, SPEC.md section 5):

    (0 < ts_min(delta(close, 1), 5)) ? delta(close, 1)
      : ((ts_max(delta(close, 1), 5) < 0) ? delta(close, 1) : -delta(close, 1))

The lab's reading, on the adjusted close (SPEC.md section 2), with daily log returns in
place of raw price changes so stocks on different price scales rank together: when
all of the last 5 daily returns were up, or all down, today's return continues
(score = r1); otherwise it reverses (score = -r1). A zero return abstains.

Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

RUN = 5
MIN_ROWS = RUN + 1


def returns(frame: pd.DataFrame) -> np.ndarray:
    """The last `RUN` daily log returns of the adjusted close, oldest first."""
    close = frame["adj_close"].to_numpy(float)[-MIN_ROWS:]
    return np.log(close[1:] / close[:-1])


def _score(frame: pd.DataFrame) -> float:
    r = returns(frame)
    r1 = float(r[-1])
    if r1 == 0.0 or not np.isfinite(r).all():
        return float("nan")
    if r.min() > 0 or r.max() < 0:
        return r1
    return -r1


def score(history: pd.DataFrame) -> pd.Series:
    """Alpha#9 per symbol: a 5-session run continues, anything else reverses."""
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
        return "F03 conditional reversal: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    r = returns(frame)
    value = _score(frame)
    if np.isnan(value):
        return "F03 conditional reversal: unchanged close, abstain"
    run = r.min() > 0 or r.max() < 0
    kind = "5-session run, continuation" if run else "no run, reversal"
    side = "bullish" if value > 0 else "bearish"
    return f"F03 conditional reversal (Alpha#9): last day {float(r[-1]):+.1%}, {kind}, {side}"
