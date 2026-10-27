"""Causality check for `strategies/a10_gap_and_go.py` (SPEC.md section 5).
Same shape as `strategies/a09_gap_fade_audit.py`: giving `BBB` one extra trailing
row must leave `AAA`'s and `CCC`'s scores unchanged. Both end on `gap_and_go`
bars (a 5-sigma gap up on triple volume above the prior range), so both fire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import a10_gap_and_go as a10
from strategies.a09_gap_fade_audit import _gap_window_then_move


def gap_and_go(symbol: str, n_pairs: int = 12, m: float = 0.05, volume_jump: float = 3.0) -> pd.DataFrame:
    """A09's deterministic fixture (gaps +-1%, then a last gap of `m`), with the last
    row's volume set to `volume_jump` x the flat 1e6 before it."""
    f = _gap_window_then_move(symbol, n_pairs, 0.01, m)
    f["volume"] = 1e6
    f.loc[f.index[-1], "volume"] = 1e6 * volume_jump
    return f


def check_cross_symbol_causality() -> dict:
    a = gap_and_go("AAA")
    c = gap_and_go("CCC", m=0.06)
    rng = np.random.default_rng(3)
    b_long = gap_and_go("BBB", n_pairs=13, m=float(rng.normal(0, 0.01)))
    b_short = b_long.iloc[:-1].copy()

    s_without = a10.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = a10.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
