"""Causality check for `strategies/h05_intermediate_momentum.py` (SPEC.md section 5).

Each stock's score reads only its own rows, so an extra trailing row on `BBB` must
leave every other stock's score unchanged (BBB's own anchors shift by one row, legitimately).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import h05_intermediate_momentum as h05
from strategies.t17_keltner_breakout_audit import frame


def stock(symbol: str, n_rows: int, seed: int, drift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return frame(symbol, 100.0 * np.exp(np.cumsum(rng.normal(drift, 0.01, n_rows))))


def check_cross_symbol_causality(n_rows: int = h05.MIN_ROWS + 10) -> dict:
    others = [stock(f"S{i}", n_rows, 10 + i, 0.001 * (i - 2)) for i in range(5)]
    b_long = stock("BBB", n_rows + 1, 3)
    b_long.loc[b_long.index[-1], "close"] = float(b_long["close"].iloc[-2]) * 3.0
    b_short = b_long.iloc[:n_rows].copy()
    s_without = h05.score(pd.concat(others + [b_short], ignore_index=True))
    s_with = h05.score(pd.concat(others + [b_long], ignore_index=True))
    fired = [s for s in s_without.index if s != "BBB"]
    unaffected = {s: bool(s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
