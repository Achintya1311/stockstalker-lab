"""Causality check for `strategies/a07c_volume_fade.py`.

A07C is `-A07`, so it inherits A07's per-symbol causality exactly; this reruns A07's own audit
scenario through A07C's `score` to make that an executable proof rather than an argument.
"""

from __future__ import annotations

import pandas as pd

from strategies import a07c_volume_fade
from strategies.a07_high_volume_premium_audit import _synthetic_symbol
from strategies.a07_high_volume_premium import MIN_ROWS


def check_cross_symbol_causality(n_rows: int = MIN_ROWS + 20) -> dict:
    a = _synthetic_symbol("AAA", n_rows, seed=1)
    c = _synthetic_symbol("CCC", n_rows, seed=2)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3)
    without = a07c_volume_fade.score(pd.concat([a, b_short, c], ignore_index=True))
    with_ = a07c_volume_fade.score(pd.concat([a, b_long, c], ignore_index=True))
    symbols = {
        s: {"before": without.get(s), "after": with_.get(s),
            "unaffected": without.get(s) is not None and with_.get(s) is not None and without.get(s) == with_.get(s)}
        for s in ("AAA", "CCC")
    }
    bbb_scored = "BBB" in with_
    return {"passed": bbb_scored and all(v["unaffected"] for v in symbols.values()), "symbols": symbols, "bbb_scored": bbb_scored}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
