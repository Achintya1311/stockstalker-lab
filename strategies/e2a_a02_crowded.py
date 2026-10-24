"""E2A: A02 extreme-day reversal kept only where futures OI ROSE on the extreme day (see `strategies/e2_a02_oi.py`)."""

import pandas as pd

from strategies import a02_extreme_day_reversal, e2_a02_oi as e2


def score(history: pd.DataFrame) -> pd.Series:
    return e2.crowded(history)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    kept = e2.crowded(history[history["symbol"] == symbol]).get(symbol)
    return "E2A: A02 pick on a crowded move (OI rose). " + a02_extreme_day_reversal.rules_fired(history, symbol) if kept is not None else "E2A: no A02 pick or OI did not rise, abstain"
