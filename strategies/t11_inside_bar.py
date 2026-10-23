"""T11: Inside bar (`cards/T11.yml`, `state/queue.md` port lane).

Classic two-bar price-action pattern: today's whole range sits inside
yesterday's (today's high at or below yesterday's high AND today's low at
or above yesterday's low), read in the direction of
`strategies/t01_sma_crossover.py`'s own fast/slow (20/50) SMA trend filter -
the catalog names no trend filter of its own for this card either, same gap
T10's NR4/NR7 hit, so this card reuses the same substitution rather than
inventing a new one (`cards/T11.yml`'s rules_plain has the full reasoning).

Unlike T10's trailing-N-day narrow-range test, this is a plain two-bar
comparison - no true range, no rolling window - so it needs only one row
of history beyond the trend filter's own minimum.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

TREND_FAST, TREND_SLOW = 20, 50
# One extra row beyond the trend filter's own minimum, so the inside-bar
# comparison always has two real, adjacent rows (today and yesterday) -
# cards/T11.yml's rules_plain.
MIN_ROWS = TREND_SLOW + 1


def _is_inside_bar(high: pd.Series, low: pd.Series) -> bool:
    """Today (the series' last row) sits inside yesterday (the row before
    it): today's high at or below yesterday's, today's low at or above
    yesterday's. Equality on either side still counts as inside
    (cards/T11.yml's red_flags)."""
    today_high, yesterday_high = float(high.iloc[-1]), float(high.iloc[-2])
    today_low, yesterday_low = float(low.iloc[-1]), float(low.iloc[-2])
    return today_high <= yesterday_high and today_low >= yesterday_low


def _trend_spread(close: pd.Series) -> float:
    """Copied from `strategies/t01_sma_crossover.py::_spread`: fast
    (20-day) SMA minus slow (50-day), scaled by the slow SMA's own level."""
    fast_latest = float(close.tail(TREND_FAST).mean())
    slow_latest = float(close.tail(TREND_SLOW).mean())
    if slow_latest == 0:
        return 0.0
    return (fast_latest - slow_latest) / abs(slow_latest)


def _latest_score(high: pd.Series, low: pd.Series, close: pd.Series) -> float:
    """`high`/`low`/`close` must already be the trailing `MIN_ROWS` rows,
    sorted by date. NaN means abstain: today is not an inside bar, or the
    trend filter's spread is exactly 0 (undefined direction)."""
    if not _is_inside_bar(high, low):
        return float("nan")
    spread = _trend_spread(close)
    return float("nan") if spread == 0 else spread


def score(history: pd.DataFrame) -> pd.Series:
    """One inside-bar score per symbol with at least `MIN_ROWS` rows of
    history and today flagged an inside bar with a non-zero trend spread;
    every other symbol abstains (left out of the returned Series, same
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
        group = group.sort_values("date").tail(MIN_ROWS)
        value = _latest_score(group["adj_high"], group["adj_low"], group["adj_close"])
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T11 inside bar: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub).tail(MIN_ROWS)
    if not _is_inside_bar(adjusted["adj_high"], adjusted["adj_low"]):
        return "T11 inside bar: today's range is not inside yesterday's, abstain"

    spread = _trend_spread(adjusted["adj_close"])
    if spread == 0:
        return "T11 inside bar: inside bar day, but trend filter spread is exactly 0, abstain"

    direction = "bullish (fast SMA above slow SMA)" if spread > 0 else "bearish (fast SMA below slow SMA)"
    return f"T11 inside bar: today's range inside yesterday's, trend spread {spread:+.4f} ({direction})"
