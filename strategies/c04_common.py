"""Shared helpers for `strategies/c04_expiry_week_day.py` and
`strategies/c04_expiry_week_week.py` (`cards/C04.yml`, `state/queue.md`
port lane). Not a strategy itself - no `score`/`rules_fired`, so nothing
calls this module directly as `strategies.c04_common`; it exists only so
the two C04 horizon variants (needed because `engine.replay.pick_date`
never tells `score(history)` which horizon it is running for, so a
calendar-anchored rule like this needs one module per horizon - see each
variant's own docstring) share one reading of "when does the near-month
future expire" instead of duplicating it.

`cards/D01.yml`'s dataset extension (`scripts/build_dataset.py`, this
run) carries each `has_future` row's own near-month contract expiry date
as `expiry_futstk` (ISO string) - the exchange's own published schedule,
not a derived guess, and not the future-information problem
`state/engine-issues.md`'s C03/C04 entry originally worried about (C03
needs tomorrow's *holiday* status, which truly isn't in any amount of
past data; C04 only needs the *already-scheduled* expiry date of the
contract active on a day already inside `history`, which the FO bhavcopy
already states on that day).
"""

from __future__ import annotations

import pandas as pd


def mode_expiry_by_date(history: pd.DataFrame) -> pd.Series:
    """Per trading date (Timestamp index), the near-month FUTSTK expiry date
    (Timestamp) most `has_future` rows carry that date.

    Taking the mode rather than any single row's value is a robustness
    choice, not a correctness requirement: in practice every `has_future`
    row on a given date should carry the identical near-month expiry (all
    NSE stock futures roll on the same monthly cycle), but the mode means a
    stray data quirk in one symbol's row can never move the market-wide
    flag this is used to build. A date with no `has_future` rows, or no
    `expiry_futstk` data for any of them, is absent from the result.
    """
    if "has_future" not in history.columns or "expiry_futstk" not in history.columns:
        return pd.Series(dtype="datetime64[ns]")
    universe = history.loc[
        history["has_future"] & history["expiry_futstk"].notna(), ["date", "expiry_futstk"]
    ].copy()
    if universe.empty:
        return pd.Series(dtype="datetime64[ns]")
    universe["date"] = pd.to_datetime(universe["date"])
    universe["expiry_futstk"] = pd.to_datetime(universe["expiry_futstk"])
    modal = universe.groupby("date")["expiry_futstk"].agg(lambda s: s.mode().iloc[0])
    return modal.sort_index()


def trading_calendar(history: pd.DataFrame) -> pd.DatetimeIndex:
    """Every distinct trading date present in `history`, sorted ascending."""
    if history.empty:
        return pd.DatetimeIndex([])
    dates = pd.to_datetime(pd.Series(history["date"].unique()))
    return pd.DatetimeIndex(sorted(dates))


def same_iso_week(a: pd.Timestamp, b: pd.Timestamp) -> bool:
    """True if `a` and `b` fall in the same ISO (year, week)."""
    iso_a, iso_b = a.isocalendar(), b.isocalendar()
    return (iso_a.year, iso_a.week) == (iso_b.year, iso_b.week)
