"""T14: Commodity Channel Index, CCI(20) (`cards/T14.yml`, `state/queue.md`
port lane).

Lambert's CCI(20): typical price TP = (high + low + close) / 3, compared
against its own 20-bar simple moving average, scaled by the 20-bar mean
*absolute* deviation of TP from that current SMA (not the standard
deviation T06/T07's Bollinger bands use). Like
`strategies/t05_macd_crossover.py`, the catalog's own wording ("crossing
above ... crossing below") is read as an event, not a persisted state -
this card only fires on the bar a threshold is actually crossed and
abstains on every other bar, including one where CCI already sits well
past -100 or +100 without a fresh cross that day.

`cards/T14.yml`'s claim_as_stated flags that the catalog's exact
threshold/sign pairing ("above -100 bullish, below +100 bearish") does
not match either common CCI convention this module's author is aware of
- tested literally as transcribed anyway, per SPEC.md section 5's "no
claim is assumed true."

Like `strategies/t07_bollinger_squeeze_breakout.py`, only the trailing
`MIN_ROWS` rows per symbol are ever read, not the full history a replay
slice may carry by a given date (`state/engine-issues.md`'s "Replay took
1h45m+" WATCH entry).

Per SPEC.md section 2, TP is built from the adjusted high/low/close series
(`scripts.adjustments.compute_adjustment_factors`), so a split or bonus
inside the 20-bar window doesn't masquerade as a real volatility or price
move.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

PERIOD = 20
LOWER_THRESHOLD = -100.0
UPPER_THRESHOLD = 100.0
SCALE = 0.015

# The 20-bar window needs PERIOD rows before SMA_TP/MeanDev are stable
# values, plus one more row for a prior-bar CCI to compare against for
# the cross itself.
MIN_ROWS = PERIOD + 1


def _mean_abs_dev(window: np.ndarray) -> float:
    return float(np.mean(np.abs(window - window.mean())))


def _cci(tp: pd.Series) -> pd.Series:
    sma_tp = tp.rolling(PERIOD, min_periods=PERIOD).mean()
    mean_dev = tp.rolling(PERIOD, min_periods=PERIOD).apply(_mean_abs_dev, raw=True)
    denom = SCALE * mean_dev
    cci = (tp - sma_tp) / denom.where(denom != 0)
    return cci


def _cci_score(cci_latest: float, cci_prev: float) -> float:
    """NaN means abstain (SPEC.md section 5): no fresh threshold cross on
    this bar, or CCI itself is undefined (a flat window)."""
    if pd.isna(cci_latest) or pd.isna(cci_prev):
        return float("nan")
    crossed_up = cci_prev <= LOWER_THRESHOLD and cci_latest > LOWER_THRESHOLD
    crossed_down = cci_prev >= UPPER_THRESHOLD and cci_latest < UPPER_THRESHOLD
    if crossed_up:
        return (cci_latest - LOWER_THRESHOLD) / 100.0
    if crossed_down:
        return (cci_latest - UPPER_THRESHOLD) / 100.0
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """One CCI-crossover score per symbol with at least `MIN_ROWS` rows of
    history and a fresh threshold cross on the latest bar; every other
    symbol abstains (left out of the returned Series, same convention
    every other card here uses)."""
    if history.empty:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    # Adjusted first, across the full slice (so the gap-detection compares
    # against the whole market's actual previous trading day, same as
    # every other `strategies/t0*` card), then per symbol: only the
    # trailing `MIN_ROWS` rows ever feed the rolling computation itself.
    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        group = group.sort_values("date").iloc[-MIN_ROWS:]
        tp = (group["adj_high"] + group["adj_low"] + group["adj_close"]) / 3.0
        cci = _cci(tp)
        value = _cci_score(float(cci.iloc[-1]), float(cci.iloc[-2]))
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T14 CCI: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    tail = adjusted.iloc[-MIN_ROWS:]
    tp = (tail["adj_high"] + tail["adj_low"] + tail["adj_close"]) / 3.0
    cci = _cci(tp)
    cci_latest, cci_prev = float(cci.iloc[-1]), float(cci.iloc[-2])
    value = _cci_score(cci_latest, cci_prev)
    if pd.isna(value):
        return (
            f"T14 CCI: CCI={cci_latest:.4f} (prior bar CCI={cci_prev:.4f}) "
            "-> no fresh threshold cross, abstain"
        )
    direction = "bullish (crossed up through -100)" if value > 0 else "bearish (crossed down through +100)"
    return (
        f"T14 CCI: CCI={cci_latest:.4f} (prior bar CCI={cci_prev:.4f}) "
        f"-> score {value:+.4f} ({direction})"
    )
