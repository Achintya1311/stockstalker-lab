"""Order-block detector shared by the O-series cards (`cards/O01.yml`, `docs/orderblock_hypotheses.md`).

Smart-money convention, in plain words: a BULLISH order block is the last down candle before an
impulsive up move that breaks the recent high; its low-to-high range is the zone price is
expected to revisit. Bearish is the mirror. A zone stays valid until a later CLOSE passes
through its far side (mitigated). Nothing here is assumed to work (SPEC.md section 5); the
O-series replays decide. Every number is computed from bars up to the last visible close.

`detect()` takes arrays oldest to newest and returns the most recent valid zone on either
side, or None. All parameters live in `DEFAULTS` so a variant (placebo, tighter impulse) is
a one-line change, not a copy of the logic.
"""

from __future__ import annotations

import numpy as np

DEFAULTS = {
    "atr_period": 14,
    "impulse_atr": 1.5,    # impulse bar body must be at least this many prior-bar ATRs
    "break_bars": 10,      # ...and close beyond the highest high (lowest low) of this many prior bars
    "require_break": True,
    "ob_lookback": 5,      # the zone candle is the last opposite candle within this many bars before the impulse
    "max_age": 20,         # an impulse older than this many bars is stale
}


def wilder_atr(high, low, close, period: int) -> np.ndarray:
    prev = np.concatenate(([close[0]], close[:-1]))
    tr = np.maximum.reduce([high - low, np.abs(high - prev), np.abs(low - prev)])
    out = np.full(len(tr), np.nan)
    if len(tr) <= period:
        return out
    out[period] = tr[1 : period + 1].mean()
    for i in range(period + 1, len(tr)):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def detect(open_, high, low, close, **overrides) -> dict | None:
    p = {**DEFAULTS, **overrides}
    n = len(close)
    atr = wilder_atr(high, low, close, p["atr_period"])
    best = None
    for j in range(n - 1, max(p["atr_period"] + 1, p["break_bars"] + 1, n - 1 - p["max_age"]) - 1, -1):
        a = atr[j - 1]
        if not a or np.isnan(a):
            continue
        body = close[j] - open_[j]
        for side in (1, -1):
            if side * body < p["impulse_atr"] * a or (side * body <= 0):
                continue
            if p["require_break"]:
                ref = high[j - p["break_bars"] : j].max() if side == 1 else low[j - p["break_bars"] : j].min()
                if not (close[j] > ref if side == 1 else close[j] < ref):
                    continue
            # zone candle: last opposite-colour candle before the impulse
            zone = None
            for i in range(j - 1, max(j - 1 - p["ob_lookback"], 0) - 1, -1):
                if side * (close[i] - open_[i]) < 0:
                    zone = (low[i], high[i], i)
                    break
            if zone is None:
                continue
            lo, hi, i = zone
            after_close, after_low, after_high = close[j + 1 :], low[j + 1 :], high[j + 1 :]
            mitigated = (after_close < lo).any() if side == 1 else (after_close > hi).any()
            if mitigated:
                continue
            touched = bool((after_low <= hi).any()) if side == 1 else bool((after_high >= lo).any())
            cand = {"side": side, "zone_low": float(lo), "zone_high": float(hi), "bars_ago": n - 1 - j, "touched": touched, "atr": float(atr[-1])}
            if best is None or cand["bars_ago"] < best["bars_ago"]:
                best = cand
        if best is not None:
            return best  # scanning newest first: the first valid impulse is the most recent
    return best


def proximity(zone: dict, last_close: float, max_dist_atr: float) -> float:
    """Signed retest score in (-1, 1): the sign is the zone side, the size is 1 inside the zone and
    fades to 0 as price drifts `max_dist_atr` ATRs away on the expected side. 0 means abstain."""
    a = zone["atr"]
    if not a or np.isnan(a):
        return 0.0
    if zone["side"] == 1:
        if last_close < zone["zone_low"]:
            return 0.0
        d = max((last_close - zone["zone_high"]) / a, 0.0)
    else:
        if last_close > zone["zone_high"]:
            return 0.0
        d = max((zone["zone_low"] - last_close) / a, 0.0)
    return zone["side"] * max(1.0 - d / max_dist_atr, 0.0)
