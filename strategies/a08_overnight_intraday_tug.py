"""A08: overnight vs intraday tug of war (`cards/A08.yml`, `state/queue.md` port lane).

Ported from Lou, Polk and Skouras (2019, JFE): a stock's recent return is
split into its overnight (close-to-open gap) and intraday (open-to-close)
components, which pull in opposite directions going forward - a stock
whose recent gains came mostly overnight tends to give some back intraday,
and one whose recent gains came mostly intraday tends to keep earning them
intraday. Not assumed true here (SPEC.md section 5) until a real train
replay's edge is in; `cards/A08.yml`'s `status` moves to
`confirmed`/`refuted` then.

Picked ahead of the indicator rules in the catalog's testing order because
our own day picks are open-to-close by construction (SPEC.md section 1) -
this card's predicted quantity and our scored outcome are the same thing.

`score = avg_intraday - avg_overnight` over the trailing `WINDOW` days:
strong recent overnight gains with weak intraday gains score negative
(bearish), and the reverse scores positive (bullish), matching
`cards/A08.yml`'s rule with no sign flip.

Per SPEC.md section 2, the overnight leg (`adj_open_t / adj_close_(t-1)`)
uses the split/bonus-adjusted series (`scripts.adjustments`) so a
corporate action between a close and the next open doesn't masquerade as
a real gap. The intraday leg (`adj_close_t / adj_open_t`) needs no
adjustment - both prices are the same row, so the same day's `adj_factor`
cancels - but is taken from the same adjusted frame for a single
consistent column set. `history` is whatever truncated slice
`engine.replay` hands this module: for a day pick made at today's open,
the last row visible is yesterday's close, so every day in the trailing
window is already fully observed without this module doing any date
arithmetic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20

# WINDOW days of overnight/intraday returns need WINDOW+1 closes (each
# day's overnight return needs the close of the day before it, and the
# first of the WINDOW days needs one extra row before it for that).
MIN_ROWS = WINDOW + 1


def _tug_score(adj_open: pd.Series, adj_close: pd.Series) -> float | None:
    """`avg_intraday - avg_overnight` over the trailing `WINDOW` days, or
    `None` if any price in the window is non-positive (can't form a
    return)."""
    opens = adj_open.to_numpy()[-MIN_ROWS:]
    closes = adj_close.to_numpy()[-MIN_ROWS:]

    prior_closes = closes[:-1]  # close_(t-1) for each of the WINDOW days
    window_opens = opens[1:]  # open_t for each of the WINDOW days
    window_closes = closes[1:]  # close_t for each of the WINDOW days

    if (prior_closes <= 0).any() or (window_opens <= 0).any():
        return None

    overnight_returns = window_opens / prior_closes - 1.0
    intraday_returns = window_closes / window_opens - 1.0

    avg_overnight = overnight_returns.mean()
    avg_intraday = intraday_returns.mean()
    score = float(avg_intraday - avg_overnight)
    return score if np.isfinite(score) else None


def score(history: pd.DataFrame) -> pd.Series:
    """One tug-of-war score per symbol with at least `MIN_ROWS` rows of history.

    A symbol with too little history, or any non-positive price in its
    window, abstains (left out of the returned Series) rather than
    falling back to a default score that would masquerade as a real
    reading.
    """
    if history.empty:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/champion_v1.py`'s identical prefilter): a symbol with
        # no F&O future anywhere in its visible history can never survive
        # the downstream universe restriction regardless of what it scores
        # here, and skipping it here avoids recomputing adjustment factors
        # over the full EQ series on every pick date.
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        group = group.sort_values("date")
        tug = _tug_score(group["adj_open"], group["adj_close"])
        if tug is None or pd.isna(tug):
            continue
        out[symbol] = tug
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "A08 overnight/intraday tug of war: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    tug = _tug_score(adjusted["adj_open"], adjusted["adj_close"])
    if tug is None or pd.isna(tug):
        return "A08 overnight/intraday tug of war: non-positive price in window, abstain"

    direction = "bullish" if tug > 0 else "bearish" if tug < 0 else "neutral"
    return (
        "A08 overnight/intraday tug of war (Lou, Polk and Skouras 2019): "
        f"trailing {WINDOW}-day avg intraday minus avg overnight return is "
        f"{tug:+.4f} -> score {tug:+.4f} ({direction})"
    )
