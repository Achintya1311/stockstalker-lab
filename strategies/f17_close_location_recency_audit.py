"""Causality check for `strategies/f17_close_location_recency.py` (SPEC.md section 5).

Cross-sectional through two ranks, the scaling and the median. `BBB` closes at the top of
its last bar on the heaviest turnover and sets a fresh 10-session high, in two versions
that differ only in how extreme that last session is: its place in both ranks is the same,
so every other stock's score must be unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f17_close_location_recency as f17
from strategies.f13_accel_range_top_audit import walk, with_turnover
from strategies.t17_keltner_breakout_audit import frame


def top_close(n_rows: int, last_step: float) -> pd.DataFrame:
    steps = np.r_[np.zeros(n_rows - 1), last_step]
    df = with_turnover(frame("BBB", 100.0 * np.exp(np.cumsum(steps))),
                       np.r_[np.full(n_rows - 1, 1e9), 1e12 * (1 + last_step)])
    df.loc[df.index[-1], "high"] = df["close"].iloc[-1]  # close at the bar's high: clv = +1
    return df


def check_cross_symbol_causality(n_rows: int = f17.MIN_ROWS + 5) -> dict:
    others = [walk(f"S{i}", n_rows, 70 + i) for i in range(6)]
    s_a = f17.score(pd.concat(others + [top_close(n_rows, 0.05)], ignore_index=True))
    s_b = f17.score(pd.concat(others + [top_close(n_rows, 0.30)], ignore_index=True))
    fired = [s for s in s_a.index if s != "BBB"]
    unaffected = {s: bool(s in s_b and abs(s_a[s] - s_b[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
