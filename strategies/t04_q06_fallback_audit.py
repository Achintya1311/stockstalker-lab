"""Causality check for `strategies/t04_q06_fallback.py`.

Which member a date reads from depends on whether T04 fires on any stock, so a symbol's final score can move
when a peer changes (as with `strategies/e2a_d01c_fallback.py`). The property that must hold is per member:
each member's own reading of a symbol, and its in-universe flag, depend only on that symbol's history. Giving
`BBB` one extra trailing row must leave `AAA`'s and `CCC`'s T04 and Q06 readings unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import q06_wick_balance, t04_connors_rsi2, t04_q06_fallback

MEMBERS = {"t04": t04_connors_rsi2, "q06": q06_wick_balance}


def bars(symbol: str, n_rows: int, seed: int) -> pd.DataFrame:
    """A noisy uptrend with a sharp two-day dip at the end (T04 fires bullish) and wicks on every bar."""
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(0.004 + rng.normal(0, 0.01, n_rows)))
    close[-2:] = close[-3] * np.array([0.96, 0.92])
    open_ = close * (1 + rng.normal(0, 0.004, n_rows))
    high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.01, n_rows))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.02, n_rows))
    dates = pd.bdate_range("2015-01-01", periods=n_rows)
    return pd.DataFrame({
        "date": dates, "symbol": symbol, "open": open_, "high": high, "low": low, "close": close,
        "prevclose": np.r_[close[0], close[:-1]], "volume": 1e6, "turnover": 5e9, "has_future": True,
    })


def _readings(history: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame({name: module.score(history) for name, module in MEMBERS.items()})
    frame["in_universe"] = [s in t04_q06_fallback.likely_in_universe(history) for s in frame.index]
    return frame


def check_cross_symbol_causality(n_rows: int = t04_connors_rsi2.MIN_ROWS + 20) -> dict:
    a, c = bars("AAA", n_rows, seed=1), bars("CCC", n_rows, seed=2)
    b_long = bars("BBB", n_rows + 1, seed=3)
    b_short = b_long.iloc[:n_rows].copy()
    before = _readings(pd.concat([a, b_short, c], ignore_index=True))
    after = _readings(pd.concat([a, b_long, c], ignore_index=True))
    symbols = {}
    for s in ("AAA", "CCC"):
        rb = before.loc[s] if s in before.index else None
        ra = after.loc[s] if s in after.index else None
        symbols[s] = {
            "before": None if rb is None else rb.to_dict(),
            "after": None if ra is None else ra.to_dict(),
            "unaffected": rb is not None and ra is not None and rb.equals(ra) and rb[["t04", "q06"]].notna().any(),
        }
    return {"passed": all(v["unaffected"] for v in symbols.values()), "symbols": symbols}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
