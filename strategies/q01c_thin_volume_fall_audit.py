"""Causality check for `strategies/q01c_thin_volume_fall.py`.

Q01C keeps Q01's positive scores and negates them, so it inherits Q01's per-symbol
causality exactly; this reruns Q01's audit scenario (`AAA` rises and `CCC` falls,
both on thinning volume; `BBB` gets one extra trailing row) through Q01C's `score`.
Only `CCC` fires here, so `AAA` must abstain both times and `CCC` must be unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import q01_price_volume_corr as q01
from strategies import q01c_thin_volume_fall as q01c
from strategies.q01_price_volume_corr_audit import thinning
from strategies.t17_keltner_breakout_audit import frame


def check_cross_symbol_causality(n_rows: int = q01.MIN_ROWS + 10) -> dict:
    a = thinning("AAA", n_rows, 0.01, seed=1)
    c = thinning("CCC", n_rows, -0.01, seed=2)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_long = frame("BBB", walk)
    b_long["volume"] = 1e6 * np.exp(rng.normal(0, 0.3, n_rows + 1))
    b_short = b_long.iloc[:n_rows].copy()

    without = q01c.score(pd.concat([a, b_short, c], ignore_index=True))
    with_ = q01c.score(pd.concat([a, b_long, c], ignore_index=True))
    symbols = {
        "AAA": bool("AAA" not in without and "AAA" not in with_),
        "CCC": bool("CCC" in without and "CCC" in with_ and without["CCC"] == with_["CCC"]),
    }
    return {"passed": all(symbols.values()), "symbols": symbols}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
