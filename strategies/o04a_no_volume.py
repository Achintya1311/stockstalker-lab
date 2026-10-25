"""O04A: O04 without A07's volume ingredient (`cards/O04A.yml`, order-block lane ablation).

Rank-average of O01 proximity and D01 OI build-up only, signed by O01's side. A07C showed the volume z
carries no reliable week edge in either sign (`research/diagnostics/a07c.md`), so dropping it, not
flipping it, is the fair test of whether the volume ingredient is what made O04 worse than O01 alone.
Arithmetic shared with O04B in `strategies/o04_ablation_core.py`. Both horizons, as O04.
"""

from __future__ import annotations

import pandas as pd

from strategies import o04_ablation_core

KEEP = ["o01", "d01"]


def score(history: pd.DataFrame) -> pd.Series:
    return o04_ablation_core.score(history, KEEP)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    return o04_ablation_core.rules_fired(history, symbol, KEEP, "O04A (O04 without volume)")
