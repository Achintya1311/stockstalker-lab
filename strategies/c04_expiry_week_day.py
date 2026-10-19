"""C04 (day horizon): F&O expiry-week effect (`cards/C04.yml`, `state/queue.md`
port lane).

India-specific practitioner claim (`cards/catalog.csv`'s own reading:
"Different behaviour in the week of the monthly F&O expiry", `prior_claim`:
"Claimed volatility and reversal around expiry; test it" - direction not
stated, only that there is one). Neither this module nor the catalog
assumes the claim true (SPEC.md section 5) - `cards/C04.yml`'s `status`
moves to `confirmed`/`refuted` once a real train replay's edge is in.

Same wall `cards/C01.yml` and `cards/C02.yml` already hit: `score(history)`
is never told the pick date, and `history` is truncated strictly before it
(B4), so nothing here ever carries the upcoming pick date's own calendar
position. Unlike C01/C02 this has nothing to do with weekday or
day-of-month identity though - it needs to know whether a specific future
date (NSE's own published monthly expiry) is coming up soon. This run's
dataset extension (`scripts/build_dataset.py`) now carries each
`has_future` row's own near-month contract's expiry date as
`expiry_futstk` - an already-scheduled fact recorded in the FO bhavcopy on
the day itself, not a derived guess and not a leak of unknowable future
information (`state/engine-issues.md`'s C03/C04 entry; `strategies/c04_common.py`'s
docstring has the full reasoning for why this unblocks C04 but not C03).

The proxy, exactly the same shape as C01's "yesterday's weekday stands in
for today's": whether `history`'s own last visible trading day's near-month
contract expires in that *same* ISO calendar week ("yesterday was itself in
expiry week") stands in for "today is in expiry week" - both the historical
base rates and the live lookup key on this identical quantity, so it is
self-consistent. This is accurate on every day of an expiry week except the
one right after expiry Friday (where yesterday, Thursday's expiry day, was
flagged true, but today the active contract has already rolled to next
month and is nowhere near expiry) - a known, accepted blur, the same shape
C01's own weekday-proxy caveat already lives with (`cards/C01.yml`).

Market-wide, not per-symbol: every eligible symbol gets the same score on
a given pick date (the catalog gives no per-symbol differentiation).
"""

from __future__ import annotations

import pandas as pd

from strategies.c04_common import mode_expiry_by_date, same_iso_week

MIN_OCCURRENCES = 20


def _pooled_daily_return(history: pd.DataFrame) -> pd.Series:
    """Mean open-to-close return across the F&O universe, per trading date
    (Timestamp index) - same construction as `c01_day_of_week._pooled_daily_return`,
    indexed by real `Timestamp` here (rather than the raw string `date`
    column) so it lines up directly with `mode_expiry_by_date`'s index."""
    universe = history[history["has_future"]] if "has_future" in history.columns else history
    universe = universe[universe["open"] != 0]
    if universe.empty:
        return pd.Series(dtype=float)
    per_row_return = (universe["close"] - universe["open"]) / universe["open"]
    dates = pd.to_datetime(universe["date"])
    return per_row_return.groupby(dates).mean().sort_index()


def _expiry_week_base_rates(
    daily_return: pd.Series, modal_expiry: pd.Series
) -> dict[bool, tuple[float, int]]:
    """`{was_yesterday_expiry_week: (mean_return_of_today, n_pairs)}` over
    every consecutive pair of dates in `daily_return`'s own index.

    Both dates in every pair, and the expiry date read off the first one,
    are already inside `history` (B4's truncation) - nothing here can leak
    the pick date itself."""
    dates = daily_return.index.to_list()
    buckets: dict[bool, list[float]] = {True: [], False: []}
    for prev_date, next_date in zip(dates[:-1], dates[1:]):
        expiry = modal_expiry.get(prev_date)
        if expiry is None or pd.isna(expiry):
            continue
        flag = same_iso_week(prev_date, expiry)
        buckets[flag].append(float(daily_return[next_date]))
    return {k: (sum(v) / len(v), len(v)) for k, v in buckets.items() if v}


def _bias_for_history(history: pd.DataFrame) -> float | None:
    """The expiry-week-bucket mean return to apply to today's pick, or
    `None` to abstain (too little history, yesterday's near-month contract
    has no recorded expiry, or the bucket keyed by yesterday's expiry-week
    status has fewer than `MIN_OCCURRENCES` historical pairs)."""
    daily_return = _pooled_daily_return(history)
    if len(daily_return) < 2:
        return None
    modal_expiry = mode_expiry_by_date(history)
    last_date = daily_return.index[-1]
    expiry = modal_expiry.get(last_date)
    if expiry is None or pd.isna(expiry):
        return None
    base_rates = _expiry_week_base_rates(daily_return, modal_expiry)
    proxy_flag = same_iso_week(last_date, expiry)
    if proxy_flag not in base_rates:
        return None
    mean_return, n = base_rates[proxy_flag]
    if n < MIN_OCCURRENCES:
        return None
    return mean_return


def score(history: pd.DataFrame) -> pd.Series:
    """The same expiry-week-bucket bias for every symbol with any
    `has_future` row in `history`, or an empty Series if the bucket keyed
    by yesterday's expiry-week status isn't trusted yet."""
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
    daily_return = _pooled_daily_return(history)
    if len(daily_return) < 2:
        return "C04 expiry-week effect (day): insufficient market-wide history, abstain"

    modal_expiry = mode_expiry_by_date(history)
    last_date = daily_return.index[-1]
    expiry = modal_expiry.get(last_date)
    if expiry is None or pd.isna(expiry):
        return "C04 expiry-week effect (day): no recorded near-month expiry for yesterday, abstain"

    base_rates = _expiry_week_base_rates(daily_return, modal_expiry)
    proxy_flag = same_iso_week(last_date, expiry)
    label = "expiry week" if proxy_flag else "not expiry week"
    if proxy_flag not in base_rates:
        return f"C04 expiry-week effect (day): no historical pairs keyed by yesterday being {label}, abstain"
    mean_return, n = base_rates[proxy_flag]
    if n < MIN_OCCURRENCES:
        return (
            f"C04 expiry-week effect (day): only {n} historical pairs keyed by "
            f"yesterday being {label}, below {MIN_OCCURRENCES}, abstain"
        )
    if mean_return == 0:
        return f"C04 expiry-week effect (day): {label}-keyed bucket mean is exactly zero, abstain"
    direction = "bullish" if mean_return > 0 else "bearish"
    return (
        "C04 expiry-week effect (day; yesterday's-expiry-week proxy): "
        f"{label}-keyed bucket mean open-to-close return {mean_return:+.5f} "
        f"over {n} pairs -> market-wide {direction} tilt"
    )
