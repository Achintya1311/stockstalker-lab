"""F11 tune grid point: ts-rank window 15 (`strategies/f11_window_grid.py`, SPEC.md section 8)."""

import pandas as pd

from strategies.f11_window_grid import rules, scorer

WINDOW = 15
score = scorer(WINDOW)
_fired = rules(WINDOW)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    return _fired(history, symbol)
