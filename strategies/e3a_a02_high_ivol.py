"""E3A: A02 extreme-day reversal kept only on stocks with above-median idiosyncratic volatility (see `strategies/e3_a02_ivol.py`)."""

import pandas as pd

from strategies import a02_extreme_day_reversal, e3_a02_ivol as e3


def score(history: pd.DataFrame) -> pd.Series:
    return e3.high_ivol(history)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    kept = e3.high_ivol(history).get(symbol)
    if kept is None:
        return "E3A: no A02 pick, or stock-specific volatility not above the median, abstain"
    return "E3A: A02 pick on a stock with above-median stock-specific volatility. " + a02_extreme_day_reversal.rules_fired(history, symbol)
