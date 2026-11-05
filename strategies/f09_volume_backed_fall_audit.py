"""Causality check for `strategies/f09_volume_backed_fall.py` (SPEC.md section 5).

Cross-sectional only through the median. `BBB` is given one extra trailing row; it
sits above the median both with and without that row (a heavy session after a steep
fall in both), so the median and every other stock's score must be unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f09_volume_backed_fall as f09
from strategies.t17_keltner_breakout_audit import frame


def stock(symbol: str, closes, turnover) -> pd.DataFrame:
    df = frame(symbol, np.asarray(closes, float))
    df["turnover"] = np.asarray(turnover, float)
    return df


def walk(symbol: str, n_rows: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return stock(symbol, 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows))),
                 1e9 * np.exp(rng.normal(0, 0.2, n_rows)))


def check_cross_symbol_causality(n_rows: int = f09.MIN_ROWS + 10) -> dict:
    others = [walk(f"S{i}", n_rows, 10 + i) for i in range(5)]
    closes = np.r_[np.full(n_rows - 8, 100.0), 100.0 * np.exp(-0.02 * np.arange(1, 10))]
    turnover = np.r_[np.full(n_rows - 1, 1e9), 5e9, 6e9]
    b_long = stock("BBB", closes, turnover)
    b_short = b_long.iloc[:n_rows].copy()

    s_without = f09.score(pd.concat(others + [b_short], ignore_index=True))
    s_with = f09.score(pd.concat(others + [b_long], ignore_index=True))
    fired = [s for s in s_without.index if s != "BBB"]
    unaffected = {s: bool(s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
