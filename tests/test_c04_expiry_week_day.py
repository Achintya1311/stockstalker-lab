import pandas as pd
import pytest

from strategies import c04_expiry_week_day
from strategies.c04_expiry_week_day_audit import (
    _biased_market,
    _cutoff_with_enough_history,
    check_proxy_reads_from_history_not_wall_clock,
)


def test_known_bias_gives_exact_score_for_every_symbol():
    history = _cutoff_with_enough_history(_biased_market(n_months=14, bias=0.02))
    scores = c04_expiry_week_day.score(history)
    assert set(scores.index) == {"AAA", "BBB", "CCC"}
    for symbol in ("AAA", "BBB", "CCC"):
        assert scores[symbol] == pytest.approx(0.02, rel=1e-9)


def test_bearish_bias_scores_negative():
    history = _cutoff_with_enough_history(_biased_market(n_months=14, bias=-0.015))
    scores = c04_expiry_week_day.score(history)
    assert all(scores[s] == pytest.approx(-0.015, rel=1e-9) for s in ("AAA", "BBB", "CCC"))


def test_zero_bias_abstains():
    history = _cutoff_with_enough_history(_biased_market(n_months=14, bias=0.0))
    scores = c04_expiry_week_day.score(history)
    assert scores.empty


def test_too_few_historical_pairs_abstains():
    # 2 months is nowhere near enough expiry-week pairs (one per month) to
    # clear MIN_OCCURRENCES (20).
    history = _biased_market(n_months=2, bias=0.05)
    scores = c04_expiry_week_day.score(history)
    assert scores.empty


def test_yesterday_not_in_expiry_week_abstains_until_bucket_has_data():
    # A cutoff whose last visible day is itself not in expiry week keys on
    # the False bucket instead - still a valid, scoreable bucket once it has
    # enough history, just a different (here: zero) bias. Pick an early
    # cutoff clear of any expiry week.
    history = _biased_market(n_months=14, bias=0.02)
    early_non_expiry_cutoff = history[history["date"] <= "2015-02-10"].copy()
    scores = c04_expiry_week_day.score(early_non_expiry_cutoff)
    # Too little history behind this cutoff either way; abstains regardless
    # of which bucket the proxy flag lands in.
    assert scores.empty


def test_empty_history_abstains():
    scores = c04_expiry_week_day.score(pd.DataFrame())
    assert scores.empty


def test_symbol_without_future_anywhere_is_excluded():
    history = _cutoff_with_enough_history(_biased_market(n_months=14, bias=0.02))
    history.loc[history["symbol"] == "CCC", "has_future"] = False
    scores = c04_expiry_week_day.score(history)
    assert "CCC" not in scores
    assert "AAA" in scores and "BBB" in scores


def test_no_recorded_expiry_for_last_session_abstains():
    history = _cutoff_with_enough_history(_biased_market(n_months=14, bias=0.02))
    last_date = history["date"].max()
    history.loc[history["date"] == last_date, "expiry_futstk"] = pd.NA
    scores = c04_expiry_week_day.score(history)
    assert scores.empty


def test_rules_fired_reports_direction_and_sample_size():
    history = _cutoff_with_enough_history(_biased_market(n_months=14, bias=0.02))
    reasoning = c04_expiry_week_day.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "pairs" in reasoning


def test_rules_fired_abstain_message_when_under_threshold():
    history = _biased_market(n_months=2, bias=0.05)
    reasoning = c04_expiry_week_day.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_proxy_reads_from_history_not_wall_clock()
    assert result["passed"], result
