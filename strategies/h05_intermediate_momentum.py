"""H05: intermediate momentum, 12-7 months (`cards/H05.yml`, `state/queue.md` port lane).

Novy-Marx (2012), "Is momentum really momentum?", Journal of Financial Economics
103(3) (replicated in Open Source Asset Pricing, X05): returns from 12 to 7 months
back predict better than the most recent six months. Here, on split/bonus-adjusted
closes, the return from `FAR_DAYS` sessions back to `NEAR_DAYS` sessions back (252 to
126), skipping the latest `NEAR_DAYS` sessions. Score = that return; the biggest
past gain is bullish, the biggest past loss bearish. A03 (12-1) differs by including
months 7 to 2. Each stock uses only its own rows; a stock with fewer than
`MIN_ROWS` rows abstains.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

FAR_DAYS = 252
NEAR_DAYS = 126
MIN_ROWS = FAR_DAYS + 1


def _formation_return(close: pd.Series) -> float:
    far = close.iloc[-(FAR_DAYS + 1)]
    near = close.iloc[-(NEAR_DAYS + 1)]
    if not far > 0:
        return float("nan")
    return float(near / far - 1.0)


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see `strategies/a03_momentum_12_1.py`).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)
    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        value = _formation_return(group.sort_values("date")["adj_close"])
        if value == value and abs(value) > 1e-12:
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "H05 intermediate momentum: insufficient history, abstain"
    value = _formation_return(compute_adjustment_factors(sub)["adj_close"])
    side = "bullish" if value > 0 else "bearish"
    return (
        f"H05 intermediate momentum (Novy-Marx 2012): return from {FAR_DAYS} to {NEAR_DAYS} sessions back "
        f"{value:+.2%}, {side}"
    )
