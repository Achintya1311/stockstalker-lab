"""Split/bonus adjustment factors, per SPEC.md section 2.

"Adjustments: split and bonus adjustment factors come from the bhavcopy's
PREVCLOSE (the exchange's adjusted base price) divided by the previous
day's CLOSE. Indicators use adjusted series. Day open-to-close moves need
no adjustment."

On an ordinary day, NSE's PREVCLOSE for a symbol is bit-identical to that
symbol's CLOSE on its previous trading day. On a split, bonus, or other
corporate action that changes the share count, the exchange rebases
PREVCLOSE to the new scale, so PREVCLOSE(t) / CLOSE(t-1) departs from 1.0
by the corporate action's ratio (e.g. a 1:1 bonus halves it to ~0.5; a 2:1
split thirds it to ~0.333).

This module turns that per-day ratio into a per-symbol, per-date
*cumulative* factor such that:

    adjusted_price(d) = raw_price(d) * cum_factor(d)

makes the whole historical series comparable on today's share-count scale:
cum_factor is 1.0 on the most recent date for each symbol and only departs
from 1.0 before a corporate action, by the cumulative product of every
action's ratio that happened after that date. It is a backward-looking
(reverse) cumulative product, not a forward one, precisely so that a
replay slice truncated at date d already carries the correct scale for
every day up to and including d without needing to know about actions
that haven't happened yet.

Volumes are never rescaled: SPEC only asks for price-series adjustment.
"""

from __future__ import annotations

import pandas as pd

# A ratio within this tolerance of 1.0 is ordinary PREVCLOSE/CLOSE rounding
# noise, not a corporate action. NSE prices carry 2 decimal places, so on a
# low-priced stock a one-paisa rounding difference can be a percent or more;
# 0.5% comfortably covers that while still catching the smallest splits and
# bonuses, which move price by at least 1:9 (10%).
NOISE_TOLERANCE = 0.005

PRICE_FIELDS = ["open", "high", "low", "close"]


def daily_factor(prevclose: pd.Series, prior_close: pd.Series) -> pd.Series:
    """Per-row day-over-day ratio, snapped to 1.0 within NOISE_TOLERANCE.

    `prior_close` must already be each row's same-symbol previous trading
    day's close (e.g. via a groupby("symbol")["close"].shift(1)); this
    function does no grouping itself so it stays a plain, testable
    elementwise op.
    """
    ratio = prevclose / prior_close
    return ratio.where((ratio - 1.0).abs() > NOISE_TOLERANCE, other=1.0)


def compute_adjustment_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Add `adj_factor` and adjusted price columns, per symbol, in date order.

    `df` must have columns date, symbol, open, high, low, close, prevclose,
    with at most one row per (date, symbol) and `date` sortable as strings
    (ISO `YYYY-MM-DD`, as build_dataset.py produces) or as datetimes.
    Returns a copy; input is not mutated.

    The dataset only keeps SERIES == "EQ" rows (SPEC.md section 2), so a
    symbol that spends one or more trading days in another series (most
    commonly "BE", NSE's trade-to-trade surveillance series) has no row
    here for those days: `groupby("symbol")["close"].shift(1)` then skips
    straight past the gap to that symbol's last *EQ* close, which can be
    weeks stale, while `prevclose` on the row after the gap is the
    exchange's real, continuous previous-day close (NSE does not reset
    PREVCLOSE for a series change). The mismatch between a stale prior
    close and a correct PREVCLOSE then looks exactly like a corporate
    action's rebasing, even though nothing happened to the share count.
    Detected directly against real NSE data: AUTOIND traded BE on
    2020-08-17 (CLOSE 37.40, filtered out) and EQ again on 2020-08-18
    (PREVCLOSE 37.40, correct), but this dataset's previous EQ row for
    AUTOIND was stale, producing a spurious ~2.68x "action" ratio.
    Such a gap is detected per row by comparing each symbol's previous
    *dataset* row's date against the whole market's actual previous
    trading day; a mismatch means a gap, so the ratio is treated the same
    as a symbol's first row: unknowable, hence unadjusted (factor 1.0)
    rather than a detected event.
    """
    out = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    prior_close = out.groupby("symbol")["close"].shift(1)
    prior_date = out.groupby("symbol")["date"].shift(1)

    all_dates = pd.Index(sorted(df["date"].unique()))
    pos = all_dates.get_indexer(out["date"])
    expected_prior_date = pd.Series(
        [all_dates[p - 1] if p > 0 else None for p in pos], index=out.index
    )
    gap = prior_date.notna() & (prior_date != expected_prior_date)

    ratio = daily_factor(out["prevclose"], prior_close)
    # First row of each symbol has no prior close: no action is knowable,
    # so treat it as unadjusted (factor 1.0) rather than NaN. Same for a
    # row after a series gap (see docstring above).
    ratio = ratio.where(prior_close.notna(), other=1.0)
    ratio = ratio.where(~gap, other=1.0)

    # cum_factor(d) = product of ratio(e) for every e > d, per symbol.
    # That is a reverse cumulative product of `ratio` shifted back one row
    # (ratio[i] is the action *arriving at* row i, i.e. *after* row i-1),
    # computed from the last row of each symbol backward.
    reversed_ratio = ratio[::-1]
    cum = reversed_ratio.groupby(out["symbol"].iloc[::-1]).cumprod()[::-1]
    # cum currently includes each row's own ratio; dividing it back out
    # leaves, at row i, the product of strictly-later ratios only.
    cum_factor = cum / ratio

    out["adj_factor"] = cum_factor
    for field in PRICE_FIELDS:
        out[f"adj_{field}"] = out[field] * cum_factor
    out["action_ratio"] = ratio
    out["series_gap"] = gap
    return out


def detect_corporate_actions(df: pd.DataFrame) -> pd.DataFrame:
    """Rows where `compute_adjustment_factors` found a non-noise ratio.

    Each row is one candidate split/bonus/rights event: the date it first
    shows up in PREVCLOSE, the symbol, and the ratio (new scale / old
    scale: 0.5 for a 2:1 split or a 1:1 bonus, 0.2 for a 5:1 split, etc).
    This is the detector half of "check against known splits and bonuses"
    (SPEC.md section 2) — it finds candidates in the data; confirming each
    one against a real, independently-sourced list of NSE corporate
    actions (not against memory) is a separate step, run once the full
    backfill is in.
    """
    out = compute_adjustment_factors(df)
    events = out[out["action_ratio"] != 1.0]
    return events[["date", "symbol", "action_ratio"]].reset_index(drop=True)
