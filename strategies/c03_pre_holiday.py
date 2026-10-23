"""C03: pre-holiday effect (`cards/C03.yml`, `state/queue.md` port lane).

Ariel (1990, JF): abnormally high returns on trading days immediately
preceding a market holiday. `cards/catalog.csv`'s own reading: "Bullish
tilt on the trading day before an NSE holiday." Neither this module nor
the catalog assumes the claim true (SPEC.md section 5) - `cards/C03.yml`'s
`status` moves to `confirmed`/`refuted` once a real train replay's edge is
in.

Unlike C01/C02 (`state/engine-issues.md`'s "score(history) never carries
the pick date" entry), this card does not need a same-day-identity proxy:
whether the pick date itself is pre-holiday is an exact, deterministic
calendar fact knowable well in advance of any trading (NSE publishes its
holiday circular every December for the following year), not market data
- so it can be computed exactly from `history`'s own last visible date
("yesterday") plus `config/nse_holidays.txt`, using
`picks.calendar.next_trading_session` the same way `picks/run.py` already
uses it for B9's own next-session arithmetic. This module answers the
literal catalog question (is *today*, the actual pick date, pre-holiday),
not an approximation of it.

`config/nse_holidays.txt` was extended 2026-10-23 (research lane) from
2026-only to cover the train split (2015-2020) specifically to unblock
this card - see that file's own header and `state/engine-issues.md`'s C03
entry for sourcing and confidence notes per year.

A trading day `d` is "pre-holiday" if the next calendar weekday (Mon-Fri)
strictly after `d` - regardless of whether that weekday would otherwise
be a trading day - is itself in the holiday file. This picks up both the
ordinary case (Thursday before a Friday holiday) and the catalog's classic
case (Friday before a Monday holiday), and deliberately ignores plain
weekends on their own (a Friday followed only by an ordinary Saturday is
not "pre-holiday").

Selective, like T03: this card has no stated view on non-pre-holiday days,
so it abstains on those rather than inventing a claim the catalog never
makes (SPEC.md section 3's coverage reporting applies once scoring is
wired). Market-wide, not per-symbol (the catalog gives no per-symbol
differentiation).
"""

from __future__ import annotations

import pandas as pd

from picks.calendar import load_holidays, next_trading_session

MIN_OCCURRENCES = 20


def _next_weekday(d: pd.Timestamp) -> pd.Timestamp:
    """The next calendar weekday (Mon-Fri) strictly after `d`, ignoring
    whether it is itself an NSE holiday - this is only the date whose
    holiday-membership decides `d`'s own pre-holiday status, not a claim
    that it is a trading day."""
    nxt = d + pd.Timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += pd.Timedelta(days=1)
    return nxt


def _is_pre_holiday(d: pd.Timestamp, holidays: set[str]) -> bool:
    return _next_weekday(d).date().isoformat() in holidays


def _pooled_daily_return(history: pd.DataFrame) -> pd.Series:
    """Mean open-to-close return across the F&O universe, per trading date
    (same shape as `strategies.c01_day_of_week._pooled_daily_return`,
    copied not imported so this card stays standalone)."""
    universe = history[history["has_future"]] if "has_future" in history.columns else history
    universe = universe[universe["open"] != 0]
    if universe.empty:
        return pd.Series(dtype=float)
    per_row_return = (universe["close"] - universe["open"]) / universe["open"]
    return per_row_return.groupby(universe["date"]).mean().sort_index()


def _pre_holiday_base_rate(
    daily_return: pd.Series, holidays: set[str]
) -> tuple[float, int] | None:
    """`(mean_return, n_days)` over every historical trading date already
    in `history` that is itself pre-holiday, keyed by *its own*
    open-to-close return (not the next day's, unlike C01/C02 - this card's
    claim is about the pre-holiday day's own return), or `None` if fewer
    than `MIN_OCCURRENCES`. Every date here is already realised (inside
    `history`, B4's truncation), so nothing leaks the pick date."""
    flagged = [
        float(ret)
        for date, ret in daily_return.items()
        if _is_pre_holiday(pd.Timestamp(date), holidays)
    ]
    if len(flagged) < MIN_OCCURRENCES:
        return None
    return sum(flagged) / len(flagged), len(flagged)


