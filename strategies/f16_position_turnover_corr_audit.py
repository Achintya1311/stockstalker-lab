"""Causality check for `strategies/f16_position_turnover_corr.py` (SPEC.md section 5).

Cross-sectional through the daily ranks. `BBB` has the highest range position and the
highest turnover on each of the last 6 dates in two versions that differ only in how
extreme its last session is, so its place in every daily rank is the same and every
other stock's score must be unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f16_position_turnover_corr as f16
from strategies.f13_accel_range_top_audit import walk, with_turnover
from strategies.t17_keltner_breakout_audit import frame


def leader(n_rows: int, last_step: float) -> pd.DataFrame:
    steps = np.r_[np.zeros(n_rows - 7), np.full(6, 0.05), last_step]
    turnover = np.r_[np.full(n_rows - 7, 1e9), 1e11 * np.arange(1, 7), 1e12 * (1 + last_step)]
    return with_turnover(frame("BBB", 100.0 * np.exp(np.cumsum(steps))), turnover)


def check_cross_symbol_causality(n_rows: int = f16.MIN_ROWS + 4) -> dict:
    others = [walk(f"S{i}", n_rows, 50 + i) for i in range(6)]
    s_a = f16.score(pd.concat(others + [leader(n_rows, 0.10)], ignore_index=True))
    s_b = f16.score(pd.concat(others + [leader(n_rows, 0.60)], ignore_index=True))
    fired = [s for s in s_a.index if s != "BBB"]
    unaffected = {s: bool(s in s_b and abs(s_a[s] - s_b[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
