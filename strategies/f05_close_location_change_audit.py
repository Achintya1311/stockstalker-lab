"""Causality check for `strategies/f05_close_location_change.py` (SPEC.md section 5).
Same shape as `strategies/q06_wick_balance_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` ends on a close
near its low and `CCC` near its high (`location_bar`), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f05_close_location_change as f05
from strategies.t17_keltner_breakout_audit import frame


def location_bar(symbol: str, n_rows: int, close: float) -> pd.DataFrame:
    """Every bar L 99, H 101 at a close of 100 (loc 0), except the last, which closes at `close`."""
    f = frame(symbol, np.full(n_rows, 100.0))
    f[["low", "high"]] = [99.0, 101.0]
    f.loc[f.index[-1], ["open", "close"]] = [100.0, close]
    return f


def check_cross_symbol_causality(n_rows: int = f05.MIN_ROWS + 10) -> dict:
    a = location_bar("AAA", n_rows, 99.5)
    c = location_bar("CCC", n_rows, 100.5)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = f05.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = f05.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
