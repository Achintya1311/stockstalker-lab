"""Market X-Ray data for one session: where every eligible stock stands, as ranks, plus the market's breadth.

Published as ranks and counts only, never prices (SPEC.md section 10): `b` is the stock's percentile among
the names the day-bullish strategy scores bullish, `d` the same for the day-bearish strategy's bearish names,
each null when that strategy does not score the stock. `breadth` counts the previous session's open-to-close
moves across the eligible universe in fixed bins; `m` is that same move for each stock, in percent to two
decimals (null when the stock has no bar), so a page can show a board of the market. Built from the same
truncated history the picks use. `p` is the stock's cumulative percent move over the last `PATH_SESSIONS`
sessions, one value per session (close against the exchange's adjusted previous close, so splits do not
show as moves), null when the stock has fewer bars; `path_dates` names those sessions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.replay import truncate
from picks.select import eligible_symbols
from picks.source import resolve_strategy

PATH_SESSIONS = 20
BIN_EDGES = [-4.0, -3.0, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0]  # percent; outer bins are open-ended


def _percentiles(scores: pd.Series, eligible: set[str], side: int) -> dict[str, int]:
    s = scores[scores.index.isin(eligible)]
    s = s[s > 0] if side > 0 else s[s < 0]
    if s.empty:
        return {}
    pct = s.abs().rank(pct=True) * 100
    return {sym: int(round(v)) for sym, v in pct.items()}


def last_moves(history: pd.DataFrame, eligible: set[str]) -> pd.Series:
    """Each eligible stock's open-to-close move on its last bar, in percent, indexed by symbol."""
    last = history[history["symbol"].isin(eligible)].sort_values("date").groupby("symbol").tail(1)
    return ((last["close"] / last["open"] - 1.0) * 100).set_axis(last["symbol"].to_numpy()).dropna()


def recent_paths(history: pd.DataFrame, eligible: set[str], n: int = PATH_SESSIONS) -> tuple[list[str], dict[str, list[float]]]:
    """Cumulative percent move per eligible stock over the market's last `n` sessions (percent only, no prices)."""
    h = history[history["symbol"].isin(eligible)]
    dates = sorted(h["date"].astype(str).unique())[-n:]
    if len(dates) < n:
        return dates, {}
    h = h[h["date"].astype(str).isin(dates)].sort_values("date")
    out = {}
    for sym, g in h.groupby("symbol"):
        if len(g) != n or not (g["prevclose"] > 0).all():
            continue   # a stock missing a session would draw a path that skips a day
        cum = (g["close"] / g["prevclose"]).cumprod().to_numpy()
        if np.isfinite(cum).all():
            out[sym] = [round(float((c - 1.0) * 100), 1) for c in cum]
    return dates, out


def breadth(history: pd.DataFrame, eligible: set[str]) -> dict:
    moves = last_moves(history, eligible).to_numpy()
    edges = [-np.inf, *BIN_EDGES, np.inf]
    counts, _ = np.histogram(moves, bins=edges)
    return {"edges_pct": BIN_EDGES, "counts": [int(c) for c in counts], "up": int((moves > 0).sum()), "down": int((moves < 0).sum()), "n": int(len(moves))}


def build_xray(dataset: pd.DataFrame, source: dict, session: str, asof: str) -> dict:
    history = truncate(dataset, session)
    eligible = eligible_symbols(dataset, asof)
    bull_cfg, bear_cfg = source["tables"]["day_bullish"], source["tables"]["day_bearish"]
    bull = _percentiles(resolve_strategy(bull_cfg["strategy"]).score(history), eligible, 1)
    bear = _percentiles(resolve_strategy(bear_cfg["strategy"]).score(history), eligible, -1)
    moves = {sym: round(float(v), 2) for sym, v in last_moves(history, eligible).items() if np.isfinite(v)}
    dates, paths = recent_paths(history, eligible)
    stocks = [{"s": sym, "b": bull.get(sym), "d": bear.get(sym), "m": moves.get(sym), "p": paths.get(sym)} for sym in sorted(eligible)]
    return {"asof": asof, "path_dates": dates, "bullish_strategy": bull_cfg["strategy"], "bearish_strategy": bear_cfg["strategy"],
            "n": len(stocks), "stocks": stocks, "breadth": breadth(history, eligible)}
