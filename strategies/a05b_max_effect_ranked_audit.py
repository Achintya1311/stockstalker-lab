"""Causality check for `strategies/a05b_max_effect_ranked.py`.

A05B ranks v1's per-symbol `z = MAX / sigma` across the symbols present on a
date, so its final score is meant to move when a peer enters, leaves or
changes. A test asserting otherwise would assert the card doesn't do its job
(same reasoning as `strategies/o04_order_block_composite_audit.py`).

The property that must still hold is narrower: each symbol's own pre-rank `z`
(`a05b_max_effect_ranked._z_by_symbol`) depends only on that symbol's own
history. Giving `BBB` one extra trailing row must leave `AAA`'s and `CCC`'s
own `z` unchanged before any ranking happens.
"""

from __future__ import annotations

import pandas as pd

from strategies import a05b_max_effect_ranked as a05b
from strategies.a05_max_effect_audit import _synthetic_symbol


def check_cross_symbol_causality(n_rows: int = a05b.MIN_ROWS + 20) -> dict:
    a = _synthetic_symbol("AAA", n_rows, seed=1)
    c = _synthetic_symbol("CCC", n_rows, seed=2)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3)

    z_without = a05b._z_by_symbol(pd.concat([a, b_short, c], ignore_index=True))
    z_with = a05b._z_by_symbol(pd.concat([a, b_long, c], ignore_index=True))

    symbols = {}
    for symbol in ("AAA", "CCC"):
        before, after = z_without.get(symbol), z_with.get(symbol)
        symbols[symbol] = {
            "before": before,
            "after": after,
            "unaffected": before is not None and after is not None and before == after,
        }

    bbb_scored = "BBB" in z_with
    passed = bbb_scored and all(v["unaffected"] for v in symbols.values())
    return {"passed": passed, "symbols": symbols, "bbb_scored": bbb_scored}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
