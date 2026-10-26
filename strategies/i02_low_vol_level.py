"""I02: Nifty Low Volatility 30 rule (`cards/I02.yml`, `state/queue.md` port lane).

NSE Indices' Nifty Low Volatility 30 picks the stocks with the lowest
volatility of daily price returns over the last year. `cards/catalog.csv`'s
reading for this lab: lowest 1-year daily volatility bullish, highest bearish.

This is a cross-sectional **level**, unlike `strategies/a06_low_volatility.py`,
which compares each stock's recent sigma with its own earlier sigma (a
change, not a level). Here a stock that is always calm stays bullish.

Per symbol: sigma = population standard deviation of the last `WINDOW` daily
log returns of the adjusted close (SPEC.md section 2). Score, per date:
`median(log sigma) - log sigma`, the median taken over every symbol scored on
that date. So the calmest stocks are the largest bullish scores and the most
volatile the largest bearish ones. The median only sets where bullish turns
bearish (it matters for the `all` selection); the `top` five on each side are
the five lowest and five highest sigmas whatever the centre is.

Unlike most cards here, the score depends on which other symbols are present
(the median). `raw_sigma` is the per-symbol reading that depends only on that
symbol's own rows; `strategies/i02_low_vol_level_audit.py` checks that, and
that the ordering between symbols is unchanged by another symbol's new row.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 252
# One extra row so there are WINDOW returns. Only the trailing MIN_ROWS rows
# per symbol are used (`state/engine-issues.md`'s "Replay took 1h45m+" WATCH).
MIN_ROWS = WINDOW + 1


def _sigma(close: pd.Series) -> float:
    tail = close.iloc[-MIN_ROWS:].to_numpy(dtype=float)
    if (tail <= 0).any():
        return float("nan")
    returns = np.diff(np.log(tail))
    sigma = float(np.std(returns))
    return sigma if sigma > 0 else float("nan")


def raw_sigma(history: pd.DataFrame) -> pd.Series:
    """Per-symbol 1-year daily sigma; symbols with too little history, or a
    flat or non-positive series, are left out."""
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        value = _sigma(group.sort_values("date")["adj_close"])
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """Positive = calmer than the date's median symbol (bullish)."""
    sigma = raw_sigma(history)
    if sigma.empty:
        return sigma
    log_sigma = np.log(sigma)
    return (log_sigma.median() - log_sigma).astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sigma = raw_sigma(history)
    if symbol not in sigma.index:
        return "I02 low volatility level: insufficient history, abstain"
    value = float(score(history)[symbol])
    direction = "bullish" if value > 0 else "bearish" if value < 0 else "neutral"
    annual = float(sigma[symbol]) * np.sqrt(252)
    rank = int((sigma <= sigma[symbol]).sum())
    return (
        f"I02 low volatility level: 1-year sigma {annual:.1%} annualised, "
        f"{rank} of {len(sigma)} from calmest -> score {value:+.4f} ({direction})"
    )
