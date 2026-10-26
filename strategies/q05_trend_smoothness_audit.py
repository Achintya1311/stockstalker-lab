"""Causality check for `strategies/q05_trend_smoothness.py` (SPEC.md section 5).
Same shape as `strategies/t17_keltner_breakout_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that Q05's per-symbol arithmetic (including its
per-symbol `tail`) cannot leak across symbols. Giving `BBB` one extra trailing
row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` drifts up and `CCC`
down, so both fire and the check compares real scores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import q05_trend_smoothness as q05
from strategies.q03_up_day_balance_audit import drift
from strategies.t17_keltner_breakout_audit import frame


def check_cross_symbol_causality(n_rows: int = q05.MIN_ROWS + 10) -> dict:
    a = drift("AAA", n_rows, 0.01, seed=1)
    c = drift("CCC", n_rows, -0.01, seed=2)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = q05.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = q05.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
