"""F12: fresh 5-session low inside the 11-month trend (`cards/F12.yml`, port lane).

Alpha#52 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 5 Nov 2026, SPEC.md section 5):

    ((((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5)) * rank(((sum(returns, 240) -
      sum(returns, 20)) / 220))) * ts_rank(volume, 5))

On adjusted prices (SPEC.md section 2):
- drop = (lowest low of the 5 sessions ending 5 sessions ago - lowest low of the last 5)
  / last close: positive when a fresh lower low was made (the paper's term is in price
  units; dividing by the close lets stocks of any price compare);
- trend = percentile rank, among the stocks scored that date, of (sum of the last 240
  daily close-to-close returns - sum of the last 20) / 220: the 11-month move skipping
  the last month;
- vol = rank of the last session's volume among the last 5 (ties averaged), divided by 5.

score = drop x trend x vol. A pullback low in a strong 11-month trend on heavy volume
is bullish; rising lows are bearish. Unchanged lows abstain.

Cross-sectional only through the trend rank (`strategies/f12_trend_pullback_low_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

LOW_WINDOW = 5
LONG = 240
SHORT = 20
MIN_ROWS = LONG + 1


def parts(frame: pd.DataFrame) -> tuple[float, float, float]:
    """(drop in the 5-session low over the close, 11-month-skip-1 summed return / 220, volume ts-rank)."""
    close = frame["adj_close"].to_numpy(float)[-MIN_ROWS:]
    low = frame["adj_low"].to_numpy(float)[-2 * LOW_WINDOW:]
    volume = frame["volume"].to_numpy(float)[-LOW_WINDOW:]
    drop = (low[:LOW_WINDOW].min() - low[LOW_WINDOW:].min()) / close[-1]
    rets = close[1:] / close[:-1] - 1.0
    trend = (rets.sum() - rets[-SHORT:].sum()) / (LONG - SHORT)
    last = volume[-1]
    vol = ((volume < last).sum() + 0.5 * ((volume == last).sum() + 1)) / LOW_WINDOW
    return float(drop), float(trend), float(vol)


def components(history: pd.DataFrame) -> pd.DataFrame:
    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    rows = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        drop, trend, vol = parts(group.sort_values("date"))
        if np.isfinite(drop) and np.isfinite(trend) and np.isfinite(vol) and drop != 0.0:
            rows[symbol] = (drop, trend, vol)
    return pd.DataFrame.from_dict(rows, orient="index", columns=["drop", "trend", "vol"])


def score(history: pd.DataFrame) -> pd.Series:
    """Drop in the 5-session low x 11-month trend rank x volume ts-rank."""
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see `strategies/t01_sma_crossover.py`).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)
    comp = components(history)
    if comp.empty:
        return pd.Series(dtype=float)
    return (comp["drop"] * comp["trend"].rank(pct=True) * comp["vol"]).astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F12 trend pullback low: insufficient history or unchanged lows, abstain"
    sub = compute_adjustment_factors(history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS))
    drop, trend, vol = parts(sub)
    side = "bullish" if sc[symbol] > 0 else "bearish"
    what = "fresh lower 5-session low" if drop > 0 else "rising 5-session lows"
    return (f"F12 trend pullback low (Alpha#52): {what} ({drop:+.1%} of the close), 11-month trend "
            f"{trend * 220:+.0%}, volume rank {vol:.1f} of 5 sessions, {side}")
