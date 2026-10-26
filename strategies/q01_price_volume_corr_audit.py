"""Causality check for `strategies/q01_price_volume_corr.py` (SPEC.md section 5).
Same shape as `strategies/t17_keltner_breakout_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that Q01's per-symbol arithmetic (including its
per-symbol `tail`) cannot leak across symbols. Giving `BBB` one extra trailing
row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` rises and `CCC` falls,
both on thinning volume (`thinning`), so both fire and the check compares real
scores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import q01_price_volume_corr as q01
from strategies.t17_keltner_breakout_audit import frame


def thinning(symbol: str, n_rows: int, mu: float, seed: int) -> pd.DataFrame:
    """A drift of `mu` a session with volume falling 3% a session plus noise."""
    rng = np.random.default_rng(seed)
    f = frame(symbol, 100.0 * np.exp(np.cumsum(mu + rng.normal(0, 0.003, n_rows))))
    f["volume"] = 1e6 * np.exp(-0.03 * np.arange(n_rows) + rng.normal(0, 0.05, n_rows))
    return f


def check_cross_symbol_causality(n_rows: int = q01.MIN_ROWS + 10) -> dict:
    a = thinning("AAA", n_rows, 0.01, seed=1)
    c = thinning("CCC", n_rows, -0.01, seed=2)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_long = frame("BBB", walk)
    b_long["volume"] = 1e6 * np.exp(rng.normal(0, 0.3, n_rows + 1))
    b_short = b_long.iloc[:n_rows].copy()

    s_without = q01.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = q01.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
