"""H01: Amihud illiquidity (`cards/H01.yml`, `state/queue.md` port lane).

Amihud (2002), "Illiquidity and stock returns", Journal of Financial Markets 5(1)
(replicated in Open Source Asset Pricing, X05): stocks with a larger price impact per
rupee traded earn higher subsequent returns. Over the last `WINDOW` sessions:

- illiq_i = mean over the window of |daily log return| / traded value (`turnover`,
  rupees; `docs/nse_formats.md`), returns from split/bonus-adjusted closes;
- score = log(illiq_i) - log(median illiq over the stocks scored that date): less
  liquid than the median bullish, more liquid bearish.

A stock with a missing session in the window, or a zero traded value, abstains.
Cross-sectional only through the median (`strategies/h01_amihud_illiquidity_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20
SLACK = 20  # extra trailing dates kept, so each stock's window is set by its own last date


def amihud(history: pd.DataFrame) -> pd.Series:
    """Mean |log return| per rupee traded over each symbol's last WINDOW sessions (gap-free only)."""
    adjusted = compute_adjustment_factors(history)
    close = adjusted.pivot_table(index="date", columns="symbol", values="adj_close", aggfunc="last").sort_index()
    turnover = history.pivot_table(index="date", columns="symbol", values="turnover", aggfunc="last").sort_index()
    rets = np.log(close).diff().iloc[1:]
    out: dict[str, float] = {}
    for symbol in rets.columns:
        if symbol not in turnover.columns:
            continue
        r = rets[symbol].dropna()
        if len(r) < WINDOW:
            continue
        r = r.iloc[-WINDOW:]
        if len(r) != len(rets.loc[r.index[0]:r.index[-1]]):
            continue  # a gap in the window
        t = turnover[symbol].reindex(r.index)
        if t.isna().any() or not (t > 0).all():
            continue
        value = float((r.abs() / t).mean())
        if value > 1e-30:
            out[symbol] = value
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """Log of own Amihud ratio over the date's median; illiquid bullish."""
    if history.empty or "turnover" not in history.columns:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see `strategies/t01_sma_crossover.py`).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)
    dates = np.sort(history["date"].unique())[-(WINDOW + 1 + SLACK):]
    history = history[history["date"].isin(dates)]
    a = amihud(history)
    if len(a) < 2:
        return pd.Series(dtype=float)
    sc = np.log(a) - np.log(a.median())
    sc = sc[sc.abs() > 1e-12]
    return sc.astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "H01 Amihud illiquidity: insufficient or gapped history, or at the median, abstain"
    value = float(sc[symbol])
    side = "bullish" if value > 0 else "bearish"
    return (
        f"H01 Amihud illiquidity (Amihud 2002): 20-day price impact per rupee traded "
        f"{np.exp(value):.2f}x the median, {side}"
    )
