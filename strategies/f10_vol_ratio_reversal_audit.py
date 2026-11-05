"""Causality check for `strategies/f10_vol_ratio_reversal.py` (SPEC.md section 5).

Cross-sectional through two ranks and the median. `BBB` is flat, then jumps 20% a
session: with its last two sessions both jumps (short slice) or its last three (long
slice), its 2-session deviation is 0, the lowest ratio in the set, and its last return
the highest. Its place in both ranks is the same either way, so every other stock's
score must be unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f10_vol_ratio_reversal as f10
from strategies.t17_keltner_breakout_audit import frame


def walk(symbol: str, n_rows: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return frame(symbol, 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows))))


def check_cross_symbol_causality(n_rows: int = f10.MIN_ROWS + 10) -> dict:
    others = [walk(f"S{i}", n_rows, 10 + i) for i in range(6)]
    closes = np.r_[np.full(n_rows - 2, 100.0), 100.0 * 1.2 ** np.arange(1, 4)]
    b_long = frame("BBB", closes)
    b_short = b_long.iloc[:n_rows].copy()

    s_without = f10.score(pd.concat(others + [b_short], ignore_index=True))
    s_with = f10.score(pd.concat(others + [b_long], ignore_index=True))
    fired = [s for s in s_without.index if s != "BBB"]
    unaffected = {s: bool(s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
