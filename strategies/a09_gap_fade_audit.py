"""Causality check for `strategies/a09_gap_fade.py` (SPEC.md section 5:
"audit.py causality check" is required for every strategy).

Same shape of proof as `strategies/a02_extreme_day_reversal_audit.py` and
`strategies/a08_overnight_intraday_tug_audit.py`: `engine/replay.py`'s
`truncate()` already proves no strategy is ever handed a row dated on or
after its own pick date (B4). This checks the narrower, strategy-own-
arithmetic risk instead - that `a09_gap_fade.score`'s per-symbol z-score
cannot leak across symbols within the slice it IS handed, the same
failure mode B6's leak alarm exists to catch, but from inside this
strategy's own `groupby` rather than `history` being truncated wrong
engine-side.

`score` groups by symbol and reads only that group's own rows, sorted by
that group's own dates (see its module docstring), so this should pass by
construction; this module makes that an executable proof.
"""

from __future__ import annotations

import pandas as pd

from strategies import a09_gap_fade


def _gap_window_then_move(symbol: str, n_pairs: int, d: float, m: float, extra_rows: int = 0) -> pd.DataFrame:
    """A deterministic series that makes `a09_gap_fade.score` fire by
    construction, unlike a pure random walk: `2 * n_pairs` trading days of
    close-to-open gaps alternating `+d, -d` (population std of these gaps
    is exactly `d`, since their mean is 0), followed by one more day whose
    gap is `m` - so that final (yesterday's, from the pick date's view)
    gap's z-score is exactly `m / d`, computed the same way
    `_yesterdays_gap_z` does, by construction rather than chance.

    Intraday moves are flat (`close == open` every day) so the chain of
    prices is driven purely by the gap sequence, with nothing else to
    disentangle - this strategy never reads the intraday leg at all.

    `extra_rows` prepends that many additional flat days before the first
    row (same price as the first row) - prepending, not appending, so the
    window and move-day gaps this function builds for are untouched and
    the fixture still fires deterministically; it only exists to prove the
    causality check below isn't trivially comparing two `None`s.
    """
    gaps = ([d, -d] * n_pairs)[: 2 * n_pairs] + [m]
    prices = [100.0]
    for g in gaps:
        prices.append(prices[-1] * (1.0 + g))
    prices = [prices[0]] * extra_rows + prices

    dates = pd.bdate_range("2015-01-01", periods=len(prices)).strftime("%Y-%m-%d")
    rows = []
    prev_close = prices[0]
    for date, price in zip(dates, prices):
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": price,
                "high": max(prev_close, price),
                "low": min(prev_close, price),
                "close": price,
                "prevclose": prev_close,
                "volume": 1_000_000.0,
            }
        )
        prev_close = price
    return pd.DataFrame(rows)


def check_cross_symbol_causality(n_pairs: int = 10, d: float = 0.01, m: float = 0.05) -> dict:
    """Give `BBB` one extra leading row; `AAA` and `CCC`'s scores must not move.

    `AAA` and `CCC` are built to fire deterministically (`m / d` well past
    `Z_THRESHOLD`), so the comparison below is never a trivial `None == None`.
    """
    a = _gap_window_then_move("AAA", n_pairs, d, m)
    c = _gap_window_then_move("CCC", n_pairs, d, m)
    b_short = _gap_window_then_move("BBB", n_pairs, d, m)
    b_long = _gap_window_then_move("BBB", n_pairs, d, m, extra_rows=1)

    history_without_extra_row = pd.concat([a, b_short, c], ignore_index=True)
    history_with_extra_row = pd.concat([a, b_long, c], ignore_index=True)

    scores_without = a09_gap_fade.score(history_without_extra_row)
    scores_with = a09_gap_fade.score(history_with_extra_row)

    unaffected_symbols = {}
    any_scored = False
    for symbol in ("AAA", "CCC"):
        before, after = scores_without.get(symbol), scores_with.get(symbol)
        both_scored = before is not None and after is not None
        any_scored = any_scored or both_scored
        unaffected_symbols[symbol] = {
            "before": before,
            "after": after,
            "unaffected": (not both_scored) or before == after,
        }

    passed = any_scored and all(v["unaffected"] for v in unaffected_symbols.values())
    return {"passed": passed, "symbols": unaffected_symbols, "any_scored": any_scored}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
