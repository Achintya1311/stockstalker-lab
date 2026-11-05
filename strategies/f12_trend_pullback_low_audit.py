"""Causality check for `strategies/f12_trend_pullback_low.py` (SPEC.md section 5).

Cross-sectional only through the trend rank. `BBB` gets one extra trailing row; its
11-month return is far above every other stock's with and without that row, and its
5-session lows move both times, so the others' ranks and scores must be unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f12_trend_pullback_low as f12
from strategies.t17_keltner_breakout_audit import frame


def walk(symbol: str, n_rows: int, seed: int, drift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = frame(symbol, 100.0 * np.exp(np.cumsum(rng.normal(drift, 0.01, n_rows))))
    df["volume"] = 1e6 * np.exp(rng.normal(0, 0.3, n_rows))
    return df


def check_cross_symbol_causality(n_rows: int = f12.MIN_ROWS + 5) -> dict:
    others = [walk(f"S{i}", n_rows, 30 + i) for i in range(5)]
    b_long = walk("BBB", n_rows + 1, 4, drift=0.01)
    b_short = b_long.iloc[:n_rows].copy()

    s_without = f12.score(pd.concat(others + [b_short], ignore_index=True))
    s_with = f12.score(pd.concat(others + [b_long], ignore_index=True))
    fired = [s for s in s_without.index if s != "BBB"]
    unaffected = {s: bool(s in s_with and abs(s_without[s] - s_with[s]) < 1e-15) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()) and "BBB" in s_without and "BBB" in s_with,
            "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
