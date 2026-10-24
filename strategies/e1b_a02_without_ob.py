"""E1B: A02 extreme-day reversal kept only where NO order-block zone agrees (see `strategies/e1_a02_ob_confluence.py`)."""

import pandas as pd

from strategies import a02_extreme_day_reversal, e1_a02_ob_confluence as e1


def score(history: pd.DataFrame) -> pd.Series:
    return e1.without_zone(history)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    kept = e1.without_zone(history[history["symbol"] == symbol]).get(symbol)
    return "E1B: A02 pick with no agreeing order-block zone. " + a02_extreme_day_reversal.rules_fired(history, symbol) if kept is not None else "E1B: no A02 pick or an agreeing zone exists, abstain"
