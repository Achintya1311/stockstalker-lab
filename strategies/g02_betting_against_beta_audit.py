"""Causality check for `strategies/g02_betting_against_beta.py` (SPEC.md section 5).

G02 is cross-sectional (the market return averages every stock), so the check is
the one that matters for it: a row dated after every other stock's last row must not
change their scores. `BBB` gets one extra trailing row; `AAA`'s and `CCC`'s scores
must be unchanged. `AAA` moves with the common factor at half strength and `CCC` at
double strength, so their betas sit either side of 1 and both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import g02_betting_against_beta as g02
from strategies.t17_keltner_breakout_audit import frame


def loaded(symbol: str, n_rows: int, loading: float, seed: int, factor_seed: int = 0) -> pd.DataFrame:
    """Log returns = `loading` x a shared factor + idiosyncratic noise."""
    f = np.random.default_rng(factor_seed).normal(0, 0.01, n_rows - 1)
    e = np.random.default_rng(seed).normal(0, 0.005, n_rows - 1)
    return frame(symbol, 100.0 * np.exp(np.r_[0.0, np.cumsum(loading * f + e)]))


def check_cross_symbol_causality(n_rows: int = g02.MIN_ROWS + 10) -> dict:
    a = loaded("AAA", n_rows, 0.5, 1)
    c = loaded("CCC", n_rows, 2.0, 2)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = g02.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = g02.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
