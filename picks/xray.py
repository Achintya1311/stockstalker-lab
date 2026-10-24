"""Market X-Ray data for one session: where every eligible stock stands, as ranks, plus the market's breadth.

Published as ranks and counts only, never prices (SPEC.md section 10): `b` is the stock's percentile among
the names the day-bullish strategy scores bullish, `d` the same for the day-bearish strategy's bearish names,
each null when that strategy does not score the stock. `breadth` counts the previous session's open-to-close
moves across the eligible universe in fixed bins. Built from the same truncated history the picks use.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.replay import truncate
from picks.select import eligible_symbols
from picks.source import resolve_strategy

BIN_EDGES = [-4.0, -3.0, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0]  # percent; outer bins are open-ended


def _percentiles(scores: pd.Series, eligible: set[str], side: int) -> dict[str, int]:
    s = scores[scores.index.isin(eligible)]
    s = s[s > 0] if side > 0 else s[s < 0]
    if s.empty:
        return {}
    pct = s.abs().rank(pct=True) * 100
    return {sym: int(round(v)) for sym, v in pct.items()}


def breadth(history: pd.DataFrame, eligible: set[str]) -> dict:
    last = history[history["symbol"].isin(eligible)].sort_values("date").groupby("symbol").tail(1)
    moves = ((last["close"] / last["open"] - 1.0) * 100).dropna().to_numpy()
    edges = [-np.inf, *BIN_EDGES, np.inf]
    counts, _ = np.histogram(moves, bins=edges)
    return {"edges_pct": BIN_EDGES, "counts": [int(c) for c in counts], "up": int((moves > 0).sum()), "down": int((moves < 0).sum()), "n": int(len(moves))}


def build_xray(dataset: pd.DataFrame, source: dict, session: str, asof: str) -> dict:
    history = truncate(dataset, session)
    eligible = eligible_symbols(dataset, asof)
    bull_cfg, bear_cfg = source["tables"]["day_bullish"], source["tables"]["day_bearish"]
    bull = _percentiles(resolve_strategy(bull_cfg["strategy"]).score(history), eligible, 1)
    bear = _percentiles(resolve_strategy(bear_cfg["strategy"]).score(history), eligible, -1)
    stocks = [{"s": sym, "b": bull.get(sym), "d": bear.get(sym)} for sym in sorted(eligible)]
    return {"asof": asof, "bullish_strategy": bull_cfg["strategy"], "bearish_strategy": bear_cfg["strategy"],
            "n": len(stocks), "stocks": stocks, "breadth": breadth(history, eligible)}
