"""F11 tune grid: the Alpha#38 range-top fade at other ts-rank windows (`cards/F11.yml`, tune lane, SPEC.md section 8).

Same rule as `strategies/f11_range_top_fade.py` (Kakushadze 2016, Alpha#38; see its header) with the
10-session window as a parameter. `scorer(10)` reproduces F11 exactly (`tests/test_f11_window_grid.py`); F11
itself is unchanged (versions are immutable). Grid points are thin modules `strategies/f11_w<NN>.py`, each a
trial in `ledger/trials.csv` when its train replay lands.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

GRID = (6, 8, 10, 12, 15)


def _parts(frame: pd.DataFrame, window: int) -> tuple[float, float]:
    close = frame["adj_close"].to_numpy(float)[-window:]
    last = close[-1]
    ts_rank = ((close < last).sum() + 0.5 * ((close == last).sum() + 1)) / len(close)
    bar = float(frame["close"].iloc[-1]) / float(frame["open"].iloc[-1])
    return float(ts_rank), bar


def scorer(window: int) -> Callable[[pd.DataFrame], pd.Series]:
    def score(history: pd.DataFrame) -> pd.Series:
        if history.empty:
            return pd.Series(dtype=float)
        if "has_future" in history.columns:
            eligible = history.loc[history["has_future"], "symbol"].unique()
            history = history[history["symbol"].isin(eligible)]
            if history.empty:
                return pd.Series(dtype=float)
        h = history.sort_values("date").groupby("symbol", sort=False).tail(window)
        adjusted = compute_adjustment_factors(h)
        rows = {}
        for symbol, group in adjusted.groupby("symbol", sort=False):
            if len(group) < window:
                continue
            ts_rank, bar = _parts(group.sort_values("date"), window)
            if np.isfinite(ts_rank) and np.isfinite(bar) and bar > 0:
                rows[symbol] = (ts_rank, bar)
        comp = pd.DataFrame.from_dict(rows, orient="index", columns=["ts_rank", "bar"])
        if len(comp) < 2:
            return pd.Series(dtype=float)
        p = comp["ts_rank"].rank(pct=True) * comp["bar"].rank(pct=True)
        sc = p.median() - p
        return sc[sc.abs() > 1e-12].astype(float)

    return score


def rules(window: int) -> Callable[[pd.DataFrame, str], str]:
    score = scorer(window)

    def fired(history: pd.DataFrame, symbol: str) -> str:
        sc = score(history)
        if symbol not in sc.index:
            return f"F11 range-top fade ({window}-session window): insufficient history or at the median, abstain"
        sub = compute_adjustment_factors(history[history["symbol"] == symbol].sort_values("date").tail(window))
        ts_rank, bar = _parts(sub, window)
        side = "bullish" if sc[symbol] > 0 else "bearish"
        return (f"F11 range-top fade (Alpha#38, {window}-session window): close ranks {ts_rank:.2f} in its range, "
                f"last bar {bar - 1:+.1%} open to close, {side}")

    return fired
