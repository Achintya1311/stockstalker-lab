"""G01B: residual momentum losers on volatile stocks only (`cards/G01B.yml`, port lane).

A follow-up to G01 (`strategies/g01_residual_momentum.py`, `research/diagnostics/g01.md`).
G01's bearish side had the highest week-bearish train edge in the lab (+4.22, positive
in every year) but a directional move of -0.05% after the 0.25% futures cost: its
steady losers drift down by less than the cost. G01B keeps G01's signal and moves it
onto stocks that move more:

- the same 12-1 month market residual e_i,t = r_i,t - beta_i x m_t as G01, scaled by
  its volatility sd(e_i) (`g01.LOOKBACK`, `g01.SKIP`, same gap rule);
- bearish only: a stock is scored when its scaled residual is negative **and** its
  residual volatility sd(e_i) is at or above the median over every stock scored that
  date; the score is G01's (negative) value. Everything else abstains, including the
  whole bullish side.

The residual arithmetic is restated here rather than changing G01's module, so
`g01_residual_momentum@v1` stays byte-for-byte what was replayed; a test checks the two
agree on every score G01B emits.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import g01_residual_momentum as g01

LOOKBACK = g01.LOOKBACK
SKIP = g01.SKIP
MIN_ROWS = g01.MIN_ROWS
SLACK = g01.SLACK


def residual_stats(history: pd.DataFrame) -> pd.DataFrame:
    """Per symbol: G01's scaled residual (`score`) and the residual volatility (`resid_vol`)."""
    adjusted = compute_adjustment_factors(history)
    close = adjusted.pivot_table(index="date", columns="symbol", values="adj_close", aggfunc="last").sort_index()
    rets = np.log(close).diff().iloc[1:]
    market = rets.mean(axis=1, skipna=True)
    rows: dict[str, tuple[float, float]] = {}
    for symbol in rets.columns:
        r = rets[symbol].dropna()
        if len(r) < MIN_ROWS - 1:
            continue
        r = r.iloc[-(MIN_ROWS - 1):]
        if len(r) != len(rets.loc[r.index[0]:r.index[-1]]):
            continue  # a gap in the window
        r = r.iloc[:LOOKBACK]  # drop the skipped month
        m = market.loc[r.index]
        var = float(m.var(ddof=0))
        if not var > 0:
            continue
        beta = float(((r - r.mean()) * (m - m.mean())).mean()) / var
        e = r - beta * m
        sd = float(e.std(ddof=0))
        if not sd > 1e-12:
            continue
        rows[symbol] = (float(e.sum()) / (sd * np.sqrt(LOOKBACK)), sd)
    return pd.DataFrame.from_dict(rows, orient="index", columns=["score", "resid_vol"], dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """G01's negative scores on stocks with at least median residual volatility; else abstain."""
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, as in G01.
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)
    dates = np.sort(history["date"].unique())[-(MIN_ROWS + SLACK):]
    history = history[history["date"].isin(dates)]
    stats = residual_stats(history)
    if stats.empty:
        return pd.Series(dtype=float)
    keep = (stats["score"] < 0) & (stats["resid_vol"] >= stats["resid_vol"].median())
    return stats.loc[keep, "score"].astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "G01B volatile residual losers: not a residual loser with above-median residual volatility, abstain"
    return (
        f"G01B volatile residual losers (after Blitz, Huij and Martens 2011): scaled 12-1 month residual "
        f"{float(sc[symbol]):+.2f} with above-median residual volatility, bearish"
    )
