"""Causality check for `strategies/g05_residual_reversal.py` (SPEC.md section 5).

G05 is cross-sectional (the market return averages every stock), so the check is
the one that matters for it: a row dated after every other stock's last row must not
change their scores. `BBB` gets one extra trailing row; `AAA`'s and `CCC`'s scores
must be unchanged. Both get a last-week move away from the market, so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import g05_residual_reversal as g05
from strategies.t17_keltner_breakout_audit import frame


def walk(symbol: str, n_rows: int, seed: int, last_week: float = 0.0) -> pd.DataFrame:
    """A random walk whose last LOOKBACK log returns each get `last_week` / LOOKBACK added."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, n_rows)
    r[-g05.LOOKBACK:] += last_week / g05.LOOKBACK
    return frame(symbol, 100.0 * np.exp(np.cumsum(r)))


def check_cross_symbol_causality(n_rows: int = g05.MIN_ROWS + 10) -> dict:
    a = walk("AAA", n_rows, 1, 0.08)
    c = walk("CCC", n_rows, 2, -0.08)
    b_long = walk("BBB", n_rows + 1, 3)
    b_short = b_long.iloc[:n_rows].copy()

    s_without = g05.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = g05.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
