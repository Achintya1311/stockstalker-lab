"""E2: A02 extreme-day reversal split by open-interest behaviour on the extreme day (`cards/E2A.yml`, `cards/E2B.yml`).

Hypothesis fixed before any replay: an extreme move that came with RISING futures OI is a crowded move (new
positions piled in) and should fade harder; one that came with FALLING OI is mostly position-closing and
should fade less. E2A keeps A02 where `oi_chg_futstk > 0` on the extreme day, E2B where it is <= 0. Both signs
are scored, so a result in either direction is reported. Day horizon; imports A02 as a library.
"""

from __future__ import annotations

import pandas as pd

from strategies import a02_extreme_day_reversal, e_confluence_core as core


def crowded(history: pd.DataFrame) -> pd.Series:
    base = a02_extreme_day_reversal.score(history)
    chg = core.last_oi_chg(history)
    return core.keep_if(base, {s: chg[s] > 0 for s in base.index if s in chg})


def uncrowded(history: pd.DataFrame) -> pd.Series:
    base = a02_extreme_day_reversal.score(history)
    chg = core.last_oi_chg(history)
    return core.keep_if(base, {s: chg[s] <= 0 for s in base.index if s in chg})
