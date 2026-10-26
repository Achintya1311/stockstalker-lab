"""Causality check for `strategies/q02_return_volume_corr.py` (SPEC.md section 5).
Same shape as `strategies/q01_price_volume_corr_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. Both use `confirmed`
fixtures (volume rises on up days and falls on down days), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import q02_return_volume_corr as q02
from strategies.t17_keltner_breakout_audit import frame


def confirmed(symbol: str, n_rows: int, mu: float, seed: int) -> pd.DataFrame:
    """A drift of `mu` a session; each day's log volume change follows that day's return."""
    rng = np.random.default_rng(seed)
    r = mu + rng.normal(0, 0.01, n_rows)
    f = frame(symbol, 100.0 * np.exp(np.cumsum(r)))
    f["volume"] = 1e6 * np.exp(np.cumsum(20.0 * r + rng.normal(0, 0.02, n_rows)))
    return f


def check_cross_symbol_causality(n_rows: int = q02.MIN_ROWS + 10) -> dict:
    a = confirmed("AAA", n_rows, 0.01, seed=1)
    c = confirmed("CCC", n_rows, -0.01, seed=2)
    rng = np.random.default_rng(3)
    b_long = frame("BBB", 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1))))
    b_long["volume"] = 1e6 * np.exp(rng.normal(0, 0.3, n_rows + 1))
    b_short = b_long.iloc[:n_rows].copy()

    s_without = q02.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = q02.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
