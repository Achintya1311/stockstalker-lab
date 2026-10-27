"""G01: residual momentum (`cards/G01.yml`, `state/queue.md` port lane).

Blitz, Huij and Martens (2011), "Residual momentum", Journal of Empirical Finance
(catalogued by Quantpedia, X04): momentum computed on the part of each stock's
12-1 month return that the market does not explain, scaled by that residual's
volatility, earns about the premium of A03's total momentum
(`strategies/a03_momentum_12_1.py`) with less exposure to market swings. The lab's
reading, on adjusted closes (SPEC.md section 2):

- m_t = equal-weighted mean daily log return of the F&O stocks visible on date t
  (the stocks this module is handed, after the has_future prefilter);
- formation window = the `LOOKBACK` sessions ending `SKIP` sessions before the last
  date (A03's 12-1 months);
- beta_i = cov(r_i, m) / var(m) over the formation window (the paper's 36-month
  factor regression is shortened to the 12 months the window holds, for coverage);
- e_i,t = r_i,t - beta_i x m_t; score = sum(e_i) / (std(e_i) x sqrt(LOOKBACK)):
  the highest scaled residual winners bullish, the lowest bearish.

A stock missing any return in the window abstains. Cross-sectional by design: a
stock's score depends on the other stocks' returns on its own past dates, never on
any later date (`strategies/g01_residual_momentum_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

LOOKBACK = 252
SKIP = 21
MIN_ROWS = LOOKBACK + SKIP + 1
SLACK = 20  # extra trailing dates kept, so each stock's window is set by its own last date


def scaled_residuals(history: pd.DataFrame) -> pd.Series:
    """Volatility-scaled 12-1 month residual return per symbol (NaN-free symbols only)."""
    adjusted = compute_adjustment_factors(history)
    close = adjusted.pivot_table(index="date", columns="symbol", values="adj_close", aggfunc="last").sort_index()
    rets = np.log(close).diff().iloc[1:]
    market = rets.mean(axis=1, skipna=True)
    out: dict[str, float] = {}
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
        out[symbol] = float(e.sum()) / (sd * np.sqrt(LOOKBACK))
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """Volatility-scaled 12-1 month market-residual return, per symbol."""
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)
    dates = np.sort(history["date"].unique())[-(MIN_ROWS + SLACK):]
    history = history[history["date"].isin(dates)]
    sc = scaled_residuals(history)
    sc = sc[sc != 0.0]
    return sc.astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "G01 residual momentum: insufficient or gapped history, abstain"
    value = float(sc[symbol])
    side = "bullish" if value > 0 else "bearish"
    return f"G01 residual momentum (Blitz, Huij and Martens 2011): scaled 12-1 month residual {value:+.2f}, {side}"
