"""D02 confirmatory variant (`cards/D02.yml`): extreme stock put/call OI
read as sentiment persisting - extreme-high PCR (relatively many puts)
scores bearish, extreme-low PCR (relatively many calls) scores bullish.

All the real logic (what counts as an extreme, the trailing-window
z-score, the F&O-universe gate) lives in `strategies/d02_stock_pcr_core.py`,
shared with `d02_stock_pcr_contrarian.py`; this module only fixes which
sign the extreme gets.
"""

from __future__ import annotations

import pandas as pd

from strategies import d02_stock_pcr_core as core


def score(history: pd.DataFrame) -> pd.Series:
    return core.signal(history, contrarian=False)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    return core.reasoning(history, symbol, contrarian=False, label="confirmatory")
