"""O05: order-block retest on weekly-resampled bars (`cards/O05.yml`, `docs/orderblock_hypotheses.md`).

Horizon-sensitivity check on O01: same retest rule (impulse >= 1.5 ATR that breaks the 10-bar
high/low, zone = last opposite candle, mitigated on a later close through the far side), same
`ob_core.DEFAULTS`, but the detector runs on ISO-week OHLC bars built from daily closes
(`ob_core.resample_weekly`) instead of daily bars. Week horizon only: a zone built from weekly
structure is a multi-week read, not something a next-day table can sensibly carry.

Per SPEC.md section 2 the zone runs on split-adjusted prices. A symbol abstains (left out of the
Series) when it has no valid weekly zone or price is not at the zone, so coverage is reported next
to accuracy.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import ob_core

PARAMS = {}
MAX_DIST_ATR = 2.0
MIN_ROWS = 60           # daily rows: enough trading days to form a usable run of weekly bars
MIN_WEEKS = 60          # weekly bars: same bar count as O01's own MIN_ROWS, at this bar's own period


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
        g = g.sort_values("date")
        o, h, l, c = ob_core.resample_weekly(g["date"], g["adj_open"].to_numpy(float), g["adj_high"].to_numpy(float), g["adj_low"].to_numpy(float), g["adj_close"].to_numpy(float))
        if len(c) < MIN_WEEKS:
            continue
        o, h, l, c = o[-MIN_WEEKS:], h[-MIN_WEEKS:], l[-MIN_WEEKS:], c[-MIN_WEEKS:]
        zone = ob_core.detect(o, h, l, c, **PARAMS)
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
        return "O05: no valid weekly zone at price, abstain"
    s, z = hit
    side = "bullish" if z["side"] == 1 else "bearish"
    return f"O05: {side} weekly order block from {z['bars_ago']} weeks ago, price at the zone ({'retested' if z['touched'] else 'first visit'}), score {s:+.2f}"
