"""F07: fade of a high above its 20-day mean (`cards/F07.yml`, `state/queue.md` port lane).

Alpha#23 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix 27 Oct 2026, SPEC.md section 5):

    ((sum(high, 20) / 20) < high) ? (-1 * delta(high, 2)) : 0

On the adjusted high (SPEC.md section 2), with the log change in place of the raw
change so stocks on different price scales rank together: when today's high is above
the mean of the last 20 highs (today's included, as in the paper), score = -(log
high today - log high 2 sessions ago); otherwise, or when that change is zero, the
stock abstains (the paper's 0). A high pushed up over two sessions scores bearish; a
high still above its mean but lower than two sessions ago scores bullish.

Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20
LAG = 2
MIN_ROWS = WINDOW


def parts(frame: pd.DataFrame) -> tuple[bool, float]:
    """(today's high above the 20-session mean high, 2-session log change in the high)."""
    high = frame["adj_high"].to_numpy(float)[-MIN_ROWS:]
    return bool(high.mean() < high[-1]), float(np.log(high[-1] / high[-1 - LAG]))


def _score(frame: pd.DataFrame) -> float:
    above, change = parts(frame)
    if not above or change == 0.0 or not np.isfinite(change):
        return float("nan")
    return -change


def score(history: pd.DataFrame) -> pd.Series:
    """Minus the 2-session change in the high, for stocks whose high is above its 20-session mean."""
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
        return "F07 high-push fade: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    above, change = parts(frame)
    if np.isnan(_score(frame)):
        where = "above" if above else "not above"
        return f"F07 high-push fade: high {where} its 20-session mean, 2-session change {change:+.1%}, abstain"
    side = "bullish" if change < 0 else "bearish"
    return f"F07 high-push fade (Alpha#23): high above its 20-session mean, up {change:+.1%} in 2 sessions, {side}"
