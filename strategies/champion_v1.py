"""Champion v1: the current StockStalker blended score (`state/queue.md` B7).

Ported from `STOCKSTALKER/stockstalker/screener.py` and
`STOCKSTALKER/stockstalker/signals/{trend,momentum,volume}.py` (Achintya's own
prior repo; checked out read-only alongside this lab as the champion-v1
reference). The three signal formulas and their blend weights are unchanged:

- trend: SMA(20, 50) crossover spread, scaled by 10 and clipped to [-1, 1]
- momentum: 0.5 * RSI(14) re-centred on 50 + 0.5 * MACD(12, 26, 9) histogram
  as a percentage of price, each clipped to [-1, 1]
- volume: 0.5 * rolling 20-day volume z-score (divided by 3) + 0.5 * 20-day
  OBV change over 20-day traded volume, each clipped to [-1, 1]
- blend: weighted average, weights {trend: 0.4, momentum: 0.35, volume: 0.25}

StockStalker's own `blended_score` remaps that [-1, 1] blend into [0, 1] for
display. This module skips that remap and returns the blend itself: SPEC.md
section 5's strategy contract ("one score per symbol; NaN means abstain")
reads a pick's side from its score's sign (the convention `engine.selftest`
already establishes for the leak/random self-tests), so the sign has to
survive, not get folded away into a display-only magnitude.

Per SPEC.md section 2, indicators run on the adjusted close series
(`scripts.adjustments.compute_adjustment_factors`); volumes are raw, same as
StockStalker's own volume signal. `history` is whatever truncated slice
`engine.replay` hands this module (never the full dataset), so adjustment
factors are themselves recomputed walk-forward from only what is visible as
of the pick date, per SPEC.md section 4.

A symbol abstains (dropped from the returned Series, which `engine.replay`
then `dropna()`s the same as an explicit NaN would) until it has at least
`MIN_ROWS` trading days of history - the longest lookback any component
needs (the 50-day slow SMA) - so no component silently falls back to its
own neutral default on a thin history and masquerades as a real reading.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WEIGHTS = {"trend": 0.4, "momentum": 0.35, "volume": 0.25}

TREND_FAST, TREND_SLOW = 20, 50
RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
VOLUME_Z_WINDOW, VOLUME_OBV_WINDOW = 20, 20

MIN_ROWS = max(TREND_SLOW, MACD_SLOW + MACD_SIGNAL, VOLUME_Z_WINDOW, VOLUME_OBV_WINDOW + 1)


def _sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window, min_periods=window).mean()


def _ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False, min_periods=span).mean()


def _trend_component(close: pd.Series) -> float:
    fast_latest = _sma(close, TREND_FAST).iloc[-1]
    slow_latest = _sma(close, TREND_SLOW).iloc[-1]
    if pd.isna(fast_latest) or pd.isna(slow_latest) or slow_latest == 0:
        return 0.0
    spread = (fast_latest - slow_latest) / abs(slow_latest)
    return float(np.clip(spread * 10, -1.0, 1.0))


def _wilder_smooth(values: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing: simple-mean seed, then his recursion (see
    STOCKSTALKER/stockstalker/signals/momentum.py for why plain `ewm` disagrees
    early on)."""
    arr = values.to_numpy(dtype=float)
    out = np.full(arr.shape, np.nan)
    if arr.size > period:
        out[period] = arr[1 : period + 1].mean()
        for i in range(period + 1, arr.size):
            out[i] = (out[i - 1] * (period - 1) + arr[i]) / period
    return pd.Series(out, index=values.index)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    avg_gain = _wilder_smooth(delta.clip(lower=0), period)
    avg_loss = _wilder_smooth(-delta.clip(upper=0), period)
    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    result[(avg_gain == 0) & (avg_loss == 0)] = 50.0
    return result


def _macd_histogram(close: pd.Series) -> pd.Series:
    macd_line = _ema(close, MACD_FAST) - _ema(close, MACD_SLOW)
    signal_line = _ema(macd_line, MACD_SIGNAL)
    return macd_line - signal_line


def _momentum_component(close: pd.Series) -> float:
    latest_rsi = _rsi(close, RSI_PERIOD).iloc[-1]
    rsi_component = 0.0 if pd.isna(latest_rsi) else float(np.clip((latest_rsi - 50) / 50, -1.0, 1.0))

    histogram = _macd_histogram(close).iloc[-1]
    latest_close = close.iloc[-1]
    if pd.isna(histogram) or latest_close == 0:
        macd_component = 0.0
    else:
        macd_component = float(np.clip((histogram / latest_close) * 100, -1.0, 1.0))

    return float(np.clip(0.5 * rsi_component + 0.5 * macd_component, -1.0, 1.0))


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def _volume_zscore(volume: pd.Series, window: int) -> pd.Series:
    rolling_mean = volume.rolling(window=window, min_periods=window).mean()
    rolling_std = volume.rolling(window=window, min_periods=window).std()
    z = (volume - rolling_mean) / rolling_std
    z[rolling_std == 0] = 0.0
    return z


def _volume_component(close: pd.Series, volume: pd.Series) -> float:
    latest_z = _volume_zscore(volume, VOLUME_Z_WINDOW).iloc[-1]
    z_component = 0.0 if pd.isna(latest_z) else float(np.clip(latest_z / 3, -1.0, 1.0))

    obv_series = _obv(close, volume)
    if len(obv_series) > VOLUME_OBV_WINDOW:
        change = obv_series.iloc[-1] - obv_series.iloc[-VOLUME_OBV_WINDOW - 1]
        traded = volume.iloc[-VOLUME_OBV_WINDOW:].sum()
        obv_component = 0.0 if traded == 0 else float(np.clip(change / traded, -1.0, 1.0))
    else:
        obv_component = 0.0

    return float(np.clip(0.5 * z_component + 0.5 * obv_component, -1.0, 1.0))


def _components(close: pd.Series, volume: pd.Series) -> dict[str, float]:
    return {
        "trend": _trend_component(close),
        "momentum": _momentum_component(close),
        "volume": _volume_component(close, volume),
    }


def _blend(components: dict[str, float]) -> float:
    total = sum(WEIGHTS.get(k, 0.0) for k in components)
    if total == 0:
        return sum(components.values()) / len(components)
    return sum(components[k] * WEIGHTS.get(k, 0.0) for k in components) / total


def score(history: pd.DataFrame) -> pd.Series:
    """One StockStalker blended score per symbol with at least `MIN_ROWS` rows.

    Positive means bullish, negative bearish (sign is the pick's side); a
    symbol with too little history to compute every component honestly is
    left out of the returned Series, which `engine.replay.pick_date`'s
    `dropna()` treats exactly like an explicit NaN abstain.
    """
    if history.empty:
        return pd.Series(dtype=float)

    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        group = group.sort_values("date")
        components = _components(group["adj_close"], group["volume"])
        out[symbol] = _blend(components)
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "champion v1 (StockStalker blended score): insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    components = _components(adjusted["adj_close"], adjusted["volume"])
    blended = _blend(components)
    direction = "bullish" if blended > 0 else "bearish" if blended < 0 else "neutral"
    return (
        "champion v1 (StockStalker blended score): "
        f"trend {components['trend']:+.3f}, momentum {components['momentum']:+.3f}, "
        f"volume {components['volume']:+.3f} -> blended {blended:+.3f} ({direction})"
    )
