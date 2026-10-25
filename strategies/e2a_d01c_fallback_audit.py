"""Causality check for `strategies/e2a_d01c_fallback.py`.

Which member a date reads from depends on whether E2A fires on any stock, so a symbol's final score can
move when a peer changes (as with the consensus cards). The property that must hold is per member: each
member's own reading of a symbol depends only on that symbol's history. Same fixture and check as
`strategies/consensus_db_v1_audit.py`, on this card's two members.
"""

from __future__ import annotations

import pandas as pd

from strategies import d01c_oi_fade, e2a_a02_crowded
from strategies.a09_gap_fade_audit import _gap_window_then_move
from strategies.consensus_db_v1_audit import _with_oi

MEMBERS = {"e2a": e2a_a02_crowded, "d01c": d01c_oi_fade}


def _readings(history: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({name: module.score(history) for name, module in MEMBERS.items()})


def check_cross_symbol_causality(n_pairs: int = 10, d: float = 0.01, m: float = 0.05) -> dict:
    a = _with_oi(_gap_window_then_move("AAA", n_pairs, d, m))
    c = _with_oi(_gap_window_then_move("CCC", n_pairs, d, m))
    b_short = _with_oi(_gap_window_then_move("BBB", n_pairs, d, m))
    b_long = _with_oi(_gap_window_then_move("BBB", n_pairs, d, m, extra_rows=1))
    before = _readings(pd.concat([a, b_short, c], ignore_index=True))
    after = _readings(pd.concat([a, b_long, c], ignore_index=True))
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
