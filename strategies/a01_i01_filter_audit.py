"""Causality check for `strategies/a01_i01_filter.py` (SPEC.md section 5).

Both members have their own audits (`strategies/a01_weekly_reversal_audit.py` and
`strategies/i01_momentum_score_audit.py`). The filter adds one cross-sectional step through I01's z-scores,
so, like I01, full invariance to the symbol set is not expected. What must hold: each kept symbol's score is
exactly A01's own score for it, and giving `BBB` one extra trailing row does not change `AAA`'s A01 score.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import a01_i01_filter, a01_weekly_reversal, i01_momentum_score
from strategies.i01_momentum_score_audit import _synthetic_symbol
from strategies.t21_minervini_template_audit import _frame


def downtrend_then_bounce(symbol: str, n_rows: int) -> pd.DataFrame:
    """A year-long decline (I01 below zero) ending in a 15% five-day bounce (A01 bearish)."""
    closes = 100.0 * np.exp(-0.002 * np.arange(n_rows))
    closes[-5:] = closes[-6] * np.array([1.03, 1.06, 1.09, 1.12, 1.15])
    return _frame(symbol, closes)


def check_cross_symbol_causality(n_rows: int = i01_momentum_score.MIN_ROWS + 10) -> dict:
    a = downtrend_then_bounce("AAA", n_rows)
    c = _synthetic_symbol("CCC", n_rows, seed=2, drift=0.002)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3, drift=0.0)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3, drift=0.0)

    without = pd.concat([a, b_short, c], ignore_index=True)
    with_row = pd.concat([a, b_long, c], ignore_index=True)

    kept_without = a01_i01_filter.score(without)
    kept_with = a01_i01_filter.score(with_row)
    a01_own = a01_weekly_reversal.score(without)

    aaa_kept = "AAA" in kept_without and "AAA" in kept_with
    magnitude_is_a01 = aaa_kept and kept_without["AAA"] == a01_own["AAA"]
    unaffected = aaa_kept and kept_without["AAA"] == kept_with["AAA"]
    return {"passed": bool(aaa_kept and magnitude_is_a01 and unaffected), "aaa_kept": aaa_kept}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
