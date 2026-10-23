"""Shared core for T08's two catalog-stated variants (`cards/T08.yml`):
Donchian/Turtle channel breakout, parameterized by lookback window. The
catalog's own `default_params` names both 20 and 55 as the rule's stated
defaults (Faith's Turtle System 1 and System 2), not a single number with
an unstated alternative - so both are tested as independent trials
(`t08_donchian_breakout_20.py`, `t08_donchian_breakout_55.py`), sharing
every line of logic except the window length, the same shared-core shape
`d02_stock_pcr_core.py` already uses for its own two catalog-stated
variants.

Breakout is read against the PRIOR window's high/low, not a window that
includes today's own close: Faith's own Turtle rule is "price exceeds the
highest high of the preceding N days," and a window that included today
would make every bar trivially "at the high" of its own window by
construction (a value is always <= the max of a set containing itself),
which could never distinguish a real breakout from an ordinary bar.
Catalog's own "close at a 20-day high" is read the same way T07 reads
"then" or T04 reads its conjunction: the narrowest claim the engine's
single-bar interface can test, not the most literal parse of eight words
(see `cards/T08.yml`'s red_flags for this choice).

A tie (close exactly equal to the prior window's high or low) does not
count as a new breakout - same "strictly outside" convention T06's %B
cards already use at their own boundaries.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors


def _breakout_score(close: pd.Series, window: int) -> float:
    """`close` must already be the trailing `window + 1` rows (the
    `window` prior sessions plus today's own row), sorted by date. NaN
    means abstain: today's close sits at or inside the prior window's
    range, or the prior high/low is zero (can't be scaled)."""
    prior = close.iloc[:-1]
    latest = float(close.iloc[-1])
    prior_high = float(prior.max())
    prior_low = float(prior.min())

    if latest > prior_high:
        return float("nan") if prior_high == 0 else (latest - prior_high) / abs(prior_high)
    if latest < prior_low:
        return float("nan") if prior_low == 0 else (latest - prior_low) / abs(prior_low)
    return float("nan")


def score(history: pd.DataFrame, window: int) -> pd.Series:
    """One breakout score per symbol with at least `window + 1` rows of
    history; everything else (too little history, or no breakout on the
    latest bar) abstains (left out of the returned Series, same
    convention every other card here uses)."""
    if history.empty:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    min_rows = window + 1
    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < min_rows:
            continue
        group = group.sort_values("date")
        close = group["adj_close"].tail(min_rows)
        value = _breakout_score(close, window)
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def reasoning(history: pd.DataFrame, symbol: str, window: int, label: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    min_rows = window + 1
    if len(sub) < min_rows:
        return f"T08 Donchian breakout ({label}-day): insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    close = adjusted["adj_close"].tail(min_rows)
    value = _breakout_score(close, window)
    prior = close.iloc[:-1]
    if pd.isna(value):
        return (
            f"T08 Donchian breakout ({label}-day): close {float(close.iloc[-1]):.4f} "
            f"within prior {label}-day range [{float(prior.min()):.4f}, {float(prior.max()):.4f}], abstain"
        )
    direction = "bullish (new prior-window high)" if value > 0 else "bearish (new prior-window low)"
    return f"T08 Donchian breakout ({label}-day): score {value:+.4f} ({direction})"
