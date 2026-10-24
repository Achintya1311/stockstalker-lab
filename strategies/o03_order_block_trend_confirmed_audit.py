"""Causality check for `strategies/o03_order_block_trend_confirmed.py`.

O01's own audit already proves its zone detection doesn't leak across symbols; T01's own interface
(`strategies/t01_sma_crossover.py`) computes each symbol's SMA spread from that symbol's own rows only.
This checks the one thing unique to O03's own arithmetic: that merging the two per-symbol lookups
(`o01_order_block_retest.score`, `t01_sma_crossover.score`) keeps each symbol's result independent of
every other symbol's rows, in the slice O03 itself is handed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import o03_order_block_trend_confirmed as o03
from tests.test_o01_order_block import _history


def _linear_bg(start: float, end: float, n: int = 60) -> list[tuple[float, float]]:
    closes = np.linspace(start, end, n)
    opens = np.concatenate(([start + (start - closes[0])], closes[:-1]))
    return list(zip(opens.tolist(), closes.tolist()))


_UP_BG = _linear_bg(85.0, 99.8)
_DOWN_BG = _linear_bg(115.0, 100.2)
_RETEST_UP = [(105.0, 100.5), (100.5, 101.0)]


def check_cross_symbol_causality() -> dict:
    """AAA is a fixed bullish-zone-plus-uptrend pick that O03 should keep; BBB's own trend flips
    between agreeing (uptrend, O03 should fire) and disagreeing (downtrend, O03 should abstain).
    AAA's score must not move either way."""
    bull_zone = [(101.0, 99.0), (99.0, 105.0)] + _RETEST_UP
    a = _history(_UP_BG + bull_zone, "AAA")  # uptrend agrees with O01's bullish side -> O03 fires

    b_up = _history(_UP_BG + bull_zone, "BBB")
    b_down = _history(_DOWN_BG + bull_zone, "BBB")

    before = o03.score(pd.concat([a, b_up], ignore_index=True))
    after = o03.score(pd.concat([a, b_down], ignore_index=True))

    aaa_unaffected = "AAA" in before and "AAA" in after and before["AAA"] == after["AAA"]
    bbb_changed = ("BBB" in before) and ("BBB" not in after)  # downtrend disagrees, BBB should abstain
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
