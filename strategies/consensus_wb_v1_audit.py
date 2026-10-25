"""Causality check for `strategies/consensus_wb_v1.py`.

The consensus ranks across stocks, so its final score is meant to move when a peer changes. What must
hold is that each member's own reading of a symbol depends only on that symbol's history: give `BBB` one
extra trailing row and `AAA`'s and `CCC`'s member readings (before ranking) must not move. The members
have their own per-symbol audits; this checks the plumbing that feeds them all one `history`.
"""

from __future__ import annotations

import pandas as pd

from strategies import consensus_wb_v1
from strategies.a05_max_effect_audit import _synthetic_symbol


def check_cross_symbol_causality(n_rows: int = 120) -> dict:
    a = _synthetic_symbol("AAA", n_rows, seed=1)
    c = _synthetic_symbol("CCC", n_rows, seed=2)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3)
    before = consensus_wb_v1.member_scores(pd.concat([a, b_short, c], ignore_index=True))
    after = consensus_wb_v1.member_scores(pd.concat([a, b_long, c], ignore_index=True))
    symbols = {}
    for s in ("AAA", "CCC"):
        rb = before.loc[s] if s in before.index else None
        ra = after.loc[s] if s in after.index else None
        symbols[s] = {
            "before": None if rb is None else rb.to_dict(),
            "after": None if ra is None else ra.to_dict(),
            "unaffected": rb is not None and ra is not None and rb.equals(ra) and rb.notna().any(),
        }
    return {"passed": all(v["unaffected"] for v in symbols.values()), "symbols": symbols}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
