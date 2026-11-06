"""Shared helpers for the 101 Formulaic Alphas ports from F13 on (`research/notes/discover_2026-11-06_x03.md`).

Kakushadze (2016), "101 Formulaic Alphas", Wilmott 84 (arXiv:1601.00991). Helpers only; each card's formula
lives in its own module.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ts_rank_last(values: np.ndarray) -> float:
    """Rank of the last value among `values` (ties averaged), divided by len(values): in (0, 1]."""
    last = values[-1]
    return float(((values < last).sum() + 0.5 * ((values == last).sum() + 1)) / len(values))


def live_cross_section(history: pd.DataFrame) -> pd.DataFrame:
    """Rows of the symbols that have a row with an active future on the slice's last date.

    The cross-section a rank or median is taken over. A delisted or merged name (the stale-symbol WATCH in
    `state/engine-issues.md`) has no future on the last date and drops out. Uses only the slice itself, so it
    is causal. Without a `has_future` column (synthetic tests) every symbol is kept.
    """
    if history.empty or "has_future" not in history.columns:
        return history
    last = history["date"].max()
    live = history.loc[(history["date"] == last) & history["has_future"].fillna(False).astype(bool), "symbol"]
    return history[history["symbol"].isin(set(live))]


def centred(raw: pd.Series) -> pd.Series:
    """raw - median over the stocks scored that date; exact zeros abstain. Needs at least two stocks."""
    raw = raw.dropna()
    if len(raw) < 2:
        return pd.Series(dtype=float)
    sc = raw - raw.median()
    return sc[sc.abs() > 1e-12].astype(float)
