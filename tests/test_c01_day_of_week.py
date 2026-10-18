import pandas as pd
import pytest

from strategies import c01_day_of_week
from strategies.c01_day_of_week_audit import (
    _biased_market,
    check_proxy_reads_from_history_not_wall_clock,
)


def test_known_bias_gives_exact_score_for_every_symbol():
    # Bias fires on the trading day after Friday (i.e. Monday), bias=0.02.
    # 25 weeks gives 24 Friday->Monday pairs (the last week's own Friday has
    # no following pair in the data), clearing MIN_OCCURRENCES (20).
    history = _biased_market(n_weeks=25, bias_after_weekday=4, bias=0.02)
    scores = c01_day_of_week.score(history)
    assert set(scores.index) == {"AAA", "BBB", "CCC"}
    for symbol in ("AAA", "BBB", "CCC"):
        assert scores[symbol] == pytest.approx(0.02, rel=1e-9)


def test_bearish_bias_scores_negative():
    history = _biased_market(n_weeks=25, bias_after_weekday=4, bias=-0.015)
    scores = c01_day_of_week.score(history)
    assert all(scores[s] == pytest.approx(-0.015, rel=1e-9) for s in ("AAA", "BBB", "CCC"))


def test_zero_bias_abstains():
    # bias_after_weekday has nothing to trigger on if bias is 0 everywhere.
    history = _biased_market(n_weeks=25, bias_after_weekday=4, bias=0.0)
    scores = c01_day_of_week.score(history)
    assert scores.empty


def test_too_few_historical_pairs_abstains():
    # 3 weeks gives only 3 Friday->Monday pairs, well below MIN_OCCURRENCES (20).
    history = _biased_market(n_weeks=3, bias_after_weekday=4, bias=0.05)
    scores = c01_day_of_week.score(history)
    assert scores.empty


def test_at_the_min_occurrences_threshold_is_included():
    # Exactly MIN_OCCURRENCES (20) Friday->Monday pairs needs 20 full weeks
    # (one pair per week) plus one trailing day so the last visible date is
    # itself a Friday (today's proxy weekday).
    history = _biased_market(n_weeks=20, bias_after_weekday=4, bias=0.03)
    extra_friday = _biased_market(n_weeks=1, bias_after_weekday=4, bias=0.03)
    extra_friday["date"] = (
        pd.to_datetime(history["date"]).max() + pd.tseries.offsets.BDay(5)
    ).strftime("%Y-%m-%d")
    history = pd.concat([history, extra_friday], ignore_index=True)
    scores = c01_day_of_week.score(history)
    assert not scores.empty


def test_empty_history_abstains():
    scores = c01_day_of_week.score(pd.DataFrame())
    assert scores.empty


def test_symbol_without_future_anywhere_is_excluded():
    history = _biased_market(n_weeks=25, bias_after_weekday=4, bias=0.02)
    history.loc[history["symbol"] == "CCC", "has_future"] = False
    scores = c01_day_of_week.score(history)
    assert "CCC" not in scores
    assert "AAA" in scores and "BBB" in scores


def test_rules_fired_reports_direction_and_sample_size():
    history = _biased_market(n_weeks=25, bias_after_weekday=4, bias=0.02)
    reasoning = c01_day_of_week.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "pairs" in reasoning


def test_rules_fired_abstain_message_when_under_threshold():
    history = _biased_market(n_weeks=3, bias_after_weekday=4, bias=0.05)
    reasoning = c01_day_of_week.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_proxy_reads_from_history_not_wall_clock()
    assert result["passed"], result
