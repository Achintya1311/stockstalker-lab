"""Causality check for `strategies/o04_order_block_composite.py`.

O01, D01 and A07 each already have their own per-symbol causality audits proving their own scores
don't leak across symbols or across time. O04 only consumes those three already-audited scores and
then RANKS them cross-sectionally - so unlike every other O-series card, O04's final output is
*meant* to move when another symbol enters or leaves the universe (that's what "rank-average"
means), and a test asserting the opposite would be asserting the strategy doesn't do its job.

The property that still must hold is narrower: the *inputs* to the ranking step - each symbol's own
`side`, `o01`, `d01` and `vol` readings in `_ingredients()` - must depend only on that symbol's own
history, exactly like O01/D01/A07 do individually. A bug that let one symbol's extra trailing rows
(e.g. a later last-trading-day than another symbol has) change a *different* symbol's own ingredient
reading - before ranking even starts - would be the same leak B6's engine-level self-test and every
other O-series audit exists to catch, just reachable through this card's extra plumbing instead.
"""

from __future__ import annotations

import pandas as pd

from strategies import o04_order_block_composite as o04
from tests.test_o01_order_block import _bull_setup, _flat, _history


def check_cross_symbol_causality() -> dict:
    a = _history(_bull_setup([(105.0, 104.0), (104.0, 101.0)]), "AAA")
    b_short, b_long = _history(_flat(70), "BBB"), _history(_flat(71), "BBB")

    ing_before, _ = o04._composite(pd.concat([a, b_short], ignore_index=True))
    ing_after, _ = o04._composite(pd.concat([a, b_long], ignore_index=True))

    row_before = ing_before.loc["AAA"] if "AAA" in ing_before.index else None
    row_after = ing_after.loc["AAA"] if "AAA" in ing_after.index else None
    ingredients_unchanged = (
        row_before is not None
        and row_after is not None
        and row_before.equals(row_after)
    )
    return {
        "passed": ingredients_unchanged,
        "aaa_ingredients_before": None if row_before is None else row_before.to_dict(),
        "aaa_ingredients_after": None if row_after is None else row_after.to_dict(),
    }


if __name__ == "__main__":
    r = check_cross_symbol_causality()
    print(r)
    raise SystemExit(0 if r["passed"] else 1)
