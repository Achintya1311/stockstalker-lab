"""H02: idiosyncratic volatility (`cards/H02.yml`, `state/queue.md` port lane).

Ang, Hodrick, Xing and Zhang (2006), "The Cross-Section of Volatility and Expected
Returns", Journal of Finance 61(1) (replicated in Open Source Asset Pricing, X05):
stocks whose returns are most volatile after removing common factors earn much lower
subsequent returns. The paper uses the Fama-French three-factor residual over the
past month; the lab has no size or value factors, so it uses the one-factor residual
against the equal-weighted F&O mean. It differs from A06/I02 (total volatility) and
G02 (beta) by measuring only the stock-specific part. The lab's reading, on adjusted
closes (SPEC.md section 2):

- m_t = equal-weighted mean daily log return of the F&O stocks visible on date t;
- over the last `WINDOW` daily returns: beta_i = cov(r_i, m) / var(m),
  e_i,t = r_i,t - alpha_i - beta_i x m_t, ivol_i = std(e_i);
- score = log(median ivol over the stocks scored that date) - log(ivol_i): calmer
  than the median bullish, more volatile bearish.

A stock missing any return in the window abstains. Cross-sectional by design (the
market mean and the median use every stock), never any later date
(`strategies/h02_idiosyncratic_volatility_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20
MIN_ROWS = WINDOW + 1
SLACK = 20  # extra trailing dates kept, so each stock's window is set by its own last date


def idiosyncratic_vol(history: pd.DataFrame) -> pd.Series:
    """Std of the one-factor residual over the last WINDOW daily log returns, per symbol (gap-free symbols only)."""
    adjusted = compute_adjustment_factors(history)
    close = adjusted.pivot_table(index="date", columns="symbol", values="adj_close", aggfunc="last").sort_index()
    rets = np.log(close).diff().iloc[1:]
    market = rets.mean(axis=1, skipna=True)
    out: dict[str, float] = {}
    for symbol in rets.columns:
        r = rets[symbol].dropna()
        if len(r) < WINDOW:
            continue
        r = r.iloc[-WINDOW:]
        if len(r) != len(rets.loc[r.index[0]:r.index[-1]]):
            continue  # a gap in the window
        m = market.loc[r.index]
        var = float(m.var(ddof=0))
        if not var > 0:
            continue
        beta = float(((r - r.mean()) * (m - m.mean())).mean()) / var
        e = (r - r.mean()) - beta * (m - m.mean())
        sd = float(e.std(ddof=0))
        if sd > 1e-12:
            out[symbol] = sd
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """Log of the median idiosyncratic volatility over the stock's own; low ivol bullish."""
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
    ivol = idiosyncratic_vol(history)
    if len(ivol) < 2:
        return pd.Series(dtype=float)
    sc = np.log(ivol.median()) - np.log(ivol)
    sc = sc[sc.abs() > 1e-12]
    return sc.astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "H02 idiosyncratic volatility: insufficient or gapped history, or at the median, abstain"
    value = float(sc[symbol])
    side = "bullish" if value > 0 else "bearish"
    return (
        f"H02 idiosyncratic volatility (Ang, Hodrick, Xing and Zhang 2006): 20-day stock-specific volatility "
        f"{np.exp(-value):.2f}x the median, {side}"
    )
