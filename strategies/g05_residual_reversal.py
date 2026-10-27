"""G05: market-residual short-term reversal (`cards/G05.yml`, `state/queue.md` port lane).

Da, Liu and Schaumburg (2014), "A Closer Look at the Short-Term Return Reversal",
Management Science (catalogued by Quantpedia, X04): the weekly reversal of A01
(`strategies/a01_weekly_reversal.py`) is stronger when computed on the part of last
week's return that the market does not explain. The lab's reading, on adjusted closes
(SPEC.md section 2):

- m_t = equal-weighted mean daily log return of the F&O stocks visible on date t
  (the stocks this module is handed, after the has_future prefilter);
- beta_i = cov(r_i, m) / var(m) over the `BETA_WINDOW` sessions before the last
  `LOOKBACK` sessions, so last week's move does not set its own beta;
- resid_i = sum over the last `LOOKBACK` sessions of (r_i,t - beta_i x m_t);
- score = -resid_i: the biggest residual losers bullish, the biggest residual winners bearish.

A stock missing any return in the window abstains. Cross-sectional by design: a
stock's score depends on the other stocks' returns on its own past dates, never on
any later date (`strategies/g05_residual_reversal_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

LOOKBACK = 5
BETA_WINDOW = 60
MIN_ROWS = LOOKBACK + BETA_WINDOW + 1
SLACK = 20  # extra trailing dates kept, so each stock's window is set by its own last date


def residuals(history: pd.DataFrame) -> pd.Series:
    """Last-week residual log return per symbol (NaN-free symbols only)."""
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
        m = market.loc[r.index]
        est_r, est_m = r.iloc[:BETA_WINDOW], m.iloc[:BETA_WINDOW]
        var = float(est_m.var(ddof=0))
        if not var > 0:
            continue
        beta = float(((est_r - est_r.mean()) * (est_m - est_m.mean())).mean()) / var
        out[symbol] = float((r.iloc[BETA_WINDOW:] - beta * m.iloc[BETA_WINDOW:]).sum())
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """Minus last week's market-residual return, per symbol."""
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
    resid = residuals(history)
    resid = resid[resid != 0.0]
    return (-resid).astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "G05 residual reversal: insufficient or gapped history, abstain"
    value = float(sc[symbol])
    side = "bullish" if value > 0 else "bearish"
    return f"G05 residual reversal (Da, Liu and Schaumburg 2014): last week's market-residual return {-value:+.1%}, {side}"
