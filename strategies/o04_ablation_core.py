"""Shared arithmetic for the O04 ablations (`cards/O04A.yml`, `cards/O04B.yml`).

O04 (`strategies/o04_order_block_composite.py`) rank-averages three side-aligned ingredients (O01
proximity, D01 OI build-up, A07 volume z) among the symbols O01 fires on, and lost to O01 alone on all
four train cells (`research/diagnostics/o04.md`). Each ablation drops one ingredient and keeps
everything else bit-for-bit O04's: the same `_ingredients()` readings (imported, not copied), the same
percentile ranking among O01's firing symbols, the same skip-if-abstaining mean, and the same sign
from O01's side. Only the list of ingredients averaged changes.
"""

from __future__ import annotations

import pandas as pd

from strategies import o04_order_block_composite as o04


def composite(history: pd.DataFrame, keep: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    ing = o04._ingredients(history)
    if ing.empty:
        return ing, pd.Series(dtype=float)
    return ing, ing[keep].rank(pct=True).mean(axis=1, skipna=True)


def score(history: pd.DataFrame, keep: list[str]) -> pd.Series:
    ing, avg_rank = composite(history, keep)
    if ing.empty:
        return pd.Series(dtype=float)
    return ing["side"] * avg_rank


def rules_fired(history: pd.DataFrame, symbol: str, keep: list[str], label: str) -> str:
    ing, avg_rank = composite(history, keep)
    if ing.empty or symbol not in ing.index:
        return f"{label}: O01 has no valid zone at price, abstain"
    row = ing.loc[symbol]
    side = "bullish" if row["side"] > 0 else "bearish"
    have = [name for name in keep if pd.notna(row[name])]
    final = row["side"] * avg_rank.loc[symbol]
    return (
        f"{label}: {side} order block, composite rank {avg_rank.loc[symbol]:.2f} from {len(have)}/{len(keep)} "
        f"ingredients ({'+'.join(have)}) against {len(ing)} order-block picks today -> score {final:+.3f}"
    )
