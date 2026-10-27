"""F06: trend acceleration (`cards/F06.yml`, `state/queue.md` port lane).

Alpha#46 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix 27 Oct 2026, SPEC.md section 5). With
X = (delay(close, 20) - delay(close, 10)) / 10 - (delay(close, 10) - close) / 10:

    0.25 < X ? -1 : (X < 0 ? 1 : -(close - delay(close, 1)))

X is the recent 10-session slope minus the older one, so a rise that speeds up
scores -1 (faded) and one that slows down +1.

The lab's reading, on the log of the adjusted close (SPEC.md section 2), so stocks on
different price scales compare:

- older = (log close 10 back - log close 20 back) / 10, recent = (log close - log close 10 back) / 10;
- x = recent - older, a difference of average daily log returns;
- x > THRESHOLD: score = -x (bearish); x < 0: score = -x (bullish); otherwise score = -r1,
  minus today's log return.

Two departures, both forced by the top-5 table and fixed before the replay: the
paper's 0.25 is in US dollars per day and becomes THRESHOLD = 0.00625 in log-return
units (0.25 on a $40 stock); and the paper's constant -1 / +1 would make every top five
an alphabetical tie, so the score keeps the paper's sign with |x| as its size.
Zero scores abstain.

Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

HALF = 10
MIN_ROWS = 2 * HALF + 1
THRESHOLD = 0.00625


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(x, r1): recent minus older 10-session mean log return, and today's log return."""
    y = np.log(frame["adj_close"].to_numpy(float)[-MIN_ROWS:])
    older = (y[HALF] - y[0]) / HALF
    recent = (y[-1] - y[HALF]) / HALF
    return float(recent - older), float(y[-1] - y[-2])


def _score(frame: pd.DataFrame) -> float:
    x, r1 = parts(frame)
    if not np.isfinite(x):
        return float("nan")
    value = -x if (x > THRESHOLD or x < 0) else -r1
    return float("nan") if value == 0.0 else float(value)


def score(history: pd.DataFrame) -> pd.Series:
    """Alpha#46 per symbol, sized by the acceleration (or by today's move in the middle band)."""
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
        return "F06 trend acceleration: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    x, r1 = parts(frame)
    value = _score(frame)
    if np.isnan(value):
        return "F06 trend acceleration: no signal, abstain"
    if x > THRESHOLD:
        kind = "trend speeding up, faded"
    elif x < 0:
        kind = "trend slowing, read as a turn"
    else:
        kind = f"middle band, today's {r1:+.1%} reversed"
    side = "bullish" if value > 0 else "bearish"
    return f"F06 trend acceleration (Alpha#46): {x * 100:+.2f}% a day faster than the prior 10 sessions, {kind}, {side}"
