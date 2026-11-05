"""E3: A02 extreme-day reversal split by H02's idiosyncratic volatility (`cards/E3A.yml`, `cards/E3B.yml`).

Hypothesis fixed before any replay (5 Nov 2026; named in `research/diagnostics/h02_day.md`): an
extreme day on a stock whose stock-specific volatility is above the date's median should fade harder,
since H02 found high idiosyncratic volatility bearish on its own (day bearish +2.06) with only 2.6% top-5
overlap with A02. E3A keeps A02 where H02's score is negative (ivol above the median of the stocks H02
scores that date), E3B where it is positive (below). Both signs of A02 are kept, so a result in either
direction is reported. Day horizon; imports A02 and H02 as libraries and copies neither.
"""

from __future__ import annotations

import pandas as pd

from strategies import a02_extreme_day_reversal, e_confluence_core as core, h02_idiosyncratic_volatility


def _split(history: pd.DataFrame, high: bool) -> pd.Series:
    base = a02_extreme_day_reversal.score(history)
    if base.empty:
        return base
    ivol = h02_idiosyncratic_volatility.score(history)
    return core.keep_if(base, {s: bool(ivol[s] < 0) if high else bool(ivol[s] > 0) for s in base.index if s in ivol})


def high_ivol(history: pd.DataFrame) -> pd.Series:
    return _split(history, high=True)


def low_ivol(history: pd.DataFrame) -> pd.Series:
    return _split(history, high=False)
