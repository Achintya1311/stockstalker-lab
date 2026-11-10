"""A pick's chart data: the last bars and the nearest order-block zone, scaled to 0-100 on the window.

Published as shapes only (SPEC.md section 10: no entry, target or stop prices), so the raw prices never
appear: bars and zone share one min-max scale and the page draws them without an axis. The zone is the
structure `strategies/ob_core.py` finds on the same bars, shown for every pick whatever strategy chose it;
it describes the chart, not why the stock was picked.

`levels` are the nearest swing highs above the last close ("r", resistance) and swing lows below it
("s", support), at most two of each, on the same 0-100 scale: `at` is the height and `from` the bar the
swing printed on. A swing is a bar whose high (low) is the extreme of the `SWING` bars either side of it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import ob_core

BARS = 45
DETECT_ROWS = 60
SWING = 3
MAX_LEVELS = 2
MERGE = 4.0   # swings closer than this many scale points count as one level


def swing_levels(bars: list[list[float]]) -> list[dict]:
    """Nearest swing highs above and swing lows below the last close, from scaled [o, h, l, c] bars."""
    hi, lo, last = [b[1] for b in bars], [b[2] for b in bars], bars[-1][3]
    out = []
    for kind, vals, pick, ok in (("r", hi, max, lambda v: v > last), ("s", lo, min, lambda v: v < last)):
        found = [(vals[i], i) for i in range(SWING, len(vals) - SWING)
                 if vals[i] == pick(vals[i - SWING:i + SWING + 1]) and vals[i - SWING:i + SWING + 1].count(vals[i]) == 1 and ok(vals[i])]
        kept = []
        for v, i in sorted(found, key=lambda t: abs(t[0] - last)):
            if all(abs(v - k["at"]) >= MERGE for k in kept):
                kept.append({"k": kind, "at": v, "from": i})
        out += kept[:MAX_LEVELS]
    return out


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
    levels = swing_levels(out["bars"])
    if levels:
        out["levels"] = levels
    return out
