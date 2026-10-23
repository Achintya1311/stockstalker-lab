import pandas as pd
import pytest

from strategies import c03_pre_holiday
from strategies.c03_pre_holiday_audit import (
    BIAS,
    _recurring_wednesday_holiday_market,
    _truncate_before_final_tuesday,
    check_abstains_when_not_pre_holiday,
    check_cross_symbol_uniformity,
    check_pre_holiday_flag_matches_independent_calculation,
)


def test_known_bias_gives_exact_score_for_every_symbol():
    history, holidays = _recurring_wednesday_holiday_market()
    truncated = _truncate_before_final_tuesday(history)
    scores = c03_pre_holiday.score(truncated, holidays)
    assert set(scores.index) == {"AAA", "BBB", "CCC"}
    for symbol in ("AAA", "BBB", "CCC"):
        assert scores[symbol] == pytest.approx(BIAS, rel=1e-9)


def test_bearish_bias_scores_negative():
    # Same calendar, but every pre-holiday Tuesday's return is negative.
    bdates = pd.bdate_range("2024-01-01", periods=30 * 5)
    holidays = {d.date().isoformat() for d in bdates if d.weekday() == 2}
    rows = []
    for d in bdates:
        if d.weekday() == 2:
            continue
        ret = -0.01 if d.weekday() == 1 else 0.0
        open_price = 100.0
        close_price = open_price * (1.0 + ret)
        for symbol in ("AAA", "BBB", "CCC"):
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
    history = pd.DataFrame(rows)
    truncated = _truncate_before_final_tuesday(history)
    scores = c03_pre_holiday.score(truncated, holidays)
    assert all(scores[s] == pytest.approx(-0.01, rel=1e-9) for s in ("AAA", "BBB", "CCC"))


def test_abstains_when_pick_date_is_not_pre_holiday():
    result = check_abstains_when_not_pre_holiday()
    assert result["passed"], result


def test_zero_bias_abstains():
    bdates = pd.bdate_range("2024-01-01", periods=30 * 5)
    holidays = {d.date().isoformat() for d in bdates if d.weekday() == 2}
    rows = []
    for d in bdates:
        if d.weekday() == 2:
            continue
        open_price = 100.0
        for symbol in ("AAA", "BBB", "CCC"):
            rows.append(
                {
                    "date": d.date().isoformat(),
                    "symbol": symbol,
                    "open": open_price,
                    "high": open_price,
                    "low": open_price,
                    "close": open_price,
                    "prevclose": open_price,
                    "volume": 1_000_000.0,
                    "has_future": True,
                }
            )
    history = pd.DataFrame(rows)
    truncated = _truncate_before_final_tuesday(history)
    scores = c03_pre_holiday.score(truncated, holidays)
    assert scores.empty


def test_too_few_historical_pre_holiday_days_abstains():
    # Only 3 weeks: far fewer than MIN_OCCURRENCES (20) pre-holiday Tuesdays.
    bdates = pd.bdate_range("2024-01-01", periods=3 * 5)
    holidays = {d.date().isoformat() for d in bdates if d.weekday() == 2}
    rows = []
    for d in bdates:
        if d.weekday() == 2:
            continue
        ret = 0.05 if d.weekday() == 1 else 0.0
        open_price = 100.0
        close_price = open_price * (1.0 + ret)
        for symbol in ("AAA", "BBB", "CCC"):
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
    history = pd.DataFrame(rows)
    truncated = _truncate_before_final_tuesday(history)
    scores = c03_pre_holiday.score(truncated, holidays)
    assert scores.empty


def test_empty_history_abstains():
    scores = c03_pre_holiday.score(pd.DataFrame(), holidays=set())
    assert scores.empty


def test_symbol_without_future_anywhere_is_excluded():
    history, holidays = _recurring_wednesday_holiday_market()
    truncated = _truncate_before_final_tuesday(history).copy()
    truncated.loc[truncated["symbol"] == "CCC", "has_future"] = False
    scores = c03_pre_holiday.score(truncated, holidays)
    assert "CCC" not in scores
    assert "AAA" in scores and "BBB" in scores


def test_rules_fired_reports_direction_and_sample_size():
    history, holidays = _recurring_wednesday_holiday_market()
    truncated = _truncate_before_final_tuesday(history)
    reasoning = c03_pre_holiday.rules_fired(truncated, "AAA", holidays)
    assert "days" in reasoning
    assert "bullish" in reasoning
    assert "pre-holiday" in reasoning


def test_rules_fired_abstain_message_when_not_pre_holiday():
    history, holidays = _recurring_wednesday_holiday_market()
    dates = pd.to_datetime(history["date"])
    thursdays = sorted(dates[dates.dt.day_of_week == 3].unique())
    truncated = history[dates <= thursdays[len(thursdays) // 2]]
    reasoning = c03_pre_holiday.rules_fired(truncated, "AAA", holidays)
    assert "not pre-holiday" in reasoning
    assert "abstain" in reasoning


def test_rules_fired_no_history_message():
    reasoning = c03_pre_holiday.rules_fired(pd.DataFrame(), "AAA", holidays=set())
    assert "no history" in reasoning
    assert "abstain" in reasoning


def test_is_pre_holiday_matches_catalog_definition_friday_before_monday_holiday():
    # Friday 2026-01-23 followed by a Monday holiday (2026-01-26, Republic
    # Day, from the real committed file) must be flagged pre-holiday even
    # though a plain weekend sits in between.
    assert c03_pre_holiday._is_pre_holiday(
        pd.Timestamp("2026-01-23"), {"2026-01-26"}
    )


def test_is_pre_holiday_false_for_a_plain_friday_before_an_ordinary_weekend():
    assert not c03_pre_holiday._is_pre_holiday(pd.Timestamp("2026-01-16"), {"2026-01-26"})


def test_causality_audit_passes():
    result = check_pre_holiday_flag_matches_independent_calculation()
    assert result["passed"], result


def test_causality_audit_cross_symbol_uniformity_passes():
    result = check_cross_symbol_uniformity()
    assert result["passed"], result
