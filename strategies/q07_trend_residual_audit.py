"""Causality check for `strategies/q07_trend_residual.py` (SPEC.md section 5).
Same shape as `strategies/q05_trend_smoothness_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` ends on a dip
below a rising line and `CCC` on a jump above a falling one, so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import q07_trend_residual as q07
from strategies.t17_keltner_breakout_audit import frame


def line_then_last(symbol: str, n_rows: int, slope: float, last: float) -> pd.DataFrame:
    """Log closes on a straight line of `slope` a session, with the last one moved by `last` (log)."""
    y = np.log(100.0) + slope * np.arange(n_rows)
    y[-1] += last
    return frame(symbol, np.exp(y))


def check_cross_symbol_causality(n_rows: int = q07.MIN_ROWS + 10) -> dict:
    a = line_then_last("AAA", n_rows, 0.01, -0.05)
    c = line_then_last("CCC", n_rows, -0.01, 0.05)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = q07.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = q07.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
