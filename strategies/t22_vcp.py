"""T22: volatility contraction pattern, VCP (`cards/T22.yml`, `state/queue.md` port lane).

Minervini's VCP: inside a stage-2 uptrend, each pullback is shallower than the
one before, volume dries up in the pullbacks, and the stock lifts off near its
recent high on heavier volume. `cards/catalog.csv` points to PKScreener's
`validateVCPMarkMinervini` (MIT, `third_party/pkscreener/ScreeningStatistics.py`,
Copyright (c) 2023 pkjmesra); this is a re-implementation of its checklist, not
a copy, rewritten for oldest-first data and made causal.

The lab's reading, on the adjusted series (SPEC.md section 2), all required:

1. weekly trend: on Friday-ending weekly closes, EMA13 > EMA26 > SMA50;
2. daily trend: close > SMA50 > SMA150 > SMA200;
3. swing highs: a bar whose high is at least the 10 bars before and above the
   10 after.
   Only peaks with all 10 later bars already visible count (PKScreener's
   centred window would otherwise read bars after the pick date). The last 4
   such peaks inside the last 90 bars are kept; at least 3 are needed;
4. tightening: the pullback after each peak (peak high to the lowest low before
   the next peak, over the peak high) is at most 70% of the one before;
5. volume dry-up: mean volume between the last two peaks is at most 70% of the
   mean volume on the up-closes of the last 10 bars;
6. lift-off: the last bar's volume is above 1.2x the mean of the 10 before it;
7. near the high: close above 90% of the highest high of the last 20 bars.

Bullish only (the pattern has no published mirror). Score: first pullback over
last pullback, so the stocks whose swings tightened most rank first. Every
other stock abstains.

Only the trailing `MIN_ROWS` rows are read (`state/engine-issues.md`'s "Replay
took 1h45m+" WATCH): 260 sessions hold the 200-day SMA and about 52 weekly bars.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

MIN_ROWS = 260
PEAK_ORDER = 10
PEAK_LOOKBACK = 90
MAX_PEAKS = 4
TIGHTEN = 0.70
DRY_UP = 0.70
LIFT = 1.2
NEAR_HIGH = 0.90


def peaks(high: np.ndarray, start: int = PEAK_ORDER) -> list[int]:
    """Indices (from `start`) of confirmed swing highs: at least the PEAK_ORDER bars
    before and above the PEAK_ORDER bars after, every one of which is already in
    `high`. Strict on the right so a flat top counts once, at its last bar."""
    n = len(high)
    out = []
    for i in range(max(start, PEAK_ORDER), n - PEAK_ORDER):
        if high[i] >= high[i - PEAK_ORDER:i].max() and high[i] > high[i + 1:i + PEAK_ORDER + 1].max():
            out.append(i)
    return out


def pullbacks(high: np.ndarray, low: np.ndarray, idx: list[int]) -> list[float]:
    return [(high[a] - low[a:b + 1].min()) / high[a] for a, b in zip(idx, idx[1:])]


def check(frame: pd.DataFrame) -> tuple[float, str]:
    """(score or NaN, reason) for the last row of one symbol's adjusted frame."""
    tail = frame.iloc[-MIN_ROWS:]
    close = tail["adj_close"].to_numpy(float)
    high = tail["adj_high"].to_numpy(float)
    low = tail["adj_low"].to_numpy(float)
    vol = tail["volume"].to_numpy(float)
    n = len(close)

    weekly = pd.Series(close, index=pd.to_datetime(tail["date"].to_numpy())).resample("W-FRI").last().dropna()
    if len(weekly) < 50:
        return float("nan"), "fewer than 50 weekly bars"
    e13 = weekly.ewm(span=13, adjust=False).mean().iloc[-1]
    e26 = weekly.ewm(span=26, adjust=False).mean().iloc[-1]
    s50w = weekly.iloc[-50:].mean()
    if not e13 > e26 > s50w:
        return float("nan"), "weekly EMA13 > EMA26 > SMA50 fails"

    s50, s150, s200 = close[-50:].mean(), close[-150:].mean(), close[-200:].mean()
    if not close[-1] > s50 > s150 > s200:
        return float("nan"), "close > SMA50 > SMA150 > SMA200 fails"

    idx = peaks(high, start=n - PEAK_LOOKBACK)[-MAX_PEAKS:]
    if len(idx) < 3:
        return float("nan"), f"{len(idx)} swing highs in {PEAK_LOOKBACK} bars, need 3"
    legs = pullbacks(high, low, idx)
    if not all(p > 0 for p in legs) or any(b > TIGHTEN * a for a, b in zip(legs, legs[1:])):
        return float("nan"), "pullbacks " + " / ".join(f"{p:.1%}" for p in legs) + " not tightening"

    pull_vol = vol[idx[-2]:idx[-1] + 1].mean()
    up = np.diff(close[-11:]) > 0
    up_vol = vol[-10:][up].mean() if up.any() else pull_vol
    if not pull_vol <= DRY_UP * up_vol:
        return float("nan"), "no volume dry-up in the last pullback"
    if not vol[-1] > LIFT * vol[-11:-1].mean():
        return float("nan"), "no volume lift-off on the last bar"
    if not close[-1] > NEAR_HIGH * high[-20:].max():
        return float("nan"), "more than 10% below the 20-bar high"
    return legs[0] / legs[-1], "pullbacks " + " / ".join(f"{p:.1%}" for p in legs)


def score(history: pd.DataFrame) -> pd.Series:
    """Positive score for symbols showing the VCP checklist; every other symbol abstains."""
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
        value, _ = check(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T22 VCP: insufficient history, abstain"
    value, reason = check(compute_adjustment_factors(sub))
    if np.isnan(value):
        return f"T22 VCP: {reason}, abstain"
    return f"T22 VCP: bullish, {reason}, tightened {value:.1f}x, volume lift-off near the 20-bar high"