def _today_and_holidays(
    history: pd.DataFrame, holidays: set[str] | None
) -> tuple[pd.Timestamp, set[str]] | None:
    """`(today, holidays)` where `today` is the pick date, computed exactly
    as the next trading session after `history`'s own last visible date -
    or `None` if `history` is empty."""
    if history.empty:
        return None
    calendar_dates = pd.to_datetime(pd.Series(history["date"].unique())).sort_values()
    if calendar_dates.empty:
        return None
    yesterday = calendar_dates.iloc[-1]
    resolved_holidays = load_holidays() if holidays is None else holidays
    today = pd.Timestamp(
        next_trading_session(yesterday.date().isoformat(), resolved_holidays)
    )
    return today, resolved_holidays


def _bias_for_history(
    history: pd.DataFrame, holidays: set[str] | None = None
) -> float | None:
    """The pre-holiday-bucket mean return to apply to today's pick, or
    `None` to abstain (today isn't pre-holiday, or too little history)."""
    resolved = _today_and_holidays(history, holidays)
    if resolved is None:
        return None
    today, holiday_set = resolved
    if not _is_pre_holiday(today, holiday_set):
        return None
    daily_return = _pooled_daily_return(history)
    if len(daily_return) < 2:
        return None
    base_rate = _pre_holiday_base_rate(daily_return, holiday_set)
    if base_rate is None:
        return None
    mean_return, _ = base_rate
    return mean_return


def score(history: pd.DataFrame, holidays: set[str] | None = None) -> pd.Series:
    """The pre-holiday-bucket bias for every symbol with any `has_future`
    row in `history`, if today (the pick date, inferred exactly via
    `picks.calendar.next_trading_session`) is itself pre-holiday and the
    bucket has at least `MIN_OCCURRENCES` historical days behind it;
    otherwise an empty Series (abstain). `holidays` is test-only dependency
    injection - the engine always calls this with the default, which reads
    the real committed `config/nse_holidays.txt`."""
    if history.empty:
        return pd.Series(dtype=float)

    bias = _bias_for_history(history, holidays)
    if bias is None or bias == 0:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        eligible = history.loc[history["has_future"], "symbol"].unique()
    else:
        eligible = history["symbol"].unique()
    if len(eligible) == 0:
        return pd.Series(dtype=float)
    return pd.Series({symbol: bias for symbol in eligible}, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str, holidays: set[str] | None = None) -> str:
    resolved = _today_and_holidays(history, holidays)
    if resolved is None:
        return "C03 pre-holiday effect: no history, abstain"
    today, holiday_set = resolved
    if not _is_pre_holiday(today, holiday_set):
        return f"C03 pre-holiday effect: {today.date().isoformat()} is not pre-holiday, abstain"

    daily_return = _pooled_daily_return(history)
    if len(daily_return) < 2:
        return "C03 pre-holiday effect: insufficient market-wide history, abstain"
    base_rate = _pre_holiday_base_rate(daily_return, holiday_set)
    if base_rate is None:
        return (
            f"C03 pre-holiday effect: fewer than {MIN_OCCURRENCES} historical "
            "pre-holiday days, abstain"
        )
    mean_return, n = base_rate
    if mean_return == 0:
        return "C03 pre-holiday effect: pre-holiday bucket mean is exactly zero, abstain"
    direction = "bullish" if mean_return > 0 else "bearish"
    return (
        f"C03 pre-holiday effect (Ariel 1990, {today.date().isoformat()} is "
        f"pre-holiday): pre-holiday bucket mean open-to-close return "
        f"{mean_return:+.5f} over {n} days -> market-wide {direction} tilt"
    )
