"""Causality check for `strategies/h04_return_seasonality.py` (SPEC.md section 5).

Each stock's score reads only its own rows. An extra trailing row on `BBB` (still in
the same month, so the month-end it would define is not yet complete) must leave every
stock's score unchanged, and must not be counted as a finished month.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import h04_return_seasonality as h04
from strategies.t17_keltner_breakout_audit import frame

START = "2015-01-01"


def monthly_path(symbol: str, end: str, january_move: float, other_move: float = 0.0) -> pd.DataFrame:
    """Business-day closes, flat inside a month, stepping on each month's first row by that month's move."""
    dates = pd.bdate_range(START, end)
    level, closes, prev_month = 100.0, [], None
    for d in dates:
        if d.to_period("M") != prev_month:
            level *= 1 + (january_move if d.month == 1 else other_move)
            prev_month = d.to_period("M")
        closes.append(level)
    df = frame(symbol, np.array(closes))
    df["date"] = dates.strftime("%Y-%m-%d")
    return df


def check_cross_symbol_causality() -> dict:
    end = "2017-12-29"  # a Friday: the pick week starts Mon 1 Jan 2018 -> January
    others = [monthly_path(f"S{i}", end, 0.02 * (i - 2)) for i in range(5)]
    b_short = monthly_path("BBB", end, 0.05)
    extra = b_short.iloc[[-1]].copy()
    extra["date"] = "2017-12-30"
    extra["close"] = float(extra["close"].iloc[0]) * 5
    b_long = pd.concat([b_short, extra], ignore_index=True)
    s_without = h04.score(pd.concat(others + [b_short], ignore_index=True))
    s_with = h04.score(pd.concat(others + [b_long], ignore_index=True))
    fired = [s for s in s_without.index]
    unaffected = {s: bool(s in s_with and abs(s_without[s] - s_with[s]) < 1e-12) for s in fired}
    return {"passed": len(fired) >= 5 and all(unaffected.values()), "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
