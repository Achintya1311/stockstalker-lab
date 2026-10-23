"""Causality check for `strategies/t13_williams_r.py` (SPEC.md section 5:
"audit.py causality check" is required for every strategy).

Same shape of proof as `strategies/t01_sma_crossover_audit.py` through
`strategies/t12_stochastic_audit.py`: `engine/replay.py`'s `truncate()`
already proves no strategy is ever handed a row dated on or after its own
pick date (B4). This checks the narrower, strategy-own-arithmetic risk
instead - that `t13_williams_r.score`'s per-symbol rolling windows and
threshold comparison cannot leak across symbols within the slice it IS
handed.

`score` groups by symbol and reads only that group's own rows, sorted by
that group's own dates (see its module docstring), so this should pass by
construction; this module makes that an executable proof.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import t13_williams_r


def _synthetic_symbol(symbol: str, n_rows: int, seed: int) -> pd.DataFrame:
    """`n_rows` business days of a plausible, mildly trending OHLCV series
    with a real intraday high/low spread (this card's rolling high/low
    window needs non-degenerate high/low, not just close, the same
    property `strategies/t12_stochastic_audit.py`'s helper already needs)
    - same deterministic-stream property as that helper: numpy's
    `Generator` draws from the same seed are identical for the first
    `n_rows` rows whether `n_rows` or `n_rows + 1` rows are requested, the
    property the two scenarios below rely on to differ only in whether
    `symbol`'s series has one extra trailing row.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    steps = rng.normal(0.05, 1, n_rows)
    closes = np.clip(100.0 + np.cumsum(steps), 1.0, None)
    spreads = np.clip(rng.normal(1.0, 0.3, n_rows), 0.1, None)
    volumes = np.clip(1_000_000.0 + rng.normal(0, 50_000, n_rows), 1.0, None)

    rows = []
    prev_close = float(closes[0])
    for date, close, spread, volume in zip(dates, closes, spreads, volumes):
        close = float(close)
        high = max(prev_close, close) + spread
        low = min(prev_close, close) - spread
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": high,
                "low": low,
                "close": close,
                "prevclose": prev_close,
                "volume": float(volume),
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def check_cross_symbol_causality(n_rows: int = 80) -> dict:
    """Give `BBB` one extra trailing row; `AAA` and `CCC`'s scores must not move.

    `n_rows=80` (well past `t13_williams_r.MIN_ROWS=14`) with a mildly
    trending random walk: %R past either threshold is not guaranteed on
    any given seed's latest bar, so this checks whatever each symbol's
    score actually is (including abstain, i.e. absent from the Series) is
    identical before and after, rather than assuming all three fire.
    """
    a = _synthetic_symbol("AAA", n_rows, seed=1)
    c = _synthetic_symbol("CCC", n_rows, seed=2)
    b_short = _synthetic_symbol("BBB", n_rows, seed=3)
    b_long = _synthetic_symbol("BBB", n_rows + 1, seed=3)

    history_without_extra_row = pd.concat([a, b_short, c], ignore_index=True)
    history_with_extra_row = pd.concat([a, b_long, c], ignore_index=True)

    scores_without = t13_williams_r.score(history_without_extra_row)
    scores_with = t13_williams_r.score(history_with_extra_row)

    unaffected_symbols = {}
    for symbol in ("AAA", "CCC"):
        before, after = scores_without.get(symbol), scores_with.get(symbol)
        unaffected_symbols[symbol] = {
            "before": before,
            "after": after,
            "unaffected": (before is None and after is None) or (before is not None and after is not None and before == after),
        }

    passed = all(v["unaffected"] for v in unaffected_symbols.values())
    return {"passed": passed, "symbols": unaffected_symbols}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
