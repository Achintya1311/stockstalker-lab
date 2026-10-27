"""Causality check for `strategies/f04_open_volume_corr.py` (SPEC.md section 5).
Same shape as `strategies/q02_return_volume_corr_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA`'s volume falls as
its opens rise and `CCC`'s rises with them (`trend_with_volume`), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f04_open_volume_corr as f04
from strategies.t17_keltner_breakout_audit import frame


def trend_with_volume(symbol: str, n_rows: int, volume_step: float) -> pd.DataFrame:
    """Closes (and so next-day opens) rising 1% a session; volume x exp(`volume_step`) a session."""
    f = frame(symbol, 100.0 * np.exp(0.01 * np.arange(n_rows)))
    f["volume"] = 1e6 * np.exp(volume_step * np.arange(n_rows))
    return f


def check_cross_symbol_causality(n_rows: int = f04.MIN_ROWS + 10) -> dict:
    a = trend_with_volume("AAA", n_rows, -0.1)
    c = trend_with_volume("CCC", n_rows, 0.1)
    rng = np.random.default_rng(3)
    b_long = frame("BBB", 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1))))
    b_long["volume"] = 1e6 * np.exp(rng.normal(0, 0.3, n_rows + 1))
    b_short = b_long.iloc[:n_rows].copy()

    s_without = f04.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = f04.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
