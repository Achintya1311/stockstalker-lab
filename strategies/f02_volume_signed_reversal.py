"""F02: volume-signed one-day reversal (`cards/F02.yml`, `state/queue.md` port lane).

Alpha#12 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from
the paper's formula, SPEC.md section 5): sign(delta(volume, 1)) * (-1 * delta(close, 1)).
The lab's reading, on the adjusted close and raw volume of the last two bars
(SPEC.md section 2), with the one-day log return in place of the raw price change so
stocks on different price scales rank together:

    score = sign(volume today - volume yesterday) * -(log close today - log close yesterday)

On rising volume a fall scores bullish and a rise bearish (a reversal); on falling
volume a rise scores bullish and a fall bearish (a continuation). Unchanged volume
or an unchanged close abstains.

Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

MIN_ROWS = 2


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(sign of the volume change, one-day log return) on the last bar of `frame`."""
    close = frame["adj_close"].to_numpy(float)[-2:]
    volume = frame["volume"].to_numpy(float)[-2:]
    return float(np.sign(volume[1] - volume[0])), float(np.log(close[1] / close[0]))


def _score(frame: pd.DataFrame) -> float:
    dv, r1 = parts(frame)
    if dv == 0.0 or r1 == 0.0 or not np.isfinite(r1):
        return float("nan")
    return -dv * r1


def score(history: pd.DataFrame) -> pd.Series:
    """Volume-signed reversal of the last day's return, per symbol."""
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
        return "F02 volume-signed reversal: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    dv, r1 = parts(frame)
    value = _score(frame)
    if np.isnan(value):
        return "F02 volume-signed reversal: unchanged volume or close, abstain"
    volume = "rising" if dv > 0 else "falling"
    kind = "reversal" if dv > 0 else "continuation"
    side = "bullish" if value > 0 else "bearish"
    return f"F02 volume-signed reversal (Alpha#12): last day {r1:+.1%} on {volume} volume, {kind}, {side}"
