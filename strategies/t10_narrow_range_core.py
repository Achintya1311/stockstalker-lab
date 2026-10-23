"""Shared core for T10's two variants (`cards/T10.yml`): Crabel's NR4/NR7
narrow-range day, read in the direction of a trend filter.

The catalog names two lookback windows ("NR4, NR7") rather than one, so the
two public modules (`t10_nr4_narrow_range.py`, `t10_nr7_narrow_range.py`)
are kept thin wrappers around this one, sharing every line of logic except
the lookback length - the same core-plus-variants shape
`strategies/d02_stock_pcr_core.py` already uses for its two sign variants.
Neither window is assumed better (SPEC.md section 5); both are scored and
logged as independent trials.

True range per day and the trend filter are each copied from an existing
card rather than re-derived: true range matches
`strategies/t09_supertrend.py::_true_range` exactly, and the trend filter
is `strategies/t01_sma_crossover.py`'s own fast/slow (20/50) SMA spread -
the catalog names no trend filter of its own, and reusing the one filter
already established in this codebase introduces no new tunable parameter
this card would otherwise have to invent from nothing (`cards/T10.yml`'s
rules_plain has the full reasoning).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

TREND_FAST, TREND_SLOW = 20, 50


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Copied from `strategies/t09_supertrend.py::_true_range`: row 0's
    prior close falls back to its own close, discarded by construction
    whenever the trailing NR window excludes row 0 (see `MIN_ROWS` in each
    variant and `cards/T10.yml`'s rules_plain)."""
    prev_close = np.empty_like(close)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    return np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))


def _is_narrow_range(true_range: np.ndarray, lookback: int) -> bool:
    """True range's own trailing `lookback`-day window must have fewer than
    `lookback` entries to answer; callers are expected to have already
    checked there are enough rows. Ties break toward the earliest
    occurrence (`np.argmin`'s own convention): today counts as NR<lookback>
    only if it is a strict new low over the window, not a repeat of one
    already set earlier in it (`cards/T10.yml`'s red_flags)."""
    window = true_range[-lookback:]
    return int(np.argmin(window)) == lookback - 1


def _trend_spread(close: pd.Series) -> float:
    """Copied from `strategies/t01_sma_crossover.py::_spread`: the fast
    (20-day) SMA minus the slow (50-day) one, scaled by the slow SMA's own
    level. Sign gives direction, magnitude gives conviction, same
    convention every card here uses."""
    fast_latest = float(close.tail(TREND_FAST).mean())
    slow_latest = float(close.tail(TREND_SLOW).mean())
    if slow_latest == 0:
        return 0.0
    return (fast_latest - slow_latest) / abs(slow_latest)


def _latest_score(high: pd.Series, low: pd.Series, close: pd.Series, lookback: int) -> float:
    """`high`/`low`/`close` must already be the trailing `MIN_ROWS` rows
    (`TREND_SLOW + lookback`), sorted by date. NaN means abstain: today is
    not NR<lookback>, or the trend filter's spread is exactly 0 (fast SMA
    equals slow SMA - undefined direction)."""
    true_range = _true_range(high.to_numpy(), low.to_numpy(), close.to_numpy())
    if not _is_narrow_range(true_range, lookback):
        return float("nan")
    spread = _trend_spread(close)
    return float("nan") if spread == 0 else spread


def min_rows(lookback: int) -> int:
    return TREND_SLOW + lookback


def signal(history: pd.DataFrame, *, lookback: int) -> pd.Series:
    """One NR<lookback> score per symbol with at least `min_rows(lookback)`
    rows of history and today flagged NR<lookback> with a non-zero trend
    spread; every other symbol abstains (left out of the returned Series,
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

    required = min_rows(lookback)
    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < required:
            continue
        group = group.sort_values("date").tail(required)
        value = _latest_score(group["adj_high"], group["adj_low"], group["adj_close"], lookback)
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def reasoning(history: pd.DataFrame, symbol: str, *, lookback: int, label: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    required = min_rows(lookback)
    if len(sub) < required:
        return f"T10 {label}: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub).tail(required)
    true_range = _true_range(
        adjusted["adj_high"].to_numpy(), adjusted["adj_low"].to_numpy(), adjusted["adj_close"].to_numpy()
    )
    if not _is_narrow_range(true_range, lookback):
        return f"T10 {label}: today is not the narrowest range of the last {lookback} days, abstain"

    spread = _trend_spread(adjusted["adj_close"])
    if spread == 0:
        return f"T10 {label}: narrow range day, but trend filter spread is exactly 0, abstain"

    direction = "bullish (fast SMA above slow SMA)" if spread > 0 else "bearish (fast SMA below slow SMA)"
    return f"T10 {label}: narrowest range of the last {lookback} days, trend spread {spread:+.4f} ({direction})"
