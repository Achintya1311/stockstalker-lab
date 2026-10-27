"""Causality check for `strategies/g04_realized_skewness.py` (SPEC.md section 5).
Same shape as `strategies/q06_wick_balance_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` has one big
down day and `CCC` one big up day in otherwise quiet returns (`one_jump`), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import g04_realized_skewness as g04
from strategies.t17_keltner_breakout_audit import frame


def one_jump(symbol: str, n_rows: int, jump: float, seed: int) -> pd.DataFrame:
    """Small random log returns with one return of `jump` five sessions before the end."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.005, n_rows - 1)
    r[-5] = jump
    return frame(symbol, 100.0 * np.exp(np.r_[0.0, np.cumsum(r)]))


def check_cross_symbol_causality(n_rows: int = g04.MIN_ROWS + 10) -> dict:
    a = one_jump("AAA", n_rows, -0.08, 1)
    c = one_jump("CCC", n_rows, 0.08, 2)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = g04.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = g04.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
