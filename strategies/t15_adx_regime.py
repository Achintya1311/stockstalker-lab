"""T15: ADX(14) regime filter, choosing between T01's trend rule and T03's
mean-reversion rule (`cards/T15.yml`, `state/queue.md` port lane).

Wilder (1978): ADX measures trend STRENGTH, not direction - the catalog's
own rule ("use ADX > 25 to choose trend rules, < 20 to choose
mean-reversion rules") is explicitly a chooser between two other rules it
never names, not a standalone bullish/bearish signal the way T01-T14's
cards all are. `cards/T15.yml`'s red_flags documents the specific choice
made here: ADX is paired with the two simplest already-ported
representatives of each family -
`strategies/t01_sma_crossover.py` (trend) and `strategies/t03_rsi_thresholds.py`
(mean-reversion) - rather than inventing new rules for either side.

- `ADX > 25`: trend regime. Score = T01's own SMA(20,50) spread, always
  returned (even at exactly 0), same always-on convention T01 itself uses.
- `ADX < 20`: mean-reversion regime. Score = T03's own RSI(14) 30/70
  threshold score, only returned when RSI is actually past one of the two
  thresholds - T03's own selective convention is unchanged; ADX choosing
  this branch does not force T03's gate to fire.
- `20 <= ADX <= 25`: Wilder's own "no man's land". Abstain.

`_wilder_smooth` is `strategies/champion_v1.py`'s own vectorized
Wilder-smoothing shape, copied (not imported) with the usual "skips one
value lost to a diff-like input" seed. ADX's own second smoothing pass
(DX -> ADX) uses a different helper, `_wilder_smooth_from_valid`, since DX
carries no such leading lost value to skip - see `cards/T15.yml`'s
rules_plain for the derivation. `_true_range` is
`strategies/t09_supertrend.py::_true_range`'s exact formula, copied for
the same standalone-module reason every other `strategies/t0*` card gives.
RSI reuses `strategies/t03_rsi_thresholds.py::_rsi`'s exact shape.

Per SPEC.md section 2, every indicator here runs on the adjusted
high/low/close series (`scripts.adjustments.compute_adjustment_factors`),
so a split or bonus inside any lookback window doesn't masquerade as a
real trend or volatility move.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

PERIOD = 14
TREND_THRESHOLD = 25.0
MEAN_REVERSION_THRESHOLD = 20.0

FAST, SLOW = 20, 50
RSI_OVERSOLD, RSI_OVERBOUGHT = 30.0, 70.0

# T01's own SLOW=50 dominates ADX's own 2*PERIOD=28-row minimum for a
# first valid reading - whichever branch a symbol ends up in, both
# sub-computations need to be able to run.
MIN_ROWS = SLOW


def _wilder_smooth(values: pd.Series, period: int) -> pd.Series:
    """See `strategies/champion_v1.py::_wilder_smooth` for the derivation.
    Same formula, copied rather than imported so this card stays
    standalone. First valid output at index `period` (one value lost to
    the diff-like input's own leading NaN/placeholder, never read)."""
    arr = values.to_numpy(dtype=float)
    out = np.full(arr.shape, np.nan)
    if arr.size > period:
        seed = arr[1 : period + 1].mean()
        tail = np.concatenate(([seed], arr[period + 1 :]))
        out[period:] = pd.Series(tail).ewm(alpha=1.0 / period, adjust=False).mean().to_numpy()
    return pd.Series(out, index=values.index)


def _wilder_smooth_from_valid(arr: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothing recursion for an input with NO leading lost
    value (every element is real data) - unlike `_wilder_smooth`'s
    `close.diff()`-shaped input, `DX` has nothing to skip. Seeded from the
    simple mean of the first `period` elements (Wilder's own textbook
    convention), first valid output at index `period - 1`."""
    out = np.full(arr.shape, np.nan)
    n = arr.size
    if n >= period:
        seed = arr[:period].mean()
        tail = np.concatenate(([seed], arr[period:]))
        out[period - 1 :] = pd.Series(tail).ewm(alpha=1.0 / period, adjust=False).mean().to_numpy()
    return out


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """See `strategies/t09_supertrend.py::_true_range`; same formula,
    copied rather than imported so this card stays standalone."""
    prev_close = np.empty_like(close)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    return np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))


def _rsi(close: pd.Series, period: int) -> pd.Series:
    """See `strategies/t03_rsi_thresholds.py::_rsi`; same formula, copied
    rather than imported so this card stays standalone."""
    delta = close.diff()
    avg_gain = _wilder_smooth(delta.clip(lower=0), period)
    avg_loss = _wilder_smooth(-delta.clip(upper=0), period)
    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    result[(avg_gain == 0) & (avg_loss == 0)] = 50.0
    return result


def _sma(close: pd.Series, window: int) -> float:
    return float(close.tail(window).mean())


def _adx_latest(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> float:
    """Latest-bar ADX(`period`), or NaN if there is not yet one valid
    reading (caller already guards on `MIN_ROWS`, but this stays robust
    on its own)."""
    n = len(close)
    tr = _true_range(high, low, close)

    up_move = np.empty(n)
    down_move = np.empty(n)
    up_move[0] = np.nan
    down_move[0] = np.nan
    up_move[1:] = high[1:] - high[:-1]
    down_move[1:] = low[:-1] - low[1:]

    dm_plus = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    dm_minus = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    # `_wilder_smooth` never reads index 0 (it is the formula's own "lost
    # to a diff" row), so leaving it at 0 here (rather than NaN) is
    # harmless and keeps the arrays plain float, not object/NaN-tainted.
    dm_plus[0] = 0.0
    dm_minus[0] = 0.0

    smoothed_tr = _wilder_smooth(pd.Series(tr), period).to_numpy()
    smoothed_dm_plus = _wilder_smooth(pd.Series(dm_plus), period).to_numpy()
    smoothed_dm_minus = _wilder_smooth(pd.Series(dm_minus), period).to_numpy()

    with np.errstate(invalid="ignore", divide="ignore"):
        di_plus = np.where(smoothed_tr > 0, 100.0 * smoothed_dm_plus / smoothed_tr, 0.0)
        di_minus = np.where(smoothed_tr > 0, 100.0 * smoothed_dm_minus / smoothed_tr, 0.0)
        di_sum = di_plus + di_minus
        dx = np.where(di_sum > 0, 100.0 * np.abs(di_plus - di_minus) / di_sum, 0.0)
    # DX is only meaningful from +DI/-DI's own first valid bar onward
    # (index `period`); before that, +DI/-DI/DX above are all spuriously
    # 0 (NaN smoothed_tr makes every `where` branch fall to the 0 arm),
    # not real "no trend" readings, so they must not enter the DX->ADX
    # smoothing pass at all.
    dx_valid = dx[period:]
    if dx_valid.size < period:
        return float("nan")
    adx = _wilder_smooth_from_valid(dx_valid, period)
    return float(adx[-1])


def _regime_score(high: np.ndarray, low: np.ndarray, close: pd.Series) -> float:
    """NaN means abstain (SPEC.md section 5): either the ADX reading
    itself isn't available yet, ADX falls in the 20-25 no-man's-land, or
    the chosen branch's own gate (T03's RSI thresholds, in the
    mean-reversion case) doesn't fire."""
    adx_latest = _adx_latest(high, low, close.to_numpy(dtype=float), PERIOD)
    if pd.isna(adx_latest):
        return float("nan")

    if adx_latest > TREND_THRESHOLD:
        fast_latest = _sma(close, FAST)
        slow_latest = _sma(close, SLOW)
        if slow_latest == 0:
            return 0.0
        return (fast_latest - slow_latest) / abs(slow_latest)

    if adx_latest < MEAN_REVERSION_THRESHOLD:
        rsi_latest = _rsi(close, 14).iloc[-1]
        if pd.isna(rsi_latest):
            return float("nan")
        if rsi_latest < RSI_OVERSOLD:
            return (RSI_OVERSOLD - rsi_latest) / RSI_OVERSOLD
        if rsi_latest > RSI_OVERBOUGHT:
            return -(rsi_latest - RSI_OVERBOUGHT) / RSI_OVERSOLD
        return float("nan")

    return float("nan")  # 20 <= ADX <= 25: no man's land, neither rule chosen


def score(history: pd.DataFrame) -> pd.Series:
    """One regime-filtered score per symbol with at least `MIN_ROWS` rows
    of history and a defined ADX reading whose chosen branch actually
    fires; every other symbol abstains (left out of the returned Series,
    same convention every other card here uses)."""
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
        high = group["adj_high"].to_numpy(dtype=float)
        low = group["adj_low"].to_numpy(dtype=float)
        close = group["adj_close"]
        value = _regime_score(high, low, close)
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T15 ADX regime filter: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    high = adjusted["adj_high"].to_numpy(dtype=float)
    low = adjusted["adj_low"].to_numpy(dtype=float)
    close = adjusted["adj_close"]
    adx_latest = _adx_latest(high, low, close.to_numpy(dtype=float), PERIOD)
    value = _regime_score(high, low, close)

    if pd.isna(adx_latest):
        return "T15 ADX regime filter: ADX not yet available, abstain"
    if adx_latest > TREND_THRESHOLD:
        regime = f"trend regime (ADX={adx_latest:.2f} > {TREND_THRESHOLD:.0f}), T01 SMA(20,50) spread"
    elif adx_latest < MEAN_REVERSION_THRESHOLD:
        regime = f"mean-reversion regime (ADX={adx_latest:.2f} < {MEAN_REVERSION_THRESHOLD:.0f}), T03 RSI(14) 30/70"
    else:
        regime = f"no man's land (ADX={adx_latest:.2f}), neither rule chosen"

    if pd.isna(value):
        return f"T15 ADX regime filter: {regime} -> no agreed signal, abstain"
    direction = "bullish" if value > 0 else "bearish" if value < 0 else "neutral"
    return f"T15 ADX regime filter: {regime} -> score {value:+.4f} ({direction})"
