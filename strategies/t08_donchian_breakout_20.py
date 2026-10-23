"""T08 System 1: Donchian/Turtle 20-day breakout (`cards/T08.yml`,
`state/queue.md` port lane).

Faith (2007) Way of the Turtle: close strictly above the prior 20
sessions' highest close is bullish (new breakout), strictly below the
prior 20 sessions' lowest close is bearish. Shares its entire breakout
and scoring logic with `t08_donchian_breakout_55.py` via
`t08_donchian_breakout_core.py`, differing only in the lookback window -
see that module's docstring, and `cards/T08.yml`'s rules_plain, for why
both catalog-stated windows (20 and 55) are tested as independent trials
rather than one assumed and the other left for a later tune-lane run.
"""

from __future__ import annotations

import pandas as pd

from strategies import t08_donchian_breakout_core as core

WINDOW = 20
MIN_ROWS = WINDOW + 1


def score(history: pd.DataFrame) -> pd.Series:
    return core.score(history, window=WINDOW)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    return core.reasoning(history, symbol, window=WINDOW, label=str(WINDOW))
