"""Shared helpers for the E-series confluence cards (`docs/orderblock_hypotheses.md`, plan E1/E2).

A confluence card keeps a BASE strategy's score only where a second condition holds, and abstains
elsewhere. The base strategy and the condition are imported libraries, never copied, so each card
stays bit-for-bit consistent with the already-scored base replay. The comparison that matters is
always: base alone vs base AND condition vs base AND NOT condition, on edge, t, directional move
after costs, AND coverage (a confluence that wins only by shrinking to a cherry-picked set is rejected).
"""

from __future__ import annotations

import pandas as pd


def last_oi_chg(history: pd.DataFrame) -> dict[str, float]:
    """Change in near-month futures OI on each symbol's last visible session (NaN if missing)."""
    if history.empty or "oi_chg_futstk" not in history.columns:
        return {}
    last = history.sort_values("date").groupby("symbol", sort=False).tail(1)
    return {s: v for s, v in zip(last["symbol"], last["oi_chg_futstk"]) if pd.notna(v)}


def keep_if(base: pd.Series, keep: dict[str, bool]) -> pd.Series:
    """Base scores restricted to symbols whose condition is True; a symbol with no verdict abstains."""
    return pd.Series({s: float(v) for s, v in base.items() if keep.get(s) is True}, dtype=float)
