"""Causality check for `strategies/h01_amihud_illiquidity.py` (SPEC.md section 5).

Cross-sectional only through the median. `BBB` is far more illiquid than the others
with and without its extra trailing row (a huge price move), so the median stays the
same and every other stock's score must be unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import h01_amihud_illiquidity as h01
from strategies.t17_keltner_breakout_audit import frame


def stock(symbol: str, n_rows: int, seed: int, vol: float, turnover: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = frame(symbol, 100.0 * np.exp(np.cumsum(rng.normal(0, vol, n_rows))))
    df["turnover"] = turnover * np.exp(rng.normal(0, 0.1, n_rows))
    return df


def check_cross_symbol_causality(n_rows: int = h01.WINDOW + 10) -> dict:
    others = [stock(f"S{i}", n_rows, 10 + i, 0.01, 1e9 * (i + 1)) for i in range(5)]
    b_long = stock("BBB", n_rows + 1, 3, 0.03, 1e6)
    b_long.loc[b_long.index[-1], "close"] = float(b_long["close"].iloc[-2]) * 1.5
    b_short = b_long.iloc[:n_rows].copy()

    s_without = h01.score(pd.concat(others + [b_short], ignore_index=True))
    s_with = h01.score(pd.concat(others + [b_long], ignore_index=True))
    fired = [s for s in s_without.index if s != "BBB"]
    unaffected = {s: bool(s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
