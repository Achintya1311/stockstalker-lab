"""C04 (week horizon): F&O expiry-week effect (`cards/C04.yml`, `state/queue.md`
port lane). See `strategies/c04_expiry_week_day.py` for the day-horizon
variant and the full reasoning on why `expiry_futstk` (this run's dataset
extension) unblocks C04 without needing an external holiday calendar.

Week-horizon picks are made at Monday's open with `history` truncated
through the prior Friday's close (`engine.run_queue._dates_for_horizon`,
documented in full in `cards/C02.yml`). The question this card asks is
whether the *upcoming* week is the expiry week - not whether the trading
day right before it was, since by the time Friday's own row is visible,
Thursday's expiry (if the preceding week was the expiry week) has already
happened and the near-month contract has already rolled to the following
month; Friday's own `expiry_futstk` reflects *that* roll, not the week
just finished. So the proxy here is different from the day-horizon
variant's "yesterday was itself in expiry week": it is "does the near-month
contract active on the last visible Friday expire in the ISO week
immediately after Friday's own ISO week" - adding exactly 7 calendar days
to Friday's own date always lands in the next ISO week (ISO weeks are
fixed 7-day blocks), which is the upcoming pick week whenever `history`'s
last visible date really is a Friday. Both the historical base rates and
the live lookup key on this identical quantity, so it is self-consistent.

Unlike C02's own turn-of-month construction, this module builds its weekly
return series from real ISO calendar weeks rather than fixed-size
trading-day chunks, since real dates (via `expiry_futstk`) are already in
play here and C02's own reason for avoiding them - its causality audit
found a whole-year date shift doesn't reliably preserve weekday alignment
across a 29 February (see `cards/C02.yml`'s red flags) - is a risk to a
weekday-keyed rule, not to an ISO-week-keyed one: this module's own
causality audit (`strategies/c04_expiry_week_week_audit.py`) checks the
analogous risk directly (a pure day-count shift of both `date` and
`expiry_futstk` together must leave every score unchanged).

Market-wide, not per-symbol: every eligible symbol gets the same score on
a given pick date (the catalog gives no per-symbol differentiation).
"""

from __future__ import annotations

import pandas as pd

from strategies.c04_common import mode_expiry_by_date, same_iso_week, trading_calendar

MIN_OCCURRENCES = 20


def _iso_week_groups(calendar: pd.DatetimeIndex) -> dict[tuple[int, int], list[pd.Timestamp]]:
    """Trading dates in `calendar` grouped by ISO (year, week), in the
    calendar's own chronological order (Python dicts preserve insertion
    order, and `calendar` is sorted ascending, so each group's own date
    list is also chronological and the dict's key order is chronological)."""
    groups: dict[tuple[int, int], list[pd.Timestamp]] = {}
    for date in calendar:
        iso = date.isocalendar()
        groups.setdefault((iso.year, iso.week), []).append(date)
    return groups


def _pooled_iso_week_returns(history: pd.DataFrame) -> tuple[pd.Series, dict]:
    """One pooled, market-wide return per real ISO calendar week fully
    present in `history`, keyed by `(iso_year, iso_week)`: the mean, across
    `has_future`-eligible symbols with a row on both the week's first and
    last visible trading day, of close(last day)/open(first day) - 1.

    Also returns the `(iso_year, iso_week) -> [dates]` grouping, so callers
    needing a week's first trading date (to find the trading day right
    before it) don't have to recompute it."""
    universe = history[history["has_future"]] if "has_future" in history.columns else history
    if universe.empty:
        return pd.Series(dtype=float), {}
    universe = universe.copy()
    universe["date"] = pd.to_datetime(universe["date"])

    calendar = trading_calendar(history)
    groups = _iso_week_groups(calendar)
    results: dict[tuple[int, int], float] = {}
    for iso_key, days in groups.items():
        first_day, last_day = days[0], days[-1]
        first = universe.loc[universe["date"] == first_day].set_index("symbol")["open"]
        last = universe.loc[universe["date"] == last_day].set_index("symbol")["close"]
        common = first.index.intersection(last.index)
        common = common[first.loc[common] != 0]
        if len(common) == 0:
            continue
        results[iso_key] = float(((last.loc[common] - first.loc[common]) / first.loc[common]).mean())
    return pd.Series(results, dtype=float), groups


