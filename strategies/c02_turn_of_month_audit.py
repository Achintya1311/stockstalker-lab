"""Causality/purity check for `strategies/c02_turn_of_month.py` (SPEC.md
section 5: "audit.py causality check" is required for every strategy).

Like C01, C02 is market-wide and pooled across symbols by design
(`cards/C02.yml`), so there is nothing cross-symbol to leak - every
eligible symbol gets the identical score. The risk specific to this
module is the same shape as C01's: it decides "is yesterday turn-of-month"
only from the trading dates actually present in `history` (`cards/C02.yml`'s
`rules_plain`), never from wall-clock time or a hardcoded calendar. A bug
could instead assume a fixed reference date, which would silently stop
working (or silently work "by accident") once this runs for real. This
checks that the module's output depends only on the dates actually
present in `history`:

1. Build a synthetic market with a deterministic turn-of-month bias (the
   pooled week return is exactly `bias` for every week whose own first
   trading day is immediately preceded by a turn-of-month trading day -
   computed independently of `strategies.c02_turn_of_month`'s own ranking
   code, directly from calendar day-of-month, so this is not circular),
   over enough months to clear `MIN_OCCURRENCES`.
2. Shift every date in that synthetic market by a large number of
   calendar years - month/day positions (and therefore trading-day rank
   within each month) are unchanged by a whole-year shift, so if the
   module only reads turn-of-month status off `history`'s own dates (as
   designed), the shifted run's prediction must equal the unshifted run's;
   if it secretly depended on the actual year or a hardcoded reference
   date, the two would differ.
3. Also checks pure determinism: calling `_bias_for_history` twice on the
   identical `history` gives the identical result (no hidden state, no
   randomness).
"""

from __future__ import annotations

import pandas as pd

from strategies import c02_turn_of_month


def _preceding_day_is_totm(preceding: pd.Timestamp) -> bool:
    """Calendar-day proxy for "is `preceding` turn-of-month", independent
    of `strategies.c02_turn_of_month`'s own trading-day-rank code (so this
    fixture isn't circular). With a plain Mon-Fri business-day calendar
    and no holidays, the first 3 trading days of a month always fall
    within the first 5 calendar days (worst case: day 1 is a Friday, so
    trading days 2 and 3 land on the following Monday and Tuesday, days 4
    and 5), and the last trading day always falls within the last 3
    calendar days (worst case: the month's last day is a Sunday, so the
    last trading day is the preceding Friday, 2 days earlier) - so this
    calendar rule exactly reproduces the module's trading-day-rank rule
    for every date this generator produces."""
    days_in_month = pd.Period(preceding, freq="M").days_in_month
    return preceding.day <= 5 or preceding.day >= days_in_month - 2


def _biased_market(
    n_weeks: int,
    bias: float,
    symbols: tuple[str, ...] = ("AAA", "BBB", "CCC"),
    start: str = "2015-01-05",
) -> pd.DataFrame:
    """`n_weeks` of Mon-Fri trading days (no holidays) for each symbol,
    where a given week's pooled return (close of its last day / open of
    its first day - 1) is exactly `bias` if the trading day immediately
    before that week started is turn-of-month (`_preceding_day_is_totm`),
    and exactly 0 otherwise - by construction, not by chance, so the base
    rate this builds is deterministic. Every day's own open-to-close
    return is 0 except the week's last day, which carries the whole
    week's return, so there is no cross-day compounding to account for
    when checking the result against `bias` exactly."""
    dates = pd.bdate_range(start, periods=n_weeks * 5)
    rows = []
    for week_idx in range(n_weeks):
        week_dates = dates[week_idx * 5 : week_idx * 5 + 5]
        if week_idx == 0:
            week_return = 0.0
        else:
            preceding = dates[week_idx * 5 - 1]
            week_return = bias if _preceding_day_is_totm(preceding) else 0.0
        for i, date in enumerate(week_dates):
            is_last = i == len(week_dates) - 1
            for symbol in symbols:
                open_price = 100.0
                close_price = open_price * (1.0 + week_return) if is_last else open_price
                rows.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "symbol": symbol,
                        "open": open_price,
                        "high": max(open_price, close_price),
                        "low": min(open_price, close_price),
                        "close": close_price,
                        "prevclose": open_price,
                        "volume": 1_000_000.0,
                        "has_future": True,
                    }
                )
    return pd.DataFrame(rows)


def _shifted_years(history: pd.DataFrame, years: int) -> pd.DataFrame:
    """Same rows, every date moved `years` years later - preserves each
    date's month and day-of-month exactly (only the year changes), so
    trading-day rank within each month is unaffected."""
    shifted = history.copy()
    shifted["date"] = (
        pd.to_datetime(shifted["date"]) + pd.DateOffset(years=years)
    ).dt.strftime("%Y-%m-%d")
    return shifted


def check_proxy_reads_from_history_not_wall_clock(
    n_weeks: int = 200, bias: float = 0.02
) -> dict:
    """The predicted bias must be identical whether the synthetic market's
    dates are left alone or moved a decade later, since both carry the
    same month/day-of-month structure and the module is only supposed to
    read turn-of-month status off `history`'s own dates."""
    base = _biased_market(n_weeks, bias)
    shifted = _shifted_years(base, years=10)

    bias_base = c02_turn_of_month._bias_for_history(base)
    bias_shifted = c02_turn_of_month._bias_for_history(shifted)
    bias_base_repeat = c02_turn_of_month._bias_for_history(base)

    # `history`'s own last visible trading day is the proxy key `score()`
    # looks up (`c02_turn_of_month._bias_for_history`'s `proxy_flag`) - compute
    # the same calendar-day predicate independently to know which bucket
    # (bias, or 0) that day's week actually belongs to, rather than assuming
    # it always lands in the biased bucket.
    last_day = pd.to_datetime(base["date"]).max()
    expected = bias if _preceding_day_is_totm(last_day) else 0.0
    matches_expectation = bias_base is not None and pytest_approx_ok(bias_base, expected)
    shift_invariant = bias_base is not None and bias_shifted is not None and bias_base == bias_shifted
    deterministic = bias_base == bias_base_repeat

    passed = matches_expectation and shift_invariant and deterministic
    return {
        "passed": passed,
        "bias_base": bias_base,
        "bias_shifted": bias_shifted,
        "bias_base_repeat": bias_base_repeat,
        "expected": expected,
        "matches_expectation": matches_expectation,
        "shift_invariant": shift_invariant,
        "deterministic": deterministic,
    }


def pytest_approx_ok(value: float, target: float, tol: float = 1e-9) -> bool:
    """Tiny standalone float-equality helper so this module has no test
    dependency (`pytest`) to import when run standalone via `__main__`."""
    return abs(value - target) <= tol


if __name__ == "__main__":
    result = check_proxy_reads_from_history_not_wall_clock()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
