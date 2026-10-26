"""Causality check for `strategies/t25_heikin_ashi.py` (SPEC.md section 5).
Same shape as `strategies/t02_golden_death_cross_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that T25's per-symbol recursion cannot leak across
symbols. Giving `BBB` one extra trailing row must leave `AAA`'s and `CCC`'s
scores unchanged. `AAA` and `CCC` are built to fire bullish and bearish.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import t25_heikin_ashi as t25


def trending(symbol: str, n_rows: int, daily: float) -> pd.DataFrame:
    """Each candle opens at the previous close and moves `daily` (fractional)
    with no wick against the move, so a steady run fires."""
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    rows = []
    prev = 100.0
    for d in dates:
        close = prev * (1 + daily)
        rows.append({"date": d, "symbol": symbol, "open": prev, "high": max(prev, close) * 1.002,
                     "low": min(prev, close) * 0.998, "close": close, "prevclose": prev, "volume": 1e6})
        prev = close
    return pd.DataFrame(rows)


def check_cross_symbol_causality(n_rows: int = t25.MIN_ROWS + 10) -> dict:
    a = trending("AAA", n_rows, 0.01)
    c = trending("CCC", n_rows, -0.01)
    rng = np.random.default_rng(3)
    b_long = trending("BBB", n_rows + 1, 0.0)
    b_long["close"] = b_long["close"] * np.exp(rng.normal(0, 0.01, n_rows + 1))
    b_short = b_long.iloc[:n_rows]

    s_without = t25.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = t25.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
