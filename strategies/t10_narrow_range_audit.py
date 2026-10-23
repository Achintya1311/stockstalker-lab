"""Causality check for `strategies/t10_narrow_range_core.py` (SPEC.md
section 5: "audit.py causality check" is required for every strategy) -
shared by both T10 variants (`t10_nr4_narrow_range.py`,
`t10_nr7_narrow_range.py`), since they call `core.signal` with the same
grouping and only vary `lookback`; a cross-symbol leak in the shared
grouping would show up identically at either lookback.

Same shape of proof as `strategies/d02_stock_pcr_audit.py`:
`engine/replay.py`'s `truncate()` already proves no strategy is ever
handed a row dated on or after its own pick date (B4). This checks the
narrower, strategy-own-arithmetic risk instead - that `core.signal`'s
per-symbol true-range window and trend filter cannot leak across symbols
within the slice it IS handed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import t10_narrow_range_core as core

LOOKBACK = 7  # the stricter of the two variants' MIN_ROWS; same core either way


def _rows_from_trend(symbol: str, n_rows: int, narrow_last: bool) -> list[dict]:
    """`n_rows` business days of a steady uptrend (so the trend filter's
    spread is reliably non-zero), with every day's high/low spread wide
    enough that its true range dwarfs 0.02 - except the last day when
    `narrow_last` is set, whose high/low pins to within 0.01 of its close,
    guaranteeing it is the narrowest range of any trailing window up to
    `n_rows` long."""
    trend = np.linspace(80.0, 140.0, n_rows)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    rows = []
    prev_close = float(trend[0])
    for i, (date, close) in enumerate(zip(dates, trend)):
        close = float(close)
        if narrow_last and i == n_rows - 1:
            high, low = close + 0.01, close - 0.01
        else:
            high, low = max(prev_close, close) + 2.0, min(prev_close, close) - 2.0
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": high,
                "low": low,
                "close": close,
                "prevclose": prev_close,
                "volume": 1_000_000.0,
            }
        )
        prev_close = close
    return rows


def check_cross_symbol_causality() -> dict:
    """Give `BBB` one extra, deliberately narrow trailing day; `AAA` and
    `CCC`'s scores must not move, and only `BBB` should newly score.

    `AAA` and `CCC` have the identical, unchanged `n_rows`-day history in
    both scenarios (each symbol's own `groupby` group is unaffected by
    what rows exist for a different symbol); only `BBB` gains a new "last
    visible row" that is narrow enough to flip it from abstain to firing.
    """
    required = core.min_rows(LOOKBACK)
    a_rows = _rows_from_trend("AAA", required, narrow_last=False)
    c_rows = _rows_from_trend("CCC", required, narrow_last=False)
    b_short = _rows_from_trend("BBB", required, narrow_last=False)
    b_long = _rows_from_trend("BBB", required + 1, narrow_last=True)

    history_without_extra_row = pd.DataFrame(a_rows + b_short + c_rows)
    history_with_extra_row = pd.DataFrame(a_rows + b_long + c_rows)

    scores_without = core.signal(history_without_extra_row, lookback=LOOKBACK)
    scores_with = core.signal(history_with_extra_row, lookback=LOOKBACK)

    unaffected_symbols = {}
    for symbol in ("AAA", "CCC"):
        before, after = scores_without.get(symbol), scores_with.get(symbol)
        unaffected_symbols[symbol] = {
            "before": before,
            "after": after,
            "unaffected": (before is None and after is None)
            or (before is not None and after is not None and before == after),
        }

    bbb_newly_scored = "BBB" not in scores_without and "BBB" in scores_with
    passed = bbb_newly_scored and all(v["unaffected"] for v in unaffected_symbols.values())
    return {
        "passed": passed,
        "symbols": unaffected_symbols,
        "bbb_newly_scored": bbb_newly_scored,
    }


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
