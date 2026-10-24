"""E1: A02 extreme-day reversal with and without an order-block zone at price (`cards/E1A.yml`, `cards/E1B.yml`).

A02 is the lab's strongest family (bearish fade after an extreme up day). E1 asks whether an order block adds
information to it, as three arms scored separately: A02 alone (already replayed), E1A = A02 kept only where O01
finds a zone on the SAME side as A02's pick (a supply zone for a bearish pick), and E1B = A02 kept only where
O01 finds no agreeing zone (abstains or points the other way). If zones carried information, E1A would beat E1B
and A02 alone; if both match A02, order blocks add nothing here. Day horizon, imports A02 and O01 as libraries.
"""

from __future__ import annotations

import pandas as pd

from strategies import a02_extreme_day_reversal, e_confluence_core as core, o01_order_block_retest


def _agree(history: pd.DataFrame) -> tuple[pd.Series, dict[str, bool]]:
    base = a02_extreme_day_reversal.score(history)
    if base.empty:
        return base, {}
    ob = o01_order_block_retest.score(history[history["symbol"].isin(base.index)])
    return base, {s: bool(s in ob.index and (ob[s] > 0) == (base[s] > 0)) for s in base.index}


def with_zone(history: pd.DataFrame) -> pd.Series:
    base, agree = _agree(history)
    return core.keep_if(base, agree)


def without_zone(history: pd.DataFrame) -> pd.Series:
    base, agree = _agree(history)
    return core.keep_if(base, {s: not a for s, a in agree.items()})
