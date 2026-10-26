"""T25: Heikin-Ashi trend (`cards/T25.yml`, `state/queue.md` port lane).

Heikin-Ashi candles smooth ordinary candles:

    ha_close = (open + high + low + close) / 4
    ha_open  = (previous ha_open + previous ha_close) / 2
    ha_high  = max(high, ha_open, ha_close)
    ha_low   = min(low, ha_open, ha_close)

`cards/catalog.csv`: consecutive Heikin-Ashi candles with no lower (upper)
wick: bullish (bearish), 3 candles. The lab's reading: the last `RUN` candles
are all green (ha_close > ha_open) with ha_low == ha_open (no lower wick) ->
bullish; all red with ha_high == ha_open (no upper wick) -> bearish; anything
else abstains.

Conviction: the mean Heikin-Ashi body (|ha_close - ha_open| / ha_close) over
those `RUN` candles, signed by the side, so a strong smoothed run ranks above a
weak one.

The recursion needs a seed. Only the trailing `MIN_ROWS` rows are read
(`state/engine-issues.md`'s "Replay took 1h45m+" WATCH), seeded with
ha_open = (open + close) / 2 on the first of them. The seed's weight halves
every candle, so after `WARMUP` candles it is below 2**-60 of the result.
Prices are the adjusted series (SPEC.md section 2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

RUN = 3
WARMUP = 60
MIN_ROWS = WARMUP + RUN


def heikin_ashi(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> tuple[np.ndarray, ...]:
    ha_close = (o + h + l + c) / 4
    ha_open = np.empty_like(ha_close)
    ha_open[0] = (o[0] + c[0]) / 2
    for i in range(1, len(ha_close)):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2
    ha_high = np.maximum.reduce([h, ha_open, ha_close])
    ha_low = np.minimum.reduce([l, ha_open, ha_close])
    return ha_open, ha_high, ha_low, ha_close


def _run_score(frame: pd.DataFrame) -> float:
    tail = frame.iloc[-MIN_ROWS:]
    o, h, l, c = (tail[f"adj_{f}"].to_numpy(dtype=float) for f in ("open", "high", "low", "close"))
    ha_open, ha_high, ha_low, ha_close = heikin_ashi(o, h, l, c)
    sl = slice(-RUN, None)
    ho, hh, hl, hc = ha_open[sl], ha_high[sl], ha_low[sl], ha_close[sl]
    if (hc <= 0).any():
        return float("nan")
    body = float(np.mean(np.abs(hc - ho) / hc))
    if (hc > ho).all() and np.allclose(hl, ho, rtol=0, atol=1e-12 * np.abs(ho).max()):
        return body
    if (hc < ho).all() and np.allclose(hh, ho, rtol=0, atol=1e-12 * np.abs(ho).max()):
        return -body
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """Score for symbols whose last `RUN` Heikin-Ashi candles form a wickless
    run; every other symbol abstains."""
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        value = _run_score(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T25 Heikin-Ashi trend: insufficient history, abstain"
    value = _run_score(compute_adjustment_factors(sub))
    if np.isnan(value):
        return f"T25 Heikin-Ashi trend: no wickless {RUN}-candle run, abstain"
    side = "bullish (green, no lower wick)" if value > 0 else "bearish (red, no upper wick)"
    return f"T25 Heikin-Ashi trend: last {RUN} candles {side}, mean body {abs(value):.2%} -> score {value:+.4f}"
