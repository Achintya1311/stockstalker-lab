"""Causality check for `strategies/f02_volume_signed_reversal.py` (SPEC.md section 5).
Same shape as `strategies/q06_wick_balance_audit.py`: giving `BBB` one extra
trailing row must leave `AAA`'s and `CCC`'s scores unchanged. `AAA` ends on a fall
on rising volume and `CCC` on a rise on rising volume (`last_move`), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f02_volume_signed_reversal as f02
from strategies.t17_keltner_breakout_audit import frame


def last_move(symbol: str, n_rows: int, move: float, volume_jump: float) -> pd.DataFrame:
    """Flat at 100 on volume 1e6, then a last close of 100 x exp(`move`) on volume 1e6 x `volume_jump`."""
    closes = np.full(n_rows, 100.0)
    closes[-1] = 100.0 * np.exp(move)
    f = frame(symbol, closes)
    f.loc[f.index[-1], "volume"] = 1e6 * volume_jump
    return f


def check_cross_symbol_causality(n_rows: int = f02.MIN_ROWS + 10) -> dict:
    a = last_move("AAA", n_rows, -0.04, 2.0)
    c = last_move("CCC", n_rows, 0.04, 2.0)
    rng = np.random.default_rng(3)
    walk = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n_rows + 1)))
    b_long = frame("BBB", walk)
    b_long["volume"] = 1e6 * np.exp(rng.normal(0, 0.3, n_rows + 1))
    b_short = b_long.iloc[:n_rows].copy()

    s_without = f02.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = f02.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
