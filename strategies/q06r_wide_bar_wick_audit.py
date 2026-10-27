"""Causality check for `strategies/q06r_wide_bar_wick.py` (SPEC.md section 5).
Same shape as `strategies/q06_wick_balance_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. `wick_bar` ends on a
bar about ten times wider than the flat bars before it, so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import q06r_wide_bar_wick as q06r
from strategies.q06_wick_balance_audit import wick_bar
from strategies.t17_keltner_breakout_audit import frame


def check_cross_symbol_causality(n_rows: int = q06r.MIN_ROWS + 10) -> dict:
    a = wick_bar("AAA", n_rows, +1)
    c = wick_bar("CCC", n_rows, -1)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = q06r.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = q06r.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
