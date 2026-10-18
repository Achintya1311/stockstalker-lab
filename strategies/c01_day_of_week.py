"""C01: day-of-week effect (`cards/C01.yml`, `state/queue.md` port lane).

French (1980, JFE): historically weak Mondays, part of the broader
weekend-effect literature (no single canonical rule; see `cards/C01.yml`'s
`source_url`/`author`). Neither this module nor the catalog assumes the
claim true (SPEC.md section 5) - `cards/C01.yml`'s `status` moves to
`confirmed`/`refuted` once a real train replay's edge is in.

The catalog's rule needs the pick date's own weekday, but
`engine.replay.pick_date` never passes a date into `strategy.score()`
(SPEC.md section 5's interface is `score(history) -> pd.Series`, nothing
else), and `history` itself is truncated strictly before the pick date
(B4), so nothing here ever carries today's own calendar date. See
`cards/C01.yml`'s `rules_plain` for the full reasoning; in short, this
module uses the weekday of `history`'s own last visible date ("yesterday")
as a proxy for "today minus one trading day", since NSE trading days
almost always increment Mon->Tue->...->Fri->Mon with no gap. Both the
historical base rates and the live lookup use this exact same proxy, so
it is self-consistent.

Market-wide, not per-symbol: every eligible symbol gets the same score on
a given pick date (the catalog gives no per-symbol differentiation for
this rule).
"""

from __future__ import annotations

import pandas as pd

MIN_OCCURRENCES = 20


def _pooled_daily_return(history: pd.DataFrame) -> pd.Series:
    """Mean open-to-close return across the F&O universe, per trading date.

    Restricted to rows with `has_future` true that date (point-in-time
    universe membership, not a symbol-ever-had-a-future prefilter like
    A01-A09 use - this function computes a market-wide statistic, so it
    needs the universe right on each date, not just a candidate-symbol
    shortlist)."""
    universe = history[history["has_future"]] if "has_future" in history.columns else history
    universe = universe[universe["open"] != 0]
    if universe.empty:
        return pd.Series(dtype=float)
    per_row_return = (universe["close"] - universe["open"]) / universe["open"]
    return per_row_return.groupby(universe["date"]).mean().sort_index()


def _weekday_base_rates(daily_return: pd.Series) -> dict[int, tuple[float, int]]:
    """`{weekday_of_first_date: (mean_return_of_second_date, n_pairs)}` over
    every consecutive pair of dates in `daily_return`'s own index.

    Both dates in every pair are already inside `history` (which the engine
    truncated to strictly before the pick date, B4), so every pair is fully
    realised - there is nothing here that could leak the pick date itself."""
    dates = daily_return.index.to_list()
    buckets: dict[int, list[float]] = {wd: [] for wd in range(5)}
    for prev_date, next_date in zip(dates[:-1], dates[1:]):
        weekday = pd.Timestamp(prev_date).weekday()
        if weekday in buckets:
            buckets[weekday].append(float(daily_return[next_date]))
    return {wd: (sum(v) / len(v), len(v)) for wd, v in buckets.items() if v}


def _bias_for_history(history: pd.DataFrame) -> float | None:
    """The weekday-bucket mean return to apply to today's pick, or `None` to
    abstain (too little history, or the bucket keyed by yesterday's weekday
    has fewer than `MIN_OCCURRENCES` historical pairs)."""
    daily_return = _pooled_daily_return(history)
    if len(daily_return) < 2:
        return None
    base_rates = _weekday_base_rates(daily_return)
    proxy_weekday = pd.Timestamp(daily_return.index[-1]).weekday()
    if proxy_weekday not in base_rates:
        return None
    mean_return, n = base_rates[proxy_weekday]
    if n < MIN_OCCURRENCES:
        return None
    return mean_return


def score(history: pd.DataFrame) -> pd.Series:
    """The same weekday-bucket bias for every symbol with any `has_future`
    row in `history`, or an empty Series if the bucket keyed by yesterday's
    weekday isn't trusted yet (too few historical pairs)."""
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
        return "C01 day-of-week effect: insufficient market-wide history, abstain"

    base_rates = _weekday_base_rates(daily_return)
    proxy_weekday = pd.Timestamp(daily_return.index[-1]).weekday()
    weekday_name = pd.Timestamp(daily_return.index[-1]).day_name()
    if proxy_weekday not in base_rates:
        return (
            f"C01 day-of-week effect: no historical pairs keyed by yesterday's "
            f"weekday ({weekday_name}), abstain"
        )
    mean_return, n = base_rates[proxy_weekday]
    if n < MIN_OCCURRENCES:
        return (
            f"C01 day-of-week effect: only {n} historical pairs keyed by "
            f"yesterday's weekday ({weekday_name}), below {MIN_OCCURRENCES}, abstain"
        )
    if mean_return == 0:
        return f"C01 day-of-week effect: {weekday_name}-keyed bucket mean is exactly zero, abstain"
    direction = "bullish" if mean_return > 0 else "bearish"
    return (
        "C01 day-of-week effect (French 1980 weekend-effect literature, "
        f"yesterday's-weekday proxy): {weekday_name}-keyed bucket mean open-to-close "
        f"return {mean_return:+.5f} over {n} pairs -> market-wide {direction} tilt"
    )
