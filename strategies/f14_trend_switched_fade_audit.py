"""Causality check for `strategies/f14_trend_switched_fade.py` (SPEC.md section 5).

The score is per symbol; only the cross-section filter looks across stocks. Adding an
extra row to one stock (`BBB`, with every stock sharing the slice's dates up to then)
must leave every other stock's score unchanged, and a stock's score must not depend on
rows after the slice's last date (the engine truncates; here the slice is cut by hand).
"""

from __future__ import annotations

import pandas as pd

from strategies import f14_trend_switched_fade as f14
from strategies.f13_accel_range_top_audit import walk


def check_cross_symbol_causality(n_rows: int = f14.MIN_ROWS + 5) -> dict:
    others = [walk(f"S{i}", n_rows, 90 + i) for i in range(4)]
    b1 = walk("BBB", n_rows, 7)
    b2 = b1.copy()
    b2.loc[b2.index[-1], ["close", "high"]] = b2[["close", "high"]].iloc[-1] * 1.5
    s_a = f14.score(pd.concat(others + [b1], ignore_index=True))
    s_b = f14.score(pd.concat(others + [b2], ignore_index=True))
    fired = [s for s in s_a.index if s != "BBB"]
    unaffected = {s: bool(s in s_b and abs(s_a[s] - s_b[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
