"""Causality check for `strategies/q03_up_day_balance.py` (SPEC.md section 5).
Same shape as `strategies/t17_keltner_breakout_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that Q03's per-symbol arithmetic (including its
per-symbol `tail`) cannot leak across symbols. Giving `BBB` one extra trailing
row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` drifts up and `CCC`
down, so both fire and the check compares real scores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import q03_up_day_balance as q03
from strategies.t17_keltner_breakout_audit import frame


def drift(symbol: str, n_rows: int, mu: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return frame(symbol, 100.0 * np.exp(np.cumsum(mu + rng.normal(0, 0.01, n_rows))))


def check_cross_symbol_causality(n_rows: int = q03.MIN_ROWS + 10) -> dict:
    a = drift("AAA", n_rows, 0.01, seed=1)
    c = drift("CCC", n_rows, -0.01, seed=2)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = q03.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = q03.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
