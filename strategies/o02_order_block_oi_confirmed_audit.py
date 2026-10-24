"""Causality check for `strategies/o02_order_block_oi_confirmed.py`.

O01's own audit already proves its zone detection doesn't leak across symbols; D01's own audit proves
the same for its "last visible row" read. This checks the one thing unique to O02's own arithmetic: that
merging the two per-symbol lookups (`o01_order_block_retest.score`, `d01_oi_buildup.score`, `_last_rows`)
keeps each symbol's result independent of every other symbol's rows, in the slice O02 itself is handed.
"""

from __future__ import annotations

import pandas as pd

from strategies import o02_order_block_oi_confirmed as o02
from tests.test_o01_order_block import _bull_setup, _history


def _with_oi(history: pd.DataFrame, last_oi_chg: float) -> pd.DataFrame:
    history = history.copy()
    history["oi_futstk"] = 10_000.0
    history["oi_chg_futstk"] = 500.0
    history.iloc[-1, history.columns.get_loc("oi_chg_futstk")] = last_oi_chg
    return history


def check_cross_symbol_causality() -> dict:
    """AAA is a fixed build-up pick that O02 should keep; BBB's own last-session OI reading flips
    between build-up (agrees, O02 should fire) and unwinding (O02 should abstain). AAA's score must
    not move either way."""
    # price back at the zone, and the last session's own price also rises (so a build-up quadrant
    # can agree with O01's bullish side at all - see `tests/test_o02_order_block_oi_confirmed.py`).
    retest = [(105.0, 100.5), (100.5, 101.0)]
    a = _with_oi(_history(_bull_setup(retest), "AAA"), last_oi_chg=500.0)  # build-up, agrees -> O02 fires

    b_buildup = _with_oi(_history(_bull_setup(retest), "BBB"), last_oi_chg=500.0)
    b_unwind = _with_oi(_history(_bull_setup(retest), "BBB"), last_oi_chg=-800.0)

    before = o02.score(pd.concat([a, b_buildup], ignore_index=True))
    after = o02.score(pd.concat([a, b_unwind], ignore_index=True))

    aaa_unaffected = "AAA" in before and "AAA" in after and before["AAA"] == after["AAA"]
    bbb_changed = ("BBB" in before) and ("BBB" not in after)  # unwinding session should make BBB abstain
    passed = aaa_unaffected and bbb_changed
    return {
        "passed": passed,
        "aaa_before": before.get("AAA"),
        "aaa_after": after.get("AAA"),
        "bbb_before": before.get("BBB"),
        "bbb_after": after.get("BBB"),
    }


if __name__ == "__main__":
    r = check_cross_symbol_causality()
    print(r)
    raise SystemExit(0 if r["passed"] else 1)
