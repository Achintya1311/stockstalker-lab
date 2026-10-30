"""H03: variability of turnover (`cards/H03.yml`, `state/queue.md` port lane).

Chordia, Subrahmanyam and Anshuman (2001), "Trading activity and expected stock
returns", Journal of Financial Economics 59(1) (replicated in Open Source Asset
Pricing, X05): stocks whose trading activity is more variable earn lower subsequent
returns. The paper measures monthly turnover over three years; the lab uses daily
traded value (`turnover`, rupees; `docs/nse_formats.md`) over the last `WINDOW`
sessions:

- cv_i = std(turnover_i) / mean(turnover_i) over the window;
- score = log(median cv over the stocks scored that date) - log(cv_i): steadier than
  the median bullish, more erratic bearish.

A stock with a missing session in the window abstains, as does one with zero mean
turnover. Cross-sectional only through the median, which uses each stock's own last
`WINDOW` rows (`strategies/h03_turnover_variability_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 60
SLACK = 20  # extra trailing dates kept, so each stock's window is set by its own last date


def turnover_cv(history: pd.DataFrame) -> pd.Series:
    """Coefficient of variation of daily turnover over each symbol's last WINDOW sessions (gap-free only)."""
    wide = history.pivot_table(index="date", columns="symbol", values="turnover", aggfunc="last").sort_index()
    out: dict[str, float] = {}
    for symbol in wide.columns:
        t = wide[symbol].dropna()
        if len(t) < WINDOW:
            continue
        t = t.iloc[-WINDOW:]
        if len(t) != len(wide.loc[t.index[0]:t.index[-1]]):
            continue  # a gap in the window
        mean = float(t.mean())
        if not mean > 0:
            continue
        cv = float(t.std(ddof=0)) / mean
        if cv > 1e-12:
            out[symbol] = cv
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """Log of the median turnover CV over the stock's own; steady trading bullish."""
    if history.empty or "turnover" not in history.columns:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)
    dates = np.sort(history["date"].unique())[-(WINDOW + SLACK):]
    history = history[history["date"].isin(dates)]
    cv = turnover_cv(history)
    if len(cv) < 2:
        return pd.Series(dtype=float)
    sc = np.log(cv.median()) - np.log(cv)
    sc = sc[sc.abs() > 1e-12]
    return sc.astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "H03 turnover variability: insufficient or gapped history, or at the median, abstain"
    value = float(sc[symbol])
    side = "bullish" if value > 0 else "bearish"
    return (
        f"H03 turnover variability (Chordia, Subrahmanyam and Anshuman 2001): 60-day traded-value variability "
        f"{np.exp(-value):.2f}x the median, {side}"
    )
