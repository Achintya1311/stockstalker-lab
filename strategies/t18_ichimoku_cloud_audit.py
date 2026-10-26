"""Causality check for `strategies/t18_ichimoku_cloud.py` (SPEC.md section 5).
Same shape as `strategies/t17_keltner_breakout_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that T18's per-symbol arithmetic cannot leak across
symbols. Giving `BBB` one extra trailing row must leave `AAA`'s and `CCC`'s
scores unchanged. `AAA` trends up and `CCC` down, so both fire and the check
compares real scores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import t18_ichimoku_cloud as t18
from strategies.t17_keltner_breakout_audit import frame


def trend(symbol: str, n_rows: int, drift: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return frame(symbol, 100.0 * np.exp(np.cumsum(drift + rng.normal(0, 0.002, n_rows))))


def check_cross_symbol_causality(n_rows: int = t18.MIN_ROWS + 10) -> dict:
    a = trend("AAA", n_rows, 0.004, seed=1)
    c = trend("CCC", n_rows, -0.004, seed=2)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = t18.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = t18.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
