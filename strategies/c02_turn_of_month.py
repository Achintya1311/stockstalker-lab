"""C02: turn-of-month effect (`cards/C02.yml`, `state/queue.md` port lane).

Ariel (1987, JFE): returns historically concentrated around the turn of the
month (`cards/catalog.csv`'s own reading: "Bullish tilt in the last day and
first 3 days of a month", `default_params`: "window -1..+3"). Neither this
module nor the catalog assumes the claim true (SPEC.md section 5) -
`cards/C02.yml`'s `status` moves to `confirmed`/`refuted` once a real train
replay's edge is in.

This hits the same wall `cards/C01.yml` already documents in full: a
calendar-effect rule needs the pick date's own calendar position, but
`engine.replay.pick_date` never passes a date into `strategy.score()`
(SPEC.md section 5's interface is `score(history) -> pd.Series`, nothing
else), and `history` is truncated strictly before the pick date (B4), so
nothing here ever carries the upcoming pick week's own dates. This is a
week-horizon card (`engine.run_queue._dates_for_horizon`: one pick per ISO
week, scored at Monday's open with `history` truncated through the prior
Friday's close), so the proxy is: whether `history`'s own last visible
trading day (the day immediately before the upcoming pick week starts) is
itself a turn-of-month day stands in for "the upcoming week is close to a
turn-of-month window". Both the historical base rates and the live lookup
key on that identical quantity - the trading day immediately preceding a
week's first date - so this is self-consistent (same construction C01 uses
for its yesterday's-weekday proxy, applied to turn-of-month membership
instead of weekday identity).

"Turn-of-month" membership is computed purely from the trading days that
actually appear in `history` (never an external holiday calendar, never
wall-clock time): a date is turn-of-month if it is the *last* trading day
of its calendar month, or one of the *first 3* trading days of its
calendar month - `TOTM_LAST_N`/`TOTM_FIRST_N` below, matching the
catalog's "window -1..+3". The historical base rates this module builds
from past weeks use a *trading-day* week (non-overlapping runs of 5
consecutive trading days counted from `history`'s own earliest visible
date), not a true ISO calendar week - see `_pooled_week_returns` for why:
it keeps the base-rate construction a pure function of which trading days
`history` contains, with no dependency on any date's actual weekday.

Market-wide, not per-symbol: every eligible symbol gets the same score on
a given pick date (the catalog gives no per-symbol differentiation).
"""

from __future__ import annotations

import pandas as pd

MIN_OCCURRENCES = 20
TOTM_FIRST_N = 3
TOTM_LAST_N = 1


def _trading_calendar(history: pd.DataFrame) -> pd.DatetimeIndex:
    """Every distinct trading date present in `history`, sorted ascending."""
    if history.empty:
        return pd.DatetimeIndex([])
    dates = pd.to_datetime(pd.Series(history["date"].unique()))
    return pd.DatetimeIndex(sorted(dates))


def _is_totm(calendar: pd.DatetimeIndex) -> pd.Series:
    """Boolean per calendar date: true if it is one of the last `TOTM_LAST_N`
    trading days of its calendar month, or one of the first `TOTM_FIRST_N`
    trading days of its calendar month - ranked among the trading days
    `calendar` itself contains, not against any external holiday list."""
    if len(calendar) == 0:
        return pd.Series(dtype=bool)
    month = pd.Series(calendar).dt.to_period("M")
    rank_from_start = month.groupby(month).cumcount()
    rank_from_end = month.groupby(month).cumcount(ascending=False)
    flags = (rank_from_end == 0) | (rank_from_start < TOTM_FIRST_N)
    return pd.Series(flags.to_numpy(), index=calendar)


def _pooled_week_returns(history: pd.DataFrame) -> pd.Series:
    """One pooled, market-wide return per non-overlapping run of 5
    consecutive trading days in `history`'s own calendar (a *trading-day*
    week, counted from `history`'s earliest visible date forward - not a
    true ISO calendar week). Indexed by the chunk's own first trading
    date.

    This deliberately does not group by `.isocalendar()`: a holiday
    anywhere in the chunk would shift which weekday a chunk's first/last
    day falls on, and - more importantly for this module's own causality
    audit - true calendar-week grouping depends on each date's actual
    weekday, which a whole-year date shift does not reliably preserve
    across a multi-year span once a 29 February is crossed (leap years
    don't add a multiple of 7 days). Counting fixed-size chunks of 5
    trading days by *position* instead keeps this, like `_is_totm`,  a
    pure function of which trading days are present in `history` and in
    what order - immune to any date relabelling, consistent with this
    module's own causality audit (`strategies/c02_turn_of_month_audit.py`).

    For each `has_future`-eligible symbol with a row on both a chunk's
    first and last visible trading day, that chunk's return is
    close(last day) / open(first day) - 1; the pooled value is the mean
    across such symbols (same "market-wide, not cross-sectional"
    convention `c01_day_of_week._pooled_daily_return` uses)."""
    universe = history[history["has_future"]] if "has_future" in history.columns else history
    if universe.empty:
        return pd.Series(dtype=float)
    universe = universe.copy()
    universe["date"] = pd.to_datetime(universe["date"])

    calendar = _trading_calendar(history)
    results: dict[pd.Timestamp, float] = {}
    for start in range(0, len(calendar) - 4, 5):
        chunk = calendar[start : start + 5]
        first_day, last_day = chunk[0], chunk[-1]
        first = universe.loc[universe["date"] == first_day].set_index("symbol")["open"]
        last = universe.loc[universe["date"] == last_day].set_index("symbol")["close"]
        common = first.index.intersection(last.index)
        common = common[first.loc[common] != 0]
        if len(common) == 0:
            continue
        week_return = ((last.loc[common] - first.loc[common]) / first.loc[common]).mean()
        results[pd.Timestamp(first_day)] = float(week_return)
    return pd.Series(results, dtype=float).sort_index()


