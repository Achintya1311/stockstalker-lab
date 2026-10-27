"""Causality check for `strategies/f06_trend_acceleration.py` (SPEC.md section 5).
Same shape as `strategies/q06_wick_balance_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` speeds up and
`CCC` slows down (`two_slopes`), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f06_trend_acceleration as f06
from strategies.t17_keltner_breakout_audit import frame


def two_slopes(symbol: str, n_rows: int, older: float, recent: float) -> pd.DataFrame:
    """Log closes rising `older` a session, then `recent` a session over the last HALF sessions."""
    steps = np.r_[np.full(n_rows - 1 - f06.HALF, older), np.full(f06.HALF, recent)]
    return frame(symbol, 100.0 * np.exp(np.r_[0.0, np.cumsum(steps)]))


def check_cross_symbol_causality(n_rows: int = f06.MIN_ROWS + 10) -> dict:
    a = two_slopes("AAA", n_rows, 0.0, 0.02)
    c = two_slopes("CCC", n_rows, 0.02, 0.0)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = f06.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = f06.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
