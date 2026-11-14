"""Deterministic synthetic dataset for the horizon tests (`tests/test_month_horizon.py`).

No `test_` prefix, so pytest does not collect it. Prices come from a closed-form
formula (no random generator), so the frozen day/week values in
`tests/golden/horizon_golden.json` do not depend on a numpy RNG stream.
"""

from __future__ import annotations

import math

import pandas as pd

SYMBOLS = [f"S{i:02d}" for i in range(12)]


def trading_dates(start: str = "2015-01-01", end: str = "2016-06-30") -> list[str]:
    return list(pd.bdate_range(start, end).strftime("%Y-%m-%d"))


def make_dataset(dates: list[str] | None = None) -> pd.DataFrame:
    dates = trading_dates() if dates is None else dates
    rows = []
    for k, sym in enumerate(SYMBOLS):
        close = 100.0 + 5 * k
        for i, d in enumerate(dates):
            drift = 0.0004 * (k - 5.5)
            wave = 0.012 * math.sin(0.37 * i + 1.3 * k) + 0.008 * math.cos(0.11 * i * (k % 3 + 1))
            open_ = close * (1.0 + 0.004 * math.sin(0.53 * i + k))
            close = open_ * (1.0 + drift + wave)
            rows.append({
                "date": d, "symbol": sym, "open": round(open_, 4),
                "high": round(max(open_, close) * 1.003, 4), "low": round(min(open_, close) * 0.997, 4),
                "close": round(close, 4), "prevclose": None, "volume": 1e6 + 1e4 * ((i * (k + 1)) % 37),
                "turnover": 1e9, "has_future": True,
            })
    df = pd.DataFrame(rows)
    df["prevclose"] = df.groupby("symbol")["close"].shift(1).fillna(df["open"])
    return df


def make_picks(dates: list[str]) -> pd.DataFrame:
    """A deterministic `date, symbol, score` log with both signs and abstentions."""
    rows = []
    for i, d in enumerate(dates):
        for k, sym in enumerate(SYMBOLS):
            v = math.sin(0.7 * i + 2.1 * k) + 0.2 * math.cos(0.3 * k * i)
            if abs(v) < 0.1:
                continue  # abstain
            rows.append({"date": d, "symbol": sym, "score": round(v, 6)})
    return pd.DataFrame(rows)
