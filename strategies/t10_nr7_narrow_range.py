"""T10 NR7 variant (`cards/T10.yml`): narrowest true range of the last 7
days, read in the direction of `strategies/t01_sma_crossover.py`'s own
fast/slow (20/50) SMA trend filter.

All the real logic (true range, the narrow-range test, the trend filter)
lives in `strategies/t10_narrow_range_core.py`, shared with
`t10_nr4_narrow_range.py`; this module only fixes the lookback length.
"""

from __future__ import annotations

import pandas as pd

from strategies import t10_narrow_range_core as core

LOOKBACK = 7
MIN_ROWS = core.min_rows(LOOKBACK)


def score(history: pd.DataFrame) -> pd.Series:
    return core.signal(history, lookback=LOOKBACK)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    return core.reasoning(history, symbol, lookback=LOOKBACK, label="NR7")
