"""Causality check for `strategies/t21_minervini_template.py` (SPEC.md
section 5). Same shape as `strategies/t02_golden_death_cross_audit.py`:
`engine/replay.py`'s `truncate()` already proves no strategy sees a row on or
after its pick date (B4); this checks that T21's per-symbol arithmetic cannot
leak across symbols. Giving `BBB` one extra trailing row must leave `AAA`'s
and `CCC`'s scores unchanged. `AAA` and `CCC` are built to pass the bullish
and bearish templates, so the check compares real scores, not two abstains.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import t21_minervini_template as t21


def _frame(symbol: str, closes) -> pd.DataFrame:
    dates = pd.bdate_range("2015-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    rows = []
    prev = float(closes[0])
    for d, c in zip(dates, closes):
        c = float(c)
        rows.append({"date": d, "symbol": symbol, "open": prev, "high": max(prev, c), "low": min(prev, c),
                     "close": c, "prevclose": prev, "volume": 1e6})
        prev = c
    return pd.DataFrame(rows)


def trend(symbol: str, daily: float, n_rows: int) -> pd.DataFrame:
    """Steady exponential trend with a tiny alternating wiggle."""
    t = np.arange(n_rows)
    logs = daily * t + np.where(t % 2 == 0, 0.0, 0.0005)
    return _frame(symbol, 100.0 * np.exp(logs))


def check_cross_symbol_causality(n_rows: int = t21.MIN_ROWS + 10) -> dict:
    a = trend("AAA", 0.003, n_rows)
    c = trend("CCC", -0.003, n_rows)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_short, b_long = _frame("BBB", walk[:n_rows]), _frame("BBB", walk)

    s_without = t21.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = t21.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
