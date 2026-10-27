"""Causality check for `strategies/q04_range_extreme_timing.py` (SPEC.md section 5).
Same shape as `strategies/q02_return_volume_corr_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` trends up and
`CCC` down, so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import q04_range_extreme_timing as q04
from strategies.t17_keltner_breakout_audit import frame


def trend(symbol: str, n_rows: int, mu: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return frame(symbol, 100.0 * np.exp(np.cumsum(mu + rng.normal(0, 0.005, n_rows))))


def check_cross_symbol_causality(n_rows: int = q04.MIN_ROWS + 10) -> dict:
    a = trend("AAA", n_rows, 0.01, seed=1)
    c = trend("CCC", n_rows, -0.01, seed=2)
    b_long = trend("BBB", n_rows + 1, 0.0, seed=3)
    b_short = b_long.iloc[:n_rows].copy()

    s_without = q04.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = q04.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
