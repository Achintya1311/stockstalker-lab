"""T17: Keltner channel breakout (`cards/T17.yml`, `state/queue.md` port lane).

Keltner (1960), in the ATR form popularised by Raschke: a channel of a 20-day
EMA of the close plus and minus 2 x ATR. `cards/catalog.csv`: close above the
upper channel bullish, below the lower bearish.

The lab's reading, on the adjusted series (SPEC.md section 2):

- middle = EMA(close, 20), `ewm(span=20, adjust=False)`;
- ATR = simple mean of the last 20 true ranges, true range =
  max(high, previous close) - min(low, previous close);
- upper / lower = middle +/- 2 x ATR.

Score: `(close - upper) / ATR` when the close is above the upper channel
(bullish, positive), `(close - lower) / ATR` when below the lower (bearish,
negative); inside the channel abstains. The size is how many ATRs the close
cleared the band by.

Only the trailing `MIN_ROWS` rows are read (`state/engine-issues.md`'s
"Replay took 1h45m+" WATCH). The EMA is seeded on the first of them; with
alpha = 2/21 the seed's weight is (19/21)^(MIN_ROWS-1), below 1e-8.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

EMA_SPAN = 20
ATR_WINDOW = 20
MULT = 2.0
MIN_ROWS = 200


def channel(frame: pd.DataFrame) -> tuple[float, float, float, float]:
    """(close, upper, lower, atr) for the last row of `frame`'s adjusted columns."""
    tail = frame.iloc[-MIN_ROWS:]
    close = tail["adj_close"].astype(float)
    high = tail["adj_high"].astype(float)
    low = tail["adj_low"].astype(float)
    prev = close.shift(1)
    tr = pd.concat([high, prev], axis=1).max(axis=1) - pd.concat([low, prev], axis=1).min(axis=1)
    atr = float(tr.iloc[-ATR_WINDOW:].mean())
    middle = float(close.ewm(span=EMA_SPAN, adjust=False).mean().iloc[-1])
    return float(close.iloc[-1]), middle + MULT * atr, middle - MULT * atr, atr


def _breakout_score(frame: pd.DataFrame) -> float:
    close, upper, lower, atr = channel(frame)
    if not atr > 0:
        return float("nan")
    if close > upper:
        return (close - upper) / atr
    if close < lower:
        return (close - lower) / atr
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """Score for symbols closing outside their Keltner channel; every other
    symbol abstains."""
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
        value = _breakout_score(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T17 Keltner breakout: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    close, upper, lower, atr = channel(frame)
    value = _breakout_score(frame)
    if np.isnan(value):
        return f"T17 Keltner breakout: close {close:.2f} inside {lower:.2f}-{upper:.2f}, abstain"
    side = "bullish (above upper)" if value > 0 else "bearish (below lower)"
    return f"T17 Keltner breakout: close {close:.2f}, channel {lower:.2f}-{upper:.2f}, {side} by {abs(value):.2f} ATR"
