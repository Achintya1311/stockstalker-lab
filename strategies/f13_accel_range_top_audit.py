"""Causality check for `strategies/f13_accel_range_top.py` (SPEC.md section 5).

Cross-sectional through three ranks and the median. `BBB` is flat, then rises on a
growing step with growing turnover, so its last close is a 10-session high, its last move
the most accelerating and its turnover ratio a 5-session high. Two versions of BBB that
differ only in how extreme that last session is hold the same place in every rank, so
every other stock's score must be unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f13_accel_range_top as f13
from strategies.t17_keltner_breakout_audit import frame


def with_turnover(df: pd.DataFrame, turnover) -> pd.DataFrame:
    return df.assign(turnover=np.asarray(turnover, float), has_future=True)


def walk(symbol: str, n_rows: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows)))
    return with_turnover(frame(symbol, closes), 1e9 * np.exp(rng.normal(0, 0.2, n_rows)))


def surge(n_rows: int, last_step: float) -> pd.DataFrame:
    steps = np.r_[np.zeros(n_rows - 3), 0.05, 0.15, last_step]
    turnover = np.r_[np.full(n_rows - 3, 1e9), 2e9, 4e9, 8e9 * (1 + last_step)]
    return with_turnover(frame("BBB", 100.0 * np.exp(np.cumsum(steps))), turnover)


def check_cross_symbol_causality(n_rows: int = f13.MIN_ROWS + 6) -> dict:
    others = [walk(f"S{i}", n_rows, 30 + i) for i in range(6)]
    s_a = f13.score(pd.concat(others + [surge(n_rows, 0.40)], ignore_index=True))
    s_b = f13.score(pd.concat(others + [surge(n_rows, 0.90)], ignore_index=True))
    fired = [s for s in s_a.index if s != "BBB"]
    unaffected = {s: bool(s in s_b and abs(s_a[s] - s_b[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and "BBB" in s_a and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
