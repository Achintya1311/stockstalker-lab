"""Causality check for `strategies/q06_wick_balance.py` (SPEC.md section 5).
Same shape as `strategies/t17_keltner_breakout_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that Q06's per-symbol arithmetic (including its
per-symbol `tail`) cannot leak across symbols. Giving `BBB` one extra trailing
row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` ends on a long lower
wick and `CCC` on a long upper wick (`wick_bar`), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import q06_wick_balance as q06
from strategies.t17_keltner_breakout_audit import frame


def wick_bar(symbol: str, n_rows: int, side: int) -> pd.DataFrame:
    """Flat at 100, then a last bar opening and closing near 100 with a 5% wick
    below (`side` +1) or above (-1) and a 0.5% wick on the other end."""
    f = frame(symbol, np.full(n_rows, 100.0))
    i = n_rows - 1
    f.loc[i, ["open", "close"]] = [100.0, 100.2]
    f.loc[i, ["low", "high"]] = [95.0, 100.7] if side > 0 else [99.5, 105.2]
    return f


def check_cross_symbol_causality(n_rows: int = q06.MIN_ROWS + 10) -> dict:
    a = wick_bar("AAA", n_rows, +1)
    c = wick_bar("CCC", n_rows, -1)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = q06.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = q06.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
