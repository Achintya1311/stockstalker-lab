"""Causality check for `strategies/f07_high_push_fade.py` (SPEC.md section 5).
Same shape as `strategies/q06_wick_balance_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. Both end on a push to a
new high (`push`), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f07_high_push_fade as f07
from strategies.t17_keltner_breakout_audit import frame


def push(symbol: str, n_rows: int, last_two: tuple[float, float]) -> pd.DataFrame:
    """Flat at 100 (high 100.5), then two closes at `last_two`; highs follow with the 0.5% spread."""
    closes = np.r_[np.full(n_rows - 2, 100.0), last_two]
    return frame(symbol, closes)


def check_cross_symbol_causality(n_rows: int = f07.MIN_ROWS + 10) -> dict:
    a = push("AAA", n_rows, (102.0, 104.0))
    c = push("CCC", n_rows, (101.0, 106.0))
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = f07.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = f07.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
