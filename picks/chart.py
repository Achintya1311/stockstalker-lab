"""A pick's chart data: the last bars and the nearest order-block zone, scaled to 0-100 on the window.

Published as shapes only (SPEC.md section 10: no entry, target or stop prices), so the raw prices never
appear: bars and zone share one min-max scale and the page draws them without an axis. The zone is the
structure `strategies/ob_core.py` finds on the same bars, shown for every pick whatever strategy chose it;
it describes the chart, not why the stock was picked.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import ob_core

BARS = 45
DETECT_ROWS = 60


def chart_for(history: pd.DataFrame, symbol: str) -> dict | None:
    sub = history[history["symbol"] == symbol]
    if len(sub) < DETECT_ROWS:
        return None
    g = compute_adjustment_factors(sub.sort_values("date")).tail(DETECT_ROWS)
    o, h, l, c = (g[f"adj_{k}"].to_numpy(float) for k in ("open", "high", "low", "close"))
    zone = ob_core.detect(o, h, l, c)
    lo, hi = float(l[-BARS:].min()), float(h[-BARS:].max())
    if zone:
        lo, hi = min(lo, zone["zone_low"]), max(hi, zone["zone_high"])
    span = (hi - lo) or 1.0
    sc = lambda x: round(float((x - lo) / span * 100.0), 1)
    out = {"bars": [[sc(o[i]), sc(h[i]), sc(l[i]), sc(c[i])] for i in range(len(c) - BARS, len(c))]}
    if zone:
        out["zone"] = {"side": "demand" if zone["side"] == 1 else "supply", "from": int(len(c) - 1 - zone["bars_ago"] - (len(c) - BARS)),
                       "low": sc(zone["zone_low"]), "high": sc(zone["zone_high"]), "retested": zone["touched"]}
    return out
