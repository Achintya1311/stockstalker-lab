"""T20: volume breakout (`cards/T20.yml`, `state/queue.md` port lane).

Practitioner rule, also a PKScreener scan: a stock that closes near the top of
its day's range on unusually heavy volume continues the next day.
`cards/catalog.csv`: close in the top 25% of the day's range on volume over 2x
the 20-day average: bullish next day (mirror for bearish).

The lab's reading, on the last visible session (the day before the pick):

- close location = (close - low) / (high - low), on that session's own bar
  (a ratio, so the price adjustment does not matter; raw prices are used);
- volume ratio = that session's volume / mean volume of the 20 sessions
  before it (the session itself is not in its own baseline);
- bullish if close location >= 0.75 and volume ratio > 2; bearish if close
  location <= 0.25 and volume ratio > 2; otherwise abstain (also when
  high == low).

Score: the volume ratio, signed by side, so the heaviest-volume breakouts
rank first. Day horizon only.

Distinct from `strategies/a07_high_volume_premium.py`, which scores a
multi-day volume z-score with no price condition. Volume is not
split-adjusted here: a split inside the 20-day window would inflate the ratio
for that window (red flag in the card).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BASELINE = 20
VOL_MULT = 2.0
TOP, BOTTOM = 0.75, 0.25
MIN_ROWS = BASELINE + 1


def _signal(group: pd.DataFrame) -> float:
    tail = group.iloc[-MIN_ROWS:]
    last = tail.iloc[-1]
    rng = float(last["high"]) - float(last["low"])
    if not rng > 0:
        return float("nan")
    base = float(tail["volume"].iloc[:-1].mean())
    if not base > 0:
        return float("nan")
    ratio = float(last["volume"]) / base
    if not ratio > VOL_MULT:
        return float("nan")
    location = (float(last["close"]) - float(last["low"])) / rng
    if location >= TOP:
        return ratio
    if location <= BOTTOM:
        return -ratio
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """Score for symbols whose last session was a volume breakout; every other
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

    out: dict[str, float] = {}
    for symbol, group in history.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        value = _signal(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T20 volume breakout: insufficient history, abstain"
    value = _signal(sub)
    if np.isnan(value):
        return "T20 volume breakout: no close at a range extreme on 2x volume, abstain"
    side = "bullish (close in top quarter of range)" if value > 0 else "bearish (close in bottom quarter)"
    return f"T20 volume breakout: {side} on {abs(value):.1f}x the 20-day volume"
