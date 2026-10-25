"""Causality check for `strategies/t05c_upcross_fade.py`.

T05C keeps T05's positive scores and negates them, so it inherits T05's per-symbol causality exactly; this
reruns T05's own audit scenario through T05C's `score` to make that an executable proof.
"""

from __future__ import annotations

import pandas as pd

from strategies import t05c_upcross_fade
from strategies.t05_macd_crossover_audit import _synthetic_symbol


def check_cross_symbol_causality(n_rows: int = 80) -> dict:
    a = _synthetic_symbol("AAA", n_rows, seed=1)
    c = _synthetic_symbol("CCC", n_rows, seed=2)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3)
    without = t05c_upcross_fade.score(pd.concat([a, b_short, c], ignore_index=True))
    with_ = t05c_upcross_fade.score(pd.concat([a, b_long, c], ignore_index=True))
    symbols = {}
    for s in ("AAA", "CCC"):
        before, after = without.get(s), with_.get(s)
        symbols[s] = {"before": before, "after": after,
                      "unaffected": (before is None and after is None) or (before is not None and after is not None and before == after)}
    return {"passed": all(v["unaffected"] for v in symbols.values()), "symbols": symbols}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
