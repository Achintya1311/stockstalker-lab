"""Synthetic multi-symbol dataset builder shared by `tests/test_picks_*.py`
(no `test_` prefix, so pytest does not collect this file itself).

Mirrors `tests/test_champion_v1.py`'s `_trending_symbol` (a steadily
trending close/volume series is a known expected signal for
`strategies.champion_v1.score`), extended to several symbols sharing one
date index and carrying the columns `engine.scoring.universe_membership`
also needs (`has_future`, `turnover`) so picks tests exercise the same
universe-eligibility path the real engine uses.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TURNOVER_WELL_ABOVE_FLOOR = 1e9  # 100 cr; config/universe.yml's floor is 25 cr


def trading_dates(n_rows: int, start: str = "2015-01-01") -> list[str]:
    return list(pd.bdate_range(start, periods=n_rows).strftime("%Y-%m-%d"))


def _symbol_frame(symbol: str, dates: list[str], daily_move: float, base_volume: float) -> pd.DataFrame:
    closes = 100.0 * (1.0 + daily_move) ** np.arange(len(dates))
    volumes = base_volume * (1.0 + daily_move) ** np.arange(len(dates))
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
                "turnover": TURNOVER_WELL_ABOVE_FLOOR,
                "has_future": True,
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def make_dataset(symbol_moves: dict[str, float], dates: list[str], base_volume: float = 1_000_000.0) -> pd.DataFrame:
    """One steadily trending (or flat, for `daily_move=0.0`) symbol per
    `symbol_moves` entry, all sharing `dates`.
    """
    frames = [_symbol_frame(symbol, dates, move, base_volume) for symbol, move in symbol_moves.items()]
    return pd.concat(frames, ignore_index=True)
