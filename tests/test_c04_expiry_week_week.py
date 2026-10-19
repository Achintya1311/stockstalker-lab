import pandas as pd
import pytest

from strategies import c04_expiry_week_week
from strategies.c04_expiry_week_week_audit import (
    _biased_market,
    _cutoff_with_enough_history,
    check_proxy_reads_from_history_not_wall_clock,
)


def test_known_bias_gives_exact_score_for_every_symbol():
    history = _cutoff_with_enough_history(_biased_market(n_months=48, bias=0.03))
    scores = c04_expiry_week_week.score(history)
    assert set(scores.index) == {"AAA", "BBB", "CCC"}
    for symbol in ("AAA", "BBB", "CCC"):
        assert scores[symbol] == pytest.approx(0.03, rel=1e-9)


def test_bearish_bias_scores_negative():
    history = _cutoff_with_enough_history(_biased_market(n_months=48, bias=-0.02))
    scores = c04_expiry_week_week.score(history)
    assert all(scores[s] == pytest.approx(-0.02, rel=1e-9) for s in ("AAA", "BBB", "CCC"))


def test_zero_bias_abstains():
    history = _cutoff_with_enough_history(_biased_market(n_months=48, bias=0.0))
    scores = c04_expiry_week_week.score(history)
    assert scores.empty


def test_too_few_historical_weeks_abstains():
    # 3 months is nowhere near enough expiry weeks (~1/month) to clear
    # MIN_OCCURRENCES (20).
    history = _biased_market(n_months=3, bias=0.05)
    scores = c04_expiry_week_week.score(history)
    assert scores.empty


def test_empty_history_abstains():
    scores = c04_expiry_week_week.score(pd.DataFrame())
    assert scores.empty


def test_symbol_without_future_anywhere_is_excluded():
    history = _cutoff_with_enough_history(_biased_market(n_months=48, bias=0.03))
    history.loc[history["symbol"] == "CCC", "has_future"] = False
    scores = c04_expiry_week_week.score(history)
    assert "CCC" not in scores
    assert "AAA" in scores and "BBB" in scores


def test_no_recorded_expiry_for_last_session_abstains():
    history = _cutoff_with_enough_history(_biased_market(n_months=48, bias=0.03))
    last_date = history["date"].max()
    history.loc[history["date"] == last_date, "expiry_futstk"] = pd.NA
    scores = c04_expiry_week_week.score(history)
    assert scores.empty


def test_rules_fired_reports_direction_and_sample_size():
    history = _cutoff_with_enough_history(_biased_market(n_months=48, bias=0.03))
    reasoning = c04_expiry_week_week.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "weeks" in reasoning


def test_rules_fired_abstain_message_when_under_threshold():
    history = _biased_market(n_months=3, bias=0.05)
    reasoning = c04_expiry_week_week.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_proxy_reads_from_history_not_wall_clock()
    assert result["passed"], result
