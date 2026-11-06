"""Causality check for `strategies/e2a_f11_fallback.py` (SPEC.md section 5).

Which member a date reads from depends on whether E2A has a tradable bearish pick, so a symbol's final
score can move when a peer changes (as with every fallback card). The property that must hold is per
member: each member's reading of a symbol depends only on data up to the slice's last close. E2A is a
per-symbol rule, so its reading of the other stocks must not change when one stock gains a row; F11 is
cross-sectional through ranks and has its own audit (`strategies/f11_range_top_fade_audit.py`), which
this check reuses. The switch itself reads only the slice (last-date flags), never the pick date.
"""

from __future__ import annotations

import pandas as pd

from strategies import e2a_a02_crowded
from strategies import f11_range_top_fade_audit
from strategies.a09_gap_fade_audit import _gap_window_then_move
from strategies.consensus_db_v1_audit import _with_oi


def check_cross_symbol_causality(n_pairs: int = 10, d: float = 0.01, m: float = 0.05) -> dict:
    a = _with_oi(_gap_window_then_move("AAA", n_pairs, d, m))
    c = _with_oi(_gap_window_then_move("CCC", n_pairs, d, m))
    b_short = _with_oi(_gap_window_then_move("BBB", n_pairs, d, m))
    b_long = _with_oi(_gap_window_then_move("BBB", n_pairs, d, m, extra_rows=1))
    before = e2a_a02_crowded.score(pd.concat([a, b_short, c], ignore_index=True))
    after = e2a_a02_crowded.score(pd.concat([a, b_long, c], ignore_index=True))
    e2a_ok = all(s in before.index and pd.notna(before[s]) and before.get(s) == after.get(s)
                 for s in ("AAA", "CCC"))
    f11 = f11_range_top_fade_audit.check_cross_symbol_causality()
    return {"passed": bool(e2a_ok and f11["passed"]), "e2a_unaffected": e2a_ok, "f11": f11["passed"]}
