"""Causality check for `strategies/consensus_wb_v2.py`.

H02 and F15 are cross-sectional (market mean, median, cross-stock ranks), so a peer's same-window data may
move a stock's reading by design. What must hold is that a peer's history *before* every window does not:
give `BBB` one extra leading row (an older session before its first) and `AAA`'s and `CCC`'s member
readings must be identical. A leading row, not a trailing one: F15 keeps only stocks with a row on the
slice's last date, so a trailing row would change the date, not just a peer's history. Fixtures are the
260-session wick series from `strategies/consensus_dbu_v1_audit.py`.
"""

from __future__ import annotations

import pandas as pd

from strategies import consensus_wb_v2
from strategies.consensus_dbu_v1_audit import _symbol


def _with_leading_row(frame: pd.DataFrame) -> pd.DataFrame:
    lead = frame.iloc[[0]].assign(date=(pd.Timestamp(frame["date"].iloc[0]) - pd.offsets.BDay(1)).strftime("%Y-%m-%d"))
    return pd.concat([lead, frame], ignore_index=True)


def check_cross_symbol_causality(n_rows: int = 260) -> dict:
    a = _symbol("AAA", n_rows, seed=21)
    c = _symbol("CCC", n_rows, seed=23)
    others = [_symbol(f"S{i}", n_rows, seed=30 + i) for i in range(4)]
    b = _symbol("BBB", n_rows, seed=22)
    before = consensus_wb_v2.member_scores(pd.concat([a, b, c] + others, ignore_index=True))
    after = consensus_wb_v2.member_scores(pd.concat([a, _with_leading_row(b), c] + others, ignore_index=True))
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
