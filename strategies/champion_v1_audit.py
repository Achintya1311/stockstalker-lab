"""Causality check for `strategies/champion_v1.py` (SPEC.md section 5: "audit.py
causality check" is required for every strategy).

`engine/replay.py`'s `truncate()` already proves, engine-side, that no
strategy is ever handed a row dated on or after its own pick date
(`tests/test_replay.py`, B4). That does not cover a strategy's *own*
computation being accidentally non-causal across symbols within the slice
it IS handed - for example, a bug that normalises against the latest date
seen anywhere in `history` instead of each symbol's own latest row. That
shape of bug would let one symbol having one extra trailing row (not
far-fetched: NSE's trading calendar is union-ragged across symbols that
halt, list, or delist on different dates) silently leak into a different
symbol's score, the same failure mode B6's leak alarm exists to catch, but
from inside a strategy's own arithmetic rather than a strategy reaching
around `history` entirely.

`champion_v1.score` groups by symbol and reads only that group's own rows
(see its module docstring), so this should pass by construction; this
module makes that an executable proof rather than an assertion in a
comment, and gives the next version of this strategy (or the next one
ported the same way) a regression test for it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import champion_v1


def _synthetic_symbol(symbol: str, n_rows: int, seed: int) -> pd.DataFrame:
    """`n_rows` business days of a plausible, mildly trending OHLCV series.

    Built from a fixed-seed RNG so that requesting `n_rows` vs. `n_rows + 1`
    rows from the *same* seed yields identical values for the first `n_rows`
    rows (numpy's `Generator` draws are a deterministic stream; asking for
    one more value never changes the ones already drawn) - the property this
    check's two scenarios below rely on to differ only in whether `symbol`'s
    series has one extra trailing row.
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


def check_cross_symbol_causality(n_rows: int = 80) -> dict:
    """Give `BBB` one extra trailing row; `AAA` and `CCC`'s scores must not move.

    `n_rows` must be at least `champion_v1.MIN_ROWS` so both symbols clear
    the abstain floor in both scenarios and a real score is actually being
    compared, not two abstentions that trivially agree.
    """
    a = _synthetic_symbol("AAA", n_rows, seed=1)
    c = _synthetic_symbol("CCC", n_rows, seed=2)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3)

    history_without_extra_row = pd.concat([a, b_short, c], ignore_index=True)
    history_with_extra_row = pd.concat([a, b_long, c], ignore_index=True)

    scores_without = champion_v1.score(history_without_extra_row)
    scores_with = champion_v1.score(history_with_extra_row)

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
