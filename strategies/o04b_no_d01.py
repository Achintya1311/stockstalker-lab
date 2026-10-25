"""O04B: O04 without D01's OI ingredient (`cards/O04B.yml`, order-block lane ablation).

Rank-average of O01 proximity and A07's volume z only, signed by O01's side. D01 alone is confidently
wrong on both sides in train (`research/diagnostics/d01.md`), so it is the first suspect for O04 doing
worse than O01 alone; this drops it and keeps everything else bit-for-bit O04's. Arithmetic shared with
O04A in `strategies/o04_ablation_core.py`. Both horizons, as O04; needs no futures OI.
"""

from __future__ import annotations

import pandas as pd

from strategies import o04_ablation_core

KEEP = ["o01", "vol"]


def score(history: pd.DataFrame) -> pd.Series:
    return o04_ablation_core.score(history, KEEP)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    return o04_ablation_core.rules_fired(history, symbol, KEEP, "O04B (O04 without OI)")
