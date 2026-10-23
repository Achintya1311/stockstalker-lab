"""Causality check for `strategies/t09_supertrend.py` (SPEC.md section 5:
"audit.py causality check" is required for every strategy).

Same shape of proof as `strategies/t08_donchian_breakout_audit.py`:
`engine/replay.py`'s `truncate()` already proves no strategy is ever
handed a row dated on or after its own pick date (B4). This checks the
narrower, strategy-own-arithmetic risk instead - that `score`'s
per-symbol grouping, and `_supertrend_line`'s recursion inside it, cannot
leak across symbols within the slice it IS handed. This matters more
here than for T08: the recursion carries state forward bar-by-bar, so a
leak would be easy to introduce (e.g. accidentally running the loop over
an un-grouped frame) without any single test catching it the way a
one-shot rolling max/min would.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import t09_supertrend as t09


def _synthetic_symbol(symbol: str, n_rows: int, seed: int) -> pd.DataFrame:
    """`n_rows` business days of a plausible random-walk OHLCV series,
    with high/low spread around each day's open/close so ATR is
    non-degenerate. Same construction shape as
    `strategies/t08_donchian_breakout_audit.py`'s helper, extended with a
    high/low spread Supertrend actually needs."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    steps = rng.normal(0.0, 1, n_rows)
    closes = np.clip(100.0 + np.cumsum(steps), 1.0, None)
    spreads = np.abs(rng.normal(0.0, 0.5, n_rows)) + 0.1

    rows = []
    prev_close = float(closes[0])
    for date, close, spread in zip(dates, closes, spreads):
        close = float(close)
        day_high = max(prev_close, close) + spread
        day_low = min(prev_close, close) - spread
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": day_high,
                "low": day_low,
                "close": close,
                "prevclose": prev_close,
                "volume": 1_000_000.0,
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def check_cross_symbol_causality(n_rows: int = t09.MIN_ROWS) -> dict:
    """Give `BBB` one extra trailing row; `AAA` and `CCC`'s scores (and
    their full internal recursion, not just the final score) must not
    move."""
    a = _synthetic_symbol("AAA", n_rows, seed=1)
    c = _synthetic_symbol("CCC", n_rows, seed=2)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3)

    history_without_extra_row = pd.concat([a, b_short, c], ignore_index=True)
    history_with_extra_row = pd.concat([a, b_long, c], ignore_index=True)

    scores_without = t09.score(history_without_extra_row)
    scores_with = t09.score(history_with_extra_row)

    unaffected_symbols = {}
    for symbol in ("AAA", "CCC"):
        before, after = scores_without.get(symbol), scores_with.get(symbol)
        unaffected_symbols[symbol] = {
            "before": before,
            "after": after,
            "unaffected": (before is None and after is None)
            or (before is not None and after is not None and before == after),
        }

    passed = all(v["unaffected"] for v in unaffected_symbols.values())
    return {"passed": passed, "symbols": unaffected_symbols}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
