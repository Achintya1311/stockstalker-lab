"""T16: Parabolic SAR (`cards/T16.yml`, `state/queue.md` port lane).

Wilder (1978)'s stop-and-reverse: a trailing level that follows price and
accelerates towards it as a trend extends. `cards/catalog.csv`: price above
SAR bullish, below bearish, with step 0.02 and maximum 0.2.

The standard recursion on the adjusted high/low (SPEC.md section 2):

- in an uptrend, SAR(t) = SAR(t-1) + AF x (EP - SAR(t-1)), capped at the two
  previous lows; EP is the highest high of the trend; AF starts at 0.02 and
  rises by 0.02 (to 0.2) each time EP makes a new high;
- if the low of bar t falls below SAR(t), the trend reverses: SAR(t) = EP,
  EP = low(t), AF = 0.02; the downtrend mirrors all of this.

Score on the last visible bar: `(close - SAR) / close`. Positive (close
above SAR, uptrend) is bullish and negative is bearish; the size is how far
the close sits from its stop level. Every symbol with enough history scores
(SAR always places a stock on one side).

Only the trailing `MIN_ROWS` rows are read (`state/engine-issues.md`'s
"Replay took 1h45m+" WATCH), and the recursion starts on the first of them
(trend from the first two closes). Every reversal resets the state, so the
start matters only until the first reversal inside the window; a symbol
with no reversal in `MIN_ROWS` rows keeps a seed-dependent SAR (red flag in
the card).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

STEP, MAX_AF = 0.02, 0.2
MIN_ROWS = 120


def parabolic_sar(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(sar, uptrend flag) per bar; bar 0 is the seed."""
    n = len(close)
    sar = np.empty(n)
    up = np.empty(n, dtype=bool)
    up[0] = close[1] >= close[0] if n > 1 else True
    sar[0] = low[0] if up[0] else high[0]
    ep = high[0] if up[0] else low[0]
    af = STEP
    for i in range(1, n):
        prev = sar[i - 1]
        s = prev + af * (ep - prev)
        if up[i - 1]:
            s = min(s, low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
            if low[i] < s:
                up[i], s, ep, af = False, ep, low[i], STEP
            else:
                up[i] = True
                if high[i] > ep:
                    ep, af = high[i], min(af + STEP, MAX_AF)
        else:
            s = max(s, high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
            if high[i] > s:
                up[i], s, ep, af = True, ep, high[i], STEP
            else:
                up[i] = False
                if low[i] < ep:
                    ep, af = low[i], min(af + STEP, MAX_AF)
        sar[i] = s
    return sar, up


def _sar_score(frame: pd.DataFrame) -> float:
    tail = frame.iloc[-MIN_ROWS:]
    h, l, c = (tail[f"adj_{f}"].to_numpy(dtype=float) for f in ("high", "low", "close"))
    if c[-1] <= 0:
        return float("nan")
    sar, _ = parabolic_sar(h, l, c)
    return float((c[-1] - sar[-1]) / c[-1])


def score(history: pd.DataFrame) -> pd.Series:
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
        value = _sar_score(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T16 Parabolic SAR: insufficient history, abstain"
    value = _sar_score(compute_adjustment_factors(sub))
    side = "bullish (close above SAR)" if value > 0 else "bearish (close below SAR)" if value < 0 else "neutral"
    return f"T16 Parabolic SAR (0.02/0.2): close {value:+.2%} from SAR -> {side}"
