import pandas as pd
import pytest

from strategies import c02_turn_of_month
from strategies.c02_turn_of_month_audit import (
    _biased_market,
    _preceding_day_is_totm,
    check_proxy_reads_from_history_not_wall_clock,
)


def _expected_bucket(history: pd.DataFrame, bias: float) -> float:
    """What `score()` should return for `history`: `bias` if `history`'s own
    last visible trading day is turn-of-month, else 0 - computed
    independently of `c02_turn_of_month`'s own ranking code."""
    last_day = pd.to_datetime(history["date"]).max()
    return bias if _preceding_day_is_totm(last_day) else 0.0


def test_known_bias_gives_exact_score_for_every_symbol():
    # 200 weeks clears MIN_OCCURRENCES (20) in both buckets.
    history = _biased_market(n_weeks=200, bias=0.02)
    expected = _expected_bucket(history, 0.02)
    scores = c02_turn_of_month.score(history)
    if expected == 0.0:
        assert scores.empty
        return
    assert set(scores.index) == {"AAA", "BBB", "CCC"}
    for symbol in ("AAA", "BBB", "CCC"):
        assert scores[symbol] == pytest.approx(expected, rel=1e-9)


def test_bearish_bias_scores_negative_when_proxy_is_turn_of_month():
    history = _biased_market(n_weeks=200, bias=-0.015)
    expected = _expected_bucket(history, -0.015)
    scores = c02_turn_of_month.score(history)
    if expected == 0.0:
        assert scores.empty
        return
    assert all(scores[s] == pytest.approx(expected, rel=1e-9) for s in ("AAA", "BBB", "CCC"))


def test_zero_bias_abstains():
    history = _biased_market(n_weeks=200, bias=0.0)
    scores = c02_turn_of_month.score(history)
    assert scores.empty


def test_too_few_historical_weeks_abstains():
    # 3 weeks gives far fewer than MIN_OCCURRENCES (20) pairs in either bucket.
    history = _biased_market(n_weeks=3, bias=0.05)
    scores = c02_turn_of_month.score(history)
    assert scores.empty


def test_empty_history_abstains():
    scores = c02_turn_of_month.score(pd.DataFrame())
    assert scores.empty


def test_symbol_without_future_anywhere_is_excluded():
    history = _biased_market(n_weeks=200, bias=0.02)
    expected = _expected_bucket(history, 0.02)
    if expected == 0.0:
        pytest.skip("this run's last visible day isn't turn-of-month; nothing to assert here")
    history.loc[history["symbol"] == "CCC", "has_future"] = False
    scores = c02_turn_of_month.score(history)
    assert "CCC" not in scores
    assert "AAA" in scores and "BBB" in scores


def test_rules_fired_reports_direction_and_sample_size():
    history = _biased_market(n_weeks=200, bias=0.02)
    reasoning = c02_turn_of_month.rules_fired(history, "AAA")
    assert "weeks" in reasoning
    assert "bullish" in reasoning or "abstain" in reasoning


def test_rules_fired_abstain_message_when_under_threshold():
    history = _biased_market(n_weeks=3, bias=0.05)
    reasoning = c02_turn_of_month.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_is_totm_flags_last_and_first_three_trading_days_of_month():
    # A plain Jan 2015 business-day calendar: Thu 1 Jan (trading day 1),
    # Fri 2 Jan (td2), Mon 5 Jan (td3) are turn-of-month (first 3); the
    # last trading day of January 2015 is Sat 31 Jan -> Fri 30 Jan.
    calendar = pd.DatetimeIndex(pd.bdate_range("2015-01-01", "2015-01-31"))
    flags = c02_turn_of_month._is_totm(calendar)
    assert bool(flags.loc[pd.Timestamp("2015-01-01")])
    assert bool(flags.loc[pd.Timestamp("2015-01-02")])
    assert bool(flags.loc[pd.Timestamp("2015-01-05")])
    assert not bool(flags.loc[pd.Timestamp("2015-01-06")])
    assert bool(flags.loc[pd.Timestamp("2015-01-30")])


def test_causality_audit_passes():
    result = check_proxy_reads_from_history_not_wall_clock()
    assert result["passed"], result
