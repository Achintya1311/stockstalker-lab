"""Causality/purity check for `strategies/c03_pre_holiday.py` (SPEC.md
section 5: "audit.py causality check" is required for every strategy).

Like C01/C02, C03 is market-wide and pooled across symbols by design
(`cards/C03.yml`), so there is nothing cross-symbol to leak - every
eligible symbol gets the identical score. The risk specific to this
module is different from C01/C02's "reads only from history's own dates"
check: C03 deliberately reads an *external* static holiday calendar
(`config/nse_holidays.txt`, via `picks.calendar`), which is legitimate
(SPEC.md section 5 does not require a strategy to see nothing outside
`history` - only that it never sees the future of the *dataset* it is
scored against). What must be checked instead:

1. The pre-holiday flag the module computes for the pick date it infers
   exactly matches an independently-computed flag from the same holiday
   set (not reusing `c03_pre_holiday._is_pre_holiday`, to avoid
   circularity), and the predicted bias equals the exact historical
   pre-holiday mean - nothing from the live, not-yet-realised pick date
   itself leaks in, since that date is never a row of `history` at all
   (B4's truncation; this module cannot see a price it was never given).
2. The module abstains (empty score) when the inferred pick date is *not*
   pre-holiday, rather than always firing.
3. Market-wide, not cross-sectional: every eligible symbol gets the
   identical nonzero score on a firing pick date - nothing here is
   supposed to differ by symbol.
4. Pure determinism: calling `_bias_for_history` twice on identical inputs
   gives the identical result.
"""

from __future__ import annotations

import datetime

import pandas as pd

from strategies import c03_pre_holiday

BIAS = 0.015
N_WEEKS = 30
SYMBOLS = ("AAA", "BBB", "CCC")


def _independent_is_pre_holiday(d: str, holidays: set[str]) -> bool:
    """Reimplementation of "the next calendar weekday after `d` is a
    holiday", using plain `datetime` instead of `pandas.Timestamp`
    arithmetic, so this fixture shares no code with
    `c03_pre_holiday._is_pre_holiday`."""
    cur = datetime.date.fromisoformat(d) + datetime.timedelta(days=1)
    while cur.weekday() >= 5:
        cur += datetime.timedelta(days=1)
    return cur.isoformat() in holidays


def _recurring_wednesday_holiday_market() -> tuple[pd.DataFrame, set[str]]:
    """`N_WEEKS` weeks of a Mon/Tue/Thu/Fri trading calendar where every
    Wednesday is a declared holiday - so every Tuesday is, by
    construction, pre-holiday (the next weekday after Tuesday is the
    holiday Wednesday), and every other day is not. Every Tuesday's
    market-wide open-to-close return is exactly `BIAS`; every other day's
    is exactly 0 - deterministic, not by chance, so the base rate this
    builds is exactly `BIAS` with no noise to account for."""
    bdates = pd.bdate_range("2024-01-01", periods=N_WEEKS * 5)
    holidays = {d.date().isoformat() for d in bdates if d.weekday() == 2}
    trading_days = [d for d in bdates if d.weekday() != 2]

    rows = []
    for d in trading_days:
        ret = BIAS if d.weekday() == 1 else 0.0
        open_price = 100.0
        close_price = open_price * (1.0 + ret)
        for symbol in SYMBOLS:
            rows.append(
                {
                    "date": d.date().isoformat(),
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
    return pd.DataFrame(rows), holidays


def _truncate_before_final_tuesday(history: pd.DataFrame) -> pd.DataFrame:
    """`history` cut to end on the last Monday present - the trading day
    immediately before the final week's Tuesday, which is deliberately
    left out of the truncated frame so that Tuesday plays the role of the
    live, not-yet-realised pick date."""
    dates = pd.to_datetime(history["date"])
    mondays = sorted(dates[dates.dt.day_of_week == 0].unique())
    last_monday = mondays[-1]
    return history[dates <= last_monday]


def check_pre_holiday_flag_matches_independent_calculation() -> dict:
    """On a `history` truncated to end the Monday before the final week's
    Tuesday, the module must infer "today" = that Tuesday, agree with an
    independently-computed pre-holiday flag that it is pre-holiday, and
    predict a bias equal to the exact historical mean (`BIAS`)."""
    history, holidays = _recurring_wednesday_holiday_market()
    truncated = _truncate_before_final_tuesday(history)

    bias_result = c03_pre_holiday._bias_for_history(truncated, holidays)
    bias_result_repeat = c03_pre_holiday._bias_for_history(truncated, holidays)

    resolved = c03_pre_holiday._today_and_holidays(truncated, holidays)
    today = resolved[0] if resolved else None
    today_iso = today.date().isoformat() if today is not None else None

    independent_flag = (
        _independent_is_pre_holiday(today_iso, holidays) if today is not None else None
    )
    module_flag = c03_pre_holiday._is_pre_holiday(today, holidays) if today is not None else None

    deterministic = bias_result == bias_result_repeat
    today_is_tuesday = today is not None and today.weekday() == 1
    flags_agree = independent_flag is not None and independent_flag == module_flag is True
    matches_expectation = bias_result is not None and abs(bias_result - BIAS) < 1e-9

    passed = deterministic and today_is_tuesday and flags_agree and matches_expectation
    return {
        "passed": passed,
        "today": today_iso,
        "today_is_tuesday": today_is_tuesday,
        "bias_result": bias_result,
        "expected_bias": BIAS,
        "independent_flag": independent_flag,
        "module_flag": module_flag,
        "deterministic": deterministic,
        "flags_agree": flags_agree,
        "matches_expectation": matches_expectation,
    }


def check_abstains_when_not_pre_holiday() -> dict:
    """Truncate `history` to end on a Thursday whose next trading day
    (Friday) is not a holiday - the module must abstain (empty score),
    not fall back to some default bias."""
    history, holidays = _recurring_wednesday_holiday_market()
    dates = pd.to_datetime(history["date"])
    thursdays = sorted(dates[dates.dt.day_of_week == 3].unique())
    # Any Thursday works: Friday is never in `holidays` (only Wednesdays are).
    truncated = history[dates <= thursdays[len(thursdays) // 2]]

    score = c03_pre_holiday.score(truncated, holidays)
    passed = score.empty
    return {"passed": passed, "score": dict(score)}


def check_cross_symbol_uniformity() -> dict:
    """On a firing pick date, every eligible symbol must get the identical
    nonzero score - this card is market-wide by design, with no per-symbol
    differentiation (`cards/C03.yml`)."""
    history, holidays = _recurring_wednesday_holiday_market()
    truncated = _truncate_before_final_tuesday(history)

    score = c03_pre_holiday.score(truncated, holidays)
    values = set(score.to_numpy().tolist())
    passed = (
        not score.empty
        and set(score.index) == set(SYMBOLS)
        and len(values) == 1
        and next(iter(values)) != 0
    )
    return {"passed": passed, "score": dict(score)}


if __name__ == "__main__":
    results = {
        "pre_holiday_flag": check_pre_holiday_flag_matches_independent_calculation(),
        "abstains_when_not_pre_holiday": check_abstains_when_not_pre_holiday(),
        "cross_symbol_uniformity": check_cross_symbol_uniformity(),
    }
    for name, result in results.items():
        print(name, result)
    raise SystemExit(0 if all(r["passed"] for r in results.values()) else 1)
