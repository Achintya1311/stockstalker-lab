"""T19: OBV divergence (`cards/T19.yml`, `state/queue.md` port lane).

Granville (1963)'s on-balance volume adds the day's volume on an up close and
subtracts it on a down close. `cards/catalog.csv`: price making a lower low
while OBV makes a higher low is bullish, the reverse bearish, over a 20-day
swing window.

The lab's reading, on the last 2 x `SWING` sessions split into a prior and a
recent window of `SWING` sessions each:

- OBV is built over those sessions from 0 (only differences of OBV are
  compared, so the starting level does not matter), with up/down days from
  the adjusted close (SPEC.md section 2) and raw volume;
- bullish: the recent window's lowest close is below the prior window's
  lowest close, and the recent window's lowest OBV is above the prior
  window's lowest OBV;
- bearish: the recent window's highest close is above the prior window's,
  and its highest OBV is below the prior window's;
- otherwise, or if both hold at once, abstain.

Score: the OBV gap between the two windows' extremes, divided by the total
volume traded over the 2 x `SWING` sessions, signed by side, so a wider
divergence ranks first.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

SWING = 20
MIN_ROWS = 2 * SWING + 1


def _divergence(frame: pd.DataFrame) -> float:
    tail = frame.iloc[-MIN_ROWS:]
    close = tail["adj_close"].to_numpy(dtype=float)
    volume = tail["volume"].to_numpy(dtype=float)
    step = np.sign(np.diff(close)) * volume[1:]
    obv = np.cumsum(step)
    px = close[1:]
    total = float(volume[1:].sum())
    if not total > 0:
        return float("nan")
    prior, recent = slice(0, SWING), slice(SWING, 2 * SWING)

    lower_low = px[recent].min() < px[prior].min()
    obv_higher_low = obv[recent].min() > obv[prior].min()
    higher_high = px[recent].max() > px[prior].max()
    obv_lower_high = obv[recent].max() < obv[prior].max()

    bullish = lower_low and obv_higher_low
    bearish = higher_high and obv_lower_high
    if bullish and not bearish:
        return float((obv[recent].min() - obv[prior].min()) / total)
    if bearish and not bullish:
        return float(-(obv[prior].max() - obv[recent].max()) / total)
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """Score for symbols showing a price/OBV divergence; every other symbol
    abstains."""
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
        value = _divergence(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T19 OBV divergence: insufficient history, abstain"
    value = _divergence(compute_adjustment_factors(sub))
    if np.isnan(value):
        return "T19 OBV divergence: no divergence between the last two 20-session windows, abstain"
    side = "bullish (lower price low, higher OBV low)" if value > 0 else "bearish (higher price high, lower OBV high)"
    return f"T19 OBV divergence: {side}, gap {abs(value):.1%} of window volume"
