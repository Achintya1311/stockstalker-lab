"""Causality/purity check for `strategies/c04_expiry_week_week.py` (SPEC.md
section 5: "audit.py causality check" is required for every strategy). Same
reasoning as `strategies/c04_expiry_week_day_audit.py` - see its docstring
for why a pure, whole-number-of-weeks day-count shift of both `date` and
`expiry_futstk` is the right invariance to check here, rather than C01's
weekday-only shift or a `DateOffset(years=...)` shift.

1. Build a synthetic market with a deterministic expiry-week bias (pooled
   week open-to-close return is exactly `bias` on every ISO week whose
   preceding Friday's own near-month contract expired in the week right
   after that Friday, 0 otherwise), over enough months to clear
   `MIN_OCCURRENCES`.
2. Shift every date (both `date` and `expiry_futstk`) by a whole number of
   weeks and check the predicted bias is unchanged.
3. Checks pure determinism: calling `score` twice on the identical
   `history` gives the identical result.
"""

from __future__ import annotations

import calendar as _calendar

import pandas as pd

from strategies import c04_expiry_week_week as c04
from strategies.c04_common import mode_expiry_by_date, same_iso_week, trading_calendar


def _last_thursday(year: int, month: int) -> pd.Timestamp:
    last_day = _calendar.monthrange(year, month)[1]
    end = pd.Timestamp(year=year, month=month, day=last_day)
    return end - pd.Timedelta(days=(end.weekday() - 3) % 7)


def _near_month_expiry(date: pd.Timestamp) -> pd.Timestamp:
    expiry = _last_thursday(date.year, date.month)
    if date <= expiry:
        return expiry
    month, year = date.month + 1, date.year
    if month == 13:
        month, year = 1, year + 1
    return _last_thursday(year, month)


def _biased_market(
    n_months: int = 48, bias: float = 0.03, symbols: tuple[str, ...] = ("AAA", "BBB", "CCC")
) -> pd.DataFrame:
    """Mon-Fri trading days over `n_months` months; each ISO week's pooled
    open-to-close return is exactly `bias` if the trading day right before
    that week's own first date had a near-month contract expiring in the
    week right after it (the live proxy's own +7-day condition), 0
    otherwise - spread evenly across that week's days so the week-level
    return comes out exact. Every symbol in `symbols` gets the identical
    move each day (pooling across identical series trivially recovers the
    same value)."""
    dates = pd.bdate_range("2015-01-05", periods=n_months * 21)
    expiry_by_date = {date: _near_month_expiry(date) for date in dates}

    groups: dict[tuple[int, int], list[pd.Timestamp]] = {}
    for date in dates:
        iso = date.isocalendar()
        groups.setdefault((iso.year, iso.week), []).append(date)
    iso_keys = list(groups.keys())
    calendar_dates = list(dates)
    position = {date: i for i, date in enumerate(calendar_dates)}

    week_return: dict[tuple[int, int], float] = {}
    for iso_key in iso_keys:
        first_day = groups[iso_key][0]
        pos = position[first_day]
        if pos == 0:
            week_return[iso_key] = 0.0
            continue
        preceding = calendar_dates[pos - 1]
        expiry = expiry_by_date[preceding]
        marker = preceding + pd.Timedelta(days=7)
        flag = (expiry.isocalendar().year, expiry.isocalendar().week) == (
            marker.isocalendar().year, marker.isocalendar().week,
        )
        week_return[iso_key] = bias if flag else 0.0

    rows = []
    level = 100.0
    for iso_key in iso_keys:
        days = groups[iso_key]
        growth = (1.0 + week_return[iso_key]) ** (1.0 / len(days))
        for date in days:
            open_price = level
            close_price = level * growth
            level = close_price
            expiry = expiry_by_date[date]
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


def _shifted_weeks(history: pd.DataFrame, weeks: int) -> pd.DataFrame:
    """Same rows, `date` and `expiry_futstk` both moved `weeks` whole weeks
    later - preserves weekday, ISO-week alignment and the gap between the
    two columns all at once (see `c04_expiry_week_day_audit`'s matching
    helper for the full reasoning)."""
    shifted = history.copy()
    offset = pd.Timedelta(days=7 * weeks)
    for col in ("date", "expiry_futstk"):
        shifted[col] = (pd.to_datetime(shifted[col]) + offset).dt.strftime("%Y-%m-%d")
    return shifted


def _cutoff_with_enough_history(history: pd.DataFrame) -> pd.DataFrame:
    """Trim `history` to end right after an expiry-predicting trading day,
    with more than `MIN_OCCURRENCES` such days already behind it.

    A single O(n) walk over the trading calendar, counting a hit at the
    last trading day of each ISO week whenever that day's own +7-day proxy
    matches - the exact condition `_expiry_week_base_rates` buckets as
    `True` - rather than recomputing the whole base-rate table from
    scratch for every candidate day (which made this quadratic in the
    number of trading days and, for a many-month synthetic market, visibly
    slow)."""
    calendar = trading_calendar(history)
    modal_expiry = mode_expiry_by_date(history)
    hits = 0
    for i, date in enumerate(calendar):
        is_last_of_its_week = i + 1 == len(calendar) or not same_iso_week(calendar[i + 1], date)
        if not is_last_of_its_week:
            continue
        expiry = modal_expiry.get(date)
        if expiry is None or pd.isna(expiry):
            continue
        marker = date + pd.Timedelta(days=7)
        if same_iso_week(expiry, marker):
            hits += 1
            if hits > c04.MIN_OCCURRENCES:
                return history[history["date"] <= date.strftime("%Y-%m-%d")].copy()
    raise AssertionError("synthetic market never accumulated enough expiry-week weeks")


def check_proxy_reads_from_history_not_wall_clock(n_months: int = 48, bias: float = 0.03) -> dict:
    """The predicted bias must survive a pure whole-weeks shift of every
    date in `history`, since the module is only supposed to read the
    relationship between `date` and `expiry_futstk`, never an absolute
    date."""
    base = _biased_market(n_months, bias)
    base_cutoff = _cutoff_with_enough_history(base)
    shifted_cutoff = _shifted_weeks(base_cutoff, weeks=522)  # ~10 years

    bias_base = c04._bias_for_history(base_cutoff)
    bias_shifted = c04._bias_for_history(shifted_cutoff)
    bias_base_repeat = c04._bias_for_history(base_cutoff)

    matches_expectation = bias_base is not None and abs(bias_base - bias) < 1e-9
    shift_invariant = bias_base is not None and bias_shifted is not None and abs(bias_base - bias_shifted) < 1e-9
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


if __name__ == "__main__":
    result = check_proxy_reads_from_history_not_wall_clock()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
