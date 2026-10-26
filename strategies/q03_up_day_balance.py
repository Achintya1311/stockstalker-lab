"""Q03: up-day count balance (`cards/Q03.yml`, `state/queue.md` port lane).

Alpha158's CNTD feature (microsoft/qlib, MIT; feature list in
`third_party/qlib/loader.py`): over the last 20 sessions, the share of up closes
minus the share of down closes. The lab's reading, on the adjusted close (SPEC.md
section 2):

    balance = (up closes - down closes) / 20,  in steps of 0.05

Positive balance is bullish, negative bearish, zero abstains. The bullish top five
are therefore the stocks that rose most often, and the bearish top five those that
fell most often; whether that persists or reverses is what the replay measures.

Ties: the balance takes only 41 values, so the score adds a tie-break smaller
than half a step, `0.02 * tanh(r20 / 0.2)` with r20 the 20-session log return.
It orders stocks with the same balance by how far they moved, without ever
reordering two different balances.

Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20
TIE = 0.02
MIN_ROWS = WINDOW + 1


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(balance, 20-session log return) on the last row of `frame`."""
    close = frame["adj_close"].to_numpy(float)[-(WINDOW + 1):]
    step = np.diff(close)
    balance = (np.sum(step > 0) - np.sum(step < 0)) / WINDOW
    return float(balance), float(np.log(close[-1] / close[0]))


def _score(frame: pd.DataFrame) -> float:
    balance, r20 = parts(frame)
    if balance == 0:
        return float("nan")
    return balance + TIE * np.tanh(r20 / 0.2)


def _detail(frame: pd.DataFrame) -> str:
    balance, r20 = parts(frame)
    up = int(round((balance * WINDOW + WINDOW) / 2))
    return f"up-day balance {balance:+.2f} over {WINDOW} sessions (about {up} up), 20-session move {r20:+.1%}"


def score(history: pd.DataFrame) -> pd.Series:
    """Signed up-day balance for every symbol whose balance is not zero."""
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
        return "Q03 up-day balance: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    value = _score(frame)
    if np.isnan(value):
        return f"Q03 up-day balance: {_detail(frame)}, abstain"
    side = "bullish (more up closes)" if value > 0 else "bearish (more down closes)"
    return f"Q03 up-day balance: {_detail(frame)}, {side}"
