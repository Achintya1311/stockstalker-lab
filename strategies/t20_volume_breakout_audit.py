"""Causality check for `strategies/t20_volume_breakout.py` (SPEC.md section 5).
Same shape as `strategies/t02_golden_death_cross_audit.py`: `truncate()` in
`engine/replay.py` already proves no strategy sees a row on or after its pick
date (B4); this checks that T20's per-symbol arithmetic cannot leak across
symbols. Giving `BBB` one extra trailing row must leave `AAA`'s and `CCC`'s
scores unchanged. `AAA` and `CCC` end on a bullish and a bearish breakout.
"""

from __future__ import annotations

import pandas as pd

from strategies import t20_volume_breakout as t20


def bars(symbol: str, n_rows: int, last_location: float | None = None, last_volume: float = 1e6) -> pd.DataFrame:
    """Flat bars (low 99, high 101, close 100, volume 1e6). If `last_location`
    is given, the last bar closes at that fraction of its 99-101 range on
    `last_volume`."""
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    rows = [{"date": d, "symbol": symbol, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
             "prevclose": 100.0, "volume": 1e6} for d in dates]
    if last_location is not None:
        rows[-1]["close"] = 99.0 + 2.0 * last_location
        rows[-1]["volume"] = last_volume
    return pd.DataFrame(rows)


def check_cross_symbol_causality(n_rows: int = t20.MIN_ROWS + 10) -> dict:
    a = bars("AAA", n_rows, 0.9, 3e6)
    c = bars("CCC", n_rows, 0.1, 4e6)
    b_short = bars("BBB", n_rows)
    b_long = bars("BBB", n_rows + 1, 0.95, 5e6)

    s_without = t20.score(pd.concat([a, b_short, c], ignore_index=True))
    s_with = t20.score(pd.concat([a, b_long, c], ignore_index=True))
    unaffected = {
        s: bool(s in s_without and s in s_with and s_without[s] == s_with[s]) for s in ("AAA", "CCC")
    }
    return {"passed": all(unaffected.values()) and "BBB" in s_with, "symbols": unaffected}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
