"""Causality check for `strategies/t22_vcp.py` (SPEC.md section 5). Same shape
as `strategies/t17_keltner_breakout_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that T22's per-symbol arithmetic cannot leak across
symbols. Giving `BBB` one extra trailing row must leave `AAA`'s and `CCC`'s
scores unchanged. Both are built to show the pattern (`vcp_frame`), so both
fire and the check compares real scores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import t22_vcp as t22
from strategies.t17_keltner_breakout_audit import frame

# Close path after the trend, as (bars, end close): three swing highs at 200, 201
# and 202 with pullbacks to 176 (12%) and 189 (6%) between them, then a 3% base
# to 196 and a rise to 201.
LEGS = [(10, 176.0), (12, 201.0), (8, 189.0), (10, 202.0), (6, 196.0), (13, 201.0)]


def vcp_frame(symbol: str, n_rows: int = t22.MIN_ROWS + 10, scale: float = 1.0,
              lift: float = 2.0, dry: float = 0.5) -> pd.DataFrame:
    """A steady rise to a peak at 200, then LEGS. High/low are close +/- 0.5%,
    volume is 1e6, `dry` x 1e6 from the second peak to the third, and `lift` x 1e6
    on the last bar."""
    tail_len = sum(b for b, _ in LEGS)
    rise = np.geomspace(60.0, 200.0, n_rows - tail_len)
    path, last = [rise], 200.0
    for bars, end in LEGS:
        path.append(np.linspace(last, end, bars + 1)[1:])
        last = end
    closes = np.concatenate(path) * scale
    f = frame(symbol, closes)
    f["high"], f["low"] = f["close"] * 1.005, f["close"] * 0.995
    p2 = n_rows - tail_len + LEGS[0][0] + LEGS[1][0] - 1
    p3 = p2 + LEGS[2][0] + LEGS[3][0]
    f.loc[p2:p3, "volume"] = dry * 1e6
    f.loc[n_rows - 1, "volume"] = lift * 1e6
    return f


def check_cross_symbol_causality(n_rows: int = t22.MIN_ROWS + 10) -> dict:
    a = vcp_frame("AAA", n_rows)
    c = vcp_frame("CCC", n_rows, scale=0.5, lift=3.0)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = t22.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = t22.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
