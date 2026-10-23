"""O00: placebo: last opposite candle, no impulse requirement (`cards/O00.yml`, `docs/orderblock_hypotheses.md`).

The same retest rule with the displacement requirement removed (any up bar counts as the move, no structure break). If O01 does not beat
this, the impulse that defines an order block adds nothing, which is the central question about order blocks.

Per SPEC.md section 2 the zone runs on split-adjusted prices. A symbol abstains (left out of the
Series) when it has no valid zone or price is not at the zone, so coverage is reported next to accuracy.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import ob_core

PARAMS = {"impulse_atr": 0.0, "require_break": False}
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
        return "O00: no valid zone at price, abstain"
    s, z = hit
    side = "bullish" if z["side"] == 1 else "bearish"
    return f"O00: {side} order block from {z['bars_ago']} bars ago, price at the zone ({'retested' if z['touched'] else 'first visit'}), score {s:+.2f}"
