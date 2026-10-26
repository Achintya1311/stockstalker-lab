"""A01_I01F: A01's week-bearish scores, kept only where I01's momentum score is below zero (`cards/A01_I01F.yml`).

A01 (weekly reversal) holds the week-bearish draft choice: it calls last week's biggest winners bearish. I01
(`strategies/i01_momentum_score.py`) reads the slower, volatility-adjusted 6/12-month trend; its whole-universe
reading persists mildly (`research/diagnostics/i01.md`). The pre-declared idea: a one-week bounce inside a
weak longer trend fades more reliably than a bounce inside a strong one. Per date, return A01's bearish
scores only for symbols whose I01 score is below zero; every other symbol abstains. A01's own magnitude is
kept, so the `top` five are A01's five strongest bearish readings among the filtered stocks. Bullish scores
are dropped: a week-bearish table only.

Imports both as libraries. I01 needs 253 rows, so this card has no picks in 2015 (the dataset starts on
2015-01-01), unlike A01.
"""

from __future__ import annotations

import pandas as pd

from strategies import a01_weekly_reversal, i01_momentum_score


def filtered(history: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """(A01's bearish scores that pass, I01's scores) for the date `history` ends on."""
    a01 = a01_weekly_reversal.score(history)
    a01 = a01[a01 < 0]
    if a01.empty:
        return a01, pd.Series(dtype=float)
    i01 = i01_momentum_score.score(history)
    weak = i01[i01 < 0].index
    return a01[a01.index.isin(weak)].astype(float), i01


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    return filtered(history)[0]


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    kept, i01 = filtered(history)
    if symbol in kept.index:
        return (
            f"A01_I01F: A01 bearish {float(kept[symbol]):+.4f}, I01 momentum {float(i01[symbol]):+.3f} "
            "(below zero) -> bearish"
        )
    if symbol in i01.index and i01[symbol] >= 0:
        return f"A01_I01F: I01 momentum {float(i01[symbol]):+.3f} not below zero, abstain"
    return "A01_I01F: no A01 bearish reading or no I01 reading, abstain"
