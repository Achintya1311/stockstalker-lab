"""Causality check for `strategies/f03_conditional_reversal.py` (SPEC.md section 5).
Same shape as `strategies/q06_wick_balance_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` ends on a
five-session rise (continuation) and `CCC` on a lone up day (reversal), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f03_conditional_reversal as f03
from strategies.t17_keltner_breakout_audit import frame


def from_returns(symbol: str, n_flat: int, rets) -> pd.DataFrame:
    """Flat at 100 for `n_flat` rows, then one close per log return in `rets`."""
    closes = np.r_[np.full(n_flat, 100.0), 100.0 * np.exp(np.cumsum(rets))]
    return frame(symbol, closes)


def check_cross_symbol_causality(n_flat: int = 10) -> dict:
    a = from_returns("AAA", n_flat, [0.01, 0.01, 0.01, 0.01, 0.02])
    c = from_returns("CCC", n_flat, [0.01, -0.01, 0.01, -0.01, 0.03])
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_flat + 6)))
    b_short, b_long = frame("BBB", walk[:-1]), frame("BBB", walk)

    s_without = f03.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = f03.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
