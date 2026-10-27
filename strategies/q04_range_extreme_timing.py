"""Q04: timing of the range extremes (`cards/Q04.yml`, `state/queue.md` port lane).

Alpha158's IMXD feature (microsoft/qlib, MIT; feature list in
`third_party/qlib/loader.py`): (IdxMax(high, d) - IdxMin(low, d)) / d. The lab's
reading, on the adjusted high and low (SPEC.md section 2), over the last 60
sessions including today:

- pos_high, pos_low = position (0 = oldest, 59 = today) of the 60-session high
  and low; the first occurrence wins a tie, as numpy's argmax does;
- imxd = (pos_high - pos_low) / 60, which equals days since the low minus days
  since the high, over 60. Positive (a recent high after an old low) is bullish,
  negative (a recent low after an old high) bearish, zero abstains.

Ties: imxd takes only 119 values, so the score adds a tie-break smaller than half
a step (1/120): TIE x tanh(60-session log return / 0.3), which orders stocks with
equal timing by the size of their 60-session move, in the same direction. Only the
last `WINDOW` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 60
MIN_ROWS = WINDOW
TIE = 0.008


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(imxd, r60) on the last row of `frame`; r60 is the log move across the window."""
    high = frame["adj_high"].to_numpy(float)[-WINDOW:]
    low = frame["adj_low"].to_numpy(float)[-WINDOW:]
    close = frame["adj_close"].to_numpy(float)[-WINDOW:]
    imxd = (int(np.argmax(high)) - int(np.argmin(low))) / WINDOW
    return imxd, float(np.log(close[-1] / close[0]))


def _score(frame: pd.DataFrame) -> float:
    imxd, r60 = parts(frame)
    if imxd == 0.0 or not np.isfinite(r60):
        return float("nan")
    return imxd + TIE * float(np.tanh(r60 / 0.3))


def score(history: pd.DataFrame) -> pd.Series:
    """Range-extreme timing per symbol; symbols whose high and low share a session abstain."""
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
        return "Q04 range-extreme timing: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    imxd, r60 = parts(frame)
    days = round(imxd * WINDOW)
    detail = f"60-session high {days:+d} sessions after the low, 60-session move {r60:+.1%}"
    value = _score(frame)
    if np.isnan(value):
        return f"Q04 range-extreme timing: {detail}, abstain"
    side = "bullish" if value > 0 else "bearish"
    return f"Q04 range-extreme timing: {detail}, {side}"
