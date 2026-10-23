"""O01: order-block retest (impulse + structure break) (`cards/O01.yml`, `docs/orderblock_hypotheses.md`).

A fresh, unmitigated order block (last opposite candle before a >=1.5 ATR impulse that breaks the 10-bar high/low) with price back at the zone:
bullish when the zone is a demand block, bearish when supply. Score = zone side x closeness to the zone.

Per SPEC.md section 2 the zone runs on split-adjusted prices. A symbol abstains (left out of the
Series) when it has no valid zone or price is not at the zone, so coverage is reported next to accuracy.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import ob_core

PARAMS = {}
MAX_DIST_ATR = 2.0
MIN_ROWS = 60


def _scores(history: pd.DataFrame) -> dict[str, tuple[float, dict]]:
    if history.empty:
        return {}
    if "has_future" in history.columns:
        history = history[history["symbol"].isin(history.loc[history["has_future"], "symbol"].unique())]
        if history.empty:
            return {}
    adjusted = compute_adjustment_factors(history)
    out = {}
    for symbol, g in adjusted.groupby("symbol", sort=False):
        if len(g) < MIN_ROWS:
            continue
        g = g.sort_values("date").tail(MIN_ROWS)
        zone = ob_core.detect(g["adj_open"].to_numpy(float), g["adj_high"].to_numpy(float), g["adj_low"].to_numpy(float), g["adj_close"].to_numpy(float), **PARAMS)
        if zone is None:
            continue
        s = ob_core.proximity(zone, float(g["adj_close"].iloc[-1]), MAX_DIST_ATR)
        if s != 0.0:
            out[symbol] = (s, zone)
    return out


def score(history: pd.DataFrame) -> pd.Series:
    return pd.Series({k: v[0] for k, v in _scores(history).items()}, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    hit = _scores(history[history["symbol"] == symbol]).get(symbol)
    if hit is None:
        return "O01: no valid zone at price, abstain"
    s, z = hit
    side = "bullish" if z["side"] == 1 else "bearish"
    return f"O01: {side} order block from {z['bars_ago']} bars ago, price at the zone ({'retested' if z['touched'] else 'first visit'}), score {s:+.2f}"
