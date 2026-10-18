import numpy as np
import pandas as pd
import pytest

from strategies import a01_weekly_reversal
from strategies.a01_weekly_reversal_audit import check_cross_symbol_causality


def _flat_then_move(symbol: str, n_rows: int, final_move: float, base_volume: float = 1_000_000.0) -> pd.DataFrame:
    """A flat series of `n_rows` rows, except the final close is `final_move`
    away from the row before it - a known expected signal: the trailing
    `LOOKBACK_DAYS`-day return (and so the reversal score's sign and exact
    magnitude) is fully determined by `final_move` alone, with nothing else
    in the series moving at all.
    """
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    closes = np.full(n_rows, 100.0)
    closes[-1] = 100.0 * (1.0 + final_move)

    rows = []
    prev_close = float(closes[0])
    for date, close in zip(dates, closes):
        close = float(close)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": max(prev_close, close),
                "low": min(prev_close, close),
                "close": close,
                "prevclose": prev_close,
                "volume": base_volume,
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def test_a_loss_over_the_lookback_scores_bullish():
    history = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS + 10, final_move=-0.10)
    scores = a01_weekly_reversal.score(history)
    assert "AAA" in scores
    assert scores["AAA"] > 0


def test_a_gain_over_the_lookback_scores_bearish():
    history = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS + 10, final_move=0.10)
    scores = a01_weekly_reversal.score(history)
    assert "AAA" in scores
    assert scores["AAA"] < 0


def test_flat_series_scores_exactly_zero():
    history = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS + 10, final_move=0.0)
    scores = a01_weekly_reversal.score(history)
    assert scores["AAA"] == 0.0


def test_score_magnitude_is_the_negative_trailing_return():
    # Known expected signal, exactly: a 10% rise over MIN_ROWS - 1 trading
    # days back from the last row gives a trailing return of +0.10, so the
    # reversal score must be exactly -0.10 (rtol/atol for float rounding
    # only), not merely "negative".
    history = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS + 10, final_move=0.10)
    scores = a01_weekly_reversal.score(history)
    assert scores["AAA"] == pytest.approx(-0.10, rel=1e-9)


def test_too_little_history_abstains():
    history = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS - 1, final_move=-0.10)
    scores = a01_weekly_reversal.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = a01_weekly_reversal.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    loser = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS + 10, final_move=-0.10)
    winner = _flat_then_move("BBB", a01_weekly_reversal.MIN_ROWS + 10, final_move=0.10)
    scores = a01_weekly_reversal.score(pd.concat([loser, winner], ignore_index=True))
    assert scores["AAA"] > 0
    assert scores["BBB"] < 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS + 10, final_move=-0.10)
    reasoning = a01_weekly_reversal.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "reversal score" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS - 1, final_move=-0.10)
    reasoning = a01_weekly_reversal.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result


def test_score_drops_a_symbol_that_never_had_a_future():
    history = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS + 10, final_move=-0.10)
    history["has_future"] = False
    scores = a01_weekly_reversal.score(history)
    assert "AAA" not in scores


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS + 10, final_move=-0.10)
    history["has_future"] = True
    scores = a01_weekly_reversal.score(history)
    assert scores["AAA"] > 0


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    loser = _flat_then_move("AAA", a01_weekly_reversal.MIN_ROWS + 10, final_move=-0.10)
    ineligible = _flat_then_move("ZZZ", a01_weekly_reversal.MIN_ROWS + 10, final_move=0.10)

    with_future_column = pd.concat([loser, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = loser  # no ineligible symbol, no has_future column at all

    assert a01_weekly_reversal.score(with_future_column)["AAA"] == a01_weekly_reversal.score(without_future_column)["AAA"]
