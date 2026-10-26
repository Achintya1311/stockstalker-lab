"""Causality check for `strategies/t24_pivot_points.py` (SPEC.md section 5).
Same shape as `strategies/t17_keltner_breakout_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that T24's per-symbol arithmetic (including its
per-symbol `tail`) cannot leak across symbols. Giving `BBB` one extra trailing
row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` ends with a jump up
and `CCC` with a jump down, so both fire and the check compares real scores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import t24_pivot_points as t24
from strategies.t17_keltner_breakout_audit import frame, quiet_then_jump


def check_cross_symbol_causality(n_rows: int = t24.MIN_ROWS + 10) -> dict:
    a = quiet_then_jump("AAA", n_rows, 0.05, seed=1)
    c = quiet_then_jump("CCC", n_rows, -0.05, seed=2)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = t24.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = t24.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
