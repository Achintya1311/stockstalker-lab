"""A pick's technical context (FINISH FT1): words, ranks and ratios from the same adjusted bars, no prices.

Shown for every pick whatever strategy chose it, like `picks/chart.py`: it describes where the stock
stands, not why it was picked. Every field is computed only from rows up to the last close the pick was
made from (the caller passes the already-truncated history).

Keys (any one is left out when the history is too short for it):
- `trend50`, `trend200`: "above" or "below" the 50- and 200-day simple average of adjusted closes.
- `rsi14`: Wilder 14-day RSI, one decimal; `rsi_band`: "oversold" (<30), "weak" (30-45), "neutral" (45-55),
  "firm" (55-70), "overbought" (>70).
- `vol_x20`: last session's volume as a multiple of its prior 20-session average (split-adjusted shares).
- `range20`: last close's position in the 20-session high-low range, 0 (at the low) to 100 (at the high).
- `ob_dist`: distance from the last close to the nearest edge of the order-block zone `strategies/ob_core.py`
  finds (the same zone the chart draws), as a share of the 20-session range; 0 when the close is inside it.
  `ob_side` says whether that zone is "demand" or "supply". Both are absent when there is no zone.

Picks files are write-once, so `tech` appears from the next file written; the rehearsal file for
2026-11-11 was deleted and rewritten by the Live dry run to carry it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import ob_core

RSI_N = 14
VOL_N = 20
RANGE_N = 20
OB_ROWS = 60   # same window `picks/chart.py` detects the zone on


def rsi_band(v: float) -> str:
    return "oversold" if v < 30 else "weak" if v < 45 else "neutral" if v <= 55 else "firm" if v <= 70 else "overbought"


def wilder_rsi(close: np.ndarray, n: int = RSI_N) -> float | None:
    if len(close) < n + 1:
        return None
    d = np.diff(close)
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = up[:n].mean(), dn[:n].mean()
    for u, w in zip(up[n:], dn[n:]):
        au, ad = (au * (n - 1) + u) / n, (ad * (n - 1) + w) / n
    if ad == 0:
        return 100.0 if au > 0 else 50.0
    return float(100.0 - 100.0 / (1.0 + au / ad))


def tech_for(history: pd.DataFrame, symbol: str) -> dict | None:
    sub = history[history["symbol"] == symbol]
    if len(sub) < RANGE_N + 1:
        return None
    g = compute_adjustment_factors(sub.sort_values("date"))
    c = g["adj_close"].to_numpy(float)
    h, l, o = (g[f"adj_{k}"].to_numpy(float) for k in ("high", "low", "open"))
    last = c[-1]
    out: dict = {}
    for n in (50, 200):
        if len(c) >= n:
            out[f"trend{n}"] = "above" if last > c[-n:].mean() else "below"
    rsi = wilder_rsi(c)
    if rsi is not None:
        out["rsi14"] = round(rsi, 1)
        out["rsi_band"] = rsi_band(rsi)
    if "volume" in g and len(g) >= VOL_N + 1:
        vol = (g["volume"].to_numpy(float) / g["adj_factor"].to_numpy(float))
        base = vol[-VOL_N - 1:-1].mean()
        if base > 0:
            out["vol_x20"] = round(float(vol[-1] / base), 2)
    hi, lo = h[-RANGE_N:].max(), l[-RANGE_N:].min()
    span = hi - lo
    out["range20"] = round(float((last - lo) / span * 100.0), 1) if span > 0 else 50.0
    if len(c) >= OB_ROWS and span > 0:
        w = slice(len(c) - OB_ROWS, len(c))
        zone = ob_core.detect(o[w], h[w], l[w], c[w])
        if zone:
            gap = max(zone["zone_low"] - last, last - zone["zone_high"], 0.0)
            out["ob_dist"] = round(float(gap / span), 2)
            out["ob_side"] = "demand" if zone["side"] == 1 else "supply"
    return out
