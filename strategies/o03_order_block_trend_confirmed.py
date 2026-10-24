"""O03: order-block retest confirmed by T01's trend (`cards/O03.yml`, `docs/orderblock_hypotheses.md`).

Tests whether an order block is just a trend signal in disguise: O01's side is kept only when
T01's SMA(20,50) spread has the same sign (T01's score is never exactly 0.0 once it has enough
history, since champion v1's own trend module makes the same simplifying assumption - a tie would
need the two SMAs to match to the trailing float, not a real case this card special-cases). Abstains
whenever O01 or T01 abstains, or whenever the signs disagree.

Both horizons (`cards/catalog.csv`'s O03 row: horizon=both), unlike O02's day-only restriction: T01
serves day and week picks identically (`strategies/t01_sma_crossover.py`'s own docstring), so there is
no missing-horizon gap the way D01's day-only OI reading left O02.

Imports `strategies.o01_order_block_retest` and `strategies.t01_sma_crossover` as libraries (not
copied): this card's whole point is comparing OB+trend against the bare retest, so it must stay
bit-for-bit consistent with the already-queued O01 train replay.
"""

from __future__ import annotations

import pandas as pd

from strategies import o01_order_block_retest, t01_sma_crossover


def _confirmed_scores(history: pd.DataFrame) -> dict[str, float]:
    ob_scores = o01_order_block_retest.score(history)
    if ob_scores.empty:
        return {}
    trend_scores = t01_sma_crossover.score(history[history["symbol"].isin(ob_scores.index)])
    if trend_scores.empty:
        return {}

    out: dict[str, float] = {}
    for symbol, ob_score in ob_scores.items():
        trend_score = trend_scores.get(symbol)
        if trend_score is None or pd.isna(trend_score):
            continue
        ob_side = 1.0 if ob_score > 0 else -1.0
        trend_side = 1.0 if trend_score > 0 else -1.0 if trend_score < 0 else 0.0
        if trend_side == ob_side:
            out[symbol] = ob_score
    return out


def score(history: pd.DataFrame) -> pd.Series:
    return pd.Series(_confirmed_scores(history), dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol]
    hit = _confirmed_scores(sub).get(symbol)
    if hit is None:
        ob = o01_order_block_retest.score(sub)
        if symbol not in ob.index:
            return "O03: O01 has no valid zone at price, abstain"
        return "O03: O01 has a zone but T01's trend disagrees with its side, abstain"
    side = "bullish" if hit > 0 else "bearish"
    return f"O03: {side} order block retest confirmed by T01 trend, score {hit:+.2f}"
