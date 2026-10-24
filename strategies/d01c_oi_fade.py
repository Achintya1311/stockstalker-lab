"""D01C: the contrarian reading of D01's OI build-up (`cards/D01C.yml`).

D01 read yesterday's price-and-OI classification as a continuation signal and lost confidently on
both sides in every train year (bullish -4.61 pts, t -8.15). The sign is therefore tested the other
way round, as its own pre-declared card: score = -D01. Long build-up (price up, OI up) becomes
bearish, short build-up becomes bullish, and the weaker unwinding/covering quadrants fade at half
strength exactly as D01 weights them. Imports D01 as a library so abstentions and magnitudes are
bit-for-bit D01's; only the sign flips. Day horizon only, like D01.
"""

from __future__ import annotations

import pandas as pd

from strategies import d01_oi_buildup


def score(history: pd.DataFrame) -> pd.Series:
    return -d01_oi_buildup.score(history)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    base = d01_oi_buildup.rules_fired(history, symbol)
    return base.replace("D01 OI build-up classification", "D01C (fade of D01)", 1) if "abstain" not in base else base.replace("D01 OI build-up", "D01C fade", 1)
