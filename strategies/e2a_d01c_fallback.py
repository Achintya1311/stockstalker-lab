"""E2A_D01C_FB: E2A's day-bearish picks when it fires, D01C's on the dates it does not (`cards/E2A_D01C_FB.yml`).

E2A (A02's extreme-day fade kept where futures OI rose) is the lab's strongest day-bearish train reading
(+7.46, `research/diagnostics/consensus_db_v1.md`) but has bearish picks on only 64% of train dates.
D01C (D01 faded) is weaker (+4.74) but reads nearly every date. Rank-averaging them
(`strategies/consensus_db_v1.py`) diluted E2A towards D01C. This card is the pre-declared alternative:
not an average but a fallback, decided per date. If E2A scores any stock bearish on the date, only E2A's
bearish scores are returned; otherwise only D01C's. Bullish scores of either member are dropped, so this is
a bearish table only. Imports both members as libraries, so each pick's magnitude is its member's own.
Day horizon only, like both members.
"""

from __future__ import annotations

import pandas as pd

from strategies import d01c_oi_fade, e2a_a02_crowded


def _bearish(scores: pd.Series) -> pd.Series:
    return scores[scores < 0]


def chosen_member(history: pd.DataFrame) -> tuple[str, pd.Series]:
    """("e2a" or "d01c", that member's bearish scores) for the date `history` ends on."""
    e2a = _bearish(e2a_a02_crowded.score(history))
    if not e2a.empty:
        return "e2a", e2a
    return "d01c", _bearish(d01c_oi_fade.score(history))


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    return chosen_member(history)[1]


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    member, scores = chosen_member(history)
    name = "E2A crowded fade" if member == "e2a" else "D01C OI fade (E2A has no bearish pick this date)"
    if symbol not in scores.index:
        return f"E2A_D01C_FB: reading from {name}; no bearish score for this stock, abstain"
    return f"E2A_D01C_FB: reading from {name} -> score {float(scores[symbol]):+.4f} (bearish)"
