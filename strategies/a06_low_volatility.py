"""A06: low volatility / idiosyncratic volatility (`cards/A06.yml`,
`state/queue.md` port lane).

Ported from Ang, Hodrick, Xing and Zhang (2006, JF): the paper ranks
stocks by lagged idiosyncratic volatility (the standard deviation of the
daily return left over after removing Fama-French three-factor
co-movement) and finds high-idiosyncratic-volatility stocks subsequently
underperform, low-idiosyncratic-volatility stocks subsequently
outperform. Neither the paper's own effect size nor its one-month holding
period is assumed to transfer to a one-week NSE pick (SPEC.md section 5) -
this module only computes the signal; `cards/A06.yml`'s `status` moves to
`confirmed`/`refuted` once a real train replay's edge is in.

This module measures total realised volatility of the raw daily return
series, not the paper's idiosyncratic (factor-residual) volatility - no
market, size or value factor is fitted or removed (`cards/A06.yml`'s red
flags). A realised sigma is never negative, so (like A04's range position
and A05's MAX/sigma) it is not directly signed around zero the way A01's
trailing return is - this card centres `RECENT_WINDOW`-day sigma against
a `BASELINE_WINDOW`-day baseline immediately preceding it (non-overlapping,
the same boundary trick A02 and A05 use so the window being judged can't
inflate the yardstick it's judged against): `ratio = sigma_recent /
sigma_baseline`; `score = 1 - ratio`, so a stock calmer than its own
recent normal (ratio < 1) scores bullish, and one more turbulent than its
own recent normal (ratio > 1) scores bearish - the same "sign gives
direction, magnitude gives conviction" convention every other card on
this roster uses.

Per SPEC.md section 2, both windows are computed on the adjusted close
series (`scripts.adjustments.compute_adjustment_factors`), so a split or
bonus inside either window doesn't masquerade as a real daily return.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

RECENT_WINDOW = 20
BASELINE_WINDOW = 60

# Closes needed: BASELINE_WINDOW + 1 closes for the baseline window's own
# BASELINE_WINDOW returns, plus RECENT_WINDOW more closes for the recent
# window's own RECENT_WINDOW returns (the baseline window's last close
# doubles as the recent window's first close, the same boundary-sharing
# A05 uses between its sigma window and its MAX window).
MIN_ROWS = RECENT_WINDOW + BASELINE_WINDOW + 1


def _returns(closes: np.ndarray) -> np.ndarray:
    prior = closes[:-1]
    current = closes[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(prior != 0, (current - prior) / prior, 0.0)


def _recent_over_baseline(close: pd.Series) -> float | None:
    """`ratio = sigma_recent / sigma_baseline`, or `None` if the baseline
    sigma can't be estimated."""
    closes = close.to_numpy()[-MIN_ROWS:]
    baseline_closes = closes[: BASELINE_WINDOW + 1]
    recent_closes = closes[-(RECENT_WINDOW + 1) :]

    sigma_baseline = _returns(baseline_closes).std(ddof=0)
    if sigma_baseline == 0 or pd.isna(sigma_baseline):
        return None

    sigma_recent = _returns(recent_closes).std(ddof=0)
    return float(sigma_recent / sigma_baseline)


def score(history: pd.DataFrame) -> pd.Series:
    """One low-volatility score per symbol with at least `MIN_ROWS` rows
    of history.

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
        ratio = _recent_over_baseline(group["adj_close"])
        if ratio is None or pd.isna(ratio):
            continue
        out[symbol] = 1.0 - ratio
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "A06 low volatility: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    ratio = _recent_over_baseline(adjusted["adj_close"])
    if ratio is None or pd.isna(ratio):
        return "A06 low volatility: zero trailing baseline volatility, abstain"

    vol_score = 1.0 - ratio
    direction = "bullish" if vol_score > 0 else "bearish" if vol_score < 0 else "neutral"
    return (
        "A06 low volatility (Ang, Hodrick, Xing and Zhang 2006): "
        f"trailing {RECENT_WINDOW}-day sigma is {ratio:.2f}x the trailing "
        f"{BASELINE_WINDOW}-day baseline -> score {vol_score:+.4f} ({direction})"
    )
