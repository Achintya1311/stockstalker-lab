"""T12: Stochastic %K/%D, 14/3/3 (`cards/T12.yml`, `state/queue.md` port lane).

George Lane's Stochastic Oscillator: smoothed %K crossing up through 20 is
bullish (oversold reversal), crossing down through 80 is bearish
(overbought reversal). Like `strategies/t05_macd_crossover.py`'s MACD
crossing and `strategies/t03_rsi_thresholds.py`'s RSI thresholds, this is
an event, not a persisted state - this card only fires on the bar %K
actually crosses a threshold and abstains otherwise, even if %K has
already sat below 20 (or above 80) for several bars without a fresh cross.

Raw %K = 100 * (close - lowest_low_14) / (highest_high_14 - lowest_low_14),
over a trailing 14-day window of adjusted high/low. %K itself (what this
card reads and what most retail platforms display, and the "slow %K" the
default_params' middle value (3) names) is a 3-day simple moving average of
raw %K. %D (the default_params' third value) is part of the standard
indicator's full definition but is never computed here: the catalog's
literal rule only references %K crossing fixed thresholds, not a %K/%D
crossover (`cards/T12.yml`'s red_flags).

Score reuses `strategies/t03_rsi_thresholds.py`'s threshold-distance
convention rather than T05's price-denominated one: the 20/80 thresholds
are symmetric around 50 with a 20-point distance to each series boundary
(0, 100), the same shape T03's 30/70 thresholds have to their own
boundaries. The magnitude is set by the PRIOR bar's %K (how
oversold/overbought it was, which is what makes the fresh cross notable),
not the latest bar's %K (constrained to sit just the other side of the
threshold by the cross condition itself).

Catalog lists this card's horizon as day only, so one module serves that
one horizon (unlike T01/T03/T05's "both").
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

K_PERIOD = 14
K_SMOOTH = 3
D_SMOOTH = 3  # Part of the standard definition; unused by this card's literal rule (cards/T12.yml red_flags).

# Smoothed %K is first valid at 0-indexed row K_PERIOD + K_SMOOTH - 2 (14-row
# rolling high/low window, then a 3-row SMA on top needs 2 more rows past
# its own first input). One more row than that so a prior-bar smoothed %K
# also exists to compare against for the cross itself - MIN_ROWS = 17.
MIN_ROWS = K_PERIOD + K_SMOOTH


def _smoothed_k(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    rolling_high = high.rolling(K_PERIOD).max()
    rolling_low = low.rolling(K_PERIOD).min()
    denom = (rolling_high - rolling_low).where(lambda d: d != 0)
    raw_k = (close - rolling_low) / denom * 100.0
    return raw_k.rolling(K_SMOOTH).mean()


def _stochastic_score(k_prev: float, k_latest: float) -> float:
    """NaN means abstain (SPEC.md section 5): no fresh threshold cross on
    this bar."""
    if pd.isna(k_prev) or pd.isna(k_latest):
        return float("nan")
    crossed_up = k_prev < 20 and k_latest >= 20
    crossed_down = k_prev > 80 and k_latest <= 80
    if crossed_up:
        return (20.0 - k_prev) / 20.0
    if crossed_down:
        return -(k_prev - 80.0) / 20.0
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """One Stochastic-crossing score per symbol with at least `MIN_ROWS`
    rows of history and a fresh threshold cross on the latest bar; every
    other symbol abstains (left out of the returned Series, same
    convention every other card here uses)."""
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
        group = group.sort_values("date")
        k = _smoothed_k(group["adj_high"], group["adj_low"], group["adj_close"])
        value = _stochastic_score(float(k.iloc[-2]), float(k.iloc[-1]))
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T12 Stochastic %K/%D: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    k = _smoothed_k(adjusted["adj_high"], adjusted["adj_low"], adjusted["adj_close"])
    k_prev, k_latest = float(k.iloc[-2]), float(k.iloc[-1])
    value = _stochastic_score(k_prev, k_latest)
    if pd.isna(value):
        return f"T12 Stochastic %K/%D: %K={k_latest:.2f} (prior bar %K={k_prev:.2f}) -> no fresh threshold cross, abstain"
    direction = "bullish (crossed up through 20)" if value > 0 else "bearish (crossed down through 80)"
    return f"T12 Stochastic %K/%D: %K={k_latest:.2f} (prior bar %K={k_prev:.2f}) -> score {value:+.4f} ({direction})"