def _totm_base_rates(history: pd.DataFrame) -> dict[bool, tuple[float, int]]:
    """`{is_totm_of_preceding_trading_day: (mean_week_return, n_weeks)}`.

    Every week this buckets is fully inside `history` (both its first and
    last visible day, B4's truncation), and the key it buckets on - the
    trading day immediately before that week's own first date - is also
    always inside `history`, since it is by definition the day right
    before a week that is itself inside `history`. Nothing here can leak
    the pick date: every pair is fully realised already."""
    calendar = _trading_calendar(history)
    if len(calendar) < 2:
        return {}
    totm_flags = _is_totm(calendar)
    position = {date: i for i, date in enumerate(calendar)}

    week_returns = _pooled_week_returns(history)
    buckets: dict[bool, list[float]] = {True: [], False: []}
    for week_start, week_return in week_returns.items():
        pos = position.get(week_start)
        if pos is None or pos == 0:
            continue
        preceding_date = calendar[pos - 1]
        flag = bool(totm_flags.loc[preceding_date])
        buckets[flag].append(week_return)
    return {flag: (sum(v) / len(v), len(v)) for flag, v in buckets.items() if v}


def _bias_for_history(history: pd.DataFrame) -> float | None:
    """The turn-of-month-bucket mean week return to apply to the upcoming
    pick week, or `None` to abstain (too little history, or the bucket
    keyed by whether `history`'s own last visible day is turn-of-month has
    fewer than `MIN_OCCURRENCES` historical weeks)."""
    calendar = _trading_calendar(history)
    if len(calendar) < 2:
        return None
    totm_flags = _is_totm(calendar)
    base_rates = _totm_base_rates(history)
    proxy_flag = bool(totm_flags.iloc[-1])
    if proxy_flag not in base_rates:
        return None
    mean_return, n = base_rates[proxy_flag]
    if n < MIN_OCCURRENCES:
        return None
    return mean_return


def score(history: pd.DataFrame) -> pd.Series:
    """The same turn-of-month-bucket bias for every symbol with any
    `has_future` row in `history`, or an empty Series if the bucket keyed
    by whether yesterday was turn-of-month isn't trusted yet (too few
    historical weeks)."""
    if history.empty:
        return pd.Series(dtype=float)

    bias = _bias_for_history(history)
    if bias is None or bias == 0:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        eligible = history.loc[history["has_future"], "symbol"].unique()
    else:
        eligible = history["symbol"].unique()
    if len(eligible) == 0:
        return pd.Series(dtype=float)
    return pd.Series({symbol: bias for symbol in eligible}, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    calendar = _trading_calendar(history)
    if len(calendar) < 2:
        return "C02 turn-of-month effect: insufficient market-wide history, abstain"

    totm_flags = _is_totm(calendar)
    base_rates = _totm_base_rates(history)
    proxy_flag = bool(totm_flags.iloc[-1])
    proxy_label = "turn-of-month" if proxy_flag else "mid-month"
    if proxy_flag not in base_rates:
        return (
            f"C02 turn-of-month effect: no historical weeks keyed by "
            f"yesterday being {proxy_label}, abstain"
        )
    mean_return, n = base_rates[proxy_flag]
    if n < MIN_OCCURRENCES:
        return (
            f"C02 turn-of-month effect: only {n} historical weeks keyed by "
            f"yesterday being {proxy_label}, below {MIN_OCCURRENCES}, abstain"
        )
    if mean_return == 0:
        return f"C02 turn-of-month effect: {proxy_label}-keyed bucket mean is exactly zero, abstain"
    direction = "bullish" if mean_return > 0 else "bearish"
    return (
        "C02 turn-of-month effect (Ariel 1987, yesterday's-turn-of-month "
        f"proxy): {proxy_label}-keyed bucket mean week return {mean_return:+.5f} "
        f"over {n} weeks -> market-wide {direction} tilt"
    )
