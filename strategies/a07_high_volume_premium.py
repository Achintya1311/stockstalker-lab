"""A07: high-volume return premium (`cards/A07.yml`, `state/queue.md` port lane).

Ported from Gervais, Kaniel and Mingelgrin (2001, JF): stocks whose recent
trading volume is unusually high relative to their own trailing history
subsequently outperform, and stocks with unusually low recent volume
subsequently underperform - a visibility/investor-recognition effect, not
assumed true here (SPEC.md section 5) until a real train replay's edge is
in; `cards/A07.yml`'s `status` moves to `confirmed`/`refuted` then.

Unlike A04/A05/A06, the catalog's own rule is already directly signed:
"unusually high volume bullish, unusually low bearish" is a two-sided
z-score claim, so this module computes a plain volume z-score and uses it
as the score with no sign flip: `z = (avg_recent_volume - baseline_mean) /
baseline_std`, where `avg_recent_volume` is the mean of `RECENT_WINDOW`
trading days' volume and `baseline_mean`/`baseline_std` are the mean and
population standard deviation of daily volume over the `BASELINE_WINDOW`
trading days immediately preceding it (non-overlapping, the same
boundary trick A02/A05/A06 use so the window being judged can't inflate
the yardstick it's judged against).

Volume is used raw, not price-adjusted: a split/bonus changes share count
and so can shift raw volume independent of any real demand change
(`cards/A07.yml`'s red flags) - `scripts.adjustments` adjusts prices only,
there is no volume-adjustment in this codebase yet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RECENT_WINDOW = 5
BASELINE_WINDOW = 50

# BASELINE_WINDOW rows for the baseline, plus RECENT_WINDOW more for the
# recent window right after it; unlike A01/A06, volume needs no "+1 extra
# row" since each day's own volume (not a return between two days) is the
# raw observation.
MIN_ROWS = RECENT_WINDOW + BASELINE_WINDOW


def _volume_zscore(volume: pd.Series) -> float | None:
    """`z = (avg_recent_volume - baseline_mean) / baseline_std`, or `None`
    if the baseline standard deviation can't be estimated."""
    values = volume.to_numpy()[-MIN_ROWS:]
    baseline = values[:BASELINE_WINDOW]
    recent = values[BASELINE_WINDOW:]

    baseline_std = baseline.std(ddof=0)
    if baseline_std == 0 or pd.isna(baseline_std):
        return None

    baseline_mean = baseline.mean()
    avg_recent_volume = recent.mean()
    return float((avg_recent_volume - baseline_mean) / baseline_std)


def score(history: pd.DataFrame) -> pd.Series:
    """One volume-z-score per symbol with at least `MIN_ROWS` rows of history.

    A symbol with too little history, or a zero/undefined baseline volume
    standard deviation, abstains (left out of the returned Series) rather
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
        # here, and skipping it here avoids recomputing this over the full
        # EQ series on every pick date.
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    out: dict[str, float] = {}
    for symbol, group in history.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        group = group.sort_values("date")
        z = _volume_zscore(group["volume"])
        if z is None or pd.isna(z):
            continue
        out[symbol] = z
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "A07 high-volume return premium: insufficient history, abstain"

    z = _volume_zscore(sub["volume"])
    if z is None or pd.isna(z):
        return "A07 high-volume return premium: zero trailing baseline volume std, abstain"

    direction = "bullish" if z > 0 else "bearish" if z < 0 else "neutral"
    return (
        "A07 high-volume return premium (Gervais, Kaniel and Mingelgrin 2001): "
        f"trailing {RECENT_WINDOW}-day volume is {z:+.2f} std vs. the trailing "
        f"{BASELINE_WINDOW}-day baseline -> score {z:+.4f} ({direction})"
    )
