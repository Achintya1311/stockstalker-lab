"""A05: MAX effect / lottery stocks (`cards/A05.yml`, `state/queue.md` port lane).

Ported from Bali, Cakici and Whitelaw (2011, JFE): rank stocks by MAX, the
single largest daily close-to-close return over the trailing `MAX_WINDOW`
trading days (approximating "the past month"). The paper's own claim is
that high-MAX stocks (lottery-like: an outsized best day in recent memory)
subsequently underperform, and low-MAX stocks outperform. Neither the
paper's own effect size nor its one-month holding period is assumed to
transfer to a one-week NSE pick (SPEC.md section 5) - this module only
computes the signal; `cards/A05.yml`'s `status` moves to
`confirmed`/`refuted` once a real train replay's edge is in.

MAX itself (a maximum of a roughly mean-zero return distribution) is not
directly signed around zero the way A01's trailing return or A02's z-scored
move are - it's typically positive regardless of whether the stock is, in
the paper's own cross-sectional sense, unusually lottery-like for its own
history. This card centres MAX the same way A04 centred 52-week-high
proximity: against a per-symbol baseline rather than the paper's
cross-sectional decile sort. The baseline is `sigma`, the standard
deviation of daily returns over the `SIGMA_WINDOW` trading days
*immediately preceding* the MAX window - a separate, non-overlapping
period, so the month being judged can't inflate the yardstick it's judged
against (the same trick A02 uses to keep an extreme day out of its own
sigma estimate). `z = MAX / sigma`; `score = -z`, so an unusually large
best day relative to the stock's own normal volatility (high MAX) scores
bearish, and a muted best day relative to normal (low MAX) scores bullish -
the same "sign gives direction, magnitude gives conviction" convention
`strategies/a01_weekly_reversal.py` and `strategies/champion_v1.py` use.
This is a deliberate adaptation, not a literal replication (`cards/A05.yml`'s
red flags).

Per SPEC.md section 2, both windows are computed on the adjusted close
series (`scripts.adjustments.compute_adjustment_factors`), so a split or
bonus inside either window doesn't masquerade as a real daily return.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

MAX_WINDOW = 21
SIGMA_WINDOW = 60

# Closes needed: SIGMA_WINDOW + 1 closes for the baseline window's own
# SIGMA_WINDOW returns, plus MAX_WINDOW more closes for the MAX window's
# own MAX_WINDOW returns (the baseline window's last close doubles as the
# MAX window's first close, the same boundary-sharing A02 uses between its
# move day and its sigma window).
MIN_ROWS = MAX_WINDOW + SIGMA_WINDOW + 1


def _returns(closes: np.ndarray) -> np.ndarray:
    prior = closes[:-1]
    current = closes[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(prior != 0, (current - prior) / prior, 0.0)


def _max_over_sigma(close: pd.Series) -> float | None:
    """`z = MAX / sigma`, or `None` if the baseline sigma can't be estimated."""
    closes = close.to_numpy()[-MIN_ROWS:]
    baseline_closes = closes[: SIGMA_WINDOW + 1]
    month_closes = closes[-(MAX_WINDOW + 1) :]

    sigma = _returns(baseline_closes).std(ddof=0)
    if sigma == 0 or pd.isna(sigma):
        return None

    max_return = _returns(month_closes).max()
    return float(max_return / sigma)


def score(history: pd.DataFrame) -> pd.Series:
    """One MAX-effect score per symbol with at least `MIN_ROWS` rows of history.

    A symbol with too little history, or a zero/undefined baseline sigma,
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
        z = _max_over_sigma(group["adj_close"])
        if z is None or pd.isna(z):
            continue
        out[symbol] = -z
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "A05 MAX effect: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    z = _max_over_sigma(adjusted["adj_close"])
    if z is None or pd.isna(z):
        return "A05 MAX effect: zero trailing baseline volatility, abstain"

    max_score = -z
    direction = "bullish" if max_score > 0 else "bearish" if max_score < 0 else "neutral"
    return (
        "A05 MAX effect (Bali, Cakici and Whitelaw 2011): "
        f"best day in the trailing {MAX_WINDOW}-day window is {z:+.2f} sigma "
        f"above the trailing {SIGMA_WINDOW}-day baseline -> score {max_score:+.4f} ({direction})"
    )
