"""Causality check for `strategies/f08_weighted_reversal.py` (SPEC.md section 5).

Cross-sectional only through the yearly-return rank. `BBB` gets one extra trailing row;
its yearly return is far above every other stock's with and without that row, and its
7-session change is non-zero both times, so the ranks of the others, and their scores,
must be unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f08_weighted_reversal as f08
from strategies.t17_keltner_breakout_audit import frame


def walk(symbol: str, n_rows: int, seed: int, drift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return frame(symbol, 100.0 * np.exp(np.cumsum(rng.normal(drift, 0.01, n_rows))))


def check_cross_symbol_causality(n_rows: int = f08.MIN_ROWS + 5) -> dict:
    others = [walk(f"S{i}", n_rows, 10 + i) for i in range(5)]
    b_long = walk("BBB", n_rows + 1, 3, drift=0.01)
    b_short = b_long.iloc[:n_rows].copy()

    s_without = f08.score(pd.concat(others + [b_short], ignore_index=True))
    s_with = f08.score(pd.concat(others + [b_long], ignore_index=True))
    fired = [s for s in s_without.index if s != "BBB"]
    unaffected = {s: bool(s in s_with and s_without[s] == s_with[s]) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
