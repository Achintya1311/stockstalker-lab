"""Causality check for `strategies/o04b_no_d01.py`.

O04B ranks O04's own `_ingredients()` readings, unchanged, so the property to prove is O04's: each
symbol's pre-rank readings depend only on its own history. This reruns O04's audit scenario and also
checks that O04B's score for the order-block symbol is the same with and without the longer peer
(the peer never fires O01, so it never enters the ranking pool).
"""

from __future__ import annotations

import pandas as pd

from strategies import o04b_no_d01
from strategies.o04_order_block_composite_audit import check_cross_symbol_causality as _o04_check
from tests.test_o01_order_block import _bull_setup, _flat, _history


def check_cross_symbol_causality() -> dict:
    base = _o04_check()
    a = _history(_bull_setup([(105.0, 104.0), (104.0, 101.0)]), "AAA")
    before = o04b_no_d01.score(pd.concat([a, _history(_flat(70), "BBB")], ignore_index=True)).get("AAA")
    after = o04b_no_d01.score(pd.concat([a, _history(_flat(71), "BBB")], ignore_index=True)).get("AAA")
    same = before is not None and after is not None and before == after
    return {"passed": base["passed"] and same, "o04_ingredients": base, "aaa_before": before, "aaa_after": after}


if __name__ == "__main__":
    r = check_cross_symbol_causality()
    print(r)
    raise SystemExit(0 if r["passed"] else 1)
