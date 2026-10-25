"""Causality check for `strategies/consensus_db_v1.py`.

Same property as `strategies/consensus_wb_v1_audit.py`: the consensus ranks across stocks, so its final
score may move when a peer changes, but each member's own reading of a symbol must depend only on that
symbol's history. Give `BBB` one extra leading row and `AAA`'s and `CCC`'s member readings must not
move. The fixture is A09's own deterministic gap series (so A09 fires) with futures OI columns added
(so D01C has something to read), which makes the check compare real readings, not two abstentions.
"""

from __future__ import annotations

import pandas as pd

from strategies import consensus_db_v1
from strategies.a09_gap_fade_audit import _gap_window_then_move


def _with_oi(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.assign(oi_futstk=10_000.0, oi_chg_futstk=500.0)


def check_cross_symbol_causality(n_pairs: int = 10, d: float = 0.01, m: float = 0.05) -> dict:
    a = _with_oi(_gap_window_then_move("AAA", n_pairs, d, m))
    c = _with_oi(_gap_window_then_move("CCC", n_pairs, d, m))
    b_short = _with_oi(_gap_window_then_move("BBB", n_pairs, d, m))
    b_long = _with_oi(_gap_window_then_move("BBB", n_pairs, d, m, extra_rows=1))
    before = consensus_db_v1.member_scores(pd.concat([a, b_short, c], ignore_index=True))
    after = consensus_db_v1.member_scores(pd.concat([a, b_long, c], ignore_index=True))
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
