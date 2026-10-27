"""G02: betting against beta (`cards/G02.yml`, `state/queue.md` port lane).

Frazzini and Pedersen (2014), "Betting Against Beta", Journal of Financial Economics
(catalogued by Quantpedia, X04): low-beta stocks earn more per unit of risk than
high-beta stocks, because leverage-constrained investors bid up the high-beta ones.
It differs from A06/I02 (`strategies/a06_low_volatility.py`, total volatility) by
measuring market sensitivity only. The lab's reading, on adjusted closes (SPEC.md
section 2):

- m_t = equal-weighted mean daily log return of the F&O stocks visible on date t
  (the stocks this module is handed, after the has_future prefilter);
- beta_i = cov(r_i, m) / var(m) over the last `BETA_WINDOW` sessions (the paper's
  5-year correlation and 1-year volatility are folded into one 1-year estimate);
- shrunk beta = `SHRINK` x beta_i + (1 - `SHRINK`) x 1, as in the paper;
- score = 1 - shrunk beta: below-market beta bullish, above-market beta bearish.

A stock missing any return in the window abstains. Cross-sectional by design: a
stock's score depends on the other stocks' returns on its own past dates, never on
any later date (`strategies/g02_betting_against_beta_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

BETA_WINDOW = 250
SHRINK = 0.6
MIN_ROWS = BETA_WINDOW + 1
SLACK = 20  # extra trailing dates kept, so each stock's window is set by its own last date


def shrunk_betas(history: pd.DataFrame) -> pd.Series:
    """Shrunk 250-session beta against the equal-weighted mean, per symbol (gap-free symbols only)."""
    adjusted = compute_adjustment_factors(history)
    close = adjusted.pivot_table(index="date", columns="symbol", values="adj_close", aggfunc="last").sort_index()
    rets = np.log(close).diff().iloc[1:]
    market = rets.mean(axis=1, skipna=True)
    out: dict[str, float] = {}
    for symbol in rets.columns:
        r = rets[symbol].dropna()
        if len(r) < BETA_WINDOW:
            continue
        r = r.iloc[-BETA_WINDOW:]
        if len(r) != len(rets.loc[r.index[0]:r.index[-1]]):
            continue  # a gap in the window
        m = market.loc[r.index]
        var = float(m.var(ddof=0))
        if not var > 0:
            continue
        beta = float(((r - r.mean()) * (m - m.mean())).mean()) / var
        out[symbol] = SHRINK * beta + (1.0 - SHRINK)
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """One minus the shrunk beta, per symbol."""
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
    sc = 1.0 - shrunk_betas(history)
    sc = sc[sc.abs() > 1e-12]
    return sc.astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "G02 betting against beta: insufficient or gapped history, or beta of 1, abstain"
    value = float(sc[symbol])
    side = "bullish" if value > 0 else "bearish"
    return f"G02 betting against beta (Frazzini and Pedersen 2014): shrunk beta {1.0 - value:.2f}, {side}"
