"""Causality check for `strategies/g01b_residual_momentum_volatile.py` (SPEC.md section 5).

Cross-sectional twice over (the market return and the median residual volatility both
use every stock), so a row dated after every other stock's last row must not change
their scores. Same layout as G01's audit, with more stocks so the median is not trivial.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import g01b_residual_momentum_volatile as g01b
from strategies.t17_keltner_breakout_audit import frame


def walk(symbol: str, n_rows: int, seed: int, drift: float = 0.0, sigma: float = 0.01) -> pd.DataFrame:
    """G01's audit walk with a chosen daily volatility, so some losers sit above the median."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, sigma, n_rows)
    r[-(g01b.SKIP + g01b.LOOKBACK):-g01b.SKIP] += drift / g01b.LOOKBACK
    return frame(symbol, 100.0 * np.exp(np.cumsum(r)))


def check_cross_symbol_causality(n_rows: int = g01b.MIN_ROWS + 10) -> dict:
    others = [walk(f"S{i}", n_rows, 10 + i, -0.60 + 0.2 * i, 0.02 if i % 2 == 0 else 0.008) for i in range(6)]
    b_long = walk("BBB", n_rows + 1, 3)
    b_short = b_long.iloc[:n_rows].copy()

    s_without = g01b.score(pd.concat(others + [b_short], ignore_index=True))
    s_with = g01b.score(pd.concat(others + [b_long], ignore_index=True))
    fired = [s for s in s_without.index if s != "BBB"]
    unaffected = {s: bool(s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