def _expiry_week_base_rates(history: pd.DataFrame) -> dict[bool, tuple[float, int]]:
    """`{preceding_friday_predicted_this_week: (mean_week_return, n_weeks)}`.

    For each ISO week fully inside `history`, the "preceding Friday" is the
    trading day immediately before that week's own first visible date
    (`calendar[pos - 1]`, same idiom `c02_turn_of_month._totm_base_rates`
    uses) - by definition always inside `history` too, since it comes
    before a week that is itself inside `history`. The flag compares that
    day's own `expiry_futstk` directly against the week being bucketed's
    own known `(iso_year, iso_week)` key - an exact test here (unlike the
    live lookup below, which has to approximate the *upcoming* week's own
    key with a +7-day offset, since that week doesn't exist in `history`
    yet to look up directly)."""
    week_returns, groups = _pooled_iso_week_returns(history)
    if week_returns.empty:
        return {}
    calendar = trading_calendar(history)
    position = {date: i for i, date in enumerate(calendar)}
    modal_expiry = mode_expiry_by_date(history)

    buckets: dict[bool, list[float]] = {True: [], False: []}
    for iso_key, week_return in week_returns.items():
        first_day = groups[iso_key][0]
        pos = position.get(first_day)
        if pos is None or pos == 0:
            continue
        preceding_date = calendar[pos - 1]
        expiry = modal_expiry.get(preceding_date)
        if expiry is None or pd.isna(expiry):
            continue
        expiry_iso = expiry.isocalendar()
        flag = (expiry_iso.year, expiry_iso.week) == iso_key
        buckets[flag].append(float(week_return))
    return {k: (sum(v) / len(v), len(v)) for k, v in buckets.items() if v}


def _bias_for_history(history: pd.DataFrame) -> float | None:
    """The expiry-week-bucket mean week return to apply to the upcoming
    pick week, or `None` to abstain (too little history, the last visible
    day's near-month contract has no recorded expiry, or the bucket keyed
    by the +7-day proxy has fewer than `MIN_OCCURRENCES` historical
    weeks)."""
    calendar = trading_calendar(history)
    if len(calendar) < 2:
        return None
    modal_expiry = mode_expiry_by_date(history)
    last_date = calendar[-1]
    expiry = modal_expiry.get(last_date)
    if expiry is None or pd.isna(expiry):
        return None

    base_rates = _expiry_week_base_rates(history)
    upcoming_marker = last_date + pd.Timedelta(days=7)
    proxy_flag = same_iso_week(expiry, upcoming_marker)
    if proxy_flag not in base_rates:
        return None
    mean_return, n = base_rates[proxy_flag]
    if n < MIN_OCCURRENCES:
        return None
    return mean_return


def score(history: pd.DataFrame) -> pd.Series:
    """The same expiry-week-bucket bias for every symbol with any
    `has_future` row in `history`, or an empty Series if the bucket keyed
    by the upcoming-week proxy isn't trusted yet."""
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
    calendar = trading_calendar(history)
    if len(calendar) < 2:
        return "C04 expiry-week effect (week): insufficient market-wide history, abstain"

    modal_expiry = mode_expiry_by_date(history)
    last_date = calendar[-1]
    expiry = modal_expiry.get(last_date)
    if expiry is None or pd.isna(expiry):
        return "C04 expiry-week effect (week): no recorded near-month expiry for the last visible session, abstain"

    base_rates = _expiry_week_base_rates(history)
    upcoming_marker = last_date + pd.Timedelta(days=7)
    proxy_flag = same_iso_week(expiry, upcoming_marker)
    label = "expiry week" if proxy_flag else "not expiry week"
    if proxy_flag not in base_rates:
        return f"C04 expiry-week effect (week): no historical weeks keyed by upcoming-week being {label}, abstain"
    mean_return, n = base_rates[proxy_flag]
    if n < MIN_OCCURRENCES:
        return (
            f"C04 expiry-week effect (week): only {n} historical weeks keyed by "
            f"upcoming-week being {label}, below {MIN_OCCURRENCES}, abstain"
        )
    if mean_return == 0:
        return f"C04 expiry-week effect (week): {label}-keyed bucket mean is exactly zero, abstain"
    direction = "bullish" if mean_return > 0 else "bearish"
    return (
        "C04 expiry-week effect (week; +7-day upcoming-week proxy): "
        f"{label}-keyed bucket mean week return {mean_return:+.5f} "
        f"over {n} weeks -> market-wide {direction} tilt"
    )
