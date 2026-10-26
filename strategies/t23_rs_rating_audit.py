"""Causality check for `strategies/t23_rs_rating.py` (SPEC.md section 5).

`engine/replay.py`'s `truncate()` already proves no strategy sees a row on or
after its pick date (B4). T23's score is a cross-sectional rank, so it is
deliberately not invariant to the set of symbols present (as
`strategies/o04_order_block_composite_audit.py`). What must still hold:

1. each symbol's own `raw_perf` depends only on its own rows: giving `BBB` one
   extra trailing row leaves `AAA`'s and `CCC`'s readings unchanged;
2. the ordering of `AAA` and `CCC` by score is unchanged by that row.
"""

from __future__ import annotations

import pandas as pd

from strategies import t23_rs_rating
from strategies.i01_momentum_score_audit import _synthetic_symbol


def check_cross_symbol_causality(n_rows: int = t23_rs_rating.MIN_ROWS + 10) -> dict:
    a = _synthetic_symbol("AAA", n_rows, seed=1, drift=0.002)
    c = _synthetic_symbol("CCC", n_rows, seed=2, drift=-0.002)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3, drift=0.0)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3, drift=0.0)

    without = pd.concat([a, b_short, c], ignore_index=True)
    with_row = pd.concat([a, b_long, c], ignore_index=True)

    p_without = t23_rs_rating.raw_perf(without)
    p_with = t23_rs_rating.raw_perf(with_row)
    own_unaffected = {
        s: bool(s in p_without and s in p_with and p_without[s] == p_with[s]) for s in ("AAA", "CCC")
    }

    sc_without = t23_rs_rating.score(without)
    sc_with = t23_rs_rating.score(with_row)
    order_kept = bool((sc_without["AAA"] > sc_without["CCC"]) == (sc_with["AAA"] > sc_with["CCC"]))

    passed = all(own_unaffected.values()) and order_kept and "BBB" in p_with
    return {"passed": passed, "own_unaffected": own_unaffected, "order_kept": order_kept}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
