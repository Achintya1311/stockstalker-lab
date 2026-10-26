"""T23: relative strength rating (`cards/T23.yml`, `state/queue.md` port lane).

O'Neil's CANSLIM RS rating ranks a stock's price performance over the last
year against every other stock, with the latest quarter weighted most.
`cards/catalog.csv`'s reading: rank by weighted 3/6/9/12-month return vs the
universe, top bullish, bottom bearish.

The published rating's exact formula is not public. The lab uses the common
practitioner reading, declared in the card before the replay:

    perf = 0.4 * r63 + 0.2 * r126 + 0.2 * r189 + 0.2 * r252

where rN is the adjusted-close return over the last N sessions up to the last
visible close. Per date, symbols are ranked by perf and the rank is mapped
symmetrically onto (-1, 1): score = 2 * (rank - 0.5) / n - 1, with rank 1 the
weakest. So the strongest symbol scores just under +1 (bullish) and the
weakest just over -1 (bearish); ties share the average rank.

The rank depends on which symbols are present on a date. `raw_perf` is the
per-symbol part that depends only on that symbol's rows; the audit checks it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

PERIODS = (63, 126, 189, 252)
WEIGHTS = (0.4, 0.2, 0.2, 0.2)
MIN_ROWS = max(PERIODS) + 1


def _perf(close: pd.Series) -> float:
    tail = close.iloc[-MIN_ROWS:].to_numpy(dtype=float)
    if (tail <= 0).any():
        return float("nan")
    last = tail[-1]
    return float(sum(w * (last / tail[-1 - p] - 1) for p, w in zip(PERIODS, WEIGHTS)))


def raw_perf(history: pd.DataFrame) -> pd.Series:
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
        value = _perf(group.sort_values("date")["adj_close"])
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """Symmetric rank score in (-1, 1); needs at least two symbols."""
    perf = raw_perf(history)
    if len(perf) < 2:
        return pd.Series(dtype=float)
    rank = perf.rank(method="average")
    return (2 * (rank - 0.5) / len(perf) - 1).astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    perf = raw_perf(history)
    scores = score(history)
    if symbol not in scores.index:
        return "T23 RS rating: insufficient history or cross-section, abstain"
    value = float(scores[symbol])
    direction = "bullish" if value > 0 else "bearish" if value < 0 else "neutral"
    rating = int(round(1 + 98 * (value + 1) / 2))
    return (
        f"T23 RS rating: weighted 3/6/9/12-month return {perf[symbol]:+.1%}, "
        f"rating {rating} of 99 across {len(scores)} symbols -> score {value:+.3f} ({direction})"
    )
