"""Causality check for `strategies/f19_body_volatility_fade.py` (SPEC.md section 5).

Cross-sectional through the final rank only. `BBB` ends on a large up body in two versions that
differ only in how large (+10% or +60%), so it has the highest raw value in both and every other
stock's rank, and score, must be unchanged. Each stock's raw value reads only its own rows.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import f19_body_volatility_fade as f19
from strategies.f13_accel_range_top_audit import walk, with_turnover
from strategies.t17_keltner_breakout_audit import frame


def jumper(n_rows: int, last_step: float, symbol: str = "BBB") -> pd.DataFrame:
    steps = np.r_[np.zeros(n_rows - 1) + 0.001 * np.arange(n_rows - 1), last_step]
    return with_turnover(frame(symbol, 100.0 * np.exp(np.cumsum(steps))), np.full(n_rows, 1e9))


def check_cross_symbol_causality(n_rows: int = f19.MIN_ROWS + 5) -> dict:
    others = [walk(f"S{i}", n_rows, 70 + i) for i in range(6)]
    s_a = f19.score(pd.concat(others + [jumper(n_rows, 0.10)], ignore_index=True))
    s_b = f19.score(pd.concat(others + [jumper(n_rows, 0.60)], ignore_index=True))
    fired = [s for s in s_a.index if s != "BBB"]
    unaffected = {s: bool(s in s_b and abs(s_a[s] - s_b[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
