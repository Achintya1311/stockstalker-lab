"""Causality check for `strategies/h03_turnover_variability.py` (SPEC.md section 5).

Cross-sectional through the day's median, so a row dated after every other stock's
last row must not change their scores except through the median itself. In the
replay every stock is truncated at the same previous close, so the median is always a
same-date quantity; here `BBB`'s turnover is erratic enough to sit above the median
both with and without its extra trailing row (a huge one), so the median is fixed and
every other stock's score must be unchanged. The same holds for H02's audit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import h03_turnover_variability as h03
from strategies.t17_keltner_breakout_audit import frame


def stock(symbol: str, n_rows: int, seed: int, spread: float) -> pd.DataFrame:
    """A random walk whose daily turnover is lognormal with log-std `spread`."""
    rng = np.random.default_rng(seed)
    df = frame(symbol, 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows))))
    df["turnover"] = 1e9 * np.exp(rng.normal(0, spread, n_rows))
    return df


def check_cross_symbol_causality(n_rows: int = h03.WINDOW + 10) -> dict:
    others = [stock(f"S{i}", n_rows, 10 + i, 0.1 + 0.15 * i) for i in range(5)]
    b_long = stock("BBB", n_rows + 1, 3, 2.0)
    b_long.loc[b_long.index[-1], "turnover"] = 1e13
    b_short = b_long.iloc[:n_rows].copy()

    s_without = h03.score(pd.concat(others + [b_short], ignore_index=True))
    s_with = h03.score(pd.concat(others + [b_long], ignore_index=True))
    fired = [s for s in s_without.index if s != "BBB"]
    unaffected = {s: bool(s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
