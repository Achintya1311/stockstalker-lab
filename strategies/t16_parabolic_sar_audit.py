"""Causality check for `strategies/t16_parabolic_sar.py` (SPEC.md section 5).
Same shape as `strategies/t02_golden_death_cross_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that T16's per-symbol recursion cannot leak across
symbols. Giving `BBB` one extra trailing row must leave `AAA`'s and `CCC`'s
scores unchanged.
"""

from __future__ import annotations

import pandas as pd

from strategies import t16_parabolic_sar as t16
from strategies.i01_momentum_score_audit import _synthetic_symbol


def check_cross_symbol_causality(n_rows: int = t16.MIN_ROWS + 10) -> dict:
    a = _synthetic_symbol("AAA", n_rows, seed=1, drift=0.003)
    c = _synthetic_symbol("CCC", n_rows, seed=2, drift=-0.003)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3, drift=0.0)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3, drift=0.0)

    s_without = t16.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = t16.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
