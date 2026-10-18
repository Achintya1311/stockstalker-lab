"""A09: gap fade, one-day-lagged (`cards/A09.yml`, `state/queue.md` port lane).

Practitioner gap-trading folklore (no single canonical paper; see
`cards/A09.yml`'s `source_url`/`author`): a stock that opens well away from
its prior close tends to partly retrace that gap during the same session,
so fading the gap direction has an edge for that day's open-to-close move.
Not assumed true here (SPEC.md section 5) until a real train replay's edge
is in - `cards/A09.yml`'s `status` moves to `confirmed`/`refuted` then.

The catalog's rule, read literally, needs the *pick date's own* open to
decide the pick date's own direction. `engine/replay.py`'s `truncate()`
withholds the pick date's own row from every strategy by construction
(B4), so that literal same-day trade cannot be computed here - not a bug
in this module, a structural property of the engine any "gap" strategy
hits. `cards/A09.yml`'s `rules_plain` explains the reinterpretation this
module actually implements: *yesterday's* gap (fully observed by pick
time) is used to predict *today's* open-to-close move, on the premise that
an unusually large gap's reversal need not be fully spent within its own
session.

`score = -z`, where `z = yesterday's gap / sigma` and `sigma` is the
population std of the `SIGMA_WINDOW` gaps immediately before yesterday's
(yesterday's own gap excluded, so it cannot inflate the sigma used to
judge how large it was) - the same shape of z-score
`strategies/a02_extreme_day_reversal.py` computes on close-to-close
returns, applied here to the close-to-open gap component instead. A
symbol whose yesterday's gap doesn't clear `Z_THRESHOLD` sigmas abstains.

Per SPEC.md section 2, the gap (`adj_open_t / adj_close_(t-1)`) uses the
split/bonus-adjusted series (`scripts.adjustments`) so a corporate action
between a close and the next open doesn't masquerade as a real gap, exactly
as A08 already does for its own overnight leg. `history` is whatever
truncated slice `engine.replay` hands this module: for a day pick made at
today's open, the last row visible is yesterday's close (with yesterday's
open also visible, since the whole row is included), so "yesterday's gap"
and the sigma window before it are both already in the past without this
module doing any date arithmetic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

SIGMA_WINDOW = 20
Z_THRESHOLD = 2.0

# SIGMA_WINDOW gaps (sigma baseline, excluding yesterday's own) plus
# yesterday's own gap = SIGMA_WINDOW + 1 gaps needed. Each gap needs that
# day's open and the close of the day before it, so SIGMA_WINDOW + 1 gaps
# need SIGMA_WINDOW + 2 rows (one extra row at the start to supply the
# first gap's "close of the day before").
MIN_ROWS = SIGMA_WINDOW + 2


def _yesterdays_gap_z(adj_open: pd.Series, adj_close: pd.Series) -> float | None:
    """`z` for the most recent (yesterday's) gap, or `None` if the trailing
    sigma can't be estimated (zero gap volatility) or a price is non-positive."""
    opens = adj_open.to_numpy()[-MIN_ROWS:]
    closes = adj_close.to_numpy()[-MIN_ROWS:]

    prior_closes = closes[:-1]  # close_(t-1) for each of the SIGMA_WINDOW + 1 gap days
    gap_opens = opens[1:]  # open_t for each of the SIGMA_WINDOW + 1 gap days

    if (prior_closes <= 0).any() or (gap_opens <= 0).any():
        return None

    gaps = gap_opens / prior_closes - 1.0
    window_gaps = gaps[:-1]  # SIGMA_WINDOW gaps, yesterday's own excluded
    yesterdays_gap = gaps[-1]

    sigma = window_gaps.std(ddof=0)
    if sigma == 0 or pd.isna(sigma):
        return None
    z = yesterdays_gap / sigma
    return float(z) if np.isfinite(z) else None


def score(history: pd.DataFrame) -> pd.Series:
    """One gap-fade score per symbol whose yesterday's gap clears `Z_THRESHOLD`.

    A symbol with too little history, a zero/undefined sigma, a
    non-positive price in the window, or a gap inside the threshold
    abstains (left out of the returned Series) rather than falling back to
    a default score that would masquerade as a real reading.
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
        z = _yesterdays_gap_z(group["adj_open"], group["adj_close"])
        if z is None or abs(z) < Z_THRESHOLD:
            continue
        out[symbol] = -z
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "A09 gap fade (1-day lag): insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    z = _yesterdays_gap_z(adjusted["adj_open"], adjusted["adj_close"])
    if z is None:
        return "A09 gap fade (1-day lag): zero trailing gap volatility or non-positive price, abstain"
    if abs(z) < Z_THRESHOLD:
        return (
            f"A09 gap fade (1-day lag): yesterday's gap was {z:+.2f} sigma, "
            f"below the {Z_THRESHOLD:.1f}-sigma threshold, abstain"
        )
    fade_score = -z
    direction = "bullish" if fade_score > 0 else "bearish"
    return (
        "A09 gap fade, 1-day lag (practitioner gap-trading folklore, see cards/A09.yml "
        "for why this is lagged rather than same-day): "
        f"yesterday's gap {z:+.2f} sigma -> fade score {fade_score:+.4f} ({direction})"
    )
