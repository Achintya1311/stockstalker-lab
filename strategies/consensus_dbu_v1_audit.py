"""Causality check for `strategies/consensus_dbu_v1.py`.

Same property as `strategies/consensus_wb_v1_audit.py`: the consensus ranks across stocks, so its final
score may move when a peer changes, but each member's own reading of a symbol must depend only on that
symbol's history. Give `BBB` one extra leading row (an older session before its first) and `AAA`'s and
`CCC`'s member readings must not move. A leading row, not a trailing one: F14 keeps only stocks with a row
on the slice's last date, so a trailing row would change the date, not just a peer's history. Fixtures are
260 sessions (F14 needs 200 of warm-up) with wicks on both sides, so Q06 and F14 read real values.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import consensus_dbu_v1


def _symbol(symbol: str, n_rows: int, seed: int, drift: float = 0.05) -> pd.DataFrame:
    """Deterministic OHLCV with wicks on both sides, fixed seed per symbol."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    steps = rng.normal(drift, 1.0, n_rows)
    upper = rng.uniform(0.1, 1.5, n_rows)
    lower = rng.uniform(0.1, 1.5, n_rows)
    closes = np.clip(100.0 + np.cumsum(steps), 5.0, None)
    rows, prev = [], float(closes[0])
    for i, (date, close) in enumerate(zip(dates, closes)):
        close = float(close)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev,
                "high": max(prev, close) + float(upper[i]),
                "low": max(min(prev, close) - float(lower[i]), 0.5),
                "close": close,
                "prevclose": prev,
                "volume": 1_000_000.0,
                "turnover": close * 1_000_000.0,
                "has_future": True,
            }
        )
        prev = close
    return pd.DataFrame(rows)


def check_cross_symbol_causality(n_rows: int = 260) -> dict:
    a = _symbol("AAA", n_rows, seed=1)
    c = _symbol("CCC", n_rows, seed=3)
    before = consensus_dbu_v1.member_scores(pd.concat([a, _symbol("BBB", n_rows, seed=2), c], ignore_index=True))
    b = _symbol("BBB", n_rows, seed=2)
    lead = b.iloc[[0]].assign(date=(pd.Timestamp(b["date"].iloc[0]) - pd.offsets.BDay(1)).strftime("%Y-%m-%d"))
    b_long = pd.concat([lead, b], ignore_index=True)
    after = consensus_dbu_v1.member_scores(pd.concat([a, b_long, c], ignore_index=True))
    symbols = {}
    for s in ("AAA", "CCC"):
        rb = before.loc[s] if s in before.index else None
        ra = after.loc[s] if s in after.index else None
        symbols[s] = {
            "before": None if rb is None else rb.to_dict(),
            "after": None if ra is None else ra.to_dict(),
            "unaffected": rb is not None and ra is not None and rb.equals(ra) and rb.notna().any(),
        }
    return {"passed": all(v["unaffected"] for v in symbols.values()), "symbols": symbols}


if __name__ == "__main__":
    result = check_cross_symbol_causality()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
