"""Causality/purity check for `strategies/c04_expiry_week_day.py` (SPEC.md
section 5: "audit.py causality check" is required for every strategy).

Market-wide, like C01/C02, so there is nothing cross-symbol to leak (every
eligible symbol gets the identical score) - A01-A09's "one symbol gets an
extra row" audit shape doesn't apply. The risk specific to this module is
that it reads `history`'s own `expiry_futstk`/`date` columns, not any
wall-clock date or hardcoded expiry schedule. Unlike C01's weekday proxy
(which only needs a date's own weekday, invariant under any whole-years
shift that preserves Mon-Fri spacing), C04's proxy compares two *absolute*
dates (`date` and `expiry_futstk`) against each other, so the right
invariance check is different: shifting every date in `history` - both
`date` and `expiry_futstk` - by the exact same number of calendar days
must leave every score unchanged, since only the *relationship* between
the two columns should ever matter, never their absolute values. A pure
day-count shift (not a year/leap-sensitive `DateOffset`) is used so this
doesn't depend on the ISO calendar's own boundary quirks.

1. Build a synthetic market with a deterministic expiry-week bias (pooled
   open-to-close return is exactly `bias` on every trading day right after
   a day whose own near-month contract expires in the same ISO week as
   that day, 0 otherwise), over enough months to clear `MIN_OCCURRENCES`.
2. Shift every date (both `date` and `expiry_futstk`) by a fixed number of
   calendar days and check the predicted bias is unchanged.
3. Checks pure determinism: calling `score` twice on the identical
   `history` gives the identical result.
"""

from __future__ import annotations

import calendar as _calendar

import pandas as pd

from strategies import c04_expiry_week_day as c04
from strategies.c04_common import mode_expiry_by_date, same_iso_week


def _last_thursday(year: int, month: int) -> pd.Timestamp:
    last_day = _calendar.monthrange(year, month)[1]
    end = pd.Timestamp(year=year, month=month, day=last_day)
    return end - pd.Timedelta(days=(end.weekday() - 3) % 7)


def _near_month_expiry(date: pd.Timestamp) -> pd.Timestamp:
    """The near-month FUTSTK expiry active on `date`: that month's last
    Thursday, rolled to next month's once `date` is past it."""
    expiry = _last_thursday(date.year, date.month)
    if date <= expiry:
        return expiry
    month, year = date.month + 1, date.year
    if month == 13:
        month, year = 1, year + 1
    return _last_thursday(year, month)


def _biased_market(
    n_months: int = 14, bias: float = 0.02, symbols: tuple[str, ...] = ("AAA", "BBB", "CCC")
) -> pd.DataFrame:
    """Mon-Fri trading days over `n_months` months; the pooled open-to-close
    return is exactly `bias` on every day right after a day whose own
    near-month expiry fell in that day's own ISO week, 0 otherwise - built
    deterministically so the base rate this produces is exact, not noisy.
    Every symbol in `symbols` gets the identical move each day (pooling
    across identical series trivially recovers the same value)."""
    dates = pd.bdate_range("2015-01-05", periods=n_months * 21)
    rows = []
    prev_in_expiry_week = None
    for date in dates:
        expiry = _near_month_expiry(date)
        iso_d, iso_e = date.isocalendar(), expiry.isocalendar()
        in_expiry_week = (iso_d.year, iso_d.week) == (iso_e.year, iso_e.week)
        day_return = bias if prev_in_expiry_week else 0.0
        prev_in_expiry_week = in_expiry_week
        open_price = 100.0
        close_price = open_price * (1.0 + day_return)
        for symbol in symbols:
            rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "symbol": symbol,
                "open": open_price,
                "high": max(open_price, close_price),
                "low": min(open_price, close_price),
                "close": close_price,
                "prevclose": open_price,
                "volume": 1_000_000.0,
                "has_future": True,
                "oi_futstk": 1_000.0,
                "oi_chg_futstk": 0.0,
                "expiry_futstk": expiry.strftime("%Y-%m-%d"),
            })
    return pd.DataFrame(rows)


def _shifted_days(history: pd.DataFrame, days: int) -> pd.DataFrame:
    """Same rows, `date` and `expiry_futstk` both moved `days` calendar days
    later - `days` must be a whole multiple of 7 so every date keeps both
    its weekday (preserving the Mon-Fri trading-calendar shape) and its
    position within the 7-day ISO-week cycle (so "same ISO week" between
    `date` and `expiry_futstk` reads identically before and after the
    shift); a non-multiple-of-7 shift would move ISO week boundaries
    relative to the trading days and could flip some flags even though
    `expiry_futstk - date` is unchanged."""
    assert days % 7 == 0, "shift must be a whole number of weeks to preserve ISO-week alignment"
    shifted = history.copy()
    for col in ("date", "expiry_futstk"):
        shifted[col] = (pd.to_datetime(shifted[col]) + pd.Timedelta(days=days)).dt.strftime("%Y-%m-%d")
    return shifted


def check_proxy_reads_from_history_not_wall_clock(n_months: int = 14, bias: float = 0.02) -> dict:
    """The predicted bias must survive a pure day-count shift of every date
    in `history`, since the module is only supposed to read the
    relationship between `date` and `expiry_futstk`, never an absolute
    date."""
    base = _biased_market(n_months, bias)
    shift_days = 522 * 7  # ~10 years, a whole number of weeks (see _shifted_days)
    shifted = _shifted_days(base, days=shift_days)

    base_cutoff = _cutoff_with_enough_history(base)
    shifted_cutoff = _shifted_days(base_cutoff, days=shift_days)

    bias_base = c04._bias_for_history(base_cutoff)
    bias_shifted = c04._bias_for_history(shifted_cutoff)
    bias_base_repeat = c04._bias_for_history(base_cutoff)

    matches_expectation = bias_base is not None and abs(bias_base - bias) < 1e-9
    shift_invariant = bias_base is not None and bias_shifted is not None and abs(bias_base - bias_shifted) < 1e-12
    deterministic = bias_base == bias_base_repeat

    passed = matches_expectation and shift_invariant and deterministic
    return {
        "passed": passed,
        "bias_base": bias_base,
        "bias_shifted": bias_shifted,
        "bias_base_repeat": bias_base_repeat,
        "matches_expectation": matches_expectation,
        "shift_invariant": shift_invariant,
        "deterministic": deterministic,
    }


def _cutoff_with_enough_history(history: pd.DataFrame) -> pd.DataFrame:
    """Trim `history` to end right after an expiry-week day, with at least
    `MIN_OCCURRENCES` such pairs already behind it - the one history slice
    this audit actually scores, so the predicted bias is the bucket's known
    value, not `None` for lack of occurrences."""
    daily_return = c04._pooled_daily_return(history)
    modal_expiry = mode_expiry_by_date(history)
    hits = 0
    for date in daily_return.index:
        expiry = modal_expiry.get(date)
        if expiry is not None and not pd.isna(expiry) and same_iso_week(date, expiry):
            hits += 1
            if hits > c04.MIN_OCCURRENCES:
                cutoff = date.strftime("%Y-%m-%d")
                return history[history["date"] <= cutoff].copy()
    raise AssertionError("synthetic market never accumulated enough expiry-week pairs")


if __name__ == "__main__":
    result = check_proxy_reads_from_history_not_wall_clock()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
