"""G03: frog-in-the-pan momentum (`cards/G03.yml`, `state/queue.md` port lane).

Da, Gurun and Warachka (2014), "Frog in the Pan: Continuous Information and
Momentum", Review of Financial Studies: momentum built from many small moves in the
same direction persists longer than momentum built from a few large jumps. The
paper's information discreteness, on the 12-1 month window of A03
(`strategies/a03_momentum_12_1.py`):

    ID = sign(PRET) x (share of down days - share of up days),

where PRET is the formation-window return. Low (negative) ID means the move came
from many small days; the paper's long-short is among past winners and losers
sorted on ID. The lab's single-score reading, on adjusted closes (SPEC.md section 2):

- formation window = the `LOOKBACK` daily log returns ending `SKIP` sessions before
  the last date; PRET = their sum;
- ID >= 0 (discrete, jump-driven) abstains;
- otherwise score = PRET x (-ID): continuous winners bullish, continuous losers
  bearish, larger for bigger and smoother moves.

Per-symbol: only the symbol's own last `MIN_ROWS` rows are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

LOOKBACK = 252
SKIP = 21
MIN_ROWS = LOOKBACK + SKIP + 1


def discreteness(frame: pd.DataFrame) -> tuple[float, float]:
    """(PRET, ID) over the formation window; ID is NaN when PRET is zero."""
    close = frame["adj_close"].to_numpy(float)[-MIN_ROWS:]
    r = np.log(close[1:] / close[:-1])[:LOOKBACK]
    pret = float(r.sum())
    if pret == 0.0 or not np.isfinite(pret):
        return pret, float("nan")
    ident = float(np.sign(pret) * (np.mean(r < 0) - np.mean(r > 0)))
    return pret, ident


def _score(frame: pd.DataFrame) -> float:
    pret, ident = discreteness(frame)
    if np.isnan(ident) or ident >= 0:
        return float("nan")
    return pret * -ident


def score(history: pd.DataFrame) -> pd.Series:
    """Formation return times minus information discreteness, continuous moves only, per symbol."""
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
        return "G03 frog-in-the-pan: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    pret, ident = discreteness(frame)
    if np.isnan(ident) or ident >= 0:
        return "G03 frog-in-the-pan: discrete (jump-driven) or flat 12-1 month move, abstain"
    side = "bullish (continuous winner)" if pret > 0 else "bearish (continuous loser)"
    return f"G03 frog-in-the-pan: 12-1 month log return {pret:+.1%}, ID {ident:+.3f}, {side}"
