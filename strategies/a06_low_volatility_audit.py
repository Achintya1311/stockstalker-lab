"""Causality check for `strategies/a06_low_volatility.py` (SPEC.md section
5: "audit.py causality check" is required for every strategy).

Same shape of proof as `strategies/a05_max_effect_audit.py`:
`engine/replay.py`'s `truncate()` already proves no strategy is ever
handed a row dated on or after its own pick date (B4). This checks the
narrower, strategy-own-arithmetic risk instead - that
`a06_low_volatility.score`'s per-symbol sigma-ratio calculation cannot
leak across symbols within the slice it IS handed, the same failure mode
B6's leak alarm exists to catch, but from inside this strategy's own
`groupby` rather than `history` being truncated wrong engine-side.

`score` groups by symbol and reads only that group's own rows, sorted by
that group's own dates (see its module docstring), so this should pass by
construction; this module makes that an executable proof.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import a06_low_volatility


def _synthetic_symbol(symbol: str, n_rows: int, seed: int) -> pd.DataFrame:
    """`n_rows` business days of a plausible OHLCV series, fixed-seed per symbol.

    Mirrors `strategies/a05_max_effect_audit.py`'s helper: numpy's
    `Generator` draws are a deterministic stream, so requesting `n_rows` vs.
    `n_rows + 1` rows from the same seed yields identical values for the
    first `n_rows` rows - the property the two scenarios below rely on to
    differ only in whether `symbol`'s series has one extra trailing row.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    steps = rng.normal(0, 1, n_rows)
    closes = np.clip(100.0 + np.cumsum(steps), 1.0, None)
    volumes = np.clip(1_000_000.0 + rng.normal(0, 50_000, n_rows), 1.0, None)

    rows = []
    prev_close = float(closes[0])
    for date, close, volume in zip(dates, closes, volumes):
        close = float(close)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": max(prev_close, close),
                "low": min(prev_close, close),
                "close": close,
                "prevclose": prev_close,
                "volume": float(volume),
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def check_cross_symbol_causality(n_rows: int = a06_low_volatility.MIN_ROWS + 20) -> dict:
    """Give `BBB` one extra trailing row; `AAA` and `CCC`'s scores must not move.

    `n_rows` must be at least `a06_low_volatility.MIN_ROWS` so all three
    symbols clear the abstain floor in both scenarios and real scores are
    actually being compared, not abstentions that trivially agree.
    """
    a = _synthetic_symbol("AAA", n_rows, seed=1)
    c = _synthetic_symbol("CCC", n_rows, seed=2)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3)

    history_without_extra_row = pd.concat([a, b_short, c], ignore_index=True)
    history_with_extra_row = pd.concat([a, b_long, c], ignore_index=True)

    scores_without = a06_low_volatility.score(history_without_extra_row)
    scores_with = a06_low_volatility.score(history_with_extra_row)

    unaffected_symbols = {}
    for symbol in ("AAA", "CCC"):
        before, after = scores_without.get(symbol), scores_with.get(symbol)
        unaffected_symbols[symbol] = {
            "before": before,
            "after": after,
            "unaffected": before is not None and after is not None and before == after,
        }

    bbb_got_a_real_score = "BBB" in scores_with
    passed = bbb_got_a_real_score and all(v["unaffected"] for v in unaffected_symbols.values())
    return {"passed": passed, "symbols": unaffected_symbols, "bbb_scored": bbb_got_a_real_score}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
