"""Causality check for `strategies/h02_idiosyncratic_volatility.py` (SPEC.md section 5).

Cross-sectional (the market mean and the median use every stock), so a row dated after
every other stock's last row must not change their scores. `BBB` gets one extra
trailing row; the other stocks' scores must be unchanged. `BBB` is the most volatile
stock with or without that row, so the day's median is fixed: in the replay every
stock ends at the same previous close, so the median is a same-date quantity
(see `strategies/h03_turnover_variability_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import h02_idiosyncratic_volatility as h02
from strategies.t17_keltner_breakout_audit import frame


def walk(symbol: str, n_rows: int, seed: int, sigma: float = 0.01) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return frame(symbol, 100.0 * np.exp(np.cumsum(rng.normal(0, sigma, n_rows))))


def check_cross_symbol_causality(n_rows: int = h02.MIN_ROWS + 10) -> dict:
    others = [walk(f"S{i}", n_rows, 10 + i, 0.005 + 0.004 * i) for i in range(5)]
    b_long = walk("BBB", n_rows + 1, 3, 0.03)
    b_short = b_long.iloc[:n_rows].copy()

    s_without = h02.score(pd.concat(others + [b_short], ignore_index=True))
    s_with = h02.score(pd.concat(others + [b_long], ignore_index=True))
    fired = [s for s in s_without.index if s != "BBB"]
    unaffected = {s: bool(s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
