"""A02: daily reversal after an extreme day (`cards/A02.yml`, `state/queue.md` port lane).

Microstructure literature on short-horizon reversal (no single canonical
paper; see `cards/A02.yml`'s `source_url`/`author`): after a liquidity-driven
extreme day, the next day's price partly reverses. Neither this module nor
the catalog assumes the claim true (SPEC.md section 5) - `cards/A02.yml`'s
`status` moves to `confirmed`/`refuted` once a real train replay's edge is
in.

Unlike A01 (continuous, never abstains once there is enough history), A02
is selective (SPEC.md section 3): it only scores a symbol whose most recent
close-to-close return is at least `Z_THRESHOLD` trailing-volatility sigmas
in magnitude, abstaining otherwise. `score = -z` where
`z = yesterday_return / sigma`, so a large down day gives a large positive
(bullish) score and a large up day a large negative (bearish) one - the same
sign convention `strategies/a01_weekly_reversal.py` and
`strategies/champion_v1.py` use.

`sigma` is estimated from the `SIGMA_WINDOW` daily returns immediately
before the move day itself, deliberately excluding that day's own return,
so an extreme day cannot inflate the very volatility estimate used to judge
how extreme it was.

Per SPEC.md section 2, returns are computed on the adjusted close series
(`scripts.adjustments.compute_adjustment_factors`), so a split or bonus
inside the window doesn't masquerade as a real move. `history` is whatever
truncated slice `engine.replay` hands this module (never the full dataset):
for a day pick made at today's open, the last row visible is yesterday's
close, so "yesterday's return" and "the sigma window before it" are both
already in the past without this module doing any date arithmetic.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

SIGMA_WINDOW = 20
Z_THRESHOLD = 2.0

# Closes needed: SIGMA_WINDOW + 1 closes to form SIGMA_WINDOW trailing
# returns (excluding the move day), plus the move day's own close and the
# close before it to form the move day's own return - the move day's "close
# before it" is already the last of the SIGMA_WINDOW + 1, so the total is
# SIGMA_WINDOW + 2 closes.
MIN_ROWS = SIGMA_WINDOW + 2


def _move_day_z(close: pd.Series) -> float | None:
    """`z` for the most recent close-to-close return, or `None` if the
    trailing sigma can't be estimated (zero volatility, e.g. a frozen price)."""
    closes = close.to_numpy()
    move_day_return = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] != 0 else 0.0

    window_closes = closes[-(SIGMA_WINDOW + 2) : -1]  # SIGMA_WINDOW + 1 closes, move day's own close excluded
    window_returns = (window_closes[1:] - window_closes[:-1]) / window_closes[:-1]
    sigma = window_returns.std(ddof=0)
    if sigma == 0 or pd.isna(sigma):
        return None
    return float(move_day_return / sigma)


def score(history: pd.DataFrame) -> pd.Series:
    """One reversal score per symbol whose most recent move clears `Z_THRESHOLD`.

    A symbol with too little history, a zero/undefined sigma, or a move
    inside the threshold abstains (left out of the returned Series) rather
    than falling back to a default score that would masquerade as a real
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
        z = _move_day_z(group["adj_close"])
        if z is None or abs(z) < Z_THRESHOLD:
            continue
        out[symbol] = -z
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "A02 extreme-day reversal: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    z = _move_day_z(adjusted["adj_close"])
    if z is None:
        return "A02 extreme-day reversal: zero trailing volatility, abstain"
    if abs(z) < Z_THRESHOLD:
        return (
            f"A02 extreme-day reversal: yesterday's move was {z:+.2f} sigma, "
            f"below the {Z_THRESHOLD:.1f}-sigma threshold, abstain"
        )
    reversal_score = -z
    direction = "bullish" if reversal_score > 0 else "bearish"
    return (
        "A02 extreme-day reversal (microstructure liquidity-overreaction literature): "
        f"yesterday's move {z:+.2f} sigma -> reversal score {reversal_score:+.4f} ({direction})"
    )
