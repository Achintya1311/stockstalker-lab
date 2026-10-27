"""G04: realized skewness (`cards/G04.yml`, `state/queue.md` port lane).

Amaya, Christoffersen, Jacobs and Vasquez (2015), "Does realized skewness predict the
cross-section of equity returns?", Journal of Financial Economics (X04): stocks whose
recent returns were most negatively skewed earn more the following week than the most
positively skewed (lottery-like) ones. The paper uses intraday returns over a week; the
lab's data is daily, so the reading is the sample skewness of the last `WINDOW` daily
log returns of the adjusted close (SPEC.md section 2):

    score = -skew

Most negative skew bullish, most positive bearish. Related to A05 (`strategies/a05_max_effect.py`,
the single largest day) but using the whole 20-day distribution. A flat series abstains.

Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20
MIN_ROWS = WINDOW + 1


def skewness(frame: pd.DataFrame) -> float:
    """Population skewness of the last WINDOW daily log returns; NaN when they do not vary."""
    close = frame["adj_close"].to_numpy(float)[-MIN_ROWS:]
    r = np.log(close[1:] / close[:-1])
    d = r - r.mean()
    m2 = float(np.mean(d**2))
    if not m2 > 0 or not np.isfinite(m2):
        return float("nan")
    return float(np.mean(d**3) / m2**1.5)


def _score(frame: pd.DataFrame) -> float:
    s = skewness(frame)
    return float("nan") if np.isnan(s) or s == 0.0 else -s


def score(history: pd.DataFrame) -> pd.Series:
    """Minus the 20-session realized skewness, per symbol."""
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        value = _score(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS)
    if len(sub) < MIN_ROWS:
        return "G04 realized skewness: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    value = _score(frame)
    if np.isnan(value):
        return "G04 realized skewness: flat returns, abstain"
    side = "bullish (negatively skewed)" if value > 0 else "bearish (lottery-like, positively skewed)"
    return f"G04 realized skewness: 20-session skew {-value:+.2f}, {side}"
