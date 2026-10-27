"""F04: open-volume correlation (`cards/F04.yml`, `state/queue.md` port lane).

Alpha#6 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix 27 Oct 2026, SPEC.md section 5):

    -1 * correlation(open, volume, 10)

The lab's reading, on the adjusted open and raw volume of the last 10 sessions (SPEC.md
section 2): score = minus the correlation. Opens that rose as volume fell score
bullish; opens that rose as volume rose (or fell as it fell) score bearish. A flat
open or volume series abstains. No move size enters; ranking is by the correlation
alone.

Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 10
MIN_ROWS = WINDOW


def correlation(frame: pd.DataFrame) -> float:
    """Correlation of the adjusted open with volume over the last WINDOW rows; NaN if either is flat."""
    o = frame["adj_open"].to_numpy(float)[-WINDOW:]
    v = frame["volume"].to_numpy(float)[-WINDOW:]
    if not (np.isfinite(o).all() and np.isfinite(v).all()) or np.std(o) == 0.0 or np.std(v) == 0.0:
        return float("nan")
    return float(np.corrcoef(o, v)[0, 1])


def _score(frame: pd.DataFrame) -> float:
    rho = correlation(frame)
    return float("nan") if np.isnan(rho) or rho == 0.0 else -rho


def score(history: pd.DataFrame) -> pd.Series:
    """Minus the 10-session open-volume correlation, per symbol."""
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
        return "F04 open-volume correlation: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    value = _score(frame)
    if np.isnan(value):
        return "F04 open-volume correlation: flat open or volume, abstain"
    side = "bullish" if value > 0 else "bearish"
    return f"F04 open-volume correlation (Alpha#6): 10-session correlation {-value:+.2f}, {side}"
