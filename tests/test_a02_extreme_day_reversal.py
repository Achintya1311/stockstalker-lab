import pandas as pd
import pytest

from strategies import a02_extreme_day_reversal
from strategies.a02_extreme_day_reversal_audit import _window_then_move, check_cross_symbol_causality


def _series(n_pairs: int, d: float, m: float, symbol: str = "AAA") -> pd.DataFrame:
    return _window_then_move(symbol, n_pairs, d, m)


def test_a_big_down_day_scores_bullish():
    # z = m / d = -0.05 / 0.01 = -5.0, well past Z_THRESHOLD; score = -z.
    history = _series(n_pairs=10, d=0.01, m=-0.05)
    scores = a02_extreme_day_reversal.score(history)
    assert "AAA" in scores
    assert scores["AAA"] > 0


def test_a_big_up_day_scores_bearish():
    history = _series(n_pairs=10, d=0.01, m=0.05)
    scores = a02_extreme_day_reversal.score(history)
    assert "AAA" in scores
    assert scores["AAA"] < 0


def test_score_magnitude_is_the_negative_z_score():
    # Known expected signal, exactly: alternating +d/-d window returns give a
    # population std of exactly d, so z = m / d = 0.05 / 0.01 = 5.0 and the
    # score must be exactly -5.0 (rtol/atol for float rounding only).
    history = _series(n_pairs=10, d=0.01, m=0.05)
    scores = a02_extreme_day_reversal.score(history)
    assert scores["AAA"] == pytest.approx(-5.0, rel=1e-9)


def test_move_below_threshold_abstains():
    # z = 0.01 / 0.01 = 1.0, below Z_THRESHOLD (2.0).
    history = _series(n_pairs=10, d=0.01, m=0.01)
    scores = a02_extreme_day_reversal.score(history)
    assert "AAA" not in scores


def test_move_at_the_threshold_is_included():
    # |z| == Z_THRESHOLD clears the ">=" gate in a02_extreme_day_reversal.score.
    history = _series(n_pairs=10, d=0.01, m=0.02)
    scores = a02_extreme_day_reversal.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(-2.0, rel=1e-9)


def test_zero_volatility_window_abstains():
    # A perfectly flat window (d=0) has zero std, so z is undefined - abstain
    # regardless of how large the move day's own return is.
    history = _series(n_pairs=10, d=0.0, m=0.10)
    scores = a02_extreme_day_reversal.score(history)
    assert "AAA" not in scores


def test_too_little_history_abstains():
    history = _series(n_pairs=9, d=0.01, m=0.05)  # 2*9 + 1 = 19 < MIN_ROWS - 1 returns
    scores = a02_extreme_day_reversal.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = a02_extreme_day_reversal.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    down_day = _series(n_pairs=10, d=0.01, m=-0.05, symbol="AAA")
    up_day = _series(n_pairs=10, d=0.01, m=0.05, symbol="BBB")
    scores = a02_extreme_day_reversal.score(pd.concat([down_day, up_day], ignore_index=True))
    assert scores["AAA"] > 0
    assert scores["BBB"] < 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _series(n_pairs=10, d=0.01, m=-0.05)
    reasoning = a02_extreme_day_reversal.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "reversal score" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _series(n_pairs=9, d=0.01, m=-0.05)
    reasoning = a02_extreme_day_reversal.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_abstain_below_threshold():
    history = _series(n_pairs=10, d=0.01, m=0.01)
    reasoning = a02_extreme_day_reversal.rules_fired(history, "AAA")
    assert "abstain" in reasoning
    assert "threshold" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result


def test_score_drops_a_symbol_that_never_had_a_future():
    history = _series(n_pairs=10, d=0.01, m=-0.05)
    history["has_future"] = False
    scores = a02_extreme_day_reversal.score(history)
    assert "AAA" not in scores


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _series(n_pairs=10, d=0.01, m=-0.05)
    history["has_future"] = True
    scores = a02_extreme_day_reversal.score(history)
    assert scores["AAA"] > 0


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    eligible = _series(n_pairs=10, d=0.01, m=-0.05, symbol="AAA")
    ineligible = _series(n_pairs=10, d=0.01, m=0.05, symbol="ZZZ")

    with_future_column = pd.concat([eligible, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = eligible  # no ineligible symbol, no has_future column at all

    assert a02_extreme_day_reversal.score(with_future_column)["AAA"] == a02_extreme_day_reversal.score(without_future_column)["AAA"]
