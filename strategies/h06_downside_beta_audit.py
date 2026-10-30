"""Causality check for `strategies/h06_downside_beta.py` (SPEC.md section 5).

Cross-sectional (the market mean and the median use every stock), so a row dated after
every other stock's last row must not change their scores. `BBB` gets one extra
trailing row; it has by far the highest downside beta with or without that row, so
the day's median is fixed (in the replay every stock ends at the same previous close,
so the median is a same-date quantity; see `strategies/h03_turnover_variability_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import h06_downside_beta as h06
from strategies.t17_keltner_breakout_audit import frame


def market_and_stocks(n_rows: int, loadings: dict[str, float], seed: int = 0) -> pd.DataFrame:
    """Stocks whose daily log return is loading x a common factor plus noise."""
    rng = np.random.default_rng(seed)
    f = rng.normal(0, 0.01, n_rows)
    frames = []
    for symbol, k in loadings.items():
        r = k * f + rng.normal(0, 0.004, n_rows)
        frames.append(frame(symbol, 100.0 * np.exp(np.cumsum(r))))
    return pd.concat(frames, ignore_index=True)


def check_cross_symbol_causality(n_rows: int = h06.MIN_ROWS + 10) -> dict:
    loadings = {"S0": 0.4, "S1": 0.7, "S2": 1.0, "S3": 1.3, "BBB": 4.0}
    full = market_and_stocks(n_rows + 1, loadings)
    last = full["date"].max()
    b_short = full[full["date"] < last]
    b_long = full[(full["symbol"] == "BBB") | (full["date"] < last)]

    s_without = h06.score(b_short)
    s_with = h06.score(b_long)
    fired = [s for s in s_without.index if s != "BBB"]
    unaffected = {s: bool(s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in fired}
    return {"passed": bool(fired) and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
