"""A07C: the contrarian reading of A07's high-volume premium (`cards/A07C.yml`).

A07 scored last week's volume z-score (5-day mean vs prior 50-day mean and std) as the paper's
continuation signal and was wrong-way on both sides of the week table in train (bullish -1.42,
bearish -0.84; `all` selection t -1.60 / -1.52; `research/diagnostics/a07.md`). The sign is tested
the other way round as its own pre-declared card, the same move D01C made for D01: score = -A07.
A volume spike becomes bearish and a volume drought bullish. Imports A07 as a library so
abstentions and magnitudes are bit-for-bit A07's; only the sign flips. Week horizon only, like A07.
"""

from __future__ import annotations

import pandas as pd

from strategies import a07_high_volume_premium


def score(history: pd.DataFrame) -> pd.Series:
    return -a07_high_volume_premium.score(history)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    base = a07_high_volume_premium.rules_fired(history, symbol)
    if "abstain" in base:
        return base.replace("A07 high-volume return premium", "A07C volume fade", 1)
    head, _, tail = base.partition(" -> score ")
    z = float(tail.split(" ")[0])
    flipped = -z
    direction = "bullish" if flipped > 0 else "bearish" if flipped < 0 else "neutral"
    head = head.replace(
        "A07 high-volume return premium (Gervais, Kaniel and Mingelgrin 2001)",
        "A07C volume fade (sign-flipped A07, Gervais, Kaniel and Mingelgrin 2001)",
        1,
    )
    return f"{head} -> score {flipped:+.4f} ({direction})"
