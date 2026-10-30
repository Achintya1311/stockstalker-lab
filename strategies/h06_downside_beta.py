"""H06: downside beta (`cards/H06.yml`, `state/queue.md` port lane).

Ang, Chen and Xing (2006), "Downside Risk", Review of Financial Studies 19(4)
(replicated in Open Source Asset Pricing, X05): stocks that move most with the market
when the market falls earn a premium, because investors dislike losses in bad times.
It differs from G02 (`strategies/g02_betting_against_beta.py`, full beta, low beta
bullish) by using only down-market days and by the opposite sign. The lab's reading,
on adjusted closes (SPEC.md section 2):

- m_t = equal-weighted mean daily log return of the F&O stocks visible on date t;
- over the last `WINDOW` daily returns, keep the days with m_t < its window mean and
  compute beta_down_i = cov(r_i, m) / var(m) on those days only (the paper's
  conditioning on below-mean market returns);
- score = beta_down_i - median beta_down over the stocks scored that date: high
  downside beta bullish, low bearish.

A stock missing any return in the window abstains. Cross-sectional by design (the
market mean and the median use every stock), never any later date
(`strategies/h06_downside_beta_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 250
MIN_DOWN_DAYS = 60
MIN_ROWS = WINDOW + 1
SLACK = 20  # extra trailing dates kept, so each stock's window is set by its own last date


def downside_betas(history: pd.DataFrame) -> pd.Series:
    """Beta on below-mean market days over the last WINDOW daily log returns, per symbol (gap-free only)."""
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
        down = m < m.mean()
        if int(down.sum()) < MIN_DOWN_DAYS:
            continue
        rd, md = r[down], m[down]
        var = float(md.var(ddof=0))
        if not var > 0:
            continue
        out[symbol] = float(((rd - rd.mean()) * (md - md.mean())).mean()) / var
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """Downside beta minus the day's median; high downside beta bullish."""
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
    beta = downside_betas(history)
    if len(beta) < 2:
        return pd.Series(dtype=float)
    sc = beta - beta.median()
    sc = sc[sc.abs() > 1e-12]
    return sc.astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "H06 downside beta: insufficient or gapped history, or at the median, abstain"
    value = float(sc[symbol])
    side = "bullish" if value > 0 else "bearish"
    return f"H06 downside beta (Ang, Chen and Xing 2006): down-market beta {value:+.2f} from the median, {side}"
