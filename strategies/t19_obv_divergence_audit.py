"""Causality check for `strategies/t19_obv_divergence.py` (SPEC.md section 5).
Same shape as `strategies/t02_golden_death_cross_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that T19's per-symbol arithmetic cannot leak across
symbols. Giving `BBB` one extra trailing row must leave `AAA`'s and `CCC`'s
scores unchanged. `AAA` and `CCC` are built to diverge bullish and bearish.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import t19_obv_divergence as t19
from strategies.t21_minervini_template_audit import _frame


def diverging(symbol: str, bullish: bool, pad: int = 10) -> pd.DataFrame:
    """Prior window: a heavy-volume sell-off to a low. Recent window: a slightly
    lower low reached on light volume after heavy-volume up days, so OBV's low
    is higher (bullish). `bullish=False` mirrors it."""
    s = 1.0 if bullish else -1.0
    prior = 100.0 - s * np.linspace(0, 10, 20)
    recent = np.r_[100.0 - s * np.linspace(9, 5, 10), 100.0 - s * np.linspace(5, 10.5, 10)]
    closes = np.r_[np.full(pad + 1, 100.0), prior, recent]
    vol = np.r_[np.full(pad + 1, 1e6), np.full(20, 3e6), np.full(10, 3e6), np.full(10, 0.5e6)]
    frame = _frame(symbol, closes)
    frame["volume"] = vol
    return frame


def check_cross_symbol_causality() -> dict:
    a, c = diverging("AAA", True), diverging("CCC", False)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, len(a) + 1)))
    b_short, b_long = _frame("BBB", walk[:-1]), _frame("BBB", walk)

    s_without = t19.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = t19.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
