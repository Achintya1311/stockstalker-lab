"""Causality check for `strategies/o05_order_block_weekly.py`: a bar added to one symbol must not move another's score."""

import pandas as pd

from strategies import o05_order_block_weekly as o05
from tests.test_o05_order_block_weekly import _bull_setup_weekly, _flat, _history


def check_cross_symbol_causality() -> dict:
    a = _history(_bull_setup_weekly([(105.0, 104.0), (104.0, 101.0)]), "AAA")
    b_short, b_long = _history(_flat(70), "BBB"), _history(_flat(71), "BBB")
    before = o05.score(pd.concat([a, b_short], ignore_index=True)).get("AAA")
    after = o05.score(pd.concat([a, b_long], ignore_index=True)).get("AAA")
    return {"passed": before is not None and before == after, "before": before, "after": after}


if __name__ == "__main__":
    r = check_cross_symbol_causality()
    print(r)
    raise SystemExit(0 if r["passed"] else 1)
