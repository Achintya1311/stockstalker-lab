"""T18: Ichimoku cloud (`cards/T18.yml`, `state/queue.md` port lane).

Hosoda's Ichimoku Kinko Hyo with the standard 9/26/52 periods. `cards/catalog.csv`:
price above the cloud with Tenkan above Kijun bullish, the reverse bearish.

The lab's reading, on the adjusted daily series (SPEC.md section 2), all from rows
already visible on the last bar:

- Tenkan = midpoint of the 9-day high and low; Kijun = the same over 26 days;
- the cloud on the last bar is the one plotted 26 bars earlier: Senkou A =
  (Tenkan + Kijun) / 2 and Senkou B = the 52-day midpoint, both as of 26 bars ago.

Score: `(close - cloud top) / close` when the close is above the cloud and Tenkan
is above Kijun (bullish, positive); `(close - cloud bottom) / close` when the close
is below the cloud and Tenkan is below Kijun (bearish, negative). Anything else
abstains. The size is how far the close is from the cloud.

Only the trailing `MIN_ROWS` rows are read (`state/engine-issues.md`'s "Replay took
1h45m+" WATCH); the cloud needs 52 + 26 of them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

TENKAN = 9
KIJUN = 26
SENKOU_B = 52
SHIFT = 26
MIN_ROWS = 120


def _mid(high: pd.Series, low: pd.Series, window: int) -> pd.Series:
    return (high.rolling(window).max() + low.rolling(window).min()) / 2.0


def lines(frame: pd.DataFrame) -> tuple[float, float, float, float, float]:
    """(close, tenkan, kijun, cloud top, cloud bottom) on the last row of `frame`."""
    tail = frame.iloc[-MIN_ROWS:]
    high = tail["adj_high"].astype(float)
    low = tail["adj_low"].astype(float)
    tenkan = _mid(high, low, TENKAN)
    kijun = _mid(high, low, KIJUN)
    span_a = ((tenkan + kijun) / 2.0).shift(SHIFT)
    span_b = _mid(high, low, SENKOU_B).shift(SHIFT)
    a, b = float(span_a.iloc[-1]), float(span_b.iloc[-1])
    close = float(tail["adj_close"].iloc[-1])
    return close, float(tenkan.iloc[-1]), float(kijun.iloc[-1]), max(a, b), min(a, b)


def _cloud_score(frame: pd.DataFrame) -> float:
    close, tenkan, kijun, top, bottom = lines(frame)
    if not close > 0 or np.isnan(top) or np.isnan(bottom):
        return float("nan")
    if close > top and tenkan > kijun:
        return (close - top) / close
    if close < bottom and tenkan < kijun:
        return (close - bottom) / close
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """Score for symbols clear of their cloud with Tenkan/Kijun agreeing; every
    other symbol abstains."""
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
        value = _cloud_score(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T18 Ichimoku: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    close, tenkan, kijun, top, bottom = lines(frame)
    value = _cloud_score(frame)
    detail = f"close {close:.2f}, cloud {bottom:.2f}-{top:.2f}, Tenkan {tenkan:.2f} vs Kijun {kijun:.2f}"
    if np.isnan(value):
        return f"T18 Ichimoku: {detail}, abstain"
    side = "bullish (above cloud, Tenkan above Kijun)" if value > 0 else "bearish (below cloud, Tenkan below Kijun)"
    return f"T18 Ichimoku: {detail}, {side}"
