"""Causality check for `strategies/d01_oi_buildup.py` (SPEC.md section 5:
"audit.py causality check" is required for every strategy).

Same shape of proof as `strategies/a07_high_volume_premium_audit.py`:
`engine/replay.py`'s `truncate()` already proves no strategy is ever
handed a row dated on or after its own pick date (B4). This checks the
narrower, strategy-own-arithmetic risk instead - that
`d01_oi_buildup.score`'s per-symbol read of "the last visible row" cannot
leak across symbols within the slice it IS handed, the same failure mode
B6's leak alarm exists to catch, but from inside this strategy's own
`groupby` rather than `history` being truncated wrong engine-side.

`score` groups by symbol and reads only that group's own rows, sorted by
that group's own dates, taking just the last one; this should pass by
construction, and this module makes that an executable proof.
"""

from __future__ import annotations

import pandas as pd

from strategies import d01_oi_buildup


def _row(symbol: str, date: str, prevclose: float, close: float, oi_level: float, oi_chg: float) -> dict:
    return {
        "date": date,
        "symbol": symbol,
        "open": prevclose,
        "high": max(prevclose, close),
        "low": min(prevclose, close),
        "close": close,
        "prevclose": prevclose,
        "volume": 1_000_000.0,
        "has_future": True,
        "oi_futstk": oi_level,
        "oi_chg_futstk": oi_chg,
    }


def _history_for(symbol: str, last_date: str, extra_row: bool) -> pd.DataFrame:
    """One symbol's history: a fixed lead-in, then (optionally) one more
    trailing row dated after `last_date`'s own last entry.

    `extra_row=False` stops at `last_date`; `extra_row=True` appends one
    more session after it, changing which row is "the last visible one".
    """
    rows = [
        _row(symbol, "2015-01-05", 100.0, 101.0, 10_000.0, 500.0),
        _row(symbol, "2015-01-06", 101.0, 99.0, 10_200.0, 200.0),
        _row(symbol, last_date, 99.0, 100.5, 9_800.0, -400.0),
    ]
    if extra_row:
        rows.append(_row(symbol, "2015-01-08", 100.5, 103.0, 11_000.0, 1_200.0))
    return pd.DataFrame(rows)


def check_cross_symbol_causality() -> dict:
    """Give `BBB` one extra trailing row; `AAA` and `CCC`'s scores must not move.

    `AAA` and `CCC` have the same history in both scenarios (each symbol's
    own `groupby` group is unaffected by what rows exist for a different
    symbol); only `BBB` gains a new "last visible row" with a different
    classification, and only `BBB`'s score should change.
    """
    a_short = _history_for("AAA", "2015-01-07", extra_row=False)
    c_short = _history_for("CCC", "2015-01-07", extra_row=False)
    b_short = _history_for("BBB", "2015-01-07", extra_row=False)
    b_long = _history_for("BBB", "2015-01-07", extra_row=True)

    history_without_extra_row = pd.concat([a_short, b_short, c_short], ignore_index=True)
    history_with_extra_row = pd.concat([a_short, b_long, c_short], ignore_index=True)

    scores_without = d01_oi_buildup.score(history_without_extra_row)
    scores_with = d01_oi_buildup.score(history_with_extra_row)

    unaffected_symbols = {}
    for symbol in ("AAA", "CCC"):
        before, after = scores_without.get(symbol), scores_with.get(symbol)
        unaffected_symbols[symbol] = {
            "before": before,
            "after": after,
            "unaffected": before is not None and after is not None and before == after,
        }

    bbb_both_scored = "BBB" in scores_without and "BBB" in scores_with
    bbb_score_changed = (
        bbb_both_scored and scores_without["BBB"] != scores_with["BBB"]
    )
    passed = bbb_both_scored and bbb_score_changed and all(v["unaffected"] for v in unaffected_symbols.values())
    return {
        "passed": passed,
        "symbols": unaffected_symbols,
        "bbb_scored_both_ways": bbb_both_scored,
        "bbb_score_changed": bbb_score_changed,
    }


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
