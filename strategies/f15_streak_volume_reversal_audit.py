"""Causality check for `strategies/f15_streak_volume_reversal.py` (SPEC.md section 5).

Cross-sectional through the streak rank and the median. `BBB` closes up on each of the
last three sessions (streak +3, the top of the rank) in two versions that differ only in
the size of the last rise; its streak and turnover are the same, so every other stock's
score must be unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f15_streak_volume_reversal as f15
from strategies.f13_accel_range_top_audit import walk, with_turnover
from strategies.t17_keltner_breakout_audit import frame


def up_streak(n_rows: int, last_step: float) -> pd.DataFrame:
    steps = np.r_[np.zeros(n_rows - 3), 0.01, 0.01, last_step]
    return with_turnover(frame("BBB", 100.0 * np.exp(np.cumsum(steps))), np.full(n_rows, 1e9))


def check_cross_symbol_causality(n_rows: int = f15.MIN_ROWS + 5) -> dict:
    others = [walk(f"S{i}", n_rows, 110 + i) for i in range(6)]
    s_a = f15.score(pd.concat(others + [up_streak(n_rows, 0.02)], ignore_index=True))
    s_b = f15.score(pd.concat(others + [up_streak(n_rows, 0.20)], ignore_index=True))
    fired = [s for s in s_a.index if s != "BBB"]
    unaffected = {s: bool(s in s_b and abs(s_a[s] - s_b[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
