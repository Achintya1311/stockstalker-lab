"""Causality check for `strategies/t17_keltner_breakout.py` (SPEC.md section
5). Same shape as `strategies/t02_golden_death_cross_audit.py`: `truncate()`
in `engine/replay.py` already proves no strategy sees a row on or after its
pick date (B4); this checks that T17's per-symbol arithmetic cannot leak
across symbols. Giving `BBB` one extra trailing row must leave `AAA`'s and
`CCC`'s scores unchanged. `AAA` and `CCC` end with a jump up and a jump down,
so both fire and the check compares real scores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import t17_keltner_breakout as t17


def frame(symbol: str, closes, spread: float = 0.005) -> pd.DataFrame:
    dates = pd.bdate_range("2015-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    rows = []
    prev = float(closes[0])
    for d, c in zip(dates, closes):
        c = float(c)
        rows.append({"date": d, "symbol": symbol, "open": prev, "high": max(prev, c) * (1 + spread),
                     "low": min(prev, c) * (1 - spread), "close": c, "prevclose": prev, "volume": 1e6})
        prev = c
    return pd.DataFrame(rows)


def quiet_then_jump(symbol: str, n_rows: int, jump: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.002, n_rows)))
    closes[-1] = closes[-2] * (1 + jump)
    return frame(symbol, closes)


def check_cross_symbol_causality(n_rows: int = t17.MIN_ROWS + 10) -> dict:
    a = quiet_then_jump("AAA", n_rows, 0.08, seed=1)
    c = quiet_then_jump("CCC", n_rows, -0.08, seed=2)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = frame("BBB", walk[:n_rows]), frame("BBB", walk)

    s_without = t17.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = t17.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
