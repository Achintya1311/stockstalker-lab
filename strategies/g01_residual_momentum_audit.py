"""Causality check for `strategies/g01_residual_momentum.py` (SPEC.md section 5).

G01 is cross-sectional (the market return averages every stock), so the check is
the one that matters for it: a row dated after every other stock's last row must not
change their scores. `BBB` gets one extra trailing row; `AAA`'s and `CCC`'s scores
must be unchanged. Both get a 12-1 month move away from the market, so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import g01_residual_momentum as g01
from strategies.t17_keltner_breakout_audit import frame


def walk(symbol: str, n_rows: int, seed: int, drift: float = 0.0) -> pd.DataFrame:
    """A random walk whose formation-window log returns (the LOOKBACK before the last SKIP) each get `drift` / LOOKBACK added."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, n_rows)
    r[-(g01.SKIP + g01.LOOKBACK):-g01.SKIP] += drift / g01.LOOKBACK
    return frame(symbol, 100.0 * np.exp(np.cumsum(r)))


def check_cross_symbol_causality(n_rows: int = g01.MIN_ROWS + 10) -> dict:
    a = walk("AAA", n_rows, 1, 0.40)
    c = walk("CCC", n_rows, 2, -0.40)
    b_long = walk("BBB", n_rows + 1, 3)
    b_short = b_long.iloc[:n_rows].copy()

    s_without = g01.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = g01.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
