"""Causality/purity check for `strategies/c01_day_of_week.py` (SPEC.md
section 5: "audit.py causality check" is required for every strategy).

C01 is market-wide and pooled across symbols by design (`cards/C01.yml`),
so A01-A09's own audit shape (prove one symbol's score is unaffected by
another symbol getting an extra trailing row) doesn't apply here - there
is nothing cross-symbol to leak, since every eligible symbol gets the
identical score. The real risk specific to this module is different: it
reads "today's weekday" only via a proxy derived from `history`'s own date
column (the last visible row), per `cards/C01.yml`'s `rules_plain`. A bug
could instead read the real wall-clock date, or assume a fixed calendar
alignment, which would silently stop working (or silently work "by
accident") once this runs for real outside a test. This checks that the
module's output depends only on the dates actually present in `history`,
not on any wall-clock or hardcoded-calendar assumption:

1. Build a synthetic market with a deterministic weekday bias (the pooled
   open-to-close return on the trading day right after a chosen weekday is
   always exactly `bias`, zero otherwise), over enough weeks to clear
   `MIN_OCCURRENCES`.
2. Shift every date in that synthetic market by a large number of calendar
   years (while keeping the same weekday-of-week structure, since trading
   days are still generated Mon-Fri) - if the module secretly depended on
   which actual calendar year or a hardcoded reference date it saw, the
   shifted run's prediction would differ from the unshifted run's; if it
   only reads weekday off `history`'s own dates (as designed), the two
   runs must agree exactly.
3. Also checks pure determinism: calling `score` twice on the identical
   `history` gives the identical result (no hidden state, no randomness).
"""

from __future__ import annotations

import pandas as pd

from strategies import c01_day_of_week


def _biased_market(
    n_weeks: int,
    bias_after_weekday: int,
    bias: float,
    symbols: tuple[str, ...] = ("AAA", "BBB", "CCC"),
    start: str = "2015-01-05",
) -> pd.DataFrame:
    """`n_weeks` of Mon-Fri trading days (no holidays) for each symbol, where
    the pooled open-to-close return is exactly `bias` on every trading day
    that immediately follows `bias_after_weekday` (0=Mon..4=Fri), and exactly
    0 on every other day - by construction, not by chance, so the base rate
    this builds is deterministic and exceeds `MIN_OCCURRENCES` pairs."""
    dates = pd.bdate_range(start, periods=n_weeks * 5)
    rows = []
    for i, date in enumerate(dates):
        prev_weekday = dates[i - 1].weekday() if i > 0 else None
        day_return = bias if prev_weekday == bias_after_weekday else 0.0
        for symbol in symbols:
            open_price = 100.0
            close_price = open_price * (1.0 + day_return)
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
    date's weekday (shifting by whole years keeps Mon-Fri business-day
    spacing intact here since `_biased_market` only ever generates
    `bdate_range` dates)."""
    shifted = history.copy()
    shifted["date"] = (
        pd.to_datetime(shifted["date"]) + pd.DateOffset(years=years)
    ).dt.strftime("%Y-%m-%d")
    return shifted


def check_proxy_reads_from_history_not_wall_clock(
    n_weeks: int = 25, bias_after_weekday: int = 4, bias: float = 0.02
) -> dict:
    """The predicted bias must be identical whether the synthetic market's
    dates are left alone or moved a decade later, since both carry the same
    weekday structure and the module is only supposed to read weekday off
    `history`'s own dates."""
    base = _biased_market(n_weeks, bias_after_weekday, bias)
    shifted = _shifted_years(base, years=10)

    bias_base = c01_day_of_week._bias_for_history(base)
    bias_shifted = c01_day_of_week._bias_for_history(shifted)
    bias_base_repeat = c01_day_of_week._bias_for_history(base)

    matches_expectation = bias_base is not None and bias_base == bias
    shift_invariant = bias_base is not None and bias_shifted is not None and bias_base == bias_shifted
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
