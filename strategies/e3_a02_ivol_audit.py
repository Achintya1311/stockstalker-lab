"""Causality check for `strategies/e3_a02_ivol.py` (E3A and E3B).

The split reads H02's median, so it is cross-sectional through that median only. `AAA` and `CCC`
end on an extreme up and down day (A02 fires on both) after a quiet run; `BBB` is by far the most
volatile stock with and without one extra trailing row, so the median and the market mean on the
others' dates are unchanged, and `AAA`'s and `CCC`'s E3A/E3B readings must be identical.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import e3_a02_ivol as e3
from strategies.t17_keltner_breakout_audit import frame, quiet_then_jump


def walk(symbol: str, n_rows: int, seed: int, sd: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return frame(symbol, 100.0 * np.exp(np.cumsum(rng.normal(0, sd, n_rows))))


def fixture(n_rows: int, extra_rows: int) -> pd.DataFrame:
    others = [walk(f"S{i}", n_rows, 40 + i, 0.01) for i in range(5)]
    a = quiet_then_jump("AAA", n_rows, 0.08, seed=1)
    c = quiet_then_jump("CCC", n_rows, -0.08, seed=2)
    b = walk("BBB", n_rows + extra_rows, 3, 0.08)
    return pd.concat(others + [a, b, c], ignore_index=True)


def readings(history: pd.DataFrame) -> dict:
    return {"high": e3.high_ivol(history).to_dict(), "low": e3.low_ivol(history).to_dict()}


def check_cross_symbol_causality(n_rows: int = 45) -> dict:
    before, after = readings(fixture(n_rows, 0)), readings(fixture(n_rows, 1))
    symbols = {}
    for s in ("AAA", "CCC"):
        b = (before["high"].get(s), before["low"].get(s))
        a = (after["high"].get(s), after["low"].get(s))
        symbols[s] = {"before": b, "after": a, "unaffected": b == a and any(v is not None for v in b)}
    return {"passed": all(v["unaffected"] for v in symbols.values()), "symbols": symbols}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
