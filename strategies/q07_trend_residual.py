"""Q07: distance from the 20-day trend line (`cards/Q07.yml`, `state/queue.md` port lane).

Alpha158's RESI feature (microsoft/qlib, MIT; feature list in
`third_party/qlib/loader.py`): Resi($close, 20) / $close, the residual of the last
close from a straight-line fit to the last 20 closes, over the close. The lab's
reading, on the log of the adjusted close (SPEC.md section 2), as Q05 fits it
(`strategies/q05_trend_smoothness.py`):

    resid = log close today - (fitted line at today)
    score = -resid

A close well below its own 20-day trend line (a pullback) scores positive, bullish;
well above it (stretched) negative, bearish. A residual of zero (below 1e-12, floating-point noise) abstains.
The trend's own sign does not enter: a pullback in a downtrend scores bullish too.

Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20
MIN_ROWS = WINDOW
ZERO = 1e-12  # residuals smaller than this count as zero (floating-point noise)


def residual(frame: pd.DataFrame) -> float:
    """Last log close minus the least-squares line through the last WINDOW log closes, at today."""
    y = np.log(frame["adj_close"].to_numpy(float)[-WINDOW:])
    x = np.arange(WINDOW, dtype=float)
    xm = x - x.mean()
    slope = float(xm @ (y - y.mean())) / float(xm @ xm)
    return float(y[-1] - (y.mean() + slope * xm[-1]))


def _score(frame: pd.DataFrame) -> float:
    value = -residual(frame)
    return float("nan") if not np.isfinite(value) or abs(value) < ZERO else value


def score(history: pd.DataFrame) -> pd.Series:
    """Minus the last close's distance from its 20-day trend line, per symbol."""
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
        return "Q07 trend residual: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    resid = residual(frame)
    value = _score(frame)
    if np.isnan(value):
        return "Q07 trend residual: close exactly on its 20-day trend line, abstain"
    where = "below" if resid < 0 else "above"
    side = "bullish (pullback)" if value > 0 else "bearish (stretched)"
    return f"Q07 trend residual: close {abs(resid):.1%} {where} its 20-day trend line, {side}"
