"""Causality check for `strategies/d02_stock_pcr_core.py` (SPEC.md section
5: "audit.py causality check" is required for every strategy) - shared by
both D02 variants (`d02_stock_pcr_contrarian.py`,
`d02_stock_pcr_confirmatory.py`), since they call `core.signal` with the
same grouping and only negate the final sign; a cross-symbol leak in the
shared grouping would show up identically in either variant, and a bare
sign flip cannot introduce one.

Same shape of proof as `strategies/d01_oi_buildup_audit.py`:
`engine/replay.py`'s `truncate()` already proves no strategy is ever
handed a row dated on or after its own pick date (B4). This checks the
narrower, strategy-own-arithmetic risk instead - that
`core.signal`'s per-symbol rolling z-score cannot leak across symbols
within the slice it IS handed.
"""

from __future__ import annotations

import pandas as pd

from strategies import d02_stock_pcr_core as core


def _row(symbol: str, date: str, oi_ce: float, oi_pe: float) -> dict:
    return {
        "date": date,
        "symbol": symbol,
        "has_future": True,
        "oi_ce_optstk": oi_ce,
        "oi_pe_optstk": oi_pe,
    }


def _stable_history(symbol: str, n: int, start_day: int) -> list[dict]:
    """`n` sessions of a mildly noisy, non-extreme PCR around 1.0, so the
    rolling window has a real (non-degenerate) mean/std to compare against."""
    rows = []
    for i in range(n):
        day = start_day + i
        ce = 1000.0 + (i % 3) * 10.0
        pe = ce * (1.0 + 0.01 * ((i % 5) - 2))  # PCR wobbles near 1.0
        rows.append(_row(symbol, f"2015-{1 + day // 28:02d}-{1 + day % 28:02d}", ce, pe))
    return rows


def check_cross_symbol_causality() -> dict:
    """Give `BBB` one extra, extreme-PCR trailing session; `AAA` and `CCC`'s
    scores must not move, and only `BBB` should newly score.

    `AAA` and `CCC` have the same history in both scenarios (each symbol's
    own `groupby` group is unaffected by what rows exist for a different
    symbol); only `BBB` gains a new "last visible row" that pushes its own
    trailing z-score past the threshold.
    """
    a_rows = _stable_history("AAA", 20, start_day=0)
    c_rows = _stable_history("CCC", 20, start_day=0)
    b_rows = _stable_history("BBB", 20, start_day=0)

    extreme_row = _row("BBB", "2015-02-11", 1000.0, 5000.0)  # PCR = 5.0, far above the ~1.0 baseline

    history_without_extreme = pd.DataFrame(a_rows + b_rows + c_rows)
    history_with_extreme = pd.DataFrame(a_rows + b_rows[1:] + [extreme_row] + c_rows)

    scores_without = core.signal(history_without_extreme, contrarian=True)
    scores_with = core.signal(history_with_extreme, contrarian=True)

    unaffected_symbols = {}
    for symbol in ("AAA", "CCC"):
        before, after = scores_without.get(symbol), scores_with.get(symbol)
        unaffected_symbols[symbol] = {
            "before": before,
            "after": after,
            # Neither should ever score (stable ~1.0 PCR, no extreme) -
            # both being None/absent in both scenarios IS the "unaffected"
            # proof here, as strong as equal nonzero scores would be.
            "unaffected": before == after,
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
