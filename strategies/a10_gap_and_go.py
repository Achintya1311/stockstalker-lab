"""A10: gap and go, one-day-lagged (`cards/A10.yml`, `state/queue.md` port lane).

The catalog's opposite bet to A09 (`strategies/a09_gap_fade.py`): a gap up on
strong volume that closes above resistance keeps going, so it is bullish. The
pick date's own open is withheld by `engine/replay.py`'s `truncate()` (B4), so,
as A09 does, the rule reads *yesterday's* bar, fully observed at pick time:

- gap: yesterday's z (gap over the population std of the 20 gaps before it),
  computed by A09's own `_yesterdays_gap_z`; at least `Z_THRESHOLD`;
- strong volume: yesterday's volume at least `VOLUME_RATIO` x the median volume
  of the 20 sessions before it (the catalog's "opening volume" is not in the
  data, so the whole day's volume stands in, as `testable_now` says);
- above resistance: yesterday's adjusted close above the highest adjusted high
  of the 20 sessions before it.

All three met: score = z, bullish. Anything else abstains. Bullish table only;
gap downs are A09's question, not this row's.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies.a09_gap_fade import MIN_ROWS as GAP_ROWS
from strategies.a09_gap_fade import Z_THRESHOLD, _yesterdays_gap_z

LOOKBACK = 20
VOLUME_RATIO = 1.5
MIN_ROWS = max(GAP_ROWS, LOOKBACK + 1)


def parts(frame: pd.DataFrame) -> tuple[float | None, float, bool]:
    """(gap z, volume ratio, close above the prior 20-session high) for the last row of `frame`."""
    z = _yesterdays_gap_z(frame["adj_open"], frame["adj_close"])
    volume = frame["volume"].to_numpy(float)[-MIN_ROWS:]
    median = float(np.median(volume[-LOOKBACK - 1:-1]))
    ratio = float(volume[-1] / median) if median > 0 else float("nan")
    high = frame["adj_high"].to_numpy(float)[-LOOKBACK - 1:-1]
    above = bool(frame["adj_close"].to_numpy(float)[-1] > high.max())
    return z, ratio, above


def _score(frame: pd.DataFrame) -> float:
    z, ratio, above = parts(frame)
    if z is None or z < Z_THRESHOLD or not ratio >= VOLUME_RATIO or not above:
        return float("nan")
    return z


def score(history: pd.DataFrame) -> pd.Series:
    """Yesterday's gap z for symbols that gapped up on strong volume and closed above resistance."""
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
        return "A10 gap and go (1-day lag): insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    z, ratio, above = parts(frame)
    if z is None:
        return "A10 gap and go (1-day lag): zero trailing gap volatility or non-positive price, abstain"
    detail = (
        f"yesterday's gap {z:+.2f} sigma, volume {ratio:.2f}x its 20-session median, "
        f"close {'above' if above else 'not above'} the prior 20-session high"
    )
    if np.isnan(_score(frame)):
        return f"A10 gap and go (1-day lag): {detail}, abstain"
    return f"A10 gap and go (1-day lag): {detail}, bullish"
