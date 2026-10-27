"""Causality check for `strategies/f01_body_share.py` (SPEC.md section 5).
Same shape as `strategies/q06_wick_balance_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` ends on an
up bar and `CCC` on a down bar (`body_bar`), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f01_body_share as f01
from strategies.t17_keltner_breakout_audit import frame


def body_bar(symbol: str, n_rows: int, side: int) -> pd.DataFrame:
    """Flat at 100, then a last bar O 100, H 104, L 99 with the close at 103 (`side`
    +1) or 97 with H 101, L 96 (-1): body 3 on a range of 5."""
    f = frame(symbol, np.full(n_rows, 100.0))
    i = n_rows - 1
    if side > 0:
        f.loc[i, ["open", "high", "low", "close"]] = [100.0, 104.0, 99.0, 103.0]
    else:
        f.loc[i, ["open", "high", "low", "close"]] = [100.0, 101.0, 96.0, 97.0]
    return f


def check_cross_symbol_causality(n_rows: int = f01.MIN_ROWS + 10) -> dict:
    a = body_bar("AAA", n_rows, +1)
    c = body_bar("CCC", n_rows, -1)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = f01.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = f01.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
