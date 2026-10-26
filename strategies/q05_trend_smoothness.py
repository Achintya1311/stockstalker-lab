"""Q05: trend smoothness (`cards/Q05.yml`, `state/queue.md` port lane).

Alpha158's RSQR feature, signed by its BETA (microsoft/qlib, MIT; feature list in
`third_party/qlib/loader.py`): the R-squared of a straight-line fit to the last 20
closes. The lab's reading, on the log of the adjusted close (SPEC.md section 2):

    score = sign(slope) * R^2

So a stock that rose in a near-straight line scores close to +1 (bullish), one that
fell in a near-straight line close to -1 (bearish), and a choppy one near 0 whatever
its net move. It rewards the steadiness of a trend, not its size, which is what
separates it from the moving-average spreads of T01/T02 and the momentum of T23/I01.
A flat window (zero slope) abstains.

Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20
MIN_ROWS = WINDOW


def fit(frame: pd.DataFrame) -> tuple[float, float]:
    """(slope per session of log close, R-squared) over the last WINDOW rows."""
    y = np.log(frame["adj_close"].to_numpy(float)[-WINDOW:])
    x = np.arange(WINDOW, dtype=float)
    xm, ym = x - x.mean(), y - y.mean()
    sxx, syy = float(xm @ xm), float(ym @ ym)
    if syy == 0.0:
        return 0.0, 0.0
    slope = float(xm @ ym) / sxx
    return slope, float((xm @ ym) ** 2 / (sxx * syy))


def _score(frame: pd.DataFrame) -> float:
    slope, r2 = fit(frame)
    if slope == 0.0:
        return float("nan")
    return float(np.sign(slope) * r2)


def score(history: pd.DataFrame) -> pd.Series:
    """Signed R-squared of the 20-session log-close trend for every symbol that moved."""
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
        return "Q05 trend smoothness: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    slope, r2 = fit(frame)
    detail = f"20-session trend {slope * WINDOW:+.1%} with R-squared {r2:.2f}"
    if slope == 0.0:
        return f"Q05 trend smoothness: {detail}, abstain"
    side = "bullish (steady rise)" if slope > 0 else "bearish (steady fall)"
    return f"Q05 trend smoothness: {detail}, {side}"
