"""Causality check for `strategies/i01_momentum_score.py` (SPEC.md section 5).

`engine/replay.py`'s `truncate()` already proves no strategy sees a row on or
after its pick date (B4). I01's score is a cross-sectional z-score, so it is
deliberately not invariant to the set of symbols present (as
`strategies/o04_order_block_composite_audit.py`). What must still hold:

1. each symbol's own `raw_ratios` depend only on its own rows: giving `BBB`
   one extra trailing row leaves `AAA`'s and `CCC`'s m6 and m12 unchanged;
2. the ordering of `AAA` and `CCC` by score is unchanged by that row.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import i01_momentum_score


def _synthetic_symbol(symbol: str, n_rows: int, seed: int, drift: float, vol: float = 0.015) -> pd.DataFrame:
    """Deterministic random walk; `n_rows` and `n_rows + 1` from one seed share
    their first `n_rows` values."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    closes = 100.0 * np.exp(np.cumsum(rng.normal(drift, vol, n_rows)))
    rows = []
    prev_close = float(closes[0])
    for date, close in zip(dates, closes):
        close = float(close)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": max(prev_close, close),
                "low": min(prev_close, close),
                "close": close,
                "prevclose": prev_close,
                "volume": 1_000_000.0,
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def check_cross_symbol_causality(n_rows: int = i01_momentum_score.MIN_ROWS + 10) -> dict:
    a = _synthetic_symbol("AAA", n_rows, seed=1, drift=0.002)
    c = _synthetic_symbol("CCC", n_rows, seed=2, drift=-0.002)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3, drift=0.0)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3, drift=0.0)

    without = pd.concat([a, b_short, c], ignore_index=True)
    with_row = pd.concat([a, b_long, c], ignore_index=True)

    r_without = i01_momentum_score.raw_ratios(without)
    r_with = i01_momentum_score.raw_ratios(with_row)
    own_unaffected = {
        s: bool(s in r_without.index and s in r_with.index and r_without.loc[s].equals(r_with.loc[s]))
        for s in ("AAA", "CCC")
    }

    sc_without = i01_momentum_score.score(without)
    sc_with = i01_momentum_score.score(with_row)
    order_kept = bool((sc_without["AAA"] > sc_without["CCC"]) == (sc_with["AAA"] > sc_with["CCC"]))

    passed = all(own_unaffected.values()) and order_kept and "BBB" in r_with.index
    return {"passed": passed, "own_unaffected": own_unaffected, "order_kept": order_kept}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
