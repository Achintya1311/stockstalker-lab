"""E1A: A02 extreme-day reversal kept only where an order-block zone agrees (see `strategies/e1_a02_ob_confluence.py`)."""

import pandas as pd

from strategies import a02_extreme_day_reversal, e1_a02_ob_confluence as e1


def score(history: pd.DataFrame) -> pd.Series:
    return e1.with_zone(history)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    kept = e1.with_zone(history[history["symbol"] == symbol]).get(symbol)
    return "E1A: A02 pick with an agreeing order-block zone at price. " + a02_extreme_day_reversal.rules_fired(history, symbol) if kept is not None else "E1A: no A02 pick or no agreeing zone, abstain"
